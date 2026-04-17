"""LLM client factories for Anthropic and OpenAI."""

from __future__ import annotations

import logging
import os
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

    Supports two auth modes:
      - ``api_key``  → x-api-key header (Anthropic official, most gateways).
      - ``auth_token`` → Bearer header (some gateways like ai-in.one require this).

    The key is auto-detected from BIOAGENT_ANTHROPIC_API_KEY or
    ANTHROPIC_AUTH_TOKEN. If neither is set via BIOAGENT_ prefix, we fall
    back to Claude Code's own env vars.
    """
    from anthropic import Anthropic

    key = settings.get_anthropic_api_key()
    base_url = settings.get_anthropic_base_url()
    http_client = _make_httpx_client()

    # If the key looks like it came from ANTHROPIC_AUTH_TOKEN (Claude Code)
    # or the gateway is known to require Bearer auth, pass as auth_token.
    # Otherwise use the standard api_key (x-api-key) header.
    _BEARER_GATEWAYS = {"https://ai-in.one", "https://api.qingyuntop.top"}
    auth_token = os.environ.get("ANTHROPIC_AUTH_TOKEN", "")
    if (auth_token and key == auth_token) or (base_url in _BEARER_GATEWAYS):
        kwargs: dict = {"auth_token": key}
    else:
        kwargs = {"api_key": key}

    kwargs["http_client"] = http_client
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
