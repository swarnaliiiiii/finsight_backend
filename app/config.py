from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # LLMs
    GROQ_API_KEY: str = ""
    GEMINI_API_KEY: str = ""

    # News & sentiment
    FINNHUB_API_KEY: str = ""
    NEWSAPI_KEY: str = ""
    MARKETAUX_API_KEY: str = ""
    GNEWS_API_KEY: str = ""

    # Market data
    ALPHA_VANTAGE_KEY: str = ""

    # Macro
    FRED_API_KEY: str = ""

    # Search
    TAVILY_API_KEY: str = ""
    YOUTUBE_API_KEY: str = ""
    SERP_API_KEY: str = ""

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://finsight:finsight@postgres:5432/finsight"
    DATABASE_URL_SYNC: str = "postgresql+psycopg2://finsight:finsight@postgres:5432/finsight"

    # App
    DEFAULT_COUNTRY: str = "IN"
    HTTP_TIMEOUT_SECONDS: float = 15.0
    USER_AGENT: str = "finsight-ai/0.1"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
