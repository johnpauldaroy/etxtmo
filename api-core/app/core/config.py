from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=False)

    app_name: str = Field(default="e-txtmo API", alias="APP_NAME")
    environment: str = Field(default="development", alias="ENVIRONMENT")
    database_url: str = Field(
        default="postgresql+psycopg2://postgres:postgres@localhost:5432/textblast",
        alias="DATABASE_URL",
    )
    jwt_secret_key: str = Field(default="change-me", alias="JWT_SECRET_KEY")
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(default=120, alias="ACCESS_TOKEN_EXPIRE_MINUTES")
    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")
    cors_origins: str = Field(default="http://localhost:5173", alias="CORS_ORIGINS")
    system_timezone: str = Field(default="Asia/Manila", alias="SYSTEM_TIMEZONE")
    scheduler_enabled: bool = Field(default=True, alias="SCHEDULER_ENABLED")
    seed_admin_email: str | None = Field(default=None, alias="SEED_ADMIN_EMAIL")
    seed_admin_username: str | None = Field(default=None, alias="SEED_ADMIN_USERNAME")
    seed_admin_password: str | None = Field(default=None, alias="SEED_ADMIN_PASSWORD")
    seed_admin_full_name: str = Field(default="Administrator", alias="SEED_ADMIN_FULL_NAME")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()

