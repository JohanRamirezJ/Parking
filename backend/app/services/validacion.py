"""Validaciones compartidas entre API y panel admin."""
import re
from datetime import datetime, time

from .geo import en_bogota

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[a-zA-Z]{2,}$")
TELEFONO_RE = re.compile(r"^\+?[0-9 ]{7,15}$")


def email_valido(v: str) -> bool:
    return bool(v) and bool(EMAIL_RE.match(v)) and len(v) <= 100


def telefono_valido(v: str) -> bool:
    return bool(TELEFONO_RE.match(v))


def parse_hora(v) -> time | None:
    if v in (None, ""):
        return None
    return datetime.strptime(str(v)[:5], "%H:%M").time()


def validar_parqueadero(datos: dict) -> tuple[dict, dict]:
    """Devuelve (limpio, errores). RF-09 campos obligatorios; RF-13 coordenadas dentro de Bogotá."""
    errores: dict[str, str] = {}
    limpio: dict = {}

    nombre = (datos.get("nombre") or "").strip()
    if not nombre:
        errores["nombre"] = "El nombre es obligatorio"
    limpio["nombre"] = nombre[:100]

    direccion = (datos.get("direccion") or "").strip()
    if not direccion:
        errores["direccion"] = "La dirección es obligatoria"
    limpio["direccion"] = direccion[:200]

    try:
        lat, lon = float(datos.get("latitud")), float(datos.get("longitud"))
        if not en_bogota(lat, lon):
            errores["ubicacion"] = "Las coordenadas están fuera de Bogotá"
        limpio["latitud"], limpio["longitud"] = lat, lon
    except (TypeError, ValueError):
        errores["ubicacion"] = "La ubicación (latitud y longitud) es obligatoria"

    for campo in ("tarifa_hora", "tarifa_dia"):
        v = datos.get(campo)
        if v in (None, ""):
            limpio[campo] = None
            continue
        try:
            f = float(v)
            if f <= 0 or f > 1_000_000:
                raise ValueError
            limpio[campo] = f
        except (TypeError, ValueError):
            errores[campo] = "Valor de tarifa inválido"
    if limpio.get("tarifa_hora") is None and limpio.get("tarifa_dia") is None and "tarifa_hora" not in errores:
        errores["tarifa_hora"] = "Registra al menos una tarifa (por hora o por día)"

    try:
        limpio["horario_apertura"] = parse_hora(datos.get("horario_apertura"))
        limpio["horario_cierre"] = parse_hora(datos.get("horario_cierre"))
    except ValueError:
        errores["horario"] = "Formato de hora inválido (HH:MM)"

    for campo in ("capacidad_total", "capacidad_disponible_estimada"):
        v = datos.get(campo)
        if v in (None, ""):
            limpio[campo] = None
            continue
        try:
            n = int(v)
            if n < 0:
                raise ValueError
            limpio[campo] = n
        except (TypeError, ValueError):
            errores[campo] = "Debe ser un número entero positivo"
    if (limpio.get("capacidad_total") is not None and limpio.get("capacidad_disponible_estimada") is not None
            and limpio["capacidad_disponible_estimada"] > limpio["capacidad_total"]):
        errores["capacidad_disponible_estimada"] = "No puede superar la capacidad total"

    limpio["imagen_url"] = (datos.get("imagen_url") or "").strip()[:255] or None
    activo = datos.get("activo", True)
    limpio["activo"] = activo in (True, "on", "true", "1", 1)
    return limpio, errores
