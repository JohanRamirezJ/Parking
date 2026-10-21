"""Límite de intentos de login fallidos (en memoria, por proceso).

Con varios workers de gunicorn cada proceso lleva su propia cuenta, así que el límite
real es hasta N x workers; para un límite global usar Redis.
"""
import time
from threading import Lock

from flask import current_app, request

from .errors import ApiError

_intentos: dict[str, list[float]] = {}
_lock = Lock()


def _clave(email: str) -> str:
    return f"{request.remote_addr}|{(email or '').strip().lower()}"


def _vigentes(clave: str) -> list[float]:
    corte = time.monotonic() - current_app.config["LOGIN_VENTANA_S"]
    vigentes = [t for t in _intentos.get(clave, []) if t > corte]
    if vigentes:
        _intentos[clave] = vigentes
    else:
        _intentos.pop(clave, None)
    return vigentes


def bloqueado(email: str) -> bool:
    with _lock:
        return len(_vigentes(_clave(email))) >= current_app.config["LOGIN_MAX_INTENTOS"]


def registrar_fallo(email: str) -> None:
    with _lock:
        clave = _clave(email)
        _vigentes(clave)
        _intentos.setdefault(clave, []).append(time.monotonic())


def limpiar(email: str) -> None:
    with _lock:
        _intentos.pop(_clave(email), None)


def exigir_no_bloqueado(email: str) -> None:
    if bloqueado(email):
        raise ApiError("Demasiados intentos fallidos, espera unos minutos", 429, "demasiados_intentos")


def reiniciar() -> None:
    """Vacía todos los contadores (usado en pruebas)."""
    with _lock:
        _intentos.clear()
