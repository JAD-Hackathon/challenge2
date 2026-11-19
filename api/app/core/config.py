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

    # true -> routes are served from app/mocks (in-memory data, no DB or ML needed)
    API_MOCK: bool = False

    ML_SERVICE_URL: str = "http://localhost:8001"
    ML_TIMEOUT_S: float = 120.0  # /infer runs detection + blurring, can be slow on CPU
    ML_VIDEO_TIMEOUT_S: float = (
        900.0  # /infer-video does that for every frame of a video
    )
    SHARED_DIR: str = (
        "../data"  # ML writes blurred images to <SHARED_DIR>/images/<image_id>.jpg
    )

    MAX_BATCH_SIZE: int = 20  # images per POST /images request
    MAX_VIDEO_MB: int = 2048  # biggest video accepted by POST /videos
    # Prefix of image URLs in responses. Use an absolute URL (http://localhost:8000/media)
    # if the browser can't reach the API on the same origin. The path must stay /media.
    MEDIA_URL: str = "/media"

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
