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
    # PREFAB:config-fields


settings = Settings()
