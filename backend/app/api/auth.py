"""Autenticación y perfil — HU 1, 2, 3 (RF-01, RF-02)."""
from datetime import datetime

from flask import g, jsonify, request
from sqlalchemy import select

from ..extensions import db
from ..models import Notificacion, Usuario, Visita
from ..services.auth import emitir_token, token_requerido
from ..services.errors import ApiError
from ..services.validacion import email_valido, telefono_valido
from . import api_bp


def _json() -> dict:
    datos = request.get_json(silent=True)
    if not isinstance(datos, dict):
        raise ApiError("Cuerpo JSON inválido", 400, "json_invalido")
    return datos


@api_bp.post("/auth/registro")
def registro():
    d = _json()
    email = (d.get("email") or "").strip().lower()
    password = d.get("password") or ""
    nombre = (d.get("nombre") or "").strip()

    errores = {}
    if not email_valido(email):
        errores["email"] = "Correo inválido"
    if len(password) < 8:
        errores["password"] = "La contraseña debe tener al menos 8 caracteres"
    if not nombre:
        errores["nombre"] = "El nombre es obligatorio"
    if errores:
        raise ApiError("Formulario incompleto o inválido", 400, "validacion", errores)
    if db.session.scalar(select(Usuario).where(Usuario.email == email)):
        raise ApiError("Este correo ya está registrado", 409, "email_duplicado")

    u = Usuario(email=email, nombre=nombre[:100], ultimo_acceso=datetime.utcnow())
    u.set_password(password)
    db.session.add(u)
    db.session.commit()
    return jsonify({"token": emitir_token(u), "usuario": u.to_dict()}), 201


@api_bp.post("/auth/login")
def login():
    d = _json()
    email = (d.get("email") or "").strip().lower()
    u = db.session.scalar(select(Usuario).where(Usuario.email == email))
    if not u or not u.check_password(d.get("password") or ""):
        raise ApiError("Correo o contraseña incorrectos", 401, "credenciales_invalidas")
    if not u.activo:
        raise ApiError("Tu cuenta está suspendida", 403, "cuenta_suspendida")
    u.ultimo_acceso = datetime.utcnow()
    db.session.commit()
    return jsonify({"token": emitir_token(u), "usuario": u.to_dict()})


@api_bp.get("/me")
@token_requerido
def perfil():
    return jsonify(g.usuario.to_dict())


@api_bp.put("/me")
@token_requerido
def editar_perfil():
    d = _json()
    u: Usuario = g.usuario
    errores = {}
    if "nombre" in d:
        nombre = (d.get("nombre") or "").strip()
        if not nombre or len(nombre) > 100:
            errores["nombre"] = "Nombre inválido"
    if d.get("telefono") and not telefono_valido(str(d["telefono"])):
        errores["telefono"] = "Teléfono inválido (7 a 15 dígitos)"
    if d.get("foto_perfil") and not str(d["foto_perfil"]).startswith(("http://", "https://")):
        errores["foto_perfil"] = "La foto debe ser una URL"
    if "password" in d and d["password"] and len(d["password"]) < 8:
        errores["password"] = "La contraseña debe tener al menos 8 caracteres"
    if errores:  # HU 3: si hay formato inválido no se guarda nada
        raise ApiError("Hay campos con formato inválido", 400, "validacion", errores)

    if "nombre" in d:
        u.nombre = d["nombre"].strip()
    if "telefono" in d:
        u.telefono = d["telefono"] or None
    if "foto_perfil" in d:
        u.foto_perfil = d["foto_perfil"] or None
    if d.get("password"):
        u.set_password(d["password"])
    db.session.commit()
    return jsonify(u.to_dict())


@api_bp.get("/me/visitas")
@token_requerido
def mis_visitas():
    vs = db.session.scalars(select(Visita).where(Visita.usuario_id == g.usuario.id)
                            .order_by(Visita.fecha_visita.desc())).all()
    return jsonify([v.to_dict() for v in vs])


@api_bp.get("/me/notificaciones")
@token_requerido
def mis_notificaciones():
    ns = db.session.scalars(select(Notificacion).where(Notificacion.usuario_id == g.usuario.id)
                            .order_by(Notificacion.fecha.desc())).all()
    return jsonify([n.to_dict() for n in ns])
