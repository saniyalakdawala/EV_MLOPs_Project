"""
Application Configuration Module
Loads settings from environment variables and .env file.
"""
import os
from dotenv import load_dotenv

# Load .env from backend directory
env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
load_dotenv(dotenv_path=env_path)

class Settings:
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_PORT: int = int(os.getenv("DB_PORT", "5432"))
    DB_NAME: str = os.getenv("DB_NAME", "ev_db")
    DB_USER: str = os.getenv("DB_USER", "ev_app_user")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "")
    
    APP_HOST: str = os.getenv("APP_HOST", "0.0.0.0")
    APP_PORT: int = int(os.getenv("APP_PORT", "8000"))
    DEBUG: bool = os.getenv("DEBUG", "false").strip().lower() in ("true", "1", "yes", "on")
    CORS_ORIGINS: list = [origin.strip() for origin in os.getenv("CORS_ORIGINS", "http://localhost:8501,http://127.0.0.1:8501").split(",") if origin.strip()]
    FORECAST_MODEL_PATH: str = os.getenv("FORECAST_MODEL_PATH", os.path.join(os.path.dirname(os.path.dirname(__file__)), "models", "current", "model.joblib"))
    FORECAST_LOG_PATH: str = os.getenv("FORECAST_LOG_PATH", os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "forecast", "predictions.csv"))
    FORECAST_ACTUALS_PATH: str = os.getenv("FORECAST_ACTUALS_PATH", os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "forecast", "actuals.csv"))

settings = Settings()


def validate_settings() -> None:
    if not 1 <= settings.DB_PORT <= 65535:
        raise ValueError("DB_PORT must be between 1 and 65535.")
    if not 1 <= settings.APP_PORT <= 65535:
        raise ValueError("APP_PORT must be between 1 and 65535.")
    if not settings.DB_HOST or not settings.DB_NAME or not settings.DB_USER:
        raise ValueError("DB_HOST, DB_NAME, and DB_USER must be non-empty.")
    if not settings.CORS_ORIGINS:
        raise ValueError("CORS_ORIGINS must contain at least one origin.")
