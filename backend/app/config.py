from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    app_secret: str = "development-only-change-me-please-32-characters"
    data_dir: Path = Path("data")
    base_url: str = "http://127.0.0.1:8000"
    allowed_origins: str = "http://127.0.0.1:8000,http://localhost:8000"
    trusted_proxy_hosts: str = "127.0.0.1"
    cookie_secure: bool = False
    session_days: int = 30
    admin_session_hours: int = 12
    max_upload_mb: int = 5
    database_url: str | None = None
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def db_url(self) -> str:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        return self.database_url or f"sqlite:///{(self.data_dir / 'threeds.db').resolve().as_posix()}"

    @property
    def origins(self) -> set[str]:
        return {x.strip().rstrip("/") for x in self.allowed_origins.split(",") if x.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()

