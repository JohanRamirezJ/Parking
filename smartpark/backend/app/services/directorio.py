"""Lógica del directorio de parqueaderos, compartida por API y panel admin (Repository pattern)."""
import json

from flask import request
from sqlalchemy import select

from ..extensions import db
from ..models import LogAuditoria, Parqueadero, Tarifa
from .geo import caja_envolvente, haversine_m


def snapshot(p: Parqueadero) -> str:
    d = p.to_dict()
    d.pop("abierto_ahora", None)
    d.pop("total_resenas", None)
    return json.dumps(d, ensure_ascii=False, default=str)


def auditar(usuario_id, accion: str, entidad: str, entidad_id, previos=None, nuevos=None):
    db.session.add(LogAuditoria(
        usuario_id=usuario_id, accion=accion, entidad=entidad, entidad_id=entidad_id,
        datos_previos=previos, datos_nuevos=nuevos,
        ip_origen=(request.headers.get("X-Forwarded-For") or request.remote_addr or "")[:45],
    ))


def _fijar_tarifa(p: Parqueadero, tipo: str, unidad: str, valor: float | None):
    actual = next((t for t in p.tarifas if t.vigente and t.tipo == tipo), None)
    if actual and (valor is None or actual.valor != valor):
        actual.vigente = False  # se conserva el histórico de tarifas
    if valor is not None and (actual is None or actual.valor != valor):
        p.tarifas.append(Tarifa(tipo=tipo, unidad=unidad, valor=valor, vigente=True))


def aplicar_datos(p: Parqueadero, limpio: dict):
    for campo in ("nombre", "direccion", "latitud", "longitud", "horario_apertura", "horario_cierre",
                  "capacidad_total", "capacidad_disponible_estimada", "imagen_url", "activo"):
        setattr(p, campo, limpio[campo])
    _fijar_tarifa(p, "hora", "hora", limpio["tarifa_hora"])
    _fijar_tarifa(p, "dia", "dia", limpio["tarifa_dia"])


def buscar_cercanos(lat: float, lon: float, radio_m: float, *, orden: str = "distancia",
                    tarifa_min: float | None = None, tarifa_max: float | None = None,
                    solo_abiertos: bool = False) -> list[tuple[Parqueadero, float]]:
    lat_min, lat_max, lon_min, lon_max = caja_envolvente(lat, lon, radio_m)
    candidatos = db.session.scalars(
        select(Parqueadero).where(
            Parqueadero.activo.is_(True),
            Parqueadero.latitud.between(lat_min, lat_max),
            Parqueadero.longitud.between(lon_min, lon_max),
        )
    ).all()

    resultados = []
    for p in candidatos:
        dist = haversine_m(lat, lon, p.latitud, p.longitud)
        if dist > radio_m:
            continue
        if tarifa_min is not None or tarifa_max is not None:
            th = p.tarifa_hora
            if th is None:
                continue
            if tarifa_min is not None and th < tarifa_min:
                continue
            if tarifa_max is not None and th > tarifa_max:
                continue
        if solo_abiertos and p.abierto_ahora() is False:
            continue
        resultados.append((p, dist))

    inf = float("inf")
    if orden == "tarifa":
        # Los que no tienen tarifa van al final (RF-05)
        resultados.sort(key=lambda x: (x[0].tarifa_hora is None, x[0].tarifa_hora or inf, x[1]))
    elif orden == "calificacion":
        resultados.sort(key=lambda x: (-(x[0].calificacion_promedio or 0), x[1]))
    else:
        resultados.sort(key=lambda x: x[1])
    return resultados
