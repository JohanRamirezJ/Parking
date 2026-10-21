"""Autenticación por token JWT (HU 13, RF-08, RNF-04)."""
from datetime import datetime, timedelta, timezone
from functools import wraps

import jwt
from flask import current_app, g, request

from ..extensions import db
from ..models import Usuario
from .errors import ApiError


def emitir_token(usuario: Usuario) -> str:
    exp = datetime.now(timezone.utc) + timedelta(minutes=current_app.config["JWT_EXP_MINUTES"])
    payload = {"sub": str(usuario.id), "admin": usuario.es_admin, "exp": exp}
    return jwt.encode(payload, current_app.config["JWT_SECRET"], algorithm="HS256")


def _usuario_desde_token() -> Usuario:
    cabecera = request.headers.get("Authorization", "")
    if not cabecera.startswith("Bearer "):
        raise ApiError("Token de autenticación requerido", 401, "token_requerido")
    token = cabecera.removeprefix("Bearer ").strip()
    try:
        payload = jwt.decode(token, current_app.config["JWT_SECRET"], algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise ApiError("La sesión expiró, inicia sesión de nuevo", 401, "token_expirado")
    except jwt.InvalidTokenError:
        raise ApiError("Token inválido", 401, "token_invalido")
    usuario = db.session.get(Usuario, int(payload["sub"]))
    if usuario is None:
        raise ApiError("Token inválido", 401, "token_invalido")
    if not usuario.activo:
        raise ApiError("Tu cuenta está suspendida", 403, "cuenta_suspendida")
    return usuario


def token_requerido(fn):
    @wraps(fn)
    def envoltura(*args, **kwargs):
        g.usuario = _usuario_desde_token()
        return fn(*args, **kwargs)
    return envoltura


def token_opcional(fn):
    @wraps(fn)
    def envoltura(*args, **kwargs):
        g.usuario = None
        if request.headers.get("Authorization"):
            g.usuario = _usuario_desde_token()
        return fn(*args, **kwargs)
    return envoltura
