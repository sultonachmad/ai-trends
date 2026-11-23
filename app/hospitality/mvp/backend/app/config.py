from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/.env, independent of cwd, so both loaders below read the same file.
ENV_FILE = Path(__file__).resolve().parents[1] / ".env"

# Exports unprefixed keys (e.g. RBAC_*) that modules read via os.getenv.
# Existing process env wins; interpolate=False keeps "${...}" in values literal.
load_dotenv(ENV_FILE, interpolate=False, encoding="utf-8-sig")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="PREFAB_", env_file=ENV_FILE, env_file_encoding="utf-8-sig", extra="ignore"
    )

    APP_NAME: str = "prefab-app"
    SECRET_KEY: str = "change-me-in-production"
    DATABASE_URL: str = "sqlite+aiosqlite:///./data.db" # OR  postgres+asyncpg://user:password@localhost/dbname
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]
    ROOT_PATH: str = ""
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    CONTACT_RECIPIENT: str = ""
    # Send the session cookie over HTTPS only. Keep False for local http://localhost;
    # set PREFAB_SESSION_COOKIE_SECURE=true wherever the app is served over HTTPS.
    SESSION_COOKIE_SECURE: bool = False
    # Lets a signed-in tester send messages in "as a guest" (POST /api/simulator/...).
    # Development only: keep false anywhere real guests are served.
    MESSAGING_SIMULATOR_ENABLED: bool = False
    # Lets anyone holding a pay link mark it paid ("Simulate payment" on the pay page).
    # Development only: keep false anywhere real money is taken.
    PAYMENT_SIMULATOR_ENABLED: bool = False
    # Offers a simulated online travel agency to connect to (Channels page).
    # Development only: it stands in for agencies that need partner certification.
    CHANNEL_SIMULATOR_ENABLED: bool = False
    # Where guests open pay links (https://app.example.com). Empty = first CORS origin.
    FRONTEND_URL: str = ""
    # How often the channel pusher looks for due work (seconds).
    CHANNEL_PUSH_INTERVAL_SECONDS: int = 5
    # How often the calendar-link loop looks for calendars due a read (seconds).
    CALENDAR_SYNC_TICK_SECONDS: int = 60
    # Folder for tenant files (transfer-proof screenshots). One sub-folder per tenant.
    DOCUMENT_STORAGE_DIR: str = "uploads/documents"
    # LLM model for litellm (https://docs.litellm.ai/docs/providers).
    LLM_MODEL: str = "openai/gpt-4o"
    # Qdrant vector database URL (rag-base).
    QDRANT_URL: str = "http://localhost:6333"
    # Embedding model for litellm (https://docs.litellm.ai/docs/embedding/supported_embedding).
    EMBEDDING_MODEL: str = "openai/text-embedding-3-small"
    # Qdrant collection name for the RAG pipeline.
    RAG_COLLECTION: str = "sendo_app"
    # Max accepted upload size in bytes for POST /api/rag/upload.
    RAG_MAX_UPLOAD_BYTES: int = 10 * 1024 * 1024  # 10 MiB upload cap
    # PREFAB:config-fields


settings = Settings()


def frontend_base_url() -> str:
    """Base address of the web app, without a trailing slash."""
    base = settings.FRONTEND_URL or (settings.CORS_ORIGINS[0] if settings.CORS_ORIGINS else "")
    return base.rstrip("/")
