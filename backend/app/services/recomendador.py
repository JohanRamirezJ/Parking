"""Módulo de IA de SmartPark: recomendación multicriterio personalizada.

Para cada parqueadero cercano calcula un puntaje integral (0–100):

    puntaje = 100 · Σ wᵢ · sᵢ / Σ wᵢ

donde, para cada criterio i:
    wᵢ  peso de importancia (0–10) que el usuario puede modificar,
    sᵢ  puntaje normalizado del criterio (0 = peor opción, 1 = mejor opción).

Criterios (valor «crudo» antes de normalizar):
    gasolina    costo del combustible del trayecto en carro (COP)    → menos es mejor
    rodamiento  desgaste del vehículo por km recorrido (COP)         → menos es mejor
    tiempo      minutos en carro + minutos caminando al destino      → menos es mejor
    distancia   metros a pie entre el parqueadero y el destino       → menos es mejor
    seguridad   calificación de seguridad de los usuarios (1–5)      → más es mejor
    precio      costo estimado de la estadía según tarifa y horas    → menos es mejor

Normalización (min–max con umbral): para un criterio de costo,
    sᵢ = 1 − (v − mín) / máx(máx − mín, umbralᵢ)
El umbral evita que diferencias insignificantes (p. ej. $50 o 20 m) se conviertan
en la diferencia entre 0 y 1 cuando hay pocas opciones.

Datos faltantes:
    sin tarifa       → se asume la tarifa más alta de las opciones (conservador) y se avisa.
    sin calificación → se usa el promedio de las demás opciones y se avisa.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta

from flask import current_app

from ..models import ZONA_BOGOTA, Parqueadero
from .directorio import buscar_cercanos
from .geo import haversine_m

# ----------------------------------------------------------------------------- criterios
CRITERIOS: dict[str, dict] = {
    "gasolina":   {"nombre": "Gasolina",   "unidad": "COP", "sentido": "min", "umbral": 500,
                   "descripcion": "Combustible del trayecto en carro hasta el parqueadero"},
    "rodamiento": {"nombre": "Rodamiento", "unidad": "COP", "sentido": "min", "umbral": 500,
                   "descripcion": "Desgaste del vehículo (llantas, frenos, mantenimiento) por km"},
    "tiempo":     {"nombre": "Tiempo",     "unidad": "min", "sentido": "min", "umbral": 3,
                   "descripcion": "Minutos manejando más minutos caminando hasta el destino"},
    "distancia":  {"nombre": "Distancia",  "unidad": "m",   "sentido": "min", "umbral": 150,
                   "descripcion": "Distancia a pie entre el parqueadero y el destino"},
    "seguridad":  {"nombre": "Seguridad",  "unidad": "★",   "sentido": "max", "umbral": 1.0,
                   "descripcion": "Calificación de seguridad dada por otros usuarios (1 a 5)"},
    "precio":     {"nombre": "Precio",     "unidad": "COP", "sentido": "min", "umbral": 1000,
                   "descripcion": "Costo estimado de la estadía según la tarifa y las horas"},
}
ORDEN_CRITERIOS = list(CRITERIOS)
PESO_MIN, PESO_MAX = 0, 10

PERFILES: dict[str, dict] = {
    "equilibrado": {"nombre": "Equilibrado", "descripcion": "Todos los factores pesan parecido",
                    "pesos": {"gasolina": 2, "rodamiento": 1, "tiempo": 3, "distancia": 3, "seguridad": 3, "precio": 3}},
    "seguridad":   {"nombre": "De noche / seguridad", "descripcion": "Dejas el carro de noche o en zona desconocida",
                    "pesos": {"gasolina": 1, "rodamiento": 1, "tiempo": 2, "distancia": 3, "seguridad": 8, "precio": 2}},
    "precio":      {"nombre": "Muchas horas / precio", "descripcion": "Lo dejas varias horas y quieres pagar menos",
                    "pesos": {"gasolina": 1, "rodamiento": 1, "tiempo": 1, "distancia": 2, "seguridad": 3, "precio": 8}},
    "tiempo":      {"nombre": "Tengo afán", "descripcion": "Llegar rápido al destino es lo más importante",
                    "pesos": {"gasolina": 1, "rodamiento": 1, "tiempo": 8, "distancia": 4, "seguridad": 2, "precio": 2}},
    "vehiculo":    {"nombre": "Cuidar el carro", "descripcion": "Gastar menos gasolina y desgastar menos el vehículo",
                    "pesos": {"gasolina": 6, "rodamiento": 5, "tiempo": 2, "distancia": 2, "seguridad": 3, "precio": 3}},
}
PERFIL_DEFECTO = "equilibrado"


class ErrorRecomendacion(ValueError):
    def __init__(self, mensaje: str, campo: str | None = None):
        super().__init__(mensaje)
        self.campo = campo


# ----------------------------------------------------------------------------- parámetros
def parametros_vehiculo(personal: dict | None = None) -> dict:
    """Supuestos del costo de manejar; el usuario puede ajustarlos con su propio carro."""
    c = current_app.config
    base = {
        "precio_galon": c["PRECIO_GALON_COP"],
        "rendimiento_km_galon": c["RENDIMIENTO_KM_GALON"],
        "costo_rodamiento_km": c["COSTO_RODAMIENTO_KM"],
    }
    limites = {"precio_galon": (1000, 100_000), "rendimiento_km_galon": (5, 150), "costo_rodamiento_km": (0, 5000)}
    for k, v in (personal or {}).items():
        if k not in base or v in (None, ""):
            continue
        try:
            f = float(v)
        except (TypeError, ValueError):
            raise ErrorRecomendacion(f"Valor inválido para {k}", k)
        lo, hi = limites[k]
        if not lo <= f <= hi:
            raise ErrorRecomendacion(f"{k} debe estar entre {lo} y {hi}", k)
        base[k] = f
    return base


def resolver_pesos(perfil: str | None = None, pesos: dict | None = None, guardados: dict | None = None) -> tuple[dict, str]:
    """Prioridad: pesos enviados > pesos guardados del usuario > perfil > equilibrado."""
    if perfil and perfil not in PERFILES:
        raise ErrorRecomendacion(f"Perfil desconocido. Usa: {', '.join(PERFILES)}", "perfil")
    origen = perfil or (guardados and "personalizado") or PERFIL_DEFECTO
    resultado = dict(PERFILES[perfil or PERFIL_DEFECTO]["pesos"])
    if guardados and not perfil:
        resultado.update({k: v for k, v in guardados.items() if k in CRITERIOS})
    if pesos:
        desconocidos = set(pesos) - set(CRITERIOS)
        if desconocidos:
            raise ErrorRecomendacion(f"Criterio desconocido: {', '.join(sorted(desconocidos))}", "pesos")
        resultado.update(pesos)
        origen = "personalizado"
    limpio = {}
    for k in ORDEN_CRITERIOS:
        try:
            v = float(resultado[k])
        except (TypeError, ValueError):
            raise ErrorRecomendacion(f"Peso inválido para {k}", "pesos")
        if not PESO_MIN <= v <= PESO_MAX:
            raise ErrorRecomendacion(f"Los pesos van de {PESO_MIN} a {PESO_MAX}", "pesos")
        limpio[k] = v
    if sum(limpio.values()) <= 0:
        raise ErrorRecomendacion("Al menos un criterio debe tener peso mayor que 0", "pesos")
    return limpio, origen


def costo_estadia(p: Parqueadero, horas: float) -> float | None:
    """Tarifa por hora prorrateada, con tope en la tarifa diaria si existe."""
    th, td = p.tarifa_hora, p.tarifa_dia
    opciones = []
    if th is not None:
        opciones.append(th * horas)
    if td is not None:
        opciones.append(td * math.ceil(horas / 24))
    return min(opciones) if opciones else None


def _min_del_dia(t: time) -> int:
    return t.hour * 60 + t.minute


def disponibilidad_horaria(p: Parqueadero, llegada: datetime, horas: float) -> tuple[bool | None, str | None]:
    """(abierto_al_llegar, alerta). None si el parqueadero no reporta horario."""
    a, c = p.horario_apertura, p.horario_cierre
    if not a or not c:
        return None, "Horario no reportado"
    if a == c:
        return True, None
    m = _min_del_dia(llegada.time())
    ma, mc = _min_del_dia(a), _min_del_dia(c)
    abierto = ma <= m < mc if ma < mc else (m >= ma or m < mc)
    if not abierto:
        return False, f"Cerrado a la hora de llegada (abre {a.strftime('%H:%M')})"
    restante = (mc - m) % (24 * 60)
    if horas * 60 > restante:
        return True, f"Cierra a las {c.strftime('%H:%M')}, antes de que termine tu estadía"
    return True, None


# ----------------------------------------------------------------------------- cálculo
@dataclass
class Evaluacion:
    p: Parqueadero
    caminar_m: float
    manejo_km: float
    valores: dict = field(default_factory=dict)      # valor crudo por criterio
    imputados: set = field(default_factory=set)
    alertas: list = field(default_factory=list)
    puntajes: dict = field(default_factory=dict)     # sᵢ ∈ [0, 1]
    total: float = 0.0


def _fmt_cop(v: float) -> str:
    return "$" + f"{v:,.0f}".replace(",", ".")


def _texto_valor(k: str, v: float) -> str:
    if k in ("gasolina", "rodamiento", "precio"):
        return _fmt_cop(v)
    if k == "tiempo":
        return f"{v:.0f} min"
    if k == "distancia":
        return f"{v:.0f} m" if v < 1000 else f"{v / 1000:.1f} km"
    return f"{v:.1f}★"


def evaluar(candidatos: list[tuple[Parqueadero, float]], *, destino: tuple[float, float],
            origen: tuple[float, float] | None, horas: float, pesos: dict, vehiculo: dict,
            llegada: datetime, incluir_cerrados: bool = False) -> list[Evaluacion]:
    cfg = current_app.config
    factor, v_auto, v_pie = cfg["FACTOR_RUTA_URBANA"], cfg["VELOCIDAD_AUTO_KMH"], cfg["VELOCIDAD_PEATON_KMH"]

    evals: list[Evaluacion] = []
    for p, dist_destino in candidatos:
        caminar_m = dist_destino * factor
        if origen:
            manejo_km = haversine_m(origen[0], origen[1], p.latitud, p.longitud) * factor / 1000
        else:
            # Sin origen: se mide el desvío desde el destino hasta el parqueadero.
            manejo_km = dist_destino * factor / 1000
        min_manejo = manejo_km / v_auto * 60
        e = Evaluacion(p, caminar_m, manejo_km)
        abierto, alerta = disponibilidad_horaria(p, llegada + timedelta(minutes=min_manejo), horas)
        if abierto is False and not incluir_cerrados:
            continue
        if alerta:
            e.alertas.append(alerta)
        if p.capacidad_disponible_estimada == 0:
            e.alertas.append("Posiblemente lleno (0 cupos estimados)")

        e.valores["gasolina"] = manejo_km / vehiculo["rendimiento_km_galon"] * vehiculo["precio_galon"]
        e.valores["rodamiento"] = manejo_km * vehiculo["costo_rodamiento_km"]
        e.valores["tiempo"] = min_manejo + caminar_m / 1000 / v_pie * 60
        e.valores["distancia"] = caminar_m
        e.valores["seguridad"] = p.calificacion_seguridad if p.calificacion_seguridad is not None else p.calificacion_promedio
        e.valores["precio"] = costo_estadia(p, horas)
        if p.calificacion_seguridad is None and p.calificacion_promedio is not None:
            e.alertas.append("Seguridad estimada con la calificación general")
        evals.append(e)

    if not evals:
        return []

    # Imputación de datos faltantes
    precios = [e.valores["precio"] for e in evals if e.valores["precio"] is not None]
    seguridades = [e.valores["seguridad"] for e in evals if e.valores["seguridad"] is not None]
    precio_peor = max(precios) if precios else 0.0
    seguridad_media = sum(seguridades) / len(seguridades) if seguridades else 3.0
    for e in evals:
        if e.valores["precio"] is None:
            e.valores["precio"] = precio_peor
            e.imputados.add("precio")
            e.alertas.append("Tarifa no disponible: se asumió la más alta de la zona")
        if e.valores["seguridad"] is None:
            e.valores["seguridad"] = seguridad_media
            e.imputados.add("seguridad")
            e.alertas.append("Sin calificaciones: seguridad estimada con el promedio de la zona")

    # Normalización y puntaje ponderado
    suma_pesos = sum(pesos.values())
    for k, meta in CRITERIOS.items():
        vals = [e.valores[k] for e in evals]
        lo, hi = min(vals), max(vals)
        rango = max(hi - lo, meta["umbral"])
        for e in evals:
            v = e.valores[k]
            s = 1 - (v - lo) / rango if meta["sentido"] == "min" else 1 - (hi - v) / rango
            e.puntajes[k] = max(0.0, min(1.0, s))
    for e in evals:
        e.total = 100 * sum(pesos[k] * e.puntajes[k] for k in CRITERIOS) / suma_pesos

    evals.sort(key=lambda e: (-e.total, e.valores["tiempo"]))
    return evals


def _justificar(e: Evaluacion, pesos: dict, siguiente: Evaluacion | None, discriminan: set) -> str:
    """Explica el puntaje con los criterios que de verdad diferencian a esta opción de las demás."""
    activos = [k for k in ORDEN_CRITERIOS if pesos[k] > 0 and k in discriminan and k not in e.imputados]
    fuertes = sorted(activos, key=lambda k: -pesos[k] * e.puntajes[k])
    fuertes = [k for k in fuertes if e.puntajes[k] >= 0.7][:2]
    debil = min(activos, key=lambda k: (e.puntajes[k], -pesos[k])) if activos else None
    partes = [f"Puntaje {e.total:.0f}/100."]
    if fuertes:
        partes.append("Destaca en " + " y ".join(
            f"{CRITERIOS[k]['nombre'].lower()} ({_texto_valor(k, e.valores[k])})" for k in fuertes) + ".")
    if not activos:
        partes.append("Las opciones son muy parecidas en los criterios que más te importan.")
    elif e.puntajes[debil] < 0.5 and debil not in fuertes:
        partes.append(f"Su punto débil es {CRITERIOS[debil]['nombre'].lower()} ({_texto_valor(debil, e.valores[debil])}).")
    if siguiente:
        dif_costo = (siguiente.valores["precio"] + siguiente.valores["gasolina"] + siguiente.valores["rodamiento"]) - \
                    (e.valores["precio"] + e.valores["gasolina"] + e.valores["rodamiento"])
        dif_min = siguiente.valores["tiempo"] - e.valores["tiempo"]
        comp = []
        if abs(dif_costo) >= 500:
            comp.append(f"cuesta {_fmt_cop(abs(dif_costo))} {'menos' if dif_costo > 0 else 'más'} en total")
        if abs(dif_min) >= 1:
            comp.append(f"toma {abs(dif_min):.0f} min {'menos' if dif_min > 0 else 'más'}")
        if comp:
            partes.append(f"Frente a {siguiente.p.nombre}, " + " y ".join(comp) + ".")
    return " ".join(partes)


def serializar(evals: list[Evaluacion], pesos: dict, limite: int) -> list[dict]:
    if not evals:
        return []
    suma = sum(pesos.values())
    discriminan = {k for k, m in CRITERIOS.items()
                   if max(e.valores[k] for e in evals) - min(e.valores[k] for e in evals) >= m["umbral"] * 0.5}
    salida = []
    for i, e in enumerate(evals[:limite]):
        siguiente = evals[i + 1] if i + 1 < len(evals) else None
        criterios = {}
        for k, meta in CRITERIOS.items():
            criterios[k] = {
                "valor": round(e.valores[k], 2),
                "unidad": meta["unidad"],
                "texto": _texto_valor(k, e.valores[k]),
                "puntaje": round(e.puntajes[k], 3),
                "peso": pesos[k],
                "peso_pct": round(100 * pesos[k] / suma, 1),
                "aporte": round(100 * pesos[k] * e.puntajes[k] / suma, 1),
                "estimado": k in e.imputados,
            }
        costo_total = e.valores["precio"] + e.valores["gasolina"] + e.valores["rodamiento"]
        salida.append({
            "posicion": i + 1,
            "puntaje": round(e.total, 1),
            "parqueadero": e.p.to_dict(e.caminar_m),
            "criterios": criterios,
            "costo_total_estimado": round(costo_total),
            "manejo_km": round(e.manejo_km, 2),
            "alertas": e.alertas,
            "justificacion": _justificar(e, pesos, siguiente, discriminan),
        })
    return salida


def recomendar(*, destino: tuple[float, float], origen: tuple[float, float] | None = None,
               horas: float = 2, radio_m: float | None = None, perfil: str | None = None,
               pesos: dict | None = None, preferencias: dict | None = None, vehiculo: dict | None = None,
               llegada: datetime | None = None, incluir_cerrados: bool = False, limite: int = 10,
               tarifa_max: float | None = None) -> dict:
    cfg = current_app.config
    if not 0.25 <= horas <= 72:
        raise ErrorRecomendacion("Las horas de estadía van de 0.25 a 72", "horas")
    radio = radio_m or cfg["RADIO_DEFECTO_M"]
    if not cfg["RADIO_MIN_M"] <= radio <= cfg["RADIO_MAX_M"]:
        raise ErrorRecomendacion(f"El radio debe estar entre {cfg['RADIO_MIN_M']} y {cfg['RADIO_MAX_M']} metros", "radio")
    prefs = preferencias or {}
    pesos_final, origen_pesos = resolver_pesos(perfil, pesos, prefs.get("pesos"))
    veh = parametros_vehiculo({**(prefs.get("vehiculo") or {}), **(vehiculo or {})})
    llegada = llegada or datetime.now(ZONA_BOGOTA).replace(tzinfo=None)

    candidatos = buscar_cercanos(destino[0], destino[1], radio, tarifa_max=tarifa_max)
    evals = evaluar(candidatos, destino=destino, origen=origen, horas=horas, pesos=pesos_final,
                    vehiculo=veh, llegada=llegada, incluir_cerrados=incluir_cerrados)
    resultados = serializar(evals, pesos_final, limite)
    suma = sum(pesos_final.values())
    return {
        "total": len(evals),
        "perfil": origen_pesos,
        "pesos": pesos_final,
        "pesos_pct": {k: round(100 * v / suma, 1) for k, v in pesos_final.items()},
        "horas": horas,
        "radio_m": radio,
        "destino": {"latitud": destino[0], "longitud": destino[1]},
        "origen": {"latitud": origen[0], "longitud": origen[1]} if origen else None,
        "supuestos": {
            **veh,
            "velocidad_auto_kmh": cfg["VELOCIDAD_AUTO_KMH"],
            "velocidad_peaton_kmh": cfg["VELOCIDAD_PEATON_KMH"],
            "factor_ruta_urbana": cfg["FACTOR_RUTA_URBANA"],
            "hora_llegada": llegada.strftime("%H:%M"),
            "trayecto": "desde tu origen" if origen else "desvío desde el destino (no se envió origen)",
        },
        "resultados": resultados,
        "mensaje": None if resultados else "No hay parqueaderos abiertos en este radio. Prueba ampliando el radio.",
    }
