"""Pruebas de endurecimiento: límite de intentos, cabeceras, configuración de producción."""
import pytest

from app import create_app
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
    for _ in range(app.config["LOGIN_MAX_INTENTOS"]):
        client.post("/admin/login", data={"email": "admin@test.co", "password": "mala",
                                          "csrf": "x"})
    # el CSRF inválido responde 400 antes de contar; se consulta con token válido
    client.get("/admin/login")
    with client.session_transaction() as s:
        token = s["csrf"]
    for _ in range(app.config["LOGIN_MAX_INTENTOS"]):
        client.post("/admin/login", data={"email": "admin@test.co", "password": "mala", "csrf": token})
    r = client.post("/admin/login", data={"email": "admin@test.co", "password": "admin12345", "csrf": token})
    assert r.status_code == 429


def test_produccion_exige_secret_key(monkeypatch):
    monkeypatch.setenv("FLASK_ENV", "production")
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    import importlib
    import app.config as cfg
    importlib.reload(cfg)
    try:
        with pytest.raises(RuntimeError, match="SECRET_KEY"):
            create_app("production")
    finally:
        monkeypatch.undo()
        importlib.reload(cfg)
