import pytest
from datetime import time

from app import create_app
from app.extensions import db
from app.models import Parqueadero, Tarifa, Usuario


@pytest.fixture()
def app():
    app = create_app("test")
    with app.app_context():
        admin = Usuario(email="admin@test.co", nombre="Admin", es_admin=True)
        admin.set_password("admin12345")
        db.session.add(admin)
        # Tres parqueaderos alrededor del Hospital San Ignacio (4.6283, -74.0645)
        datos = [
            ("Cercano caro", 4.6290, -74.0640, 9000),
            ("Medio barato", 4.6320, -74.0650, 3500),
            ("Sin tarifa", 4.6275, -74.0660, None),
            ("Lejano", 4.7000, -74.0400, 2000),  # ~8 km
        ]
        for nombre, lat, lon, tarifa in datos:
            p = Parqueadero(nombre=nombre, direccion="Calle 1", latitud=lat, longitud=lon,
                            horario_apertura=time(0, 0), horario_cierre=time(0, 0), capacidad_total=50,
                            capacidad_disponible_estimada=10)
            if tarifa:
                p.tarifas.append(Tarifa(tipo="hora", unidad="hora", valor=tarifa))
            db.session.add(p)
        db.session.commit()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


def registrar(client, email="ana@test.co", password="clave1234", nombre="Ana"):
    r = client.post("/api/auth/registro", json={"email": email, "password": password, "nombre": nombre})
    return r


@pytest.fixture()
def token(client):
    return registrar(client).get_json()["token"]


@pytest.fixture()
def auth(token):
    return {"Authorization": f"Bearer {token}"}
