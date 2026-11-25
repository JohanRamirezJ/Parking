"""Pruebas unitarias de app/services/geo.py y de la geocodificación local."""
import pytest

from app.services.geo import caja_envolvente, en_bogota, haversine_m
from app.services.geocoding import buscar_local, geocodificar, normalizar


# ---------------------------------------------------------------- distancia
def test_distancia_a_si_mismo_es_cero():
    assert haversine_m(4.6283, -74.0645, 4.6283, -74.0645) == 0


def test_un_grado_de_latitud_son_unos_111_km():
    assert haversine_m(4.0, -74.0, 5.0, -74.0) == pytest.approx(111_195, rel=0.001)


def test_distancia_es_simetrica():
    a, b = (4.6283, -74.0645), (4.7020, -74.0415)
    assert haversine_m(*a, *b) == pytest.approx(haversine_m(*b, *a))


def test_distancia_conocida_entre_dos_puntos_de_bogota():
    # Hospital San Ignacio ↔ Centro Andino: unos 4.4 km en línea recta
    assert haversine_m(4.6283, -74.0645, 4.6668, -74.0526) == pytest.approx(4_450, abs=150)


# ---------------------------------------------------------------- caja envolvente
def test_la_caja_contiene_el_punto_y_crece_con_el_radio():
    lat_min, lat_max, lon_min, lon_max = caja_envolvente(4.65, -74.06, 1000)
    assert lat_min < 4.65 < lat_max and lon_min < -74.06 < lon_max
    pequena = caja_envolvente(4.65, -74.06, 200)
    assert (pequena[1] - pequena[0]) < (lat_max - lat_min)


def test_la_caja_cubre_un_punto_a_la_distancia_del_radio():
    # un punto a ~900 m al norte debe caer dentro de la caja de 1000 m
    lat_min, lat_max, _, _ = caja_envolvente(4.65, -74.06, 1000)
    assert lat_min <= 4.65 + 0.0081 <= lat_max


# ---------------------------------------------------------------- límites de Bogotá
@pytest.mark.parametrize("lat,lon", [(4.6283, -74.0645), (4.45, -74.25), (4.84, -73.99)])
def test_dentro_de_bogota(app, lat, lon):
    assert en_bogota(lat, lon)


@pytest.mark.parametrize("lat,lon", [(6.2442, -75.5812), (4.449, -74.06), (4.65, -73.98), (4.65, -74.26)])
def test_fuera_de_bogota(app, lat, lon):
    assert not en_bogota(lat, lon)


# ---------------------------------------------------------------- normalización y catálogo
def test_normalizar_quita_tildes_mayusculas_y_espacios():
    assert normalizar("  Fundación SANTA Fe ") == "fundacion santa fe"


def test_buscar_local_encuentra_dentro_de_una_frase():
    r = buscar_local("quiero ir al Hospital San Ignacio")
    assert r["nombre"] == "Hospital Universitario San Ignacio" and r["fuente"] == "catalogo_local"


def test_buscar_local_prefiere_la_coincidencia_mas_larga():
    assert buscar_local("centro andino")["nombre"] == "Centro Comercial Andino"
    assert buscar_local("zona t")["nombre"] == "Zona T"


def test_buscar_local_sin_coincidencia():
    assert buscar_local("lugar que no existe") is None


@pytest.mark.parametrize("vacio", ["", "   ", None])
def test_geocodificar_vacio_devuelve_none(app, vacio):
    assert geocodificar(vacio) is None


def test_geocodificar_usa_el_catalogo_sin_salir_a_internet(app):
    assert geocodificar("Unicentro")["latitud"] == pytest.approx(4.7020)


def test_geocodificar_en_pruebas_no_consulta_servicios_externos(app):
    assert geocodificar("una direccion cualquiera 123") is None  # TESTING desactiva la red
