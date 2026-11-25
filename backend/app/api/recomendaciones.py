"""Módulo de IA — recomendación multicriterio personalizada y preferencias del usuario."""
import json
from datetime import datetime

from flask import current_app, g, jsonify, request

from ..extensions import db
from ..models import ConsultaIA, EventoBusqueda
from ..services import recomendador as rec
from ..services.auth import token_opcional, token_requerido
from ..services.errors import ApiError
from ..services.geo import en_bogota
from ..services.geocoding import geocodificar
from . import api_bp


def _punto(d, nombre: str) -> tuple[float, float] | None:
    if d in (None, {}):
        return None
    if not isinstance(d, dict):
        raise ApiError(f"'{nombre}' debe ser un objeto {{lat, lon}}", 400, "validacion")
    try:
        lat, lon = float(d.get("lat", d.get("latitud"))), float(d.get("lon", d.get("longitud")))
    except (TypeError, ValueError):
        raise ApiError(f"Coordenadas de '{nombre}' inválidas", 400, "validacion")
    if not en_bogota(lat, lon):
        raise ApiError(f"El {nombre} está fuera de Bogotá", 400, "fuera_de_cobertura")
    return lat, lon


@api_bp.get("/recomendaciones/perfiles")
def perfiles():
    """Criterios, perfiles predefinidos y supuestos por defecto (para pintar los controles en la app)."""
    return jsonify({
        "criterios": [{"clave": k, **{c: v for c, v in m.items() if c != "umbral"}} for k, m in rec.CRITERIOS.items()],
        "perfiles": [{"clave": k, **v} for k, v in rec.PERFILES.items()],
        "perfil_defecto": rec.PERFIL_DEFECTO,
        "peso_min": rec.PESO_MIN, "peso_max": rec.PESO_MAX,
        "vehiculo_defecto": rec.parametros_vehiculo(),
    })


@api_bp.post("/recomendaciones")
@token_opcional
def recomendar():
    d = request.get_json(silent=True)
    if not isinstance(d, dict):
        raise ApiError("Cuerpo JSON inválido", 400, "json_invalido")

    destino = _punto(d.get("destino"), "destino")
    destino_nombre = None
    if destino is None and (d.get("destino_texto") or "").strip():
        geo = geocodificar(d["destino_texto"])
        if not geo:
            raise ApiError("Destino no encontrado", 404, "destino_no_encontrado")
        destino, destino_nombre = (geo["latitud"], geo["longitud"]), geo["nombre"]
    if destino is None:
        raise ApiError("Indica el destino ({lat, lon} o destino_texto)", 400, "parametro_faltante")
    origen = _punto(d.get("origen"), "origen")

    llegada = None
    if d.get("hora_llegada"):
        try:
            h = datetime.strptime(str(d["hora_llegada"])[:5], "%H:%M").time()
            llegada = datetime.combine(datetime.now(rec.ZONA_BOGOTA).date(), h)
        except ValueError:
            raise ApiError("hora_llegada debe tener formato HH:MM", 400, "validacion")

    try:
        horas = float(d.get("horas", 2))
        radio = float(d["radio"]) if d.get("radio") else None
        limite = max(1, min(int(d.get("limite", 10)), 50))
        tarifa_max = float(d["tarifa_max"]) if d.get("tarifa_max") else None
    except (TypeError, ValueError):
        raise ApiError("horas, radio, limite y tarifa_max deben ser numéricos", 400, "validacion")
    if d.get("pesos") is not None and not isinstance(d["pesos"], dict):
        raise ApiError("'pesos' debe ser un objeto {criterio: peso}", 400, "validacion")

    prefs = g.usuario.get_preferencias() if g.usuario else {}
    try:
        r = rec.recomendar(destino=destino, origen=origen, horas=horas, radio_m=radio, perfil=d.get("perfil"),
                           pesos=d.get("pesos"), preferencias=prefs, vehiculo=d.get("vehiculo"),
                           llegada=llegada, incluir_cerrados=bool(d.get("incluir_cerrados")),
                           limite=limite, tarifa_max=tarifa_max)
    except rec.ErrorRecomendacion as e:
        raise ApiError(str(e), 400, "validacion", {e.campo: str(e)} if e.campo else None)
    if destino_nombre:
        r["destino"]["nombre"] = destino_nombre

    db.session.add(EventoBusqueda(usuario_id=g.usuario.id if g.usuario else None, latitud=destino[0],
                                  longitud=destino[1], radio_m=int(r["radio_m"]), resultados=r["total"]))
    if g.usuario and r["resultados"]:
        db.session.add(ConsultaIA(usuario_id=g.usuario.id, consulta=f"[recomendador:{r['perfil']}] {horas} h",
                                  respuesta=r["resultados"][0]["justificacion"],
                                  parqueadero_recomendado_id=r["resultados"][0]["parqueadero"]["id"]))
    db.session.commit()
    return jsonify(r)


@api_bp.get("/me/preferencias")
@token_requerido
def ver_preferencias():
    prefs = g.usuario.get_preferencias()
    pesos, origen = rec.resolver_pesos(None, None, prefs.get("pesos"))
    return jsonify({"perfil": prefs.get("perfil", origen), "pesos": pesos,
                    "vehiculo": rec.parametros_vehiculo(prefs.get("vehiculo"))})


@api_bp.put("/me/preferencias")
@token_requerido
def guardar_preferencias():
    """Guarda los pesos y el vehículo del usuario: la IA los usa por defecto en sus próximas búsquedas."""
    d = request.get_json(silent=True) or {}
    try:
        pesos, origen = rec.resolver_pesos(d.get("perfil"), d.get("pesos"))
        veh_in = d.get("vehiculo") or {}
        rec.parametros_vehiculo(veh_in)  # valida
    except rec.ErrorRecomendacion as e:
        raise ApiError(str(e), 400, "validacion", {e.campo: str(e)} if e.campo else None)
    veh = {k: float(v) for k, v in veh_in.items() if v not in (None, "")}
    g.usuario.preferencias = json.dumps({"perfil": origen, "pesos": pesos, "vehiculo": veh})
    db.session.commit()
    return jsonify({"perfil": origen, "pesos": pesos, "vehiculo": rec.parametros_vehiculo(veh)})
