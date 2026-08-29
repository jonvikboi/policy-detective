"""Configuration for Policy Detective backend."""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # LLM (Groq)
    groq_api_key: str = ""
    llm_model: str = "qwen/qwen3.6-27b"
    llm_provider: str = "groq"

    # Database
    database_url: str = "sqlite+aiosqlite:///./policy_detective.db"

    # Server
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000

    # WebCMD
    webcmd_binary: str = "webcmd"
    webcmd_profile: str = "default"
    webcmd_timeout: int = 60

    # Security
    max_concurrent_scans: int = 3
    scan_timeout_minutes: int = 15

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
