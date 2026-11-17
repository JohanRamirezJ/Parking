"""Asistente SmartPark: busca candidatos efímeros en OSM y los puntúa localmente."""
import json
import re
import time
import urllib.request

from flask import current_app

from .geocoding import geocodificar, normalizar
from .geo import en_bogota
from .openstreetmap import ErrorConsultaOSM, buscar_cercanos_osm
from .recomendador import ErrorRecomendacion, PERFILES, recomendar


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
    if intencion["destino_texto"] in {"mi", "mi ubicacion", "aqui", "aca", "donde estoy"}:
        intencion["destino_texto"] = None
    intencion["buscar_parqueaderos"] = bool(
        intencion["destino_texto"] or intencion["perfil"] or intencion["tarifa_max"] is not None
        or intencion["solo_abiertos"] or intencion["radio_m"]
        or re.search(r"\b(parqueader\w*|parquear|estacionar|estacionamiento|parking)\b", n)
    )
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


def _aviso_error_http_modelo(proveedor: str, codigo: int, contenido: bytes) -> str:
    try:
        error = json.loads(contenido).get("error", {})
    except (ValueError, TypeError, AttributeError):
        error = {}
    if not isinstance(error, dict):
        error = {}
    codigos = " ".join(str(error.get(k, "")) for k in ("code", "status", "type")).lower()
    mensaje = str(error.get("message", "")).lower()
    detalle = f"{codigos} {mensaje}"

    if codigo == 429:
        if any(s in detalle for s in ("quota", "resource_exhausted", "billing", "credit")):
            return (f"Aviso de IA: {proveedor} indicó que se alcanzó la cuota o el saldo disponible "
                    "(podría ser el límite gratuito). Se muestra una respuesta de respaldo; revisa el "
                    "uso y las cuotas de tu cuenta.")
        return (f"Aviso de IA: {proveedor} alcanzó un límite temporal de solicitudes. "
                "Se muestra una respuesta de respaldo; inténtalo más tarde.")
    if codigo == 503 or any(s in detalle for s in ("overloaded", "overload", "capacity")):
        return (f"Aviso de IA: {proveedor} está saturado o temporalmente no disponible. "
                "Se muestra una respuesta de respaldo; inténtalo más tarde.")
    if codigo in {401, 403}:
        return (f"Aviso de IA: {proveedor} rechazó la clave o no tiene acceso al modelo. "
                "Se muestra una respuesta de respaldo; revisa la configuración de la clave.")
    if codigo >= 500:
        return (f"Aviso de IA: {proveedor} tuvo un error temporal (HTTP {codigo}). "
                "Se muestra una respuesta de respaldo.")
    return (f"Aviso de IA: {proveedor} rechazó la solicitud (HTTP {codigo}). "
            "Se muestra una respuesta de respaldo.")


def _respuesta_llm(consulta: str, destino_nombre: str, r: dict) -> tuple[str | None, str | None]:
    openai_key = current_app.config.get("OPENAI_API_KEY")
    gemini_key = current_app.config.get("GEMINI_API_KEY")
    if openai_key:
        proveedor = "OpenAI"
        modelo = current_app.config["OPENAI_MODEL"]
        url = "https://api.openai.com/v1/chat/completions"
        headers = {"Authorization": f"Bearer {openai_key}"}
    elif gemini_key:
        proveedor = "Gemini"
        modelo = current_app.config["GEMINI_MODEL"]
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent"
        headers = {"x-goog-api-key": gemini_key}
    else:
        current_app.logger.info("No hay clave de IA configurada; se usará la respuesta predeterminada.")
        return None, None

    contexto = [{"nombre": x["parqueadero"]["nombre"], "direccion": x["parqueadero"]["direccion"],
                 "horario_apertura": x["parqueadero"]["horario_apertura"],
                 "horario_cierre": x["parqueadero"]["horario_cierre"],
                 "tarifa_hora": x["parqueadero"]["tarifa_hora"],
                 "puntaje": x["puntaje"], "costo_total_estimado": x["costo_total_estimado"],
                 "criterios": {k: c["texto"] for k, c in x["criterios"].items()},
                 "alertas": x["alertas"], "justificacion": x["justificacion"]}
                for x in r["resultados"][:5]]
    instruccion = (
        "Eres el asistente de SmartPark (Bogotá). Responde en español, breve (máx. 80 palabras). "
        "La lista ya viene ordenada por el puntaje multicriterio de SmartPark: recomienda el PRIMERO, "
        "explica por qué con su justificación y menciona hasta 2 alternativas si hay más opciones en la lista. "
        "No afirmes que no hay alternativas cuando la lista incluya otros parqueaderos. "
        "Usa exclusivamente los datos dados. "
        "Nunca inventes parqueaderos, precios, horarios ni disponibilidad. Si falta un dato, dilo explícitamente."
    )
    mensaje = (f"Consulta: {consulta}\nDestino: {destino_nombre}\n"
               f"Pesos usados: {json.dumps(r['pesos_pct'])}\n"
               f"Parqueaderos (ya ordenados): {json.dumps(contexto, ensure_ascii=False)}")
    if proveedor == "OpenAI":
        cuerpo = {
            "model": modelo,
            "temperature": 0.3,
            "max_tokens": 256,
            "messages": [
                {"role": "system", "content": instruccion},
                {"role": "user", "content": mensaje},
            ],
        }
    else:
        cuerpo = {
            "systemInstruction": {"parts": [{"text": instruccion}]},
            "contents": [{"role": "user", "parts": [{"text": mensaje}]}],
            "generationConfig": {"temperature": 0.3, "maxOutputTokens": 256},
        }
    headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=json.dumps(cuerpo).encode("utf-8"), headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            respuesta = json.loads(r.read())
        if proveedor == "OpenAI":
            texto = respuesta["choices"][0]["message"]["content"].strip()
        else:
            partes = respuesta["candidates"][0]["content"]["parts"]
            texto = "".join(
                parte["text"] for parte in partes
                if isinstance(parte, dict) and isinstance(parte.get("text"), str) and not parte.get("thought")
            ).strip()
        if not texto:
            raise ValueError(f"{proveedor} devolvió una respuesta sin texto")
        current_app.logger.info("Respuesta generada correctamente por %s (modelo %s).", proveedor, modelo)
        return texto, None
    except urllib.error.HTTPError as exc:
        aviso = _aviso_error_http_modelo(proveedor, exc.code, exc.read())
        current_app.logger.warning("La API de %s respondió HTTP %s", proveedor, exc.code)
        return None, aviso
    except (urllib.error.URLError, TimeoutError) as exc:
        current_app.logger.warning("No se pudo conectar con %s: %s", proveedor, exc)
        return None, (f"Aviso de IA: no se pudo conectar con {proveedor}. "
                      "Se muestra una respuesta de respaldo; revisa la conexión e inténtalo más tarde.")
    except (ValueError, KeyError, IndexError, TypeError, AttributeError) as exc:
        current_app.logger.warning("No se pudo redactar la respuesta con %s: %s", proveedor, exc)
        return None, (f"Aviso de IA: {proveedor} devolvió una respuesta inesperada. "
                      "Se muestra una respuesta de respaldo.")


