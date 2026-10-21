"""Datos de EJEMPLO para desarrollo y demos.

⚠ Los parqueaderos, tarifas y reseñas generados aquí son ficticios (todos llevan "(demo)"
en el nombre). El directorio real debe poblarse con registro curado desde el panel admin
(actividad "Poblar y auditar el directorio inicial de parqueaderos").
"""
import random
from datetime import datetime, time, timedelta

from sqlalchemy import select

from .extensions import db
from .models import EventoBusqueda, Parqueadero, Resena, Tarifa, Usuario, Visita

ZONAS = [  # (zona, lat, lon) — centros aproximados
    ("San Ignacio", 4.6283, -74.0645),
    ("Andino", 4.6668, -74.0526),
    ("Parque 93", 4.6766, -74.0485),
    ("Unicentro", 4.7020, -74.0415),
    ("Santa Fe", 4.6946, -74.0330),
    ("Chapinero", 4.6486, -74.0628),
    ("Centro", 4.5981, -74.0760),
    ("Salitre", 4.6526, -74.1097),
]
TIPOS = ["Central", "Plaza", "Express", "24 Horas"]
COMENTARIOS = [
    "Buen servicio y bien iluminado.", "Un poco caro pero seguro.", "Difícil la entrada en hora pico.",
    "Personal amable, lo recomiendo.", "Cupos muy estrechos.", "Excelente ubicación.", None,
]


def cargar(semilla: int = 42) -> int:
    rnd = random.Random(semilla)
    if db.session.scalar(select(Parqueadero.id).limit(1)):
        return 0

    admin = db.session.scalar(select(Usuario).where(Usuario.email == "admin@smartpark.co"))
    if not admin:
        admin = Usuario(email="admin@smartpark.co", nombre="Admin Demo", es_admin=True)
        admin.set_password("admin12345")
        db.session.add(admin)

    usuarios = []
    for i, nombre in enumerate(["Laura Gómez", "Andrés Ruiz", "Camila Torres", "Mateo Díaz"], start=1):
        u = Usuario(email=f"demo{i}@smartpark.co", nombre=nombre)
        u.set_password("demo12345")
        db.session.add(u)
        usuarios.append(u)

    parqueaderos = []
    for zona, lat, lon in ZONAS:
        for k in range(3):
            tipo = TIPOS[(k + len(parqueaderos) // 3) % len(TIPOS)]
            p = Parqueadero(
                nombre=f"Parqueadero {tipo} {zona} (demo)",
                direccion=f"Calle {rnd.randint(20, 120)} # {rnd.randint(5, 60)}-{rnd.randint(10, 90)}",
                latitud=round(lat + rnd.uniform(-0.006, 0.006), 6),
                longitud=round(lon + rnd.uniform(-0.006, 0.006), 6),
                horario_apertura=time(0, 0) if tipo == "24 Horas" else time(6, 0),
                horario_cierre=time(0, 0) if tipo == "24 Horas" else time(rnd.choice([20, 21, 22]), 0),
                capacidad_total=(cap := rnd.choice([40, 60, 80, 120, 200])),
                capacidad_disponible_estimada=rnd.randint(0, cap),
            )
            # ~10 % sin tarifa registrada para probar "tarifa no disponible"
            if rnd.random() > 0.1:
                hora = rnd.choice([3000, 3500, 4000, 4500, 5000, 5500, 6000, 7000, 8500, 11000])
                p.tarifas.append(Tarifa(tipo="hora", unidad="hora", valor=hora))
                p.tarifas.append(Tarifa(tipo="dia", unidad="dia", valor=hora * rnd.choice([6, 7, 8])))
            db.session.add(p)
            parqueaderos.append(p)
    db.session.flush()

    ahora = datetime.utcnow()
    for p in parqueaderos:
        if rnd.random() < 0.55:
            for u in rnd.sample(usuarios, rnd.randint(1, 3)):
                fecha = ahora - timedelta(days=rnd.randint(0, 25), hours=rnd.randint(0, 23))
                db.session.add(Visita(usuario_id=u.id, parqueadero_id=p.id, fecha_visita=fecha,
                                      tarifa_pagada=p.tarifa_hora))
                db.session.add(Resena(usuario_id=u.id, parqueadero=p, calificacion=rnd.choice([2, 3, 4, 4, 5, 5]),
                                      comentario=rnd.choice(COMENTARIOS), fecha=fecha))
        db.session.flush()
        p.recalcular_promedio()

    for _ in range(180):
        _, lat, lon = rnd.choice(ZONAS)
        db.session.add(EventoBusqueda(latitud=lat, longitud=lon, radio_m=1000, resultados=rnd.randint(0, 6),
                                      fecha=ahora - timedelta(days=rnd.randint(0, 29), hours=rnd.randint(0, 23))))
    db.session.commit()
    return len(parqueaderos)
