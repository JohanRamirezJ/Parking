"""Pruebas del módulo de IA multicriterio (gasolina, rodamiento, tiempo, distancia, seguridad, precio)."""
import os
import sqlite3
import subprocess
import sys
from datetime import time

import pytest

from app.extensions import db
from app.models import Parqueadero, Resena, Tarifa, Usuario, Visita
from app.services import recomendador as rec
from tests.conftest import registrar

DEST = {"lat": 4.6283, "lon": -74.0645}  # Hospital San Ignacio (ver conftest)


def recomendar(client, headers=None, **body):
    body.setdefault("destino", DEST)
    body.setdefault("hora_llegada", "12:00")
    return client.post("/api/recomendaciones", json=body, headers=headers or {})


def nombres(r):
    return [x["parqueadero"]["nombre"] for x in r.get_json()["resultados"]]


# ---------------------------------------------------------------- fórmula
def test_puntaje_es_suma_ponderada_de_los_aportes(client):
    d = recomendar(client).get_json()
    assert d["total"] == 3  # «Lejano» queda fuera del radio
    for x in d["resultados"]:
        assert abs(sum(c["aporte"] for c in x["criterios"].values()) - x["puntaje"]) < 0.5
        assert set(x["criterios"]) == {"gasolina", "rodamiento", "tiempo", "distancia", "seguridad", "precio"}
        assert all(0 <= c["puntaje"] <= 1 for c in x["criterios"].values())
    puntajes = [x["puntaje"] for x in d["resultados"]]
    assert puntajes == sorted(puntajes, reverse=True)
    assert abs(sum(d["pesos_pct"].values()) - 100) < 0.5


def test_cambiar_pesos_cambia_la_recomendacion(client):
    assert nombres(recomendar(client, perfil="precio"))[0] == "Medio barato"
    assert nombres(recomendar(client, perfil="tiempo"))[0] == "Cercano caro"
    solo_precio = {k: 0 for k in rec.CRITERIOS} | {"precio": 10}
    assert nombres(recomendar(client, pesos=solo_precio))[0] == "Medio barato"
    solo_distancia = {k: 0 for k in rec.CRITERIOS} | {"distancia": 10}
    assert nombres(recomendar(client, pesos=solo_distancia))[0] == "Cercano caro"


def test_seguridad_usa_las_calificaciones_de_los_usuarios(client, app):
    with app.app_context():
        u = Usuario(email="x@test.co", nombre="X")
        u.set_password("clave1234")
        db.session.add(u)
        db.session.flush()
        for pid, seg in ((1, 1), (2, 5)):  # Cercano caro inseguro, Medio barato seguro
            p = db.session.get(Parqueadero, pid)
            db.session.add(Resena(usuario_id=u.id, parqueadero=p, calificacion=3, calificacion_seguridad=seg))
            db.session.flush()
            p.recalcular_promedio()
        db.session.commit()
    solo_seg = {k: 0 for k in rec.CRITERIOS} | {"seguridad": 10}
    d = recomendar(client, pesos=solo_seg).get_json()
    assert d["resultados"][0]["parqueadero"]["nombre"] == "Medio barato"
    assert d["resultados"][0]["criterios"]["seguridad"]["valor"] == 5


def test_tarifa_faltante_se_estima_con_la_mas_alta_y_se_avisa(client):
    d = recomendar(client, horas=2).get_json()
    sin = next(x for x in d["resultados"] if x["parqueadero"]["nombre"] == "Sin tarifa")
    assert sin["criterios"]["precio"]["estimado"] is True
    assert sin["criterios"]["precio"]["valor"] == 18000  # 9000 × 2 h (la más cara de la zona)
    assert any("Tarifa no disponible" in a for a in sin["alertas"])


def test_costo_estadia_con_tope_diario(app):
    p = Parqueadero(nombre="P", direccion="x", latitud=4.6, longitud=-74.06)
    p.tarifas = [Tarifa(tipo="hora", unidad="hora", valor=3000, vigente=True),
                 Tarifa(tipo="dia", unidad="dia", valor=20000, vigente=True)]
    assert rec.costo_estadia(p, 2) == 6000
    assert rec.costo_estadia(p, 10) == 20000      # sale más barato pagar el día
    assert rec.costo_estadia(p, 30) == 40000      # dos días


