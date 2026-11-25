"""Pruebas de endurecimiento: límite de intentos, cabeceras, configuración de producción."""
import pytest

from app import _exigir_secretos
from tests.conftest import registrar


def test_salud_y_cabeceras_de_seguridad(client):
    r = client.get("/api/salud")
    assert r.status_code == 200
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["X-Frame-Options"] == "DENY"


def test_login_api_se_bloquea_tras_demasiados_fallos(app, client):
    registrar(client)
    maximo = app.config["LOGIN_MAX_INTENTOS"]
    for _ in range(maximo):
        r = client.post("/api/auth/login", json={"email": "ana@test.co", "password": "mala"})
        assert r.status_code == 401
    r = client.post("/api/auth/login", json={"email": "ana@test.co", "password": "mala"})
    assert r.status_code == 429
    assert r.get_json()["error"]["codigo"] == "demasiados_intentos"
    # incluso con la clave correcta sigue bloqueado durante la ventana
    r = client.post("/api/auth/login", json={"email": "ana@test.co", "password": "clave1234"})
    assert r.status_code == 429


def test_login_exitoso_reinicia_contador(app, client):
    registrar(client)
    for _ in range(app.config["LOGIN_MAX_INTENTOS"] - 1):
        client.post("/api/auth/login", json={"email": "ana@test.co", "password": "mala"})
    assert client.post("/api/auth/login", json={"email": "ana@test.co", "password": "clave1234"}).status_code == 200
    # el contador volvió a cero: se tolera otra tanda de fallos sin llegar al bloqueo
    for _ in range(app.config["LOGIN_MAX_INTENTOS"] - 1):
        assert client.post("/api/auth/login", json={"email": "ana@test.co", "password": "mala"}).status_code == 401


def test_bloqueo_es_por_correo(app, client):
    registrar(client)
    for _ in range(app.config["LOGIN_MAX_INTENTOS"]):
        client.post("/api/auth/login", json={"email": "ana@test.co", "password": "mala"})
    r = client.post("/api/auth/login", json={"email": "otra@test.co", "password": "x"})
    assert r.status_code == 401  # otro correo no queda bloqueado


def test_login_admin_se_bloquea(app, client):
    client.get("/admin/login")
    with client.session_transaction() as s:
        token = s["csrf"]
    for _ in range(app.config["LOGIN_MAX_INTENTOS"]):
        client.post("/admin/login", data={"email": "admin@test.co", "password": "mala", "csrf": token})
    r = client.post("/admin/login", data={"email": "admin@test.co", "password": "admin12345", "csrf": token})
    assert r.status_code == 429


@pytest.mark.parametrize("secretos", [
    {"SECRET_KEY": "", "JWT_SECRET": "x" * 40},
    {"SECRET_KEY": "x" * 40, "JWT_SECRET": ""},
    {"SECRET_KEY": "dev-secret-cambiar-en-produccion", "JWT_SECRET": "x" * 40},
    {"SECRET_KEY": "x" * 40, "JWT_SECRET": "cambia-esta-clave-jwt"},
])
def test_produccion_rechaza_claves_vacias_o_de_ejemplo(secretos):
    with pytest.raises(RuntimeError, match="Define"):
        _exigir_secretos(secretos)


def test_produccion_acepta_claves_propias():
    _exigir_secretos({"SECRET_KEY": "a" * 40, "JWT_SECRET": "b" * 40})  # no lanza


def test_sesion_del_panel_es_httponly_y_dura_8_horas(app):
    assert app.config["SESSION_COOKIE_HTTPONLY"] is True
    assert app.config["PERMANENT_SESSION_LIFETIME"] == 8 * 3600
