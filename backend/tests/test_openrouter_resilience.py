"""OpenRouter resilience tests: model fallback chain, timeout budget, circuit breaker."""

from __future__ import annotations

import json
from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

import pytest

from app import personalization
from app.config import Settings


def _valid_roadmap_payload() -> dict[str, Any]:
    """A RoadmapPersonalization payload that passes the strict schema."""
    return {
        "fit_explanation": (
            "This role reflects the supplied score breakdown. "
            "Address the listed core skill gaps through the fixed weekly milestones."
        ),
        "adaptation_note": "",
        "weekly_focus": [
            {"milestone_id": f"milestone-{week}", "personalized_focus": "Focus on the supplied practical task."}
            for week in range(1, 6)
        ],
    }


def _mock_openrouter_chain(
    monkeypatch: pytest.MonkeyPatch, behavior: Callable[[str], Any]
) -> list[dict[str, Any]]:
    """Patch OpenAI with per-model behavior; records every create() call."""
    calls: list[dict[str, Any]] = []

    class FakeCompletions:
        def create(self, **kwargs: Any) -> Any:
            calls.append(kwargs)
            outcome = behavior(kwargs["model"])
            if isinstance(outcome, BaseException):
                raise outcome
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=outcome))])

    class FakeOpenAI:
        def __init__(self, **kwargs: Any) -> None:
            self.chat = SimpleNamespace(completions=FakeCompletions())

    monkeypatch.setattr(personalization, "OpenAI", FakeOpenAI)
    return calls


def _completion(settings: Settings) -> Any:
    return personalization._structured_completion(
        personalization.RoadmapPersonalization,
        settings=settings,
        system="system prompt",
        user="user prompt",
    )


def _chain_settings(**overrides: Any) -> Settings:
    return Settings(_env_file=None, openrouter_api_key="test-key", **overrides)