def test_gasolina_y_rodamiento_dependen_del_vehiculo_y_del_origen(client):
    base = recomendar(client).get_json()["resultados"][0]["criterios"]
    caro = recomendar(client, vehiculo={"precio_galon": 32662}).get_json()["resultados"][0]["criterios"]
    assert abs(caro["gasolina"]["valor"] - 2 * base["gasolina"]["valor"]) < 1
    lejos = recomendar(client, origen={"lat": 4.70, "lon": -74.04}).get_json()
    assert lejos["supuestos"]["trayecto"] == "desde tu origen"
    assert lejos["resultados"][0]["criterios"]["gasolina"]["valor"] > base["gasolina"]["valor"] * 10
    assert lejos["resultados"][0]["criterios"]["rodamiento"]["valor"] > 0


def test_parqueadero_cerrado_a_la_llegada_se_excluye(client, app):
    with app.app_context():
        p = Parqueadero(nombre="Solo mañanas", direccion="x", latitud=4.6285, longitud=-74.0647,
                        horario_apertura=time(6, 0), horario_cierre=time(12, 0))
        p.tarifas.append(Tarifa(tipo="hora", unidad="hora", valor=1000))
        db.session.add(p)
        db.session.commit()
    assert "Solo mañanas" in nombres(recomendar(client, hora_llegada="08:00"))
    assert "Solo mañanas" not in nombres(recomendar(client, hora_llegada="20:00"))
    d = recomendar(client, hora_llegada="20:00", incluir_cerrados=True).get_json()
    x = next(x for x in d["resultados"] if x["parqueadero"]["nombre"] == "Solo mañanas")
    assert any("Cerrado" in a for a in x["alertas"])
    # Llega a las 10:00 por 4 h: cierra antes de terminar la estadía
    d = recomendar(client, hora_llegada="10:00", horas=4).get_json()
    x = next(x for x in d["resultados"] if x["parqueadero"]["nombre"] == "Solo mañanas")
    assert any("Cierra a las 12:00" in a for a in x["alertas"])


def test_justificacion_explica_la_eleccion(client):
    top = recomendar(client, perfil="precio").get_json()["resultados"][0]
    assert top["justificacion"].startswith("Puntaje")
    assert "precio" in top["justificacion"]


@pytest.mark.parametrize("cuerpo,campo", [
    ({"pesos": {k: 0 for k in rec.CRITERIOS}}, "pesos"),
    ({"pesos": {"precio": 11}}, "pesos"),
    ({"pesos": {"comodidad": 5}}, "pesos"),
    ({"perfil": "inventado"}, "perfil"),
    ({"horas": 0}, "horas"),
    ({"radio": 50}, "radio"),
    ({"vehiculo": {"rendimiento_km_galon": 0}}, "rendimiento_km_galon"),
])
def test_validaciones(client, cuerpo, campo):
    r = recomendar(client, **cuerpo)
    assert r.status_code == 400
    assert campo in r.get_json()["error"]["detalles"]


def test_destino_obligatorio_y_dentro_de_bogota(client):
    assert client.post("/api/recomendaciones", json={}).status_code == 400
    r = recomendar(client, destino={"lat": 6.24, "lon": -75.58})
    assert r.status_code == 400 and r.get_json()["error"]["codigo"] == "fuera_de_cobertura"


def test_destino_por_texto(client):
    d = client.post("/api/recomendaciones", json={"destino_texto": "Hospital San Ignacio"}).get_json()
    assert d["destino"]["nombre"] == "Hospital Universitario San Ignacio"
    assert d["total"] >= 1


def test_perfiles_disponibles(client):
    d = client.get("/api/recomendaciones/perfiles").get_json()
    assert [c["clave"] for c in d["criterios"]] == list(rec.CRITERIOS)
    assert {p["clave"] for p in d["perfiles"]} == {"equilibrado", "seguridad", "precio", "tiempo", "vehiculo"}
    assert d["vehiculo_defecto"]["precio_galon"] == 16331


