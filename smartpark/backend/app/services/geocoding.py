"""Geocodificación de destinos en Bogotá (HU 5, RF-03).

Usa Nominatim (OpenStreetMap, sin API key) restringido a Bogotá. Si el servicio no
responde, se usa un pequeño catálogo local de lugares frecuentes como respaldo.
"""
import json
import unicodedata
import urllib.parse
import urllib.request

from flask import current_app

from .geo import en_bogota

# Coordenadas aproximadas de lugares de referencia (respaldo sin conexión / demo).
LUGARES_REFERENCIA = {
    "hospital san ignacio": ("Hospital Universitario San Ignacio", 4.6283, -74.0645),
    "fundacion santa fe": ("Fundación Santa Fe de Bogotá", 4.6946, -74.0330),
    "hospital militar": ("Hospital Militar Central", 4.6353, -74.0624),
    "centro andino": ("Centro Comercial Andino", 4.6668, -74.0526),
    "andino": ("Centro Comercial Andino", 4.6668, -74.0526),
    "unicentro": ("Centro Comercial Unicentro", 4.7020, -74.0415),
    "parque de la 93": ("Parque de la 93", 4.6766, -74.0485),
    "zona t": ("Zona T", 4.6667, -74.0535),
    "movistar arena": ("Movistar Arena", 4.6497, -74.0775),
    "campin": ("Estadio El Campín", 4.6459, -74.0775),
    "universidad javeriana": ("Pontificia Universidad Javeriana", 4.6282, -74.0649),
    "javeriana": ("Pontificia Universidad Javeriana", 4.6282, -74.0649),
    "universidad nacional": ("Universidad Nacional de Colombia", 4.6381, -74.0840),
    "plaza de bolivar": ("Plaza de Bolívar", 4.5981, -74.0760),
    "usaquen": ("Usaquén", 4.6947, -74.0308),
    "chapinero": ("Chapinero", 4.6486, -74.0628),
    "salitre plaza": ("Salitre Plaza", 4.6526, -74.1097),
    "gran estacion": ("Centro Comercial Gran Estación", 4.6474, -74.1017),
    "santa fe": ("Centro Comercial Santafé", 4.7626, -74.0457),
}


def normalizar(texto: str) -> str:
    t = unicodedata.normalize("NFKD", texto.lower())
    return "".join(c for c in t if not unicodedata.combining(c)).strip()


def buscar_local(consulta: str) -> dict | None:
    n = normalizar(consulta)
    # coincidencia más larga primero ("centro andino" antes que "andino")
    for clave in sorted(LUGARES_REFERENCIA, key=len, reverse=True):
        if clave in n:
            nombre, lat, lon = LUGARES_REFERENCIA[clave]
            return {"nombre": nombre, "latitud": lat, "longitud": lon, "fuente": "catalogo_local"}
    return None


def geocodificar(consulta: str, timeout: float = 4.0) -> dict | None:
    consulta = (consulta or "").strip()
    if not consulta:
        return None
    local = buscar_local(consulta)
    if local:
        return local
    if current_app.config.get("TESTING"):
        return None
    params = urllib.parse.urlencode({
        "q": f"{consulta}, Bogotá, Colombia", "format": "json", "limit": 1,
        "countrycodes": "co", "viewbox": "-74.25,4.84,-73.99,4.45", "bounded": 1,
    })
    req = urllib.request.Request(
        f"{current_app.config['GEOCODER_URL']}?{params}",
        headers={"User-Agent": "SmartPark/0.1 (proyecto academico)"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            datos = json.loads(r.read().decode())
    except Exception:  # red caída, timeout, etc.
        return None
    if not datos:
        return None
    lat, lon = float(datos[0]["lat"]), float(datos[0]["lon"])
    if not en_bogota(lat, lon):
        return None
    return {"nombre": datos[0].get("display_name", consulta).split(",")[0],
            "latitud": lat, "longitud": lon, "fuente": "nominatim"}
