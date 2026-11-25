import json
from io import BytesIO
from urllib.error import HTTPError

from app.services.chat import _interpretar_con_ia, _respuesta_llm


_RANKING = {
    "resultados": [{
        "parqueadero": {
            "nombre": "Parqueadero Centro",
            "direccion": "Calle 1",
            "horario_apertura": None,
            "horario_cierre": None,
            "tarifa_hora": 2500,
        },
        "puntaje": 90,
        "costo_total_estimado": 5000,
        "criterios": {"precio": {"texto": "$2.500 por hora"}},
        "alertas": [],
        "justificacion": "Es la mejor opción por precio.",
    }],
    "pesos_pct": {"precio": 100},
}


class _FakeResponse:
    def __init__(self, data):
        self._data = json.dumps(data).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self):
        return self._data


def _headers(request):
    return {name.lower(): value for name, value in request.header_items()}


def test_chat_redacta_con_gemini_si_no_hay_clave_openai(app, monkeypatch, caplog):
    capturada = {}

    def responder(request, timeout):
        capturada["request"] = request
        capturada["timeout"] = timeout
        return _FakeResponse({
            "candidates": [{
                "content": {
                    "parts": [
                        {"text": "Recomiendo Parqueadero Centro."},
                        {"text": "razonamiento interno", "thought": True},
                    ]
                }
            }]
        })

    monkeypatch.setattr("app.services.chat.urllib.request.urlopen", responder)
    with app.app_context():
        app.config["OPENAI_API_KEY"] = ""
        app.config["GEMINI_API_KEY"] = "gemini-test-key"
        app.config["GEMINI_MODEL"] = "gemini-3.8-flash"
        texto, aviso = _respuesta_llm("busco parqueadero", "Centro", _RANKING)

    request = capturada["request"]
    body = json.loads(request.data)
    assert texto == "Recomiendo Parqueadero Centro."
    assert aviso is None
    assert request.full_url.endswith("/models/gemini-3.8-flash:generateContent")
    assert _headers(request)["x-goog-api-key"] == "gemini-test-key"
    assert "gemini-test-key" not in request.full_url
    assert body["systemInstruction"]["parts"][0]["text"]
    assert "No afirmes que no hay alternativas" in body["systemInstruction"]["parts"][0]["text"]
    assert body["contents"][0]["parts"][0]["text"]
    assert body["generationConfig"] == {"temperature": 0.3, "maxOutputTokens": 256}
    assert "Respuesta generada correctamente por Gemini" in caplog.text


def test_chat_interpreta_parametros_estructurados_con_gemini(app, monkeypatch):
    capturada = {}
    intencion = {
        "buscar_parqueaderos": True,
        "destino_texto": "unicentro",
        "perfil": "precio",
        "orden": "tarifa",
        "horas": 3,
        "tarifa_max": 6000,
        "solo_abiertos": True,
        "radio_m": 1500,
    }

    def responder(request, timeout):
        capturada["request"] = request
        capturada["timeout"] = timeout
        return _FakeResponse({
            "candidates": [{
                "content": {"parts": [{"text": json.dumps(intencion)}]}
            }]
        })

    monkeypatch.setattr("app.services.chat.urllib.request.urlopen", responder)
    with app.app_context():
        app.config["OPENAI_API_KEY"] = ""
        app.config["GEMINI_API_KEY"] = "gemini-test-key"
        app.config["GEMINI_MODEL"] = "gemini-3.8-flash"
        resultado, aviso, proveedor, modelo = _interpretar_con_ia(
            "Busco algo económico por tres horas, abierto ahora, máximo seis mil y a 1.5 km de Unicentro")

    body = json.loads(capturada["request"].data)
    assert resultado == intencion
    assert aviso is None
    assert proveedor == "Gemini"
    assert modelo == "gemini-3.8-flash"
    assert capturada["timeout"] == 5
    assert body["generationConfig"]["responseMimeType"] == "application/json"
    assert "perfil" in body["systemInstruction"]["parts"][0]["text"]


