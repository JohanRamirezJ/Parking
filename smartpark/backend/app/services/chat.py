"""Asistente conversacional (HU chat IA, RF-12).

Diseño: la recomendación SIEMPRE sale del directorio (nunca se inventan parqueaderos).
1. Se interpreta la consulta (presupuesto, preferencia, destino, abierto ahora).
2. Se buscan candidatos reales con buscar_cercanos().
3. Si hay OPENAI_API_KEY, el modelo redacta la respuesta usando SOLO esos candidatos;
   si no, se responde con una plantilla. En ambos casos el parqueadero recomendado
   es el primero del ranking calculado aquí.
"""
import json
import re
import time
import urllib.request

from flask import current_app

from .directorio import buscar_cercanos
from .geocoding import geocodificar, normalizar


def interpretar(consulta: str) -> dict:
    n = re.sub(r"\bpor favor\b", " ", normalizar(consulta))
    intencion = {"orden": "distancia", "tarifa_max": None, "solo_abiertos": False,
                 "radio_m": None, "destino_texto": None}

    if re.search(r"\b(barat\w*|economic\w*|precio bajo|menor precio|mas bajo)\b", n):
        intencion["orden"] = "tarifa"
    elif re.search(r"\b(mejor calificad\w*|recomendad\w*|seguro|buenas? resenas?|mejor)\b", n):
        intencion["orden"] = "calificacion"

    m = re.search(r"(?:menos de|maximo|max\.?|hasta|no mas de|por debajo de)\s*\$?\s*([\d.,]+)\s*(mil|k)?", n)
    if m:
        valor = float(m.group(1).replace(".", "").replace(",", ""))
        if m.group(2) or valor < 100:
            valor *= 1000
        intencion["tarifa_max"] = valor

    if re.search(r"\b(abierto|24 ?horas|ahora mismo|de noche)\b", n):
        intencion["solo_abiertos"] = True

    m = re.search(r"(\d+(?:[.,]\d+)?)\s*(km|kilometros?|m|metros|cuadras?)\b", n)
    if m and not re.search(r"(mil|k)\b", m.group(0)):
        v = float(m.group(1).replace(",", "."))
        u = m.group(2)
        intencion["radio_m"] = v * 1000 if u.startswith("k") else v * 100 if u.startswith("cuadra") else v

    m = re.search(r"\b(?:cerca (?:del|de la|de|al|a)|junto (?:al|a la|a)|al lado (?:del|de la|de)|en|por)"
                  r"\s+(?:el |la |los |las )?(.+?)"
                  r"(?:\s+(?:que|con|por menos|por debajo|menos de|hasta|maximo|y)\b|\s+a\s+\d|[?.!,]|$)", n)
    if m:
        intencion["destino_texto"] = m.group(1).strip()
    return intencion


def _formato_cop(v: float | None) -> str:
    return "tarifa no disponible" if v is None else "$" + f"{v:,.0f}".replace(",", ".")


def _respuesta_plantilla(intencion: dict, destino_nombre: str, cands: list) -> str:
    p, dist = cands[0]
    motivo = {"tarifa": "es la opción más económica",
              "calificacion": "es la mejor calificada",
              "distancia": "es la más cercana"}[intencion["orden"]]
    cal = f"{p.calificacion_promedio:.1f}★" if p.calificacion_promedio else "sin calificaciones aún"
    txt = (f"Te recomiendo **{p.nombre}** ({p.direccion}): {motivo} cerca de {destino_nombre}, "
           f"a {round(dist)} m. Tarifa por hora: {_formato_cop(p.tarifa_hora)}; "
           f"por día: {_formato_cop(p.tarifa_dia)}. Calificación: {cal}.")
    if len(cands) > 1:
        otros = "; ".join(f"{q.nombre} ({_formato_cop(q.tarifa_hora)}/h, {round(d)} m)" for q, d in cands[1:3])
        txt += f" Otras opciones: {otros}."
    return txt


def _respuesta_llm(consulta: str, destino_nombre: str, cands: list) -> str | None:
    key = current_app.config.get("OPENAI_API_KEY")
    if not key:
        return None
    contexto = [{"id": p.id, "nombre": p.nombre, "direccion": p.direccion, "distancia_m": round(d),
                 "tarifa_hora": p.tarifa_hora, "tarifa_dia": p.tarifa_dia,
                 "calificacion": p.calificacion_promedio, "abierto_ahora": p.abierto_ahora()}
                for p, d in cands[:5]]
    cuerpo = {
        "model": current_app.config["OPENAI_MODEL"],
        "temperature": 0.3,
        "messages": [
            {"role": "system", "content": (
                "Eres el asistente de SmartPark (Bogotá). Responde en español, breve (máx. 80 palabras). "
                "Recomienda el PRIMER parqueadero de la lista y menciona hasta 2 alternativas. "
                "Usa exclusivamente los datos dados; si una tarifa es null di 'tarifa no disponible'. "
                "Nunca inventes parqueaderos, precios ni disponibilidad.")},
            {"role": "user", "content": f"Consulta: {consulta}\nDestino: {destino_nombre}\n"
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


def responder(consulta: str, lat: float | None, lon: float | None) -> dict:
    t0 = time.perf_counter()
    intencion = interpretar(consulta)
    destino_nombre = "tu ubicación"

    if intencion["destino_texto"]:
        geo = geocodificar(intencion["destino_texto"])
        if geo:
            lat, lon, destino_nombre = geo["latitud"], geo["longitud"], geo["nombre"]
    if lat is None or lon is None:
        return {"respuesta": "¿Cerca de dónde necesitas parquear? Escribe un lugar (por ejemplo "
                             "\"cerca del Hospital San Ignacio\") o activa tu ubicación.",
                "parqueadero_recomendado": None, "alternativas": [], "intencion": intencion,
                "tiempo_respuesta_ms": int((time.perf_counter() - t0) * 1000)}

    radio = intencion["radio_m"] or current_app.config["RADIO_DEFECTO_M"]
    radio = max(current_app.config["RADIO_MIN_M"], min(radio, current_app.config["RADIO_MAX_M"]))
    cands = buscar_cercanos(lat, lon, radio, orden=intencion["orden"],
                            tarifa_max=intencion["tarifa_max"], solo_abiertos=intencion["solo_abiertos"])

    if not cands:
        sugerencia = []
        if radio < current_app.config["RADIO_MAX_M"]:
            sugerencia.append("ampliar el radio de búsqueda")
        if intencion["tarifa_max"]:
            sugerencia.append("subir tu presupuesto")
        texto = (f"No encontré parqueaderos que cumplan tu criterio a {round(radio)} m de {destino_nombre}. "
                 f"Te sugiero {' o '.join(sugerencia) or 'probar con otro destino'}.")
        return {"respuesta": texto, "parqueadero_recomendado": None, "alternativas": [],
                "intencion": intencion, "destino": {"nombre": destino_nombre, "latitud": lat, "longitud": lon},
                "tiempo_respuesta_ms": int((time.perf_counter() - t0) * 1000)}

    texto = _respuesta_llm(consulta, destino_nombre, cands) or _respuesta_plantilla(intencion, destino_nombre, cands)
    p, d = cands[0]
    return {
        "respuesta": texto,
        "parqueadero_recomendado": p.to_dict(d),
        "alternativas": [q.to_dict(dd) for q, dd in cands[1:3]],
        "intencion": intencion,
        "destino": {"nombre": destino_nombre, "latitud": lat, "longitud": lon},
        "tiempo_respuesta_ms": int((time.perf_counter() - t0) * 1000),
    }
