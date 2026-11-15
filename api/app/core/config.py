from functools import lru_cache

from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "app"

    DB_ECHO: bool = False

    API_PREFIX: str = "/api"  # versioned routes live under {API_PREFIX}/v1, /v2, ...

    ML_SERVICE_URL: str = "http://localhost:8001"
    ML_TIMEOUT_S: float = 120.0  # /infer runs detection + blurring, can be slow on CPU
    SHARED_DIR: str = "../data"  # ML writes blurred images to <SHARED_DIR>/images/<image_id>.jpg

    @computed_field
    @property
    def DATABASE_URL(self) -> URL:
        return URL.create(
            drivername="postgresql+psycopg",
            username=self.POSTGRES_USER,
            password=self.POSTGRES_PASSWORD,
            host=self.POSTGRES_HOST,
            port=self.POSTGRES_PORT,
            database=self.POSTGRES_DB,
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
