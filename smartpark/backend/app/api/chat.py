"""Chat con IA — RF-12."""
from flask import g, jsonify, request
from sqlalchemy import select

from ..extensions import db
from ..models import ConsultaIA
from ..services import chat as chat_srv
from ..services.auth import token_requerido
from ..services.errors import ApiError
from . import api_bp


@api_bp.post("/chat")
@token_requerido
def chat():
    d = request.get_json(silent=True) or {}
    consulta = (d.get("mensaje") or "").strip()
    if not consulta:
        raise ApiError("Escribe tu consulta", 400, "validacion")
    if len(consulta) > 500:
        raise ApiError("La consulta es demasiado larga (máx. 500 caracteres)", 400, "validacion")
    try:
        lat = float(d["lat"]) if d.get("lat") is not None else None
        lon = float(d["lon"]) if d.get("lon") is not None else None
    except (TypeError, ValueError):
        raise ApiError("Coordenadas inválidas", 400, "validacion")

    r = chat_srv.responder(consulta, lat, lon)
    rec = r.get("parqueadero_recomendado")
    db.session.add(ConsultaIA(usuario_id=g.usuario.id, consulta=consulta, respuesta=r["respuesta"],
                              parqueadero_recomendado_id=rec["id"] if rec else None,
                              tiempo_respuesta_ms=r["tiempo_respuesta_ms"]))
    db.session.commit()
    return jsonify(r)


@api_bp.get("/chat/historial")
@token_requerido
def historial():
    cs = db.session.scalars(select(ConsultaIA).where(ConsultaIA.usuario_id == g.usuario.id)
                            .order_by(ConsultaIA.fecha.desc()).limit(50)).all()
    return jsonify([{"consulta": c.consulta, "respuesta": c.respuesta,
                     "parqueadero_recomendado_id": c.parqueadero_recomendado_id,
                     "fecha": c.fecha.isoformat()} for c in reversed(cs)])
