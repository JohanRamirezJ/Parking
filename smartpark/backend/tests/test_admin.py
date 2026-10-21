"""Pruebas del panel web de administración (HU 14, RF-09, RF-10, RF-11, RF-13)."""
import re

from app.extensions import db
from app.models import LogAuditoria, Notificacion, Parqueadero, ReporteUsuario, Usuario
from tests.conftest import registrar


def _csrf(client, url):
    html = client.get(url).get_data(as_text=True)
    return re.search(r'name="csrf" value="([0-9a-f]+)"', html).group(1)


def _login(client):
    tok = _csrf(client, "/admin/login")
    r = client.post("/admin/login", data={"email": "admin@test.co", "password": "admin12345", "csrf": tok})
    assert r.status_code == 302
    return _csrf(client, "/admin/")


def _form(**extra):
    base = {"nombre": "Nuevo P", "direccion": "Cra 7 # 40-62", "latitud": "4.63", "longitud": "-74.065",
            "tarifa_hora": "4000", "tarifa_dia": "", "horario_apertura": "06:00", "horario_cierre": "22:00",
            "capacidad_total": "30", "capacidad_disponible_estimada": "5", "activo": "on"}
    base.update(extra)
    return base


def test_requiere_login(client):
    assert client.get("/admin/").status_code == 302
    assert client.get("/admin/parqueaderos").status_code == 302


def test_usuario_normal_no_entra_al_panel(client):
    registrar(client)
    tok = _csrf(client, "/admin/login")
    r = client.post("/admin/login", data={"email": "ana@test.co", "password": "clave1234", "csrf": tok})
    assert r.status_code == 200 and "sin permisos" in r.get_data(as_text=True)


def test_dashboard_carga(client):
    _login(client)
    html = client.get("/admin/").get_data(as_text=True)
    assert "Parqueaderos activos" in html


def test_crear_parqueadero_se_refleja_en_api_y_audita(client, app):
    csrf = _login(client)
    r = client.post("/admin/parqueaderos/nuevo", data=_form(csrf=csrf))
    assert r.status_code == 302
    d = client.get("/api/parqueaderos?lat=4.63&lon=-74.065&radio=500").get_json()
    assert "Nuevo P" in [p["nombre"] for p in d["resultados"]]  # RF-09: reflejo inmediato
    with app.app_context():
        assert db.session.query(LogAuditoria).filter_by(accion="CREATE").count() == 1


def test_no_guarda_sin_campos_obligatorios(client, app):
    csrf = _login(client)
    r = client.post("/admin/parqueaderos/nuevo", data=_form(csrf=csrf, nombre="", tarifa_hora=""))
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "El nombre es obligatorio" in html and "al menos una tarifa" in html
    with app.app_context():
        assert db.session.query(Parqueadero).count() == 4


def test_no_publica_coordenadas_fuera_de_bogota(client, app):
    csrf = _login(client)
    r = client.post("/admin/parqueaderos/nuevo", data=_form(csrf=csrf, latitud="6.24", longitud="-75.58"))
    assert "fuera de Bogotá" in r.get_data(as_text=True)
    with app.app_context():
        assert db.session.query(Parqueadero).count() == 4


def test_editar_tarifa_conserva_historial(client, app):
    csrf = _login(client)
    client.post("/admin/parqueaderos/1/editar", data=_form(csrf=csrf, tarifa_hora="9500"))
    with app.app_context():
        p = db.session.get(Parqueadero, 1)
        assert p.tarifa_hora == 9500
        assert len(p.tarifas) == 2 and sum(t.vigente for t in p.tarifas) == 1


def test_desactivar_oculta_de_la_app(client):
    csrf = _login(client)
    client.post("/admin/parqueaderos/1/estado", data={"csrf": csrf})
    assert client.get("/api/parqueaderos/1").status_code == 404


def test_post_sin_csrf_rechazado(client):
    _login(client)
    assert client.post("/admin/parqueaderos/1/estado", data={}).status_code == 400


def test_suspender_usuario_reportado_notifica(client, app, auth):
    # ana reseña; beto reporta
    client.post("/api/parqueaderos/1/visitas", json={}, headers=auth)
    rid = client.post("/api/parqueaderos/1/resenas", json={"calificacion": 1, "comentario": "ofensivo"},
                      headers=auth).get_json()["resena"]["id"]
    tok2 = registrar(client, email="beto@test.co").get_json()["token"]
    assert client.post(f"/api/resenas/{rid}/reportar", json={"motivo": "Lenguaje ofensivo"},
                       headers={"Authorization": f"Bearer {tok2}"}).status_code == 201

    csrf = _login(client)
    client.post("/admin/reportes/1/accion", data={"csrf": csrf, "accion": "suspender"})
    with app.app_context():
        ana = db.session.query(Usuario).filter_by(email="ana@test.co").one()
        assert ana.activo is False
        assert db.session.query(Notificacion).filter_by(usuario_id=ana.id).count() == 1
        assert db.session.get(ReporteUsuario, 1).estado == "resuelto"
        assert db.session.get(Parqueadero, 1).calificacion_promedio is None  # reseña rechazada
    # la cuenta suspendida ya no puede usar la API
    assert client.get("/api/me", headers=auth).status_code == 403


def test_dashboard_estado_vacio_y_exportacion(client):
    _login(client)
    html = client.get("/admin/?desde=2001-01-01&hasta=2001-01-31").get_data(as_text=True)
    assert "No hay datos para el filtro seleccionado" in html  # RF-11
    r = client.get("/admin/exportar.csv")
    assert r.status_code == 200 and "Cercano caro" in r.get_data(as_text=True)