def test_chat_descarta_orden_ia_fuera_del_esquema(app, monkeypatch):
    def responder(request, timeout):
        return _FakeResponse({
            "candidates": [{
                "content": {
                    "parts": [{
                        "text": json.dumps({
                            "buscar_parqueaderos": True,
                            "destino_texto": None,
                            "perfil": None,
                            "orden": "mas_bonito",
                            "horas": None,
                            "tarifa_max": None,
                            "solo_abiertos": False,
                            "radio_m": None,
                        })
                    }]
                }
            }]
        })

    monkeypatch.setattr("app.services.chat.urllib.request.urlopen", responder)
    with app.app_context():
        app.config["OPENAI_API_KEY"] = ""
        app.config["GEMINI_API_KEY"] = "gemini-test-key"
        resultado, aviso, proveedor, modelo = _interpretar_con_ia("busco un parqueadero")

    assert resultado is None
    assert aviso.startswith("Aviso de IA: Gemini")
    assert proveedor == "Gemini"
    assert modelo == app.config["GEMINI_MODEL"]


def test_chat_prioriza_openai_si_estan_ambas_claves(app, monkeypatch):
    capturada = {}

    def responder(request, timeout):
        capturada["request"] = request
        capturada["timeout"] = timeout
        return _FakeResponse({"choices": [{"message": {"content": "Respuesta de OpenAI"}}]})

    monkeypatch.setattr("app.services.chat.urllib.request.urlopen", responder)
    with app.app_context():
        app.config["OPENAI_API_KEY"] = "openai-test-key"
        app.config["GEMINI_API_KEY"] = "gemini-test-key"
        texto, aviso = _respuesta_llm("busco parqueadero", "Centro", _RANKING)

    request = capturada["request"]
    assert texto == "Respuesta de OpenAI"
    assert aviso is None
    assert request.full_url == "https://api.openai.com/v1/chat/completions"
    assert _headers(request)["authorization"] == "Bearer openai-test-key"
    assert capturada["timeout"] == 5
    body = json.loads(request.data)
    assert body["temperature"] == 0.3
    assert body["max_tokens"] == 256


def test_chat_avisa_cuando_gemini_agota_cuota(app, monkeypatch):
    def responder(request, **_):
        body = json.dumps({
            "error": {
                "code": 429,
                "status": "RESOURCE_EXHAUSTED",
                "message": "You exceeded your current quota.",
            }
        }).encode("utf-8")
        raise HTTPError(request.full_url, 429, "Too Many Requests", None, BytesIO(body))

    monkeypatch.setattr("app.services.chat.urllib.request.urlopen", responder)
    with app.app_context():
        app.config["OPENAI_API_KEY"] = ""
        app.config["GEMINI_API_KEY"] = "gemini-test-key"
        texto, aviso = _respuesta_llm("busco parqueadero", "Centro", _RANKING)

    assert texto is None
    assert aviso is not None
    assert "cuota" in aviso.lower()
    assert "gratuito" in aviso.lower()


def test_chat_avisa_cuando_gemini_esta_saturado(app, monkeypatch):
    def responder(request, **_):
        body = json.dumps({
            "error": {"code": 503, "message": "The service is overloaded."}
        }).encode("utf-8")
        raise HTTPError(request.full_url, 503, "Service Unavailable", None, BytesIO(body))

    monkeypatch.setattr("app.services.chat.urllib.request.urlopen", responder)
    with app.app_context():
        app.config["OPENAI_API_KEY"] = ""
        app.config["GEMINI_API_KEY"] = "gemini-test-key"
        texto, aviso = _respuesta_llm("busco parqueadero", "Centro", _RANKING)

    assert texto is None
    assert aviso is not None
    assert "saturado" in aviso.lower()
