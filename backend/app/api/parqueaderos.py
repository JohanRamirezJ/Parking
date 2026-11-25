"""Búsqueda y consulta de parqueaderos — HU 5, 6, 7, 8, 9, 12 (RF-03, 04, 05, 07)."""
from flask import current_app, g, jsonify, request

from ..extensions import db
from ..models import EventoBusqueda, Parqueadero
from ..services.auth import token_opcional
from ..services.directorio import buscar_cercanos
from ..services.errors import ApiError
from ..services.geo import en_bogota
from ..services.geocoding import geocodificar
from . import api_bp


def _float(nombre: str, requerido: bool = False) -> float | None:
    v = request.args.get(nombre)
    if v in (None, ""):
        if requerido:
            raise ApiError(f"Parámetro '{nombre}' requerido", 400, "parametro_faltante")
        return None
    try:
        return float(v)
    except ValueError:
        raise ApiError(f"Parámetro '{nombre}' inválido", 400, "parametro_invalido")


@api_bp.get("/salud")
def salud():
    return jsonify({"estado": "ok", "servicio": "smartpark-api"})


@api_bp.get("/geocodificar")
def geocodificar_destino():
    q = (request.args.get("q") or "").strip()
    if not q:
        raise ApiError("Escribe una dirección o lugar", 400, "parametro_faltante")
    r = geocodificar(q)
    if not r:
        raise ApiError("Destino no encontrado", 404, "destino_no_encontrado")
    return jsonify(r)


@api_bp.get("/parqueaderos")
@token_opcional
def buscar():
    cfg = current_app.config
    lat, lon = _float("lat", True), _float("lon", True)
    radio = _float("radio") or cfg["RADIO_DEFECTO_M"]
    if not (cfg["RADIO_MIN_M"] <= radio <= cfg["RADIO_MAX_M"]):
        raise ApiError(f"El radio debe estar entre {cfg['RADIO_MIN_M']} y {cfg['RADIO_MAX_M']} metros",
                       400, "radio_fuera_de_rango")
    if not en_bogota(lat, lon):
        raise ApiError("SmartPark por ahora solo cubre Bogotá", 400, "fuera_de_cobertura")
    orden = request.args.get("orden", "distancia")
    if orden not in ("distancia", "tarifa", "calificacion"):
        raise ApiError("Orden inválido (distancia | tarifa | calificacion)", 400, "parametro_invalido")
    tmin, tmax = _float("tarifa_min"), _float("tarifa_max")
    if tmin is not None and tmax is not None and tmin > tmax:
        raise ApiError("La tarifa mínima no puede ser mayor que la máxima", 400, "parametro_invalido")

    res = buscar_cercanos(lat, lon, radio, orden=orden, tarifa_min=tmin, tarifa_max=tmax,
                          solo_abiertos=request.args.get("abiertos") in ("1", "true"))

    db.session.add(EventoBusqueda(usuario_id=g.usuario.id if g.usuario else None,
                                  latitud=lat, longitud=lon, radio_m=int(radio), resultados=len(res)))
    db.session.commit()

    cuerpo = {"total": len(res), "radio_m": radio, "orden": orden,
              "resultados": [p.to_dict(d) for p, d in res]}
    if not res:  # HU 6 / 9: mensaje guía
        cuerpo["mensaje"] = ("No hay parqueaderos en ese rango de tarifa" if (tmin or tmax)
                             else "No hay parqueaderos en este radio. Prueba ampliando el radio de búsqueda.")
        cuerpo["sugerir_ampliar_radio"] = radio < cfg["RADIO_MAX_M"]
    return jsonify(cuerpo)


@api_bp.get("/parqueaderos/<int:pid>")
def detalle(pid: int):
    p = db.session.get(Parqueadero, pid)
    if not p or not p.activo:
        raise ApiError("Parqueadero no encontrado", 404, "no_encontrado")
    lat, lon = _float("lat"), _float("lon")
    dist = None
    if lat is not None and lon is not None:
        from ..services.geo import haversine_m
        dist = haversine_m(lat, lon, p.latitud, p.longitud)
    return jsonify(p.to_dict(dist))
