import json
from io import BytesIO
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs

import pytest

from app.services.openstreetmap import ErrorConsultaOSM, buscar_cercanos_osm


def test_busqueda_osm_filtra_privados_y_conserva_tarifa_desconocida(app):
    elementos = [
        {"type": "node", "id": 101, "lat": 4.629, "lon": -74.064,
         "tags": {"amenity": "parking", "name": "Público", "fee": "yes"}},
        {"type": "way", "id": 102, "center": {"lat": 4.6291, "lon": -74.0641},
         "tags": {"amenity": "parking", "access": "customers"}},
        {"type": "node", "id": 103, "lat": 4.6292, "lon": -74.0642,
         "tags": {"amenity": "parking", "fee": "no", "opening_hours": "24/7"}},
        {"type": "node", "id": 104, "lat": 4.8, "lon": -74.064,
         "tags": {"amenity": "parking"}},
    ]
    response = BytesIO(json.dumps({"elements": elementos}).encode())

    with app.app_context(), patch("app.services.openstreetmap.urllib.request.urlopen", return_value=response) as urlopen:
        candidatos = buscar_cercanos_osm(4.6283, -74.0645, 500)

    assert len(candidatos) == 2
    assert candidatos[0].parqueadero.nombre == "Público"
    assert candidatos[0].parqueadero.tarifa_hora is None
    assert candidatos[1].parqueadero.tarifa_hora == 0
    assert candidatos[1].parqueadero.abierto_ahora()
    assert all(c.parqueadero.id < 0 for c in candidatos)
    query = parse_qs(urlopen.call_args.args[0].data.decode())["data"][0]
    assert "around:500" in query


def test_error_de_overpass_se_informa_sin_fingir_resultados(app):
    with app.app_context(), patch(
        "app.services.openstreetmap.urllib.request.urlopen", side_effect=URLError("offline")
    ):
        with pytest.raises(ErrorConsultaOSM, match="no se pudo conectar con Overpass"):
            buscar_cercanos_osm(4.6283, -74.0645, 500)


@pytest.mark.parametrize(
    ("codigo", "texto_esperado"),
    [(429, "limitó las consultas"), (502, "está saturado"), (503, "está saturado"), (406, "rechazó la solicitud")],
)
def test_http_error_de_overpass_genera_alerta_especifica(app, codigo, texto_esperado):
    with app.app_context(), patch(
        "app.services.openstreetmap.urllib.request.urlopen",
        side_effect=HTTPError("https://overpass.test/api", codigo, "error", None, BytesIO(b"{}")),
    ):
        with pytest.raises(ErrorConsultaOSM) as error:
            buscar_cercanos_osm(4.6283, -74.0645, 500)

    assert texto_esperado in str(error.value)
