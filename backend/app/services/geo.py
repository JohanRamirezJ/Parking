"""Cálculos geográficos y búsqueda por proximidad (RF-04, RNF-01)."""
import math

from flask import current_app

RADIO_TIERRA_M = 6_371_000


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * RADIO_TIERRA_M * math.asin(math.sqrt(a))


def caja_envolvente(lat: float, lon: float, radio_m: float) -> tuple[float, float, float, float]:
    """Pre-filtro rectangular indexable antes del cálculo exacto (mantiene la consulta < 2 s)."""
    dlat = math.degrees(radio_m / RADIO_TIERRA_M)
    dlon = math.degrees(radio_m / (RADIO_TIERRA_M * math.cos(math.radians(lat))))
    return lat - dlat, lat + dlat, lon - dlon, lon + dlon


def en_bogota(lat: float, lon: float) -> bool:
    c = current_app.config
    return (c["BOGOTA_LAT_MIN"] <= lat <= c["BOGOTA_LAT_MAX"]
            and c["BOGOTA_LON_MIN"] <= lon <= c["BOGOTA_LON_MAX"])
