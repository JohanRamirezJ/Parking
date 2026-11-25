"""Pruebas unitarias de las reglas de negocio de app/models.py y app/services/directorio.py."""
from datetime import time

import pytest

from app.models import Parqueadero, Resena, Tarifa, Usuario
from app.services.directorio import aplicar_datos, buscar_cercanos
from app.services.validacion import validar_parqueadero

LAT, LON = 4.6283, -74.0645  # Hospital San Ignacio (datos de conftest)


def parqueadero(**kw):
    kw.setdefault("nombre", "P")
    kw.setdefault("direccion", "Calle 1")
    kw.setdefault("latitud", LAT)
    kw.setdefault("longitud", LON)
    return Parqueadero(**kw)


# ---------------------------------------------------------------- contraseñas y preferencias
def test_la_contrasena_se_guarda_con_hash():
    u = Usuario(email="a@b.co", nombre="A")
    u.set_password("clave1234")
    assert u.password_hash != "clave1234" and u.password_hash.startswith("$2")
    assert u.check_password("clave1234")
    assert not u.check_password("otra-clave")


def test_dos_hash_de_la_misma_clave_son_distintos():
    a, b = Usuario(email="a@b.co", nombre="A"), Usuario(email="b@b.co", nombre="B")
    a.set_password("clave1234"), b.set_password("clave1234")
    assert a.password_hash != b.password_hash  # sal aleatoria


def test_to_dict_de_usuario_no_expone_la_contrasena():
    u = Usuario(email="a@b.co", nombre="A", es_admin=False)
    u.set_password("clave1234")
    assert "password_hash" not in u.to_dict() and "password" not in u.to_dict()


def test_preferencias_invalidas_o_vacias_devuelven_diccionario_vacio():
    assert Usuario(email="a@b.co", nombre="A").get_preferencias() == {}
    assert Usuario(email="a@b.co", nombre="A", preferencias="{no es json").get_preferencias() == {}


def test_preferencias_validas_se_leen():
    u = Usuario(email="a@b.co", nombre="A", preferencias='{"vehiculo": "moto"}')
    assert u.get_preferencias() == {"vehiculo": "moto"}


# ---------------------------------------------------------------- horario
@pytest.mark.parametrize("apertura,cierre,momento,esperado", [
    (time(6), time(22), time(12), True),
    (time(6), time(22), time(5, 59), False),
    (time(6), time(22), time(22), False),       # el cierre es exclusivo
    (time(6), time(22), time(6), True),         # la apertura es inclusiva
    (time(0), time(0), time(3), True),          # apertura == cierre → 24 horas
    (time(20), time(6), time(23), True),        # cruza la medianoche
    (time(20), time(6), time(3), True),
    (time(20), time(6), time(12), False),
])
def test_abierto_ahora(apertura, cierre, momento, esperado):
    p = parqueadero(horario_apertura=apertura, horario_cierre=cierre)
    assert p.abierto_ahora(momento) is esperado


def test_abierto_ahora_sin_horario_es_desconocido():
    assert parqueadero().abierto_ahora(time(12)) is None


# ---------------------------------------------------------------- tarifas
def test_tarifa_vigente_ignora_las_historicas():
    p = parqueadero()
    p.tarifas = [Tarifa(tipo="hora", unidad="hora", valor=3000, vigente=False),
                 Tarifa(tipo="hora", unidad="hora", valor=4000, vigente=True),
                 Tarifa(tipo="dia", unidad="dia", valor=20000, vigente=True)]
    assert p.tarifa_hora == 4000 and p.tarifa_dia == 20000
    assert p.tarifa_vigente("mes") is None


def test_sin_tarifas_devuelve_none():
    assert parqueadero().tarifa_hora is None


def test_aplicar_datos_conserva_la_tarifa_anterior_como_historica(app):
    p = parqueadero(tarifas=[Tarifa(tipo="hora", unidad="hora", valor=3000, vigente=True)])
    limpio, errores = validar_parqueadero({"nombre": "P", "direccion": "Calle 1", "latitud": LAT,
                                           "longitud": LON, "tarifa_hora": "4500"})
    assert errores == {}
    aplicar_datos(p, limpio)
    assert p.tarifa_hora == 4500
    assert [t.valor for t in p.tarifas if t.vigente is False] == [3000]


def test_aplicar_datos_con_la_misma_tarifa_no_crea_otra_fila(app):
    p = parqueadero(tarifas=[Tarifa(tipo="hora", unidad="hora", valor=3000, vigente=True)])
    limpio, _ = validar_parqueadero({"nombre": "P", "direccion": "Calle 1", "latitud": LAT,
                                     "longitud": LON, "tarifa_hora": "3000"})
    aplicar_datos(p, limpio)
    assert len(p.tarifas) == 1 and p.tarifas[0].vigente


# ---------------------------------------------------------------- reseñas y promedio
def test_promedio_ignora_las_resenas_rechazadas():
    p = parqueadero()
    p.resenas = [Resena(calificacion=5, estado="aprobada"), Resena(calificacion=3, estado="aprobada"),
                 Resena(calificacion=1, estado="rechazada")]
    p.recalcular_promedio()
    assert p.calificacion_promedio == 4.0 and p.total_resenas() == 2


def test_promedio_se_redondea_a_dos_decimales():
    p = parqueadero()
    p.resenas = [Resena(calificacion=5, estado="aprobada"), Resena(calificacion=4, estado="aprobada"),
                 Resena(calificacion=4, estado="aprobada")]
    p.recalcular_promedio()
    assert p.calificacion_promedio == 4.33


def test_sin_resenas_el_promedio_es_none():
    p = parqueadero()
    p.recalcular_promedio()
    assert p.calificacion_promedio is None and p.total_resenas() == 0


def test_to_dict_incluye_distancia_solo_si_se_conoce():
    p = parqueadero()
    assert "distancia_m" not in p.to_dict()
    assert p.to_dict(349.6)["distancia_m"] == 350


# ---------------------------------------------------------------- búsqueda por proximidad
def nombres(res):
    return [p.nombre for p, _ in res]


def test_buscar_cercanos_respeta_el_radio(app):
    assert "Lejano" not in nombres(buscar_cercanos(LAT, LON, 1000))      # ~8 km
    assert "Lejano" in nombres(buscar_cercanos(LAT, LON, 10_000))


def test_buscar_cercanos_ordena_por_distancia(app):
    distancias = [d for _, d in buscar_cercanos(LAT, LON, 5000)]
    assert distancias == sorted(distancias)


def test_buscar_cercanos_por_tarifa_deja_sin_tarifa_al_final(app):
    res = nombres(buscar_cercanos(LAT, LON, 5000, orden="tarifa"))
    assert res[0] == "Medio barato" and res[-1] == "Sin tarifa"


def test_buscar_cercanos_filtra_por_rango_de_tarifa(app):
    res = nombres(buscar_cercanos(LAT, LON, 5000, tarifa_min=3000, tarifa_max=4000))
    assert res == ["Medio barato"]


def test_buscar_cercanos_excluye_los_desactivados(app):
    from app.extensions import db
    db.session.query(Parqueadero).filter_by(nombre="Medio barato").update({"activo": False})
    db.session.commit()
    assert "Medio barato" not in nombres(buscar_cercanos(LAT, LON, 5000))


def test_buscar_cercanos_sin_resultados_devuelve_lista_vacia(app):
    assert buscar_cercanos(4.50, -74.20, 200) == []
