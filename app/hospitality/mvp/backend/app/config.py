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
    # Folder for tenant files (transfer-proof screenshots). One sub-folder per tenant.
    DOCUMENT_STORAGE_DIR: str = "uploads/documents"
    # PREFAB:config-fields


settings = Settings()


def frontend_base_url() -> str:
    """Base address of the web app, without a trailing slash."""
    base = settings.FRONTEND_URL or (settings.CORS_ORIGINS[0] if settings.CORS_ORIGINS else "")
    return base.rstrip("/")
