"""Pruebas funcionales de la API, trazadas a las historias de usuario / RF del Documento_PM."""
from tests.conftest import registrar

LAT, LON = 4.6283, -74.0645


# ---- HU 1 / RF-01 ----
def test_registro_exitoso_devuelve_token(client):
    r = registrar(client)
    assert r.status_code == 201
    assert r.get_json()["token"]
    assert r.get_json()["usuario"]["email"] == "ana@test.co"


def test_registro_email_duplicado(client):
    registrar(client)
    r = registrar(client)
    assert r.status_code == 409
    assert r.get_json()["error"]["codigo"] == "email_duplicado"


def test_registro_formulario_incompleto(client):
    r = client.post("/api/auth/registro", json={"email": "x@test.co"})
    assert r.status_code == 400
    assert set(r.get_json()["error"]["detalles"]) == {"password", "nombre"}


# ---- HU 2 ----
def test_login_ok_y_credenciales_incorrectas(client):
    registrar(client)
    assert client.post("/api/auth/login", json={"email": "ana@test.co", "password": "clave1234"}).status_code == 200
    r = client.post("/api/auth/login", json={"email": "ana@test.co", "password": "mala"})
    assert r.status_code == 401


# ---- HU 3 / RF-02 ----
def test_editar_perfil_valido_e_invalido(client, auth):
    r = client.put("/api/me", json={"nombre": "Ana María", "telefono": "3001234567"}, headers=auth)
    assert r.status_code == 200 and r.get_json()["nombre"] == "Ana María"
    r = client.put("/api/me", json={"nombre": "Otro", "telefono": "abc"}, headers=auth)
    assert r.status_code == 400
    assert client.get("/api/me", headers=auth).get_json()["nombre"] == "Ana María"  # no se guardó nada


# ---- HU 13 / RF-08 ----
def test_token_requerido_e_invalido(client):
    assert client.get("/api/me").status_code == 401
    r = client.get("/api/me", headers={"Authorization": "Bearer basura"})
    assert r.status_code == 401 and r.get_json()["error"]["codigo"] == "token_invalido"


