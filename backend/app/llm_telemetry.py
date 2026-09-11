"""Structured JSON telemetry for the grounded LLM layer.

Emits one JSON line per event on the ``pathfinder.llm`` logger using only the
standard ``logging`` module (no new dependency). Events:

- ``llm_success`` — a model in the chain produced schema-valid output;
- ``llm_fallback_triggered`` — the deterministic fallback was served instead,
  with the reason (timeout, validation_error, provider_unavailable, ...);
- ``prompt_injection_redacted`` — the untrusted-text guard neutralized
  instruction-shaped content before it reached storage or a prompt.

The logger has its own JSON handler and does not propagate, so these lines
stay machine-readable even when the rest of the app logs human-readable text.
Fields attached to events must stay JSON-primitive (str/int/float/bool).
"""

from __future__ import annotations

import json
import logging
import sys

LLM_TELEMETRY_LOGGER = "pathfinder.llm"


class JsonFormatter(logging.Formatter):
    """Render each LogRecord as one JSON line, safe for log ingestion."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "event": getattr(record, "event", "unknown"),
        }
        payload.update(getattr(record, "data", {}))
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def _configure_llm_telemetry() -> logging.Logger:
    logger = logging.getLogger(LLM_TELEMETRY_LOGGER)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger


llm_logger = _configure_llm_telemetry()


def log_llm_event(event: str, **fields: object) -> None:
    """Emit one structured LLM event; ``fields`` become JSON payload keys."""
    llm_logger.info("llm event: %s", event, extra={"event": event, "data": fields})
