import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    FLASK_ENV = os.getenv("FLASK_ENV", "development")
    HOST = os.getenv("HOST", "0.0.0.0")
    _port_value = os.getenv("PORT", "3000")
    PORT = int(_port_value) if str(_port_value).strip().isdigit() else 3000
    CORS_ORIGIN = os.getenv("CORS_ORIGIN", "*")
    ORACLE_USER = os.getenv("ORACLE_USER")
    ORACLE_PASSWORD = os.getenv("ORACLE_PASSWORD")
    ORACLE_DSN = os.getenv("ORACLE_DSN")

    @classmethod
    def cors_origins(cls):
        raw = (cls.CORS_ORIGIN or "*").strip()
        if raw == "*":
            return "*"
        return [origin.strip() for origin in raw.split(",") if origin.strip()]
