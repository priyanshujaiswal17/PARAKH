"""Configuration module for Label Reader.

Loads environment variables once and exposes a frozen Settings dataclass.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

# Load .env file if present
load_dotenv(override=False)

BASE_DIR = Path(__file__).resolve().parent

@dataclass(frozen=True)
class Settings:
    backend: str
    gemini_api_key: str
    gemini_model: str
    app_host: str
    app_port: int
    log_level: str
    max_side_online: int
    timeout_online: int


def load_settings() -> Settings:
    return Settings(
        backend="gemini",
        gemini_api_key=os.getenv("GEMINI_API_KEY", "").strip(),
        gemini_model=os.getenv("GEMINI_MODEL", "gemma-4-26b-a4b-it").strip(),
        app_host=os.getenv("APP_HOST", "127.0.0.1").strip(),
        app_port=int(os.getenv("APP_PORT", "8000")),
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        max_side_online=int(os.getenv("MAX_IMAGE_SIDE_ONLINE", os.getenv("MAX_IMAGE_SIDE", "1280"))),
        timeout_online=int(os.getenv("REQUEST_TIMEOUT_ONLINE", os.getenv("REQUEST_TIMEOUT", "60"))),
    )


settings = load_settings()

# Setup logging
log_format = "%(asctime)s %(levelname)s %(name)s: %(message)s"
logging.basicConfig(
    level=getattr(logging, settings.log_level, logging.INFO),
    format=log_format,
)
logger = logging.getLogger("label_reader")
