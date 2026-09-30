"""Configuración de SmartPark por entorno.

SQLite en desarrollo / PostgreSQL en producción (ver Documento_PM, matriz de tecnologías).
"""
import os


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-cambiar-en-produccion")
    JWT_SECRET = os.getenv("JWT_SECRET", SECRET_KEY)
    JWT_EXP_MINUTES = int(os.getenv("JWT_EXP_MINUTES", "1440"))  # 24 h
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///smartpark.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JSON_AS_ASCII = False

    # Radio de búsqueda (metros) — HU 7: límites mínimo y máximo
    RADIO_DEFECTO_M = 1000
    RADIO_MIN_M = 200
    RADIO_MAX_M = 5000

    # Límites geográficos de Bogotá — RF-13 / RNF-08
    BOGOTA_LAT_MIN = 4.45
    BOGOTA_LAT_MAX = 4.84
    BOGOTA_LON_MIN = -74.25
    BOGOTA_LON_MAX = -73.99

    # Chat IA: si hay API key se usa el modelo, si no, recomendador por reglas
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    # Geocodificación de destinos (HU 5). Nominatim/OSM no requiere API key.
    GEOCODER_URL = os.getenv("GEOCODER_URL", "https://nominatim.openstreetmap.org/search")


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    JWT_EXP_MINUTES = 5


def get_config(name: str | None):
    return {"test": TestConfig}.get(name or os.getenv("FLASK_ENV", ""), Config)
