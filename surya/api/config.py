"""API configuration"""
from pydantic_settings import BaseSettings
from typing import Optional


class APISettings(BaseSettings):
    """API configuration settings"""

    # Server settings
    API_TITLE: str = "Surya OCR API"
    API_VERSION: str = "0.1.0"
    API_DESCRIPTION: str = "FastAPI service for Surya OCR with MinerU compatibility"

    # Model settings
    DEFAULT_LANG: str = "en"
    DEFAULT_BATCH_SIZE: Optional[int] = None

    # File upload settings
    MAX_FILE_SIZE: int = 100 * 1024 * 1024  # 100MB
    ALLOWED_EXTENSIONS: set = {".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".bmp"}

    # Temporary directory
    TEMP_DIR: str = "./temp"

    # Debug settings
    DEBUG_LOG_ENABLED: bool = True  # Enable detailed per-page debug logging
    DEBUG_LOG_DIR: str = "./temp/debug_logs"  # Directory for debug logs

    # CORS settings
    ALLOW_ORIGINS: list = ["*"]
    ALLOW_CREDENTIALS: bool = True
    ALLOW_METHODS: list = ["*"]
    ALLOW_HEADERS: list = ["*"]

    class Config:
        env_prefix = "SURYA_API_"


settings = APISettings()
