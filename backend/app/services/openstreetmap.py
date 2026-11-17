"""Consulta efímera de parqueaderos cercanos en OpenStreetMap vía Overpass."""
import json
import math
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import time
from typing import Any

from flask import current_app

from ..models import Parqueadero, Tarifa
from .geo import en_bogota, haversine_m

_ACCESO_RESTRINGIDO = {"customers", "delivery", "no", "permit", "private", "residents"}
_ESTACIONAMIENTO_EN_VIA = {"lane", "on_street", "street_side"}
_CODIGO_TIPO = {"node": 1, "way": 2, "relation": 3}


class ErrorConsultaOSM(RuntimeError):
    """Error consultando o interpretando el servicio público Overpass."""


@dataclass(frozen=True)
class CandidatoOSM:
    parqueadero: Parqueadero
    distancia_m: float
    url: str


def _mensaje_error_http_overpass(codigo: int) -> str:
    if codigo == 429:
        return "?\nAlerta de búsqueda: Overpass limitó las consultas (HTTP 429). Inténtalo más tarde."
    if codigo in {502, 503, 504}:
        return (f"\nAlerta de búsqueda: Overpass está saturado o temporalmente no disponible "
                f"(HTTP {codigo}). Inténtalo más tarde.")
    if codigo >= 500:
        return (f"\nAlerta de búsqueda: Overpass devolvió un error del servidor "
                f"(HTTP {codigo}). Inténtalo más tarde.")
    if codigo == 406:
        return ("\nAlerta de búsqueda: Overpass rechazó la solicitud (HTTP 406). "
                "Revisa la URL del servicio o inténtalo más tarde.")
    return f"\nAlerta de búsqueda: Overpass rechazó la consulta (HTTP {codigo})."


def _candidato(elemento: dict[str, Any], lat: float, lon: float, radio_m: float) -> CandidatoOSM | None:
    tipo = elemento.get("type")
    tipo_id = _CODIGO_TIPO.get(tipo)
    tags = elemento.get("tags")
    if tipo_id is None or not isinstance(tags, dict) or tags.get("amenity") != "parking":
        return None

    acceso = str(tags.get("access", "")).lower()
    if acceso in _ACCESO_RESTRINGIDO or tags.get("parking") in _ESTACIONAMIENTO_EN_VIA:
        return None

    coordenadas = elemento if tipo == "node" else elemento.get("center", {})
    try:
        osm_id = int(elemento["id"])
        p_lat, p_lon = float(coordenadas["lat"]), float(coordenadas["lon"])
    except (KeyError, TypeError, ValueError):
        return None
    if osm_id <= 0 or not en_bogota(p_lat, p_lon):
        return None

    distancia = haversine_m(lat, lon, p_lat, p_lon)
    if distancia > radio_m:
        return None

    nombre = str(tags.get("name") or tags.get("operator") or "Parqueadero sin nombre")
    direccion = str(tags.get("addr:full") or "")
    if not direccion:
        partes = [str(tags.get("addr:street") or ""), str(tags.get("addr:housenumber") or "")]
        direccion = " ".join(parte for parte in partes if parte) or "Dirección no reportada en OpenStreetMap"

    horario = str(tags.get("opening_hours", "")).strip().lower()
    apertura, cierre = (time(0, 0), time(0, 0)) if horario in {"24/7", "always"} else (None, None)
    try:
        capacidad = int(tags["capacity"])
    except (KeyError, TypeError, ValueError):
        capacidad = None

    parqueadero = Parqueadero(
        id=-(osm_id * 4 + tipo_id),
        nombre=nombre,
        direccion=direccion,
        latitud=p_lat,
        longitud=p_lon,
        horario_apertura=apertura,
        horario_cierre=cierre,
        capacidad_total=capacidad,
        capacidad_disponible_estimada=None,
        calificacion_promedio=None,
        calificacion_seguridad=None,
        activo=True,
    )
    if str(tags.get("fee", "")).lower() in {"free", "no"}:
        parqueadero.tarifas.append(Tarifa(tipo="hora", unidad="hora", valor=0, vigente=True))

    url = f"https://www.openstreetmap.org/{tipo}/{osm_id}"
    return CandidatoOSM(parqueadero, distancia, url)


def buscar_cercanos_osm(lat: float, lon: float, radio_m: float) -> list[CandidatoOSM]:
    """Obtiene candidatos mapeados; no los guarda en la base de datos."""
    timeout = float(current_app.config["OVERPASS_TIMEOUT_SECONDS"])
    query = (
        f"[out:json][timeout:{math.ceil(timeout)}];"
        f"nwr(around:{round(radio_m)},{lat:.7f},{lon:.7f})"
        '["amenity"="parking"];out center tags;'
    )
    body = urllib.parse.urlencode({"data": query}).encode()
    request = urllib.request.Request(
        current_app.config["OVERPASS_URL"],
        data=body,
        headers={
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "User-Agent": "SmartPark/0.1 (academic parking assistant)",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise ErrorConsultaOSM(_mensaje_error_http_overpass(exc.code)) from exc
    except TimeoutError as exc:
        raise ErrorConsultaOSM(
            "Alerta de búsqueda: Overpass agotó el tiempo de espera; puede estar saturado. Inténtalo más tarde."
        ) from exc
    except urllib.error.URLError as exc:
        if isinstance(exc.reason, TimeoutError):
            mensaje = "Alerta de búsqueda: Overpass agotó el tiempo de espera; puede estar saturado. Inténtalo más tarde."
        else:
            mensaje = ("Alerta de búsqueda: no se pudo conectar con Overpass. "
                       "Revisa la conexión a Internet del backend.")
        raise ErrorConsultaOSM(mensaje) from exc
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ErrorConsultaOSM("Alerta de búsqueda: Overpass devolvió una respuesta ilegible.") from exc

    if isinstance(data, dict) and data.get("remark"):
        raise ErrorConsultaOSM(
            "Alerta de búsqueda: Overpass no pudo completar la consulta; puede estar saturado o haber un error."
        )
    if not isinstance(data, dict) or not isinstance(data.get("elements"), list):
        raise ErrorConsultaOSM("Alerta de búsqueda: Overpass devolvió una respuesta inválida.")

    candidatos = []
    for elemento in data["elements"]:
        if isinstance(elemento, dict):
            candidato = _candidato(elemento, lat, lon, radio_m)
            if candidato is not None:
                candidatos.append(candidato)
    return candidatos