def test_token_expirado(client, app):
    import jwt
    from datetime import datetime, timedelta, timezone
    registrar(client)
    tok = jwt.encode({"sub": "2", "exp": datetime.now(timezone.utc) - timedelta(minutes=1)},
                     app.config["JWT_SECRET"], algorithm="HS256")
    r = client.get("/api/me", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 401 and r.get_json()["error"]["codigo"] == "token_expirado"


# ---- HU 6, 7, 12 / RF-04, RF-07 ----
def test_busqueda_por_radio_ordenada_por_distancia(client):
    r = client.get(f"/api/parqueaderos?lat={LAT}&lon={LON}&radio=1000")
    d = r.get_json()
    assert r.status_code == 200
    nombres = [p["nombre"] for p in d["resultados"]]
    assert "Lejano" not in nombres and len(nombres) == 3
    dist = [p["distancia_m"] for p in d["resultados"]]
    assert dist == sorted(dist)


def test_busqueda_sin_resultados_sugiere_ampliar(client):
    r = client.get("/api/parqueaderos?lat=4.55&lon=-74.15&radio=500").get_json()
    assert r["total"] == 0 and r["sugerir_ampliar_radio"] is True


def test_radio_fuera_de_limites(client):
    assert client.get(f"/api/parqueaderos?lat={LAT}&lon={LON}&radio=50").status_code == 400
    assert client.get(f"/api/parqueaderos?lat={LAT}&lon={LON}&radio=99999").status_code == 400


def test_fuera_de_bogota(client):
    r = client.get("/api/parqueaderos?lat=6.2442&lon=-75.5812")  # Medellín
    assert r.status_code == 400 and r.get_json()["error"]["codigo"] == "fuera_de_cobertura"


# ---- HU 8, 9 / RF-05 ----
def test_orden_por_tarifa_sin_tarifa_al_final(client):
    d = client.get(f"/api/parqueaderos?lat={LAT}&lon={LON}&radio=1000&orden=tarifa").get_json()
    assert [p["nombre"] for p in d["resultados"]] == ["Medio barato", "Cercano caro", "Sin tarifa"]
    assert d["resultados"][-1]["tarifa_hora"] is None


def test_filtro_rango_tarifa(client):
    d = client.get(f"/api/parqueaderos?lat={LAT}&lon={LON}&radio=1000&tarifa_max=5000").get_json()
    assert [p["nombre"] for p in d["resultados"]] == ["Medio barato"]
    d = client.get(f"/api/parqueaderos?lat={LAT}&lon={LON}&radio=1000&tarifa_min=20000").get_json()
    assert d["total"] == 0 and "rango de tarifa" in d["mensaje"]


# ---- HU 10, 11 / RF-06 ----
def test_no_puede_calificar_sin_visita(client, auth):
    r = client.post("/api/parqueaderos/1/resenas", json={"calificacion": 5}, headers=auth)
    assert r.status_code == 403 and r.get_json()["error"]["codigo"] == "sin_visita"


def test_resena_actualiza_promedio(client, auth):
    assert client.get("/api/parqueaderos/1/resenas").get_json()["mensaje"] == "Aún sin reseñas"
    client.post("/api/parqueaderos/1/visitas", json={}, headers=auth)
    r = client.post("/api/parqueaderos/1/resenas", json={"calificacion": 4, "comentario": "Bien"}, headers=auth)
    assert r.status_code == 201 and r.get_json()["calificacion_promedio"] == 4

    tok2 = registrar(client, email="beto@test.co").get_json()["token"]
    h2 = {"Authorization": f"Bearer {tok2}"}
    client.post("/api/parqueaderos/1/visitas", json={}, headers=h2)
    r = client.post("/api/parqueaderos/1/resenas", json={"calificacion": 2}, headers=h2)
    assert r.get_json()["calificacion_promedio"] == 3
    lista = client.get("/api/parqueaderos/1/resenas").get_json()
    assert lista["total"] == 2 and lista["resenas"][0]["calificacion"] == 2  # más reciente primero


def test_calificacion_fuera_de_rango(client, auth):
    client.post("/api/parqueaderos/1/visitas", json={}, headers=auth)
    assert client.post("/api/parqueaderos/1/resenas", json={"calificacion": 6}, headers=auth).status_code == 400


# ---- RF-12 chat ----
def test_chat_recomienda_el_mas_barato_cerca_de_destino(client, auth):
    r = client.post("/api/chat", json={"mensaje": "parqueadero barato cerca del hospital San Ignacio"}, headers=auth)
    d = r.get_json()
    assert r.status_code == 200
    assert d["parqueadero_recomendado"]["nombre"] == "Medio barato"
    assert "Medio barato" in d["respuesta"]


def test_chat_sin_opciones_sugiere_ampliar(client, auth):
    d = client.post("/api/chat", json={"mensaje": "cerca del hospital San Ignacio por menos de 1000"},
                    headers=auth).get_json()
    assert d["parqueadero_recomendado"] is None
    assert "ampliar" in d["respuesta"] or "presupuesto" in d["respuesta"]


def test_chat_interpreta_presupuesto():
    from app.services.chat import interpretar
    i = interpretar("algo económico en Chapinero hasta 5 mil")
    assert i["orden"] == "tarifa" and i["tarifa_max"] == 5000 and i["destino_texto"] == "chapinero"


def test_geocodificar_catalogo_local(client):
    r = client.get("/api/geocodificar?q=Centro Andino")
    assert r.status_code == 200 and abs(r.get_json()["latitud"] - 4.6668) < 0.01
    assert client.get("/api/geocodificar?q=lugar inexistente xyz").status_code == 404