def responder(consulta: str, lat: float | None, lon: float | None, preferencias: dict | None = None) -> dict:
    t0 = time.perf_counter()
    intencion = interpretar(consulta)
    if not intencion["buscar_parqueaderos"]:
        return {"respuesta": "Puedo buscar parqueaderos cercanos. Dime un lugar o activa tu ubicación y cuéntame qué prefieres.",
                "parqueadero_recomendado": None, "alternativas": [], "intencion": intencion,
                "tiempo_respuesta_ms": int((time.perf_counter() - t0) * 1000)}
    destino_nombre = "tu ubicación"
    origen = None

    if intencion["destino_texto"]:
        geo = geocodificar(intencion["destino_texto"])
        if not geo:
            return {"respuesta": f"No pude ubicar «{intencion['destino_texto']}» en Bogotá. Prueba con otro nombre o dirección.",
                    "parqueadero_recomendado": None, "alternativas": [], "intencion": intencion,
                    "tiempo_respuesta_ms": int((time.perf_counter() - t0) * 1000)}
        if lat is not None and lon is not None:
            origen = (lat, lon)  # el usuario está en (lat, lon) y va hacia el destino
        lat, lon, destino_nombre = geo["latitud"], geo["longitud"], geo["nombre"]
    if lat is None or lon is None:
        return {"respuesta": "¿Cerca de dónde necesitas parquear? Escribe un lugar (por ejemplo "
                             "\"cerca del Hospital San Ignacio\") o activa tu ubicación.",
                "parqueadero_recomendado": None, "alternativas": [], "intencion": intencion,
                "tiempo_respuesta_ms": int((time.perf_counter() - t0) * 1000)}
    if not en_bogota(lat, lon):
        return {"respuesta": "SmartPark por ahora solo busca parqueaderos en Bogotá.",
                "parqueadero_recomendado": None, "alternativas": [], "intencion": intencion,
                "tiempo_respuesta_ms": int((time.perf_counter() - t0) * 1000)}

    cfg = current_app.config
    radio = intencion["radio_m"] or cfg["RADIO_DEFECTO_M"]
    radio = max(cfg["RADIO_MIN_M"], min(radio, cfg["RADIO_MAX_M"]))
    horas = min(max(intencion["horas"] or 2, 0.25), 72)
    destino = {"nombre": destino_nombre, "latitud": lat, "longitud": lon}

    def puntuar(candidatos, precio_desconocido_neutro):
        return recomendar(
            destino=(lat, lon), origen=origen, horas=horas, radio_m=radio, perfil=intencion["perfil"],
            preferencias=preferencias, tarifa_max=intencion["tarifa_max"], limite=5,
            candidatos=candidatos, precio_desconocido_neutro=precio_desconocido_neutro,
            solo_abiertos=intencion["solo_abiertos"],
        )

    aviso_osm = None
    try:
        candidatos_osm = buscar_cercanos_osm(lat, lon, radio)
    except ErrorConsultaOSM as exc:
        candidatos_osm = []
        aviso_osm = str(exc)

    total_osm = len(candidatos_osm)
    if intencion["solo_abiertos"]:
        candidatos_osm = [c for c in candidatos_osm if c.parqueadero.abierto_ahora() is True]

    fuente_datos = "openstreetmap"
    aviso_respaldo = None
    try:
        if candidatos_osm:
            r = puntuar([(c.parqueadero, c.distancia_m) for c in candidatos_osm], True)
            if not r["resultados"]:
                aviso_osm = ("Alerta de búsqueda: los resultados de Overpass no cumplieron los filtros; "
                             "se consultará el directorio local.")
                fuente_datos = "directorio_local"
                r = puntuar(None, False)
        else:
            if not aviso_osm:
                aviso_osm = ("Alerta de búsqueda: Overpass no encontró opciones que cumplan los filtros; "
                             "se consultará el directorio local.")
            fuente_datos = "directorio_local"
            r = puntuar(None, False)
    except ErrorRecomendacion as exc:
        return {"respuesta": str(exc), "parqueadero_recomendado": None, "alternativas": [],
                "aviso_osm": aviso_osm, "intencion": intencion, "destino": destino,
                "fuente_datos": fuente_datos,
                "tiempo_respuesta_ms": int((time.perf_counter() - t0) * 1000)}

    if not r["resultados"]:
        if intencion["solo_abiertos"]:
            texto = ("No encontré parqueaderos guardados con horario abierto verificado"
                     if fuente_datos == "directorio_local"
                     else "No encontré parqueaderos con horario abierto verificado en OpenStreetMap")
        elif intencion["tarifa_max"] is not None:
            texto = (f"No encontré parqueaderos guardados con tarifa de hasta "
                     f"{_formato_cop(intencion['tarifa_max'])}"
                     if fuente_datos == "directorio_local"
                     else f"No encontré parqueaderos mapeados con tarifa de hasta "
                          f"{_formato_cop(intencion['tarifa_max'])}")
        else:
            texto = ("No encontré parqueaderos guardados que cumplan tus condiciones"
                     if fuente_datos == "directorio_local"
                     else "No encontré parqueaderos mapeados")
        texto += f" a {round(radio)} m de {destino_nombre}."
        if radio < cfg["RADIO_MAX_M"]:
            texto += " Puedes ampliar el radio de búsqueda."
        if aviso_osm:
            texto = f"{aviso_osm} {texto}"
        return {"respuesta": texto, "aviso_osm": aviso_osm,
                "parqueadero_recomendado": None, "alternativas": [],
                "intencion": intencion, "destino": destino, "fuente_datos": fuente_datos,
                "total_osm": total_osm,
                "tiempo_respuesta_ms": int((time.perf_counter() - t0) * 1000)}

    texto_llm, aviso_ia = _respuesta_llm(consulta, destino_nombre, r)
    if fuente_datos == "openstreetmap":
        urls_osm = {c.parqueadero.id: c.url for c in candidatos_osm}
        if aviso_ia:
            respaldo = puntuar(None, False)
            if respaldo["resultados"]:
                r = respaldo
                fuente_datos = "directorio_local"
                aviso_respaldo = "Como respaldo, se usaron parqueaderos guardados en SmartPark."
                texto_llm = None
        if fuente_datos == "openstreetmap":
            for opcion in r["resultados"]:
                parqueadero = opcion["parqueadero"]
                parqueadero["fuente"] = "openstreetmap"
                parqueadero["osm_url"] = urls_osm[parqueadero["id"]]
    else:
        aviso_respaldo = "Como respaldo, se usaron parqueaderos guardados en SmartPark."

    for opcion in r["resultados"]:
        opcion["parqueadero"]["fuente"] = fuente_datos

    texto = texto_llm or _respuesta_plantilla(r, destino_nombre)
    top = r["resultados"][0]
    if intencion["tarifa_max"] and top["criterios"]["precio"]["valor"] is None:
        texto += " No se puede verificar si cumple tu presupuesto: no se reporta la tarifa."
    if fuente_datos == "openstreetmap":
        texto += " Datos © OpenStreetMap contributors."
    for aviso in (aviso_osm, aviso_ia, aviso_respaldo):
        if aviso:
            texto += " " + aviso
    return {
        "respuesta": texto,
        "aviso_osm": aviso_osm,
        "aviso_ia": aviso_ia,
        "aviso_respaldo": aviso_respaldo,
        "parqueadero_recomendado": top["parqueadero"],
        "puntaje": top["puntaje"],
        "alternativas": [x["parqueadero"] for x in r["resultados"][1:3]],
        "recomendacion": r,
        "intencion": intencion,
        "destino": destino,
        "fuente_datos": fuente_datos,
        "total_osm": total_osm,
        "tiempo_respuesta_ms": int((time.perf_counter() - t0) * 1000),
    }
