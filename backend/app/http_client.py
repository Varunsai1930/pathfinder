"""Process-wide pooled HTTP client for PostgREST store calls.

Opening a fresh httpx.Client per call pays TCP+TLS setup on every PostgREST
round-trip; httpx.Client is thread-safe and designed for reuse, so stores share
one pool instead. Callers keep passing absolute URLs per request.

The pool is keyed by the client class actually used: tests monkeypatch
``httpx.Client`` with fakes, and keying on the class means a patched class
always gets a fresh instance without leaking state between tests.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import httpx

_shared: tuple[type[httpx.Client], httpx.Client] | None = None


def get_pooled_client(timeout: float = 10.0) -> httpx.Client:
    """Return the shared client, (re)creating it when the class or pool changes."""
    global _shared
    client_cls = httpx.Client
    # getattr: test doubles may not implement is_closed.
    if _shared is not None and _shared[0] is client_cls and not getattr(_shared[1], "is_closed", False):
        return _shared[1]
    _shared = (client_cls, client_cls(timeout=timeout))
    return _shared[1]


@contextmanager
def pooled_client(timeout: float = 10.0) -> Iterator[httpx.Client]:
    """Context-manager shim so existing ``with`` call sites pool transparently."""
    yield get_pooled_client(timeout)
