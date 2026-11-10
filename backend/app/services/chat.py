"""Asistente conversacional (HU chat IA, RF-12).

Diseño: la recomendación SIEMPRE sale del directorio (nunca se inventan parqueaderos).
1. Se interpreta la consulta (presupuesto, perfil de prioridad, horas, destino).
2. El módulo de IA multicriterio (services/recomendador.py) puntúa los parqueaderos
   reales cercanos combinando gasolina, rodamiento, tiempo, distancia, seguridad y precio.
3. Si hay OPENAI_API_KEY, el modelo redacta la respuesta usando SOLO esos candidatos;
   si no, se responde con una plantilla. En ambos casos el parqueadero recomendado
   es el primero del ranking calculado aquí.
"""
import json
import re
import time
import urllib.request

from flask import current_app

from .geocoding import geocodificar, normalizar
from .recomendador import PERFILES, recomendar


_FIN_DESTINO = (r"(?:\s+(?:que|con|por menos|por debajo|menos de|hasta|maximo|y|durante|de noche|en la noche|todo el dia|rapido|ya|hoy|manana|ahora)\b"
                r"|\s+(?:por|a)\s+\d|[?.!,]|$)")


def interpretar(consulta: str) -> dict:
    n = re.sub(r"\bpor favor\b", " ", normalizar(consulta))
    intencion = {"orden": "distancia", "perfil": None, "horas": None, "tarifa_max": None,
                 "solo_abiertos": False, "radio_m": None, "destino_texto": None}

    # Perfil de pesos para el modelo multicriterio (el primero que aplique)
    if re.search(r"\b(de noche|en la noche|noche|segur\w*|insegur\w*|vigilad\w*)\b", n):
        intencion["perfil"] = "seguridad"
    elif re.search(r"\b(barat\w*|economic\w*|precio bajo|menor precio|mas bajo|todo el dia|muchas horas|varias horas)\b", n):
        intencion["perfil"] = "precio"
    elif re.search(r"\b(afan|prisa|rapid\w*|urgente|tarde)\b", n):
        intencion["perfil"] = "tiempo"
    elif re.search(r"\b(gasolina|combustible|desgaste|cuidar el carro)\b", n):
        intencion["perfil"] = "vehiculo"
    elif re.search(r"\b(mejor calificad\w*|buenas? resenas?)\b", n):
        intencion["perfil"] = "seguridad"

    # Compatibilidad con el orden simple de la v0.1
    if re.search(r"\b(barat\w*|economic\w*|precio bajo|menor precio|mas bajo)\b", n):
        intencion["orden"] = "tarifa"
    elif re.search(r"\b(mejor calificad\w*|recomendad\w*|seguro|buenas? resenas?|mejor)\b", n):
        intencion["orden"] = "calificacion"

    m = re.search(r"(?:menos de|maximo|max\.?|hasta|no mas de|por debajo de)\s*\$?\s*([\d.,]+)\s*(mil|k)?(?!\s*(?:horas?|h)\b)", n)
    if m:
        valor = float(m.group(1).replace(".", "").replace(",", ""))
        if m.group(2) or valor < 100:
            valor *= 1000
        intencion["tarifa_max"] = valor

    if re.search(r"\b(abierto|24 ?horas|ahora mismo|de noche)\b", n):
        intencion["solo_abiertos"] = True

    # Duración de la estadía
    if re.search(r"\bmedia hora\b", n):
        intencion["horas"] = 0.5
    elif re.search(r"\btodo el dia\b", n):
        intencion["horas"] = 10.0
    else:
        m = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:horas?|h)\b", n)
        if m and not re.search(r"abiert\w*\s+24", n):
            intencion["horas"] = float(m.group(1).replace(",", "."))

    m = re.search(r"(\d+(?:[.,]\d+)?)\s*(km|kilometros?|m|metros|cuadras?)\b", n)
    if m and not re.search(r"(mil|k)\b", m.group(0)):
        v = float(m.group(1).replace(",", "."))
        u = m.group(2)
        intencion["radio_m"] = v * 1000 if u.startswith("k") else v * 100 if u.startswith("cuadra") else v

    for patron in (r"\b(?:cerca (?:del|de la|de|al|a)|junto (?:al|a la|a)|al lado (?:del|de la|de))",
                   r"\b(?:voy (?:al|a la|a)|ir (?:al|a la|a)|llegar (?:al|a la|a)|hacia(?: el| la)?|en|por)(?!\s+\d)",
                   r"\b(?:al|a la)(?!\s+\d)"):
        m = re.search(patron + r"\s+(?:el |la |los |las )?(.+?)" + _FIN_DESTINO, n)
        if m and m.group(1).strip():
            intencion["destino_texto"] = m.group(1).strip()
            break
    return intencion


def _formato_cop(v: float | None) -> str:
    return "tarifa no disponible" if v is None else "$" + f"{v:,.0f}".replace(",", ".")


