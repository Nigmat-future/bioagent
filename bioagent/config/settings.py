"""BioAgent configuration management via pydantic-settings."""

import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

# Project root directory
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    """All configuration loaded from .env with BIOAGENT_ prefix.

    Falls back to Claude Code's own env vars (ANTHROPIC_AUTH_TOKEN,
    ANTHROPIC_MODEL, ANTHROPIC_BASE_URL) when BIOAGENT_ vars are not set.
    """

    # --- API Keys ---
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    ncbi_api_key: str = ""

    # --- API endpoint ---
    anthropic_base_url: str = ""

    # --- Models ---
    primary_model: str = ""
    fallback_model: str = "gpt-4.1"
    max_tokens: int = 4096

    # --- Execution ---
    code_timeout: int = 120
    max_iterations: int = 5
    max_tool_calls: int = 20
    max_review_rounds: int = 3

    # --- Token budget ---
    token_budget: int = 500_000       # max total tokens (input + output)
    cost_budget_usd: float = 10.0     # max estimated cost in USD

    # --- Checkpointing ---
    checkpoint_dir: str = "checkpoints"
    use_sqlite_checkpoints: bool = True

    # --- Human-in-the-loop ---
    human_in_loop: bool = False
    review_before_execution: bool = False
    review_before_submission: bool = True

    # --- Workspace ---
    workspace_dir: str = "workspace"

    # --- Logging ---
    log_level: str = "INFO"
    log_file: str = "bioagent.log"

    # --- Network ---
    # Set to False only when using a local proxy that intercepts TLS (e.g. Clash).
    tls_verify: bool = True

    # --- Data acquisition ---
    max_download_size_mb: int = 500
    download_timeout: int = 300
    entrez_email: str = "bioagent@example.com"

    # --- Reproducibility ---
    random_seed: int = 42

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_prefix="BIOAGENT_",
        extra="ignore",
    )

    def get_anthropic_api_key(self) -> str:
        """Get API key: BIOAGENT_ var > .env > Claude Code's ANTHROPIC_AUTH_TOKEN."""
        if self.anthropic_api_key:
            return self.anthropic_api_key
        return os.environ.get("ANTHROPIC_AUTH_TOKEN", "")

    def get_anthropic_base_url(self) -> str:
        """Get base URL: BIOAGENT_ var > .env > Claude Code's ANTHROPIC_BASE_URL."""
        if self.anthropic_base_url:
            return self.anthropic_base_url
        return os.environ.get("ANTHROPIC_BASE_URL", "")

    def get_primary_model(self) -> str:
        """Get model name: BIOAGENT_ var > .env > Claude Code's ANTHROPIC_MODEL."""
        if self.primary_model:
            return self.primary_model
        return os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-5-20250929")

    @property
    def workspace_path(self) -> Path:
        """Absolute path to the workspace directory."""
        p = Path(self.workspace_dir)
        if not p.is_absolute():
            return PROJECT_ROOT / p
        return p

    @property
    def checkpoint_path(self) -> Path:
        """Absolute path to the checkpoint directory."""
        p = Path(self.checkpoint_dir)
        if not p.is_absolute():
            return PROJECT_ROOT / p
        return p


# Singleton instance — imported everywhere
settings = Settings()
