from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    openai_api_key: str
    openai_model: str = "gpt-4o"
    max_image_bytes: int = 10 * 1024 * 1024
    cors_origins: list[str] = ["*"]

    # Database (Supabase Postgres)
    database_url: str  # asyncpg URL via Supabase pooler (port 6543)
    database_url_direct: str  # asyncpg URL via direct host (port 5432) — Alembic only

    # Supabase Auth
    supabase_url: str  # e.g. https://<project-ref>.supabase.co — used to fetch JWKS
    supabase_jwt_secret: str  # legacy HS256 fallback (still set; unused when JWKS verifies)
    supabase_jwt_audience: str = "authenticated"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()
