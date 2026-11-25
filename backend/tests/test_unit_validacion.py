"""Pruebas unitarias de app/services/validacion.py (sin base de datos ni HTTP)."""
from datetime import time

import pytest

from app.services.validacion import email_valido, parse_hora, telefono_valido, validar_parqueadero


def datos_validos(**cambios):
    base = {"nombre": "Parqueadero Norte", "direccion": "Cra 7 # 40-62", "latitud": "4.63",
            "longitud": "-74.065", "tarifa_hora": "5000", "horario_apertura": "06:00",
            "horario_cierre": "22:00", "capacidad_total": "50",
            "capacidad_disponible_estimada": "10"}
    base.update(cambios)
    return base


# ---------------------------------------------------------------- correo y teléfono
@pytest.mark.parametrize("correo", ["ana@correo.co", "a.b+c@sub.dominio.com"])
def test_email_valido_acepta_formatos_correctos(correo):
    assert email_valido(correo)


@pytest.mark.parametrize("correo", ["", "sin-arroba", "a@b", "a b@c.co", "@c.co", "a@c.", "x" * 100 + "@c.co"])
def test_email_valido_rechaza_formatos_incorrectos(correo):
    assert not email_valido(correo)


@pytest.mark.parametrize("tel", ["3001234567", "+57 3001234567", "1234567", "123456789012345"])
def test_telefono_valido_acepta(tel):
    assert telefono_valido(tel)


@pytest.mark.parametrize("tel", ["abc", "123456", "1234567890123456", "300-123-4567", ""])
def test_telefono_valido_rechaza(tel):
    assert not telefono_valido(tel)


# ---------------------------------------------------------------- horas
def test_parse_hora_convierte_texto():
    assert parse_hora("06:30") == time(6, 30)
    assert parse_hora("22:00:00") == time(22, 0)  # ignora los segundos


@pytest.mark.parametrize("vacio", [None, ""])
def test_parse_hora_vacio_es_none(vacio):
    assert parse_hora(vacio) is None


@pytest.mark.parametrize("malo", ["25:00", "abc", "6"])
def test_parse_hora_invalida_lanza_error(malo):
    with pytest.raises(ValueError):
        parse_hora(malo)


# ---------------------------------------------------------------- validar_parqueadero
def test_parqueadero_valido_no_tiene_errores(app):
    limpio, errores = validar_parqueadero(datos_validos())
    assert errores == {}
    assert limpio["latitud"] == 4.63 and limpio["tarifa_hora"] == 5000.0
    assert limpio["horario_apertura"] == time(6, 0)
    assert limpio["capacidad_total"] == 50 and limpio["activo"] is True


@pytest.mark.parametrize("campo", ["nombre", "direccion"])
def test_obligatorios_vacios_o_con_espacios(app, campo):
    _, errores = validar_parqueadero(datos_validos(**{campo: "   "}))
    assert campo in errores


def test_recorta_nombre_y_direccion_al_maximo(app):
    limpio, _ = validar_parqueadero(datos_validos(nombre="n" * 300, direccion="d" * 300))
    assert len(limpio["nombre"]) == 100 and len(limpio["direccion"]) == 200


def test_ubicacion_fuera_de_bogota(app):
    _, errores = validar_parqueadero(datos_validos(latitud="6.25", longitud="-75.57"))  # Medellín
    assert "Bogotá" in errores["ubicacion"]


@pytest.mark.parametrize("lat,lon", [("", ""), ("abc", "-74"), (None, None)])
def test_ubicacion_obligatoria_y_numerica(app, lat, lon):
    _, errores = validar_parqueadero(datos_validos(latitud=lat, longitud=lon))
    assert "obligatoria" in errores["ubicacion"]


@pytest.mark.parametrize("valor", ["0", "-5", "1000001", "caro"])
def test_tarifa_invalida(app, valor):
    _, errores = validar_parqueadero(datos_validos(tarifa_hora=valor))
    assert errores["tarifa_hora"] == "Valor de tarifa inválido"


def test_exige_al_menos_una_tarifa(app):
    _, errores = validar_parqueadero(datos_validos(tarifa_hora="", tarifa_dia=""))
    assert "al menos una tarifa" in errores["tarifa_hora"]


def test_basta_con_la_tarifa_por_dia(app):
    limpio, errores = validar_parqueadero(datos_validos(tarifa_hora="", tarifa_dia="25000"))
    assert errores == {} and limpio["tarifa_hora"] is None and limpio["tarifa_dia"] == 25000.0


def test_horario_con_formato_invalido(app):
    _, errores = validar_parqueadero(datos_validos(horario_apertura="99:99"))
    assert "HH:MM" in errores["horario"]


@pytest.mark.parametrize("valor", ["-1", "diez", "1.5x"])
def test_capacidad_debe_ser_entero_positivo(app, valor):
    _, errores = validar_parqueadero(datos_validos(capacidad_total=valor))
    assert "capacidad_total" in errores


def test_disponibles_no_superan_la_capacidad_total(app):
    _, errores = validar_parqueadero(datos_validos(capacidad_total="10",
                                                   capacidad_disponible_estimada="11"))
    assert "capacidad_disponible_estimada" in errores


@pytest.mark.parametrize("valor,esperado", [(True, True), ("on", True), ("1", True),
                                            (False, False), ("no", False), ("", False)])
def test_interpretacion_del_campo_activo(app, valor, esperado):
    limpio, _ = validar_parqueadero(datos_validos(activo=valor))
    assert limpio["activo"] is esperado
