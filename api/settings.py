"""Application settings loaded from environment."""
from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    app_title: str = "Crossroads Sim"
    debug: bool = os.getenv("DEBUG", "false").lower() == "true"
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./crossroads.db")
    secret_key: str = os.getenv("SECRET_KEY", "change-me-in-production")
    api_token: str = os.getenv("API_TOKEN", "dev-token")
    cors_origins: list[str] = os.getenv("CORS_ORIGINS", "*").split(",")
    ws_broadcast_interval_ms: int = int(os.getenv("WS_BROADCAST_INTERVAL_MS", "200"))


settings = Settings()
