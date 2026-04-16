"""LLM client factories for Anthropic and OpenAI."""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import TYPE_CHECKING

from bioagent.config.settings import settings

if TYPE_CHECKING:
    import httpx

logger = logging.getLogger(__name__)


def _make_httpx_client() -> "httpx.Client":
    """Create an httpx client that bypasses system proxy.

    System proxy (e.g. Clash on Windows) can interfere with direct API calls.
    We create a clean httpx client without proxy to avoid TLS handshake failures.
    """
    import httpx

    return httpx.Client(
        proxy=None,
        verify=settings.tls_verify,
        timeout=httpx.Timeout(300.0, connect=10.0),
    )


@lru_cache(maxsize=1)
def get_anthropic_client():
    """Return a configured Anthropic client.

    Auto-detects Claude Code's own configuration (base_url, model, auth_token)
    so it works without manual .env setup when run inside Claude Code.
    Bypasses system proxy to avoid TLS issues with local proxies.
    """
    from anthropic import Anthropic

    kwargs = {
        "api_key": settings.get_anthropic_api_key(),
        "http_client": _make_httpx_client(),
    }

    base_url = settings.get_anthropic_base_url()
    if base_url:
        kwargs["base_url"] = base_url

    return Anthropic(**kwargs)


def get_anthropic_model() -> str:
    """Return the configured model name."""
    return settings.get_primary_model()


@lru_cache(maxsize=1)
def get_openai_client():
    """Return a configured OpenAI client (fallback)."""
    from openai import OpenAI

    return OpenAI(
        api_key=settings.openai_api_key,
        http_client=_make_httpx_client(),
    )