# ---------------------------------------------------------------- personalización
def test_preferencias_guardadas_se_usan_por_defecto(client, auth):
    mis_pesos = {"gasolina": 0, "rodamiento": 0, "tiempo": 0, "distancia": 0, "seguridad": 0, "precio": 10}
    r = client.put("/api/me/preferencias", json={"pesos": mis_pesos, "vehiculo": {"rendimiento_km_galon": 45}},
                   headers=auth)
    assert r.status_code == 200 and r.get_json()["perfil"] == "personalizado"
    g = client.get("/api/me/preferencias", headers=auth).get_json()
    assert g["pesos"]["precio"] == 10 and g["vehiculo"]["rendimiento_km_galon"] == 45

    d = recomendar(client, headers=auth).get_json()
    assert d["perfil"] == "personalizado" and d["pesos"]["precio"] == 10
    assert d["supuestos"]["rendimiento_km_galon"] == 45
    assert d["resultados"][0]["parqueadero"]["nombre"] == "Medio barato"
    # Un perfil explícito en la petición manda sobre lo guardado
    assert recomendar(client, headers=auth, perfil="tiempo").get_json()["perfil"] == "tiempo"


def test_preferencias_invalidas(client, auth):
    assert client.put("/api/me/preferencias", json={"pesos": {"precio": -1}}, headers=auth).status_code == 400
    assert client.put("/api/me/preferencias", json={}).status_code == 401


# ---------------------------------------------------------------- reseñas y chat
def test_resena_con_calificacion_de_seguridad(client, auth):
    client.post("/api/parqueaderos/2/visitas", json={}, headers=auth)
    r = client.post("/api/parqueaderos/2/resenas", json={"calificacion": 4, "calificacion_seguridad": 5}, headers=auth)
    assert r.status_code == 201 and r.get_json()["calificacion_seguridad"] == 5
    assert client.get("/api/parqueaderos/2").get_json()["calificacion_seguridad"] == 5
    r = client.post("/api/parqueaderos/2/resenas", json={"calificacion": 4, "calificacion_seguridad": 9}, headers=auth)
    assert r.status_code == 400


def test_chat_usa_el_modelo_con_perfil_segun_la_consulta(client, auth):
    d = client.post("/api/chat", json={"mensaje": "voy de noche al hospital San Ignacio por 3 horas"},
                    headers=auth).get_json()
    assert d["intencion"]["perfil"] == "seguridad" and d["intencion"]["horas"] == 3
    assert d["recomendacion"]["perfil"] == "seguridad"
    assert d["puntaje"] == d["recomendacion"]["resultados"][0]["puntaje"]
    assert "Puntaje" in d["respuesta"]


def test_migracion_agrega_columnas_a_una_base_existente(tmp_path):
    ruta = tmp_path / "vieja.db"
    con = sqlite3.connect(ruta)
    con.executescript("""
        CREATE TABLE usuario (id INTEGER PRIMARY KEY, email VARCHAR(100), password_hash VARCHAR(255),
            nombre VARCHAR(100), telefono VARCHAR(20), foto_perfil VARCHAR(255), fecha_registro DATETIME,
            ultimo_acceso DATETIME, activo BOOLEAN, es_admin BOOLEAN, advertencias INTEGER);
        CREATE TABLE parqueadero (id INTEGER PRIMARY KEY, nombre VARCHAR(100), direccion VARCHAR(200),
            latitud FLOAT, longitud FLOAT, horario_apertura TIME, horario_cierre TIME, capacidad_total INTEGER,
            capacidad_disponible_estimada INTEGER, calificacion_promedio FLOAT, activo BOOLEAN,
            fecha_registro DATETIME, imagen_url VARCHAR(255));
        CREATE TABLE resena (id INTEGER PRIMARY KEY, usuario_id INTEGER, parqueadero_id INTEGER,
            calificacion INTEGER, comentario TEXT, fecha DATETIME, reportado BOOLEAN, estado VARCHAR(20));
    """)
    con.close()
    raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env = {**os.environ, "DATABASE_URL": f"sqlite:///{ruta}"}
    subprocess.run([sys.executable, "-c", "from app import create_app; create_app()"], cwd=raiz, env=env, check=True)
    con = sqlite3.connect(ruta)
    cols = lambda t: {r[1] for r in con.execute(f"PRAGMA table_info({t})")}
    assert "preferencias" in cols("usuario")
    assert "calificacion_seguridad" in cols("parqueadero")
    assert "calificacion_seguridad" in cols("resena")
