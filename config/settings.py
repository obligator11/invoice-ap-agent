from __future__ import annotations

import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()  # reads .env into os.environ if present


def _get_float(name: str, default: float) -> float:
    val = os.getenv(name)
    return float(val) if val else default


def _get_bool(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


@dataclass
class Settings:
    # --- Database ---
    database_url: str = field(
        default_factory=lambda: os.getenv(
            "DATABASE_URL",
            "postgresql+psycopg2://apagent:apagent@localhost:5432/invoice_ap",
        )
    )

    # --- Ollama ---
    ollama_base_url: str = field(default_factory=lambda: os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"))
    ollama_explainer_model: str = field(default_factory=lambda: os.getenv("OLLAMA_EXPLAINER_MODEL", "llama3.1"))
    ollama_router_model: str = field(default_factory=lambda: os.getenv("OLLAMA_ROUTER_MODEL", "gemma2"))

    # --- LM Studio ---
    lmstudio_base_url: str = field(default_factory=lambda: os.getenv("LMSTUDIO_BASE_URL", "http://localhost:1234/v1"))
    lmstudio_extractor_model: str = field(
        default_factory=lambda: os.getenv("LMSTUDIO_EXTRACTOR_MODEL", "qwen2.5-coder")
    )
    lmstudio_reasoner_model: str = field(
        default_factory=lambda: os.getenv("LMSTUDIO_REASONER_MODEL", "deepseek-r1-distill")
    )

    # --- Gmail ---
    gmail_address: str = field(default_factory=lambda: os.getenv("GMAIL_ADDRESS", ""))
    gmail_app_password: str = field(default_factory=lambda: os.getenv("GMAIL_APP_PASSWORD", ""))
    gmail_imap_host: str = field(default_factory=lambda: os.getenv("GMAIL_IMAP_HOST", "imap.gmail.com"))
    gmail_smtp_host: str = field(default_factory=lambda: os.getenv("GMAIL_SMTP_HOST", "smtp.gmail.com"))
    gmail_smtp_port: int = field(default_factory=lambda: int(os.getenv("GMAIL_SMTP_PORT", "587")))

    # --- Business rules (also editable from the Settings UI page at runtime) ---
    auto_approve_max_amount: float = field(default_factory=lambda: _get_float("AUTO_APPROVE_MAX_AMOUNT", 500.0))
    review_sla_hours: int = field(default_factory=lambda: int(os.getenv("REVIEW_SLA_HOURS", "48")))
    currency_default: str = field(default_factory=lambda: os.getenv("CURRENCY_DEFAULT", "USD"))

    # --- Optional Sheets mirror ---
    google_sheets_export_enabled: bool = field(default_factory=lambda: _get_bool("GOOGLE_SHEETS_EXPORT_ENABLED", False))
    google_sheets_id: str = field(default_factory=lambda: os.getenv("GOOGLE_SHEETS_ID", ""))
    google_service_account_json_path: str = field(
        default_factory=lambda: os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON_PATH", "")
    )

    # --- Retry policy shared by every LLM-calling agent ---
    max_llm_retries: int = 2


# Module-level singleton. Import this everywhere: `from config.settings import settings`
settings = Settings()
