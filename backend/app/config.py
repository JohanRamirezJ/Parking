"""Configuración de SmartPark por entorno.

SQLite en desarrollo / PostgreSQL en producción (ver Documento_PM, matriz de tecnologías).
"""
import os


# Valores de ejemplo que NUNCA deben usarse en producción (ver _exigir_secretos en app/__init__.py)
SECRETOS_DE_EJEMPLO = {"dev-secret-cambiar-en-produccion", "cambia-esta-clave", "cambia-esta-clave-jwt",
                       "cambia-esto-por-un-valor-largo-y-aleatorio"}


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-cambiar-en-produccion")
    JWT_SECRET = os.getenv("JWT_SECRET", SECRET_KEY)
    JWT_EXP_MINUTES = int(os.getenv("JWT_EXP_MINUTES", "1440"))  # 24 h
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///smartpark.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JSON_AS_ASCII = False

    # Sesión del panel admin: cookie no accesible por JS; solo por HTTPS en producción
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.getenv("FLASK_ENV") == "production"
    PERMANENT_SESSION_LIFETIME = 8 * 3600  # 8 h

    # CORS de la API: lista separada por comas ("*" por defecto; la app móvil no usa navegador)
    CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()]

    # Bloqueo de login tras demasiados intentos fallidos por IP + correo (fuerza bruta)
    LOGIN_MAX_INTENTOS = int(os.getenv("LOGIN_MAX_INTENTOS", "10"))
    LOGIN_VENTANA_S = int(os.getenv("LOGIN_VENTANA_S", "900"))  # 15 min

    # Radio de búsqueda (metros) — HU 7: límites mínimo y máximo
    RADIO_DEFECTO_M = 1000
    RADIO_MIN_M = 200
    RADIO_MAX_M = 5000

    # Límites geográficos de Bogotá — RF-13 / RNF-08
    BOGOTA_LAT_MIN = 4.45
    BOGOTA_LAT_MAX = 4.84
    BOGOTA_LON_MIN = -74.25
    BOGOTA_LON_MAX = -73.99

    # Módulo de IA: supuestos del costo de manejar (todos ajustables por el usuario)
    # Precio de referencia galón gasolina corriente Bogotá, nov. 2026: $16.331 (El Colombiano / MinEnergía)
    PRECIO_GALON_COP = float(os.getenv("PRECIO_GALON_COP", "16331"))
    RENDIMIENTO_KM_GALON = float(os.getenv("RENDIMIENTO_KM_GALON", "30"))   # carro particular en ciudad (supuesto)
    COSTO_RODAMIENTO_KM = float(os.getenv("COSTO_RODAMIENTO_KM", "250"))    # llantas, frenos, mantenimiento (supuesto)
    VELOCIDAD_AUTO_KMH = float(os.getenv("VELOCIDAD_AUTO_KMH", "18"))       # velocidad promedio urbana (supuesto)
    VELOCIDAD_PEATON_KMH = 4.5
    FACTOR_RUTA_URBANA = 1.3   # distancia real por calles ≈ 1,3 × línea recta

    # Chat IA: si hay API key se usa el modelo, si no, recomendador por reglas
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")

    # Geocodificación de destinos (HU 5). Nominatim/OSM no requiere API key.
    GEOCODER_URL = os.getenv("GEOCODER_URL", "https://nominatim.openstreetmap.org/search")
    # Búsqueda en vivo de parqueaderos (Overpass/OSM, sin API key).
    OVERPASS_URL = os.getenv("OVERPASS_URL", "https://overpass-api.de/api/interpreter")
    OVERPASS_TIMEOUT_SECONDS = float(os.getenv("OVERPASS_TIMEOUT_SECONDS", "6"))


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = os.getenv("TEST_DATABASE_URL", "sqlite:///:memory:")
    JWT_EXP_MINUTES = 5
    OPENAI_API_KEY = ""
    GEMINI_API_KEY = ""


class ProductionConfig(Config):
    SESSION_COOKIE_SECURE = True


def get_config(name: str | None):
    return {"test": TestConfig, "production": ProductionConfig}.get(name or os.getenv("FLASK_ENV", ""), Config)