class TestModelFallbackChain:
    def test_primary_failure_escalates_to_secondary_model(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        settings = _chain_settings(openrouter_models="primary-model,secondary-model")
        payload = json.dumps(_valid_roadmap_payload())

        def behavior(model: str) -> Any:
            if model == "primary-model":
                raise TimeoutError("primary timed out")
            return payload

        calls = _mock_openrouter_chain(monkeypatch, behavior)

        result = _completion(settings)

        assert [call["model"] for call in calls] == ["primary-model", "secondary-model"]
        assert result is not None
        assert result.fit_explanation == _valid_roadmap_payload()["fit_explanation"]

    def test_schema_invalid_primary_escalates_to_secondary(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A response that breaks the schema also moves on to the next model."""
        settings = _chain_settings(openrouter_models="primary-model,secondary-model")
        payload = json.dumps(_valid_roadmap_payload())

        def behavior(model: str) -> Any:
            if model == "primary-model":
                return "definitely not the requested schema"
            return payload

        calls = _mock_openrouter_chain(monkeypatch, behavior)

        result = _completion(settings)

        assert [call["model"] for call in calls] == ["primary-model", "secondary-model"]
        assert result is not None

    def test_all_models_failing_returns_none_for_deterministic_fallback(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        settings = _chain_settings(openrouter_models="primary-model,secondary-model,tertiary-model")

        def behavior(model: str) -> Any:
            raise TimeoutError(f"{model} timed out")

        calls = _mock_openrouter_chain(monkeypatch, behavior)

        result = _completion(settings)

        # Every model in the chain was tried before giving up.
        assert [call["model"] for call in calls] == [
            "primary-model",
            "secondary-model",
            "tertiary-model",
        ]
        assert result is None

    def test_empty_primary_response_escalates_to_secondary(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        settings = _chain_settings(openrouter_models="primary-model,secondary-model")
        payload = json.dumps(_valid_roadmap_payload())

        def behavior(model: str) -> Any:
            if model == "primary-model":
                return ""  # empty content: a per-model failure, not a chain failure
            return payload

        calls = _mock_openrouter_chain(monkeypatch, behavior)

        result = _completion(settings)

        assert [call["model"] for call in calls] == ["primary-model", "secondary-model"]
        assert result is not None


class TestTimeoutBudget:
    def _capture_client(self, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
        captured: dict[str, Any] = {}

        class FakeCompletions:
            def create(self, **kwargs: Any) -> Any:
                raise AssertionError("provider should not be called")

        class FakeOpenAI:
            def __init__(self, **kwargs: Any) -> None:
                captured.update(kwargs)
                self.chat = SimpleNamespace(completions=FakeCompletions())

        monkeypatch.setattr(personalization, "OpenAI", FakeOpenAI)
        return captured

    def test_budget_split_evenly_across_chain(self, monkeypatch: pytest.MonkeyPatch) -> None:
        settings = _chain_settings(openrouter_models="a,b", openrouter_timeout_seconds=8.0)
        captured = self._capture_client(monkeypatch)

        _completion(settings)

        assert captured["timeout"] == pytest.approx(4.0)
        assert captured["max_retries"] == 0

    def test_single_model_gets_full_budget(self, monkeypatch: pytest.MonkeyPatch) -> None:
        settings = _chain_settings(openrouter_timeout_seconds=6.0)
        captured = self._capture_client(monkeypatch)

        _completion(settings)

        assert captured["timeout"] == pytest.approx(6.0)


class TestCircuitBreaker:
    def test_opens_after_consecutive_provider_failures_and_skips_provider(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        for _ in range(personalization._CIRCUIT_THRESHOLD):
            personalization._record_circuit_outcome(provider_failed=True)

        assert personalization._circuit_is_open() is True

        # While open, the provider is never contacted.
        _mock_openrouter_chain(
            monkeypatch,
            lambda model: (_ for _ in ()).throw(AssertionError("provider contacted while circuit open")),
        )

        assert _completion(_chain_settings()) is None

    def test_success_closes_the_circuit(self) -> None:
        for _ in range(personalization._CIRCUIT_THRESHOLD):
            personalization._record_circuit_outcome(provider_failed=True)
        personalization._record_circuit_outcome(provider_failed=False)

        assert personalization._circuit_is_open() is False

    def test_validation_failure_does_not_trip_the_breaker(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A schema-breaking response means the provider transport is fine."""
        _mock_openrouter_chain(monkeypatch, lambda model: "definitely not the requested schema")

        result = _completion(_chain_settings())

        assert result is None
        assert personalization._circuit_is_open() is False


class TestLegacyModelConfig:
    def test_legacy_single_model_seeds_the_chain_when_list_unset(self) -> None:
        settings = _chain_settings(openrouter_model="legacy-model")
        assert settings.openrouter_model_list == ["legacy-model"]

    def test_models_list_wins_when_both_set(self) -> None:
        settings = _chain_settings(openrouter_model="legacy-model", openrouter_models="chain-a,chain-b")
        assert settings.openrouter_model_list == ["chain-a", "chain-b"]

    def test_default_chain_is_auto_router(self) -> None:
        assert _chain_settings().openrouter_model_list == ["openrouter/free"]

    def test_chain_deduplicates_and_skips_blanks(self) -> None:
        settings = _chain_settings(openrouter_models=" model-a , ,model-a,model-b ,")
        assert settings.openrouter_model_list == ["model-a", "model-b"]

    def test_empty_chain_falls_back_to_auto_router(self) -> None:
        settings = _chain_settings(openrouter_models=" , ")
        assert settings.openrouter_model_list == ["openrouter/free"]


def test_reset_llm_circuit_for_tests_restores_state() -> None:
    """The conftest reset hook must fully restore breaker state between tests."""
    for _ in range(personalization._CIRCUIT_THRESHOLD):
        personalization._record_circuit_outcome(provider_failed=True)

    personalization.reset_llm_circuit_for_tests()

    assert personalization._circuit_is_open() is False
