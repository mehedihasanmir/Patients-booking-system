from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "local"
    log_level: str = "INFO"
    database_url: str = "postgresql+asyncpg://bytevoice:bytevoice@localhost:5432/bytevoice"
    jwt_secret: str = "dev-only-change-me"
    jwt_expire_minutes: int = 720
    service_token: str = "dev-service-token-change-me"
    cors_origins: str = "http://localhost:3000"
    clinic_timezone: str = "Asia/Dhaka"
    livekit_url: str = ""
    livekit_api_key: str = ""
    livekit_api_secret: str = ""
    livekit_agent_name: str = "bytevoice"
    openai_api_key: str = ""
    seed_admin_email: str = "reviewer@strategybyte.demo"
    seed_admin_password: str = "ReviewerDemo!2026"
    seed_staff_email: str = "staff@strategybyte.demo"
    seed_staff_password: str = "StaffDemo!2026"
    seed_on_start: bool = True
    token_rate_limit: int = 5
    token_rate_window_s: int = 60
    r2_enabled: bool = False
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket: str = ""
    r2_endpoint: str = ""
    r2_public_base_url: str = ""

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @property
    def livekit_configured(self) -> bool:
        return bool(self.livekit_url and self.livekit_api_key and self.livekit_api_secret)

    @property
    def r2_configured(self) -> bool:
        return self.r2_enabled and bool(
            self.r2_access_key_id and self.r2_secret_access_key and self.r2_bucket and self.r2_endpoint
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