def _respuesta_plantilla(r: dict, destino_nombre: str) -> str:
    top = r["resultados"][0]
    p = top["parqueadero"]
    perfil = PERFILES.get(r["perfil"], {}).get("nombre", "tus preferencias guardadas")
    txt = (f"Te recomiendo **{p['nombre']}** ({p['direccion']}) cerca de {destino_nombre}, "
           f"evaluando con el perfil «{perfil}» y {r['horas']:g} h de estadía. {top['justificacion']}")
    alt = r["resultados"][1:3]
    if alt:
        txt += " Otras opciones: " + "; ".join(
            f"{a['parqueadero']['nombre']} ({a['puntaje']:.0f}/100)" for a in alt) + "."
    if top["alertas"]:
        txt += " Ojo: " + "; ".join(top["alertas"]) + "."
    return txt


def _respuesta_llm(consulta: str, destino_nombre: str, r: dict) -> str | None:
    key = current_app.config.get("OPENAI_API_KEY")
    if not key:
        return None
    contexto = [{"nombre": x["parqueadero"]["nombre"], "direccion": x["parqueadero"]["direccion"],
                 "puntaje": x["puntaje"], "costo_total_estimado": x["costo_total_estimado"],
                 "criterios": {k: c["texto"] for k, c in x["criterios"].items()},
                 "alertas": x["alertas"], "justificacion": x["justificacion"]}
                for x in r["resultados"][:5]]
    cuerpo = {
        "model": current_app.config["OPENAI_MODEL"],
        "temperature": 0.3,
        "messages": [
            {"role": "system", "content": (
                "Eres el asistente de SmartPark (Bogotá). Responde en español, breve (máx. 80 palabras). "
                "La lista ya viene ordenada por el puntaje multicriterio de SmartPark: recomienda el PRIMERO, "
                "explica por qué con su justificación y menciona hasta 2 alternativas. "
                "Usa exclusivamente los datos dados. "
                "Nunca inventes parqueaderos, precios ni disponibilidad.")},
            {"role": "user", "content": f"Consulta: {consulta}\nDestino: {destino_nombre}\n"
                                        f"Pesos usados: {json.dumps(r['pesos_pct'])}\n"
                                        f"Parqueaderos (ya ordenados): {json.dumps(contexto, ensure_ascii=False)}"},
        ],
    }
    req = urllib.request.Request("https://api.openai.com/v1/chat/completions",
                                 data=json.dumps(cuerpo).encode(),
                                 headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read())["choices"][0]["message"]["content"].strip()
    except Exception:
        return None  # si el modelo falla, se usa la plantilla


def responder(consulta: str, lat: float | None, lon: float | None, preferencias: dict | None = None) -> dict:
    t0 = time.perf_counter()
    intencion = interpretar(consulta)
    destino_nombre = "tu ubicación"
    origen = None

    if intencion["destino_texto"]:
        geo = geocodificar(intencion["destino_texto"])
        if geo:
            if lat is not None and lon is not None:
                origen = (lat, lon)  # el usuario está en (lat, lon) y va hacia el destino
            lat, lon, destino_nombre = geo["latitud"], geo["longitud"], geo["nombre"]
    if lat is None or lon is None:
        return {"respuesta": "¿Cerca de dónde necesitas parquear? Escribe un lugar (por ejemplo "
                             "\"cerca del Hospital San Ignacio\") o activa tu ubicación.",
                "parqueadero_recomendado": None, "alternativas": [], "intencion": intencion,
                "tiempo_respuesta_ms": int((time.perf_counter() - t0) * 1000)}

    cfg = current_app.config
    radio = intencion["radio_m"] or cfg["RADIO_DEFECTO_M"]
    radio = max(cfg["RADIO_MIN_M"], min(radio, cfg["RADIO_MAX_M"]))
    horas = min(max(intencion["horas"] or 2, 0.25), 72)
    r = recomendar(destino=(lat, lon), origen=origen, horas=horas, radio_m=radio, perfil=intencion["perfil"],
                   preferencias=preferencias, tarifa_max=intencion["tarifa_max"], limite=5)
    destino = {"nombre": destino_nombre, "latitud": lat, "longitud": lon}

    if not r["resultados"]:
        sugerencia = []
        if radio < cfg["RADIO_MAX_M"]:
            sugerencia.append("ampliar el radio de búsqueda")
        if intencion["tarifa_max"]:
            sugerencia.append("subir tu presupuesto")
        texto = (f"No encontré parqueaderos abiertos que cumplan tu criterio a {round(radio)} m de {destino_nombre}. "
                 f"Te sugiero {' o '.join(sugerencia) or 'probar con otro destino'}.")
        return {"respuesta": texto, "parqueadero_recomendado": None, "alternativas": [],
                "intencion": intencion, "destino": destino,
                "tiempo_respuesta_ms": int((time.perf_counter() - t0) * 1000)}

    texto = _respuesta_llm(consulta, destino_nombre, r) or _respuesta_plantilla(r, destino_nombre)
    top = r["resultados"][0]
    return {
        "respuesta": texto,
        "parqueadero_recomendado": top["parqueadero"],
        "puntaje": top["puntaje"],
        "alternativas": [x["parqueadero"] for x in r["resultados"][1:3]],
        "recomendacion": r,
        "intencion": intencion,
        "destino": destino,
        "tiempo_respuesta_ms": int((time.perf_counter() - t0) * 1000),
    }
