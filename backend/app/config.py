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
    DEBUG: bool = os.getenv("DEBUG", "True").lower() in ("true", "1")
    CORS_ORIGINS: list = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
    FORECAST_MODEL_PATH: str = os.getenv("FORECAST_MODEL_PATH", os.path.join(os.path.dirname(os.path.dirname(__file__)), "models", "current", "model.joblib"))
    FORECAST_LOG_PATH: str = os.getenv("FORECAST_LOG_PATH", os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "forecast", "predictions.csv"))
    FORECAST_ACTUALS_PATH: str = os.getenv("FORECAST_ACTUALS_PATH", os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "forecast", "actuals.csv"))

settings = Settings()
