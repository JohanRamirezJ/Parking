"""Visitas, reseñas y reportes — HU 10, 11 (RF-06, RF-10)."""
from flask import g, jsonify, request
from sqlalchemy import select

from ..extensions import db
from ..models import Parqueadero, ReporteUsuario, Resena, Visita
from ..services.auth import token_requerido
from ..services.errors import ApiError
from . import api_bp


def _parqueadero(pid: int) -> Parqueadero:
    p = db.session.get(Parqueadero, pid)
    if not p or not p.activo:
        raise ApiError("Parqueadero no encontrado", 404, "no_encontrado")
    return p


@api_bp.post("/parqueaderos/<int:pid>/visitas")
@token_requerido
def marcar_visitado(pid: int):
    _parqueadero(pid)
    d = request.get_json(silent=True) or {}
    tarifa = d.get("tarifa_pagada")
    try:
        tarifa = float(tarifa) if tarifa not in (None, "") else None
    except (TypeError, ValueError):
        raise ApiError("Tarifa pagada inválida", 400, "validacion")
    v = Visita(usuario_id=g.usuario.id, parqueadero_id=pid, tarifa_pagada=tarifa,
               metodo_pago=(d.get("metodo_pago") or None), comentario_adicional=d.get("comentario_adicional"))
    db.session.add(v)
    db.session.commit()
    return jsonify(v.to_dict()), 201


@api_bp.get("/parqueaderos/<int:pid>/resenas")
def listar_resenas(pid: int):
    _parqueadero(pid)
    rs = db.session.scalars(
        select(Resena).where(Resena.parqueadero_id == pid, Resena.estado == "aprobada")
        .order_by(Resena.fecha.desc())).all()
    cuerpo = {"total": len(rs), "resenas": [r.to_dict() for r in rs]}
    if not rs:
        cuerpo["mensaje"] = "Aún sin reseñas"
    return jsonify(cuerpo)


@api_bp.post("/parqueaderos/<int:pid>/resenas")
@token_requerido
def crear_resena(pid: int):
    p = _parqueadero(pid)
    visitado = db.session.scalar(select(Visita.id).where(
        Visita.usuario_id == g.usuario.id, Visita.parqueadero_id == pid).limit(1))
    if not visitado:  # RF-06
        raise ApiError("Debes marcar el parqueadero como visitado antes de calificarlo", 403, "sin_visita")

    d = request.get_json(silent=True) or {}
    try:
        cal = int(d.get("calificacion"))
    except (TypeError, ValueError):
        cal = 0
    if not 1 <= cal <= 5:
        raise ApiError("La calificación debe estar entre 1 y 5", 400, "validacion")
    comentario = (d.get("comentario") or "").strip()[:1000] or None

    # Una reseña por usuario y parqueadero: si ya existe se actualiza.
    r = db.session.scalar(select(Resena).where(Resena.usuario_id == g.usuario.id, Resena.parqueadero_id == pid))
    creada = r is None
    if creada:
        r = Resena(usuario_id=g.usuario.id, parqueadero=p)
        db.session.add(r)
    r.calificacion, r.comentario, r.estado = cal, comentario, "aprobada"
    db.session.flush()
    p.recalcular_promedio()
    db.session.commit()
    return jsonify({"resena": r.to_dict(), "calificacion_promedio": p.calificacion_promedio}), 201 if creada else 200


@api_bp.post("/resenas/<int:rid>/reportar")
@token_requerido
def reportar_resena(rid: int):
    r = db.session.get(Resena, rid)
    if not r:
        raise ApiError("Reseña no encontrada", 404, "no_encontrado")
    if r.usuario_id == g.usuario.id:
        raise ApiError("No puedes reportar tu propia reseña", 400, "validacion")
    d = request.get_json(silent=True) or {}
    motivo = (d.get("motivo") or "").strip()
    if not motivo:
        raise ApiError("Indica el motivo del reporte", 400, "validacion")
    ya = db.session.scalar(select(ReporteUsuario.id).where(
        ReporteUsuario.resena_id == rid, ReporteUsuario.usuario_reportante_id == g.usuario.id))
    if ya:
        raise ApiError("Ya reportaste esta reseña", 409, "reporte_duplicado")
    r.reportado = True
    db.session.add(ReporteUsuario(resena_id=rid, usuario_reportado_id=r.usuario_id,
                                  usuario_reportante_id=g.usuario.id, motivo=motivo[:1000],
                                  evidencia=d.get("evidencia")))
    db.session.commit()
    return jsonify({"mensaje": "Gracias, revisaremos el reporte"}), 201
