"""Modelos de datos — corresponden a las 'Tablas físicas' del Documento_PM.

usuario, parqueadero, tarifa, resena, visita, consulta_ia, reporte_usuario, log_auditoria
"""
from datetime import datetime, time
from zoneinfo import ZoneInfo

ZONA_BOGOTA = ZoneInfo("America/Bogota")

import bcrypt
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .extensions import db


def ahora() -> datetime:
    return datetime.utcnow()


class Usuario(db.Model):
    __tablename__ = "usuario"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    nombre: Mapped[str] = mapped_column(String(100))
    telefono: Mapped[str | None] = mapped_column(String(20))
    foto_perfil: Mapped[str | None] = mapped_column(String(255))
    fecha_registro: Mapped[datetime] = mapped_column(DateTime, default=ahora)
    ultimo_acceso: Mapped[datetime | None] = mapped_column(DateTime)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    es_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    advertencias: Mapped[int] = mapped_column(Integer, default=0)

    def set_password(self, password: str) -> None:
        self.password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    def check_password(self, password: str) -> bool:
        return bcrypt.checkpw(password.encode(), self.password_hash.encode())

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "email": self.email,
            "nombre": self.nombre,
            "telefono": self.telefono,
            "foto_perfil": self.foto_perfil,
            "fecha_registro": self.fecha_registro.isoformat() if self.fecha_registro else None,
            "es_admin": self.es_admin,
        }


class Parqueadero(db.Model):
    __tablename__ = "parqueadero"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombre: Mapped[str] = mapped_column(String(100))
    direccion: Mapped[str] = mapped_column(String(200))
    latitud: Mapped[float] = mapped_column(Float, index=True)
    longitud: Mapped[float] = mapped_column(Float, index=True)
    horario_apertura: Mapped[time | None] = mapped_column(Time)
    horario_cierre: Mapped[time | None] = mapped_column(Time)
    capacidad_total: Mapped[int | None] = mapped_column(Integer)
    capacidad_disponible_estimada: Mapped[int | None] = mapped_column(Integer)
    calificacion_promedio: Mapped[float | None] = mapped_column(Float)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    fecha_registro: Mapped[datetime] = mapped_column(DateTime, default=ahora)
    imagen_url: Mapped[str | None] = mapped_column(String(255))

    tarifas: Mapped[list["Tarifa"]] = relationship(
        back_populates="parqueadero", cascade="all, delete-orphan")
    resenas: Mapped[list["Resena"]] = relationship(
        back_populates="parqueadero", cascade="all, delete-orphan")

    # --- Tarifas vigentes de conveniencia ---
    def tarifa_vigente(self, tipo: str) -> float | None:
        for t in self.tarifas:
            if t.vigente and t.tipo == tipo:
                return t.valor
        return None

    @property
    def tarifa_hora(self) -> float | None:
        return self.tarifa_vigente("hora")

    @property
    def tarifa_dia(self) -> float | None:
        return self.tarifa_vigente("dia")

    def total_resenas(self) -> int:
        return sum(1 for r in self.resenas if r.estado != "rechazada")

    def recalcular_promedio(self) -> None:
        """RF-06: actualizar el promedio al publicarse una reseña."""
        valores = [r.calificacion for r in self.resenas if r.estado != "rechazada"]
        self.calificacion_promedio = round(sum(valores) / len(valores), 2) if valores else None

    def abierto_ahora(self, momento: time | None = None) -> bool | None:
        if not self.horario_apertura or not self.horario_cierre:
            return None
        m = momento or datetime.now(ZONA_BOGOTA).time()
        a, c = self.horario_apertura, self.horario_cierre
        if a == c:  # 24 horas
            return True
        return a <= m < c if a < c else (m >= a or m < c)

    def to_dict(self, distancia_m: float | None = None) -> dict:
        d = {
            "id": self.id,
            "nombre": self.nombre,
            "direccion": self.direccion,
            "latitud": self.latitud,
            "longitud": self.longitud,
            "horario_apertura": self.horario_apertura.strftime("%H:%M") if self.horario_apertura else None,
            "horario_cierre": self.horario_cierre.strftime("%H:%M") if self.horario_cierre else None,
            "abierto_ahora": self.abierto_ahora(),
            "capacidad_total": self.capacidad_total,
            "capacidad_disponible_estimada": self.capacidad_disponible_estimada,
            "calificacion_promedio": self.calificacion_promedio,
            "total_resenas": self.total_resenas(),
            "imagen_url": self.imagen_url,
            # RF-05: None => la app muestra "tarifa no disponible"
            "tarifa_hora": self.tarifa_hora,
            "tarifa_dia": self.tarifa_dia,
            "tarifas": [t.to_dict() for t in self.tarifas if t.vigente],
        }
        if distancia_m is not None:
            d["distancia_m"] = round(distancia_m)
        return d


class Tarifa(db.Model):
    __tablename__ = "tarifa"

    TIPOS = ("hora", "fraccion", "dia", "mes")

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    parqueadero_id: Mapped[int] = mapped_column(ForeignKey("parqueadero.id"), index=True)
    tipo: Mapped[str] = mapped_column(String(20))
    valor: Mapped[float] = mapped_column(Float)
    unidad: Mapped[str] = mapped_column(String(20))
    fecha_actualizacion: Mapped[datetime] = mapped_column(DateTime, default=ahora, onupdate=ahora)
    vigente: Mapped[bool] = mapped_column(Boolean, default=True)

    parqueadero: Mapped[Parqueadero] = relationship(back_populates="tarifas")

    def to_dict(self) -> dict:
        return {"tipo": self.tipo, "valor": self.valor, "unidad": self.unidad,
                "fecha_actualizacion": self.fecha_actualizacion.isoformat() if self.fecha_actualizacion else None}


class Resena(db.Model):
    __tablename__ = "resena"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuario.id"), index=True)
    parqueadero_id: Mapped[int] = mapped_column(ForeignKey("parqueadero.id"), index=True)
    calificacion: Mapped[int] = mapped_column(Integer)
    comentario: Mapped[str | None] = mapped_column(Text)
    fecha: Mapped[datetime] = mapped_column(DateTime, default=ahora)
    reportado: Mapped[bool] = mapped_column(Boolean, default=False)
    estado: Mapped[str] = mapped_column(String(20), default="aprobada")  # pendiente|aprobada|rechazada

    usuario: Mapped[Usuario] = relationship()
    parqueadero: Mapped[Parqueadero] = relationship(back_populates="resenas")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "parqueadero_id": self.parqueadero_id,
            "usuario": {"id": self.usuario.id, "nombre": self.usuario.nombre},
            "calificacion": self.calificacion,
            "comentario": self.comentario,
            "fecha": self.fecha.isoformat(),
        }


class Visita(db.Model):
    __tablename__ = "visita"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuario.id"), index=True)
    parqueadero_id: Mapped[int] = mapped_column(ForeignKey("parqueadero.id"), index=True)
    fecha_visita: Mapped[datetime] = mapped_column(DateTime, default=ahora)
    tarifa_pagada: Mapped[float | None] = mapped_column(Float)
    metodo_pago: Mapped[str | None] = mapped_column(String(50))
    comentario_adicional: Mapped[str | None] = mapped_column(Text)

    parqueadero: Mapped[Parqueadero] = relationship()

    def to_dict(self) -> dict:
        return {"id": self.id, "parqueadero_id": self.parqueadero_id,
                "parqueadero_nombre": self.parqueadero.nombre,
                "fecha_visita": self.fecha_visita.isoformat(),
                "tarifa_pagada": self.tarifa_pagada, "metodo_pago": self.metodo_pago}


class ConsultaIA(db.Model):
    __tablename__ = "consulta_ia"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuario.id"), index=True)
    consulta: Mapped[str] = mapped_column(Text)
    respuesta: Mapped[str] = mapped_column(Text)
    parqueadero_recomendado_id: Mapped[int | None] = mapped_column(ForeignKey("parqueadero.id"))
    fecha: Mapped[datetime] = mapped_column(DateTime, default=ahora)
    tiempo_respuesta_ms: Mapped[int | None] = mapped_column(Integer)


class ReporteUsuario(db.Model):
    __tablename__ = "reporte_usuario"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    resena_id: Mapped[int | None] = mapped_column(ForeignKey("resena.id"))
    usuario_reportado_id: Mapped[int] = mapped_column(ForeignKey("usuario.id"))
    usuario_reportante_id: Mapped[int] = mapped_column(ForeignKey("usuario.id"))
    motivo: Mapped[str] = mapped_column(Text)
    evidencia: Mapped[str | None] = mapped_column(Text)
    fecha_reporte: Mapped[datetime] = mapped_column(DateTime, default=ahora)
    estado: Mapped[str] = mapped_column(String(20), default="pendiente")  # pendiente|resuelto|descartado
    fecha_resolucion: Mapped[datetime | None] = mapped_column(DateTime)
    observaciones_admin: Mapped[str | None] = mapped_column(Text)

    resena: Mapped[Resena | None] = relationship()
    usuario_reportado: Mapped[Usuario] = relationship(foreign_keys=[usuario_reportado_id])
    usuario_reportante: Mapped[Usuario] = relationship(foreign_keys=[usuario_reportante_id])


class Notificacion(db.Model):
    """RF-10: notificar al usuario reportado de la acción tomada.
    (Tabla adicional a las del documento; la app la consulta en /api/me/notificaciones.)"""
    __tablename__ = "notificacion"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuario.id"), index=True)
    mensaje: Mapped[str] = mapped_column(Text)
    fecha: Mapped[datetime] = mapped_column(DateTime, default=ahora)
    leida: Mapped[bool] = mapped_column(Boolean, default=False)

    def to_dict(self) -> dict:
        return {"id": self.id, "mensaje": self.mensaje, "fecha": self.fecha.isoformat(), "leida": self.leida}


class LogAuditoria(db.Model):
    __tablename__ = "log_auditoria"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"))
    accion: Mapped[str] = mapped_column(String(50))
    entidad: Mapped[str] = mapped_column(String(50))
    entidad_id: Mapped[int | None] = mapped_column(Integer)
    datos_previos: Mapped[str | None] = mapped_column(Text)
    datos_nuevos: Mapped[str | None] = mapped_column(Text)
    fecha: Mapped[datetime] = mapped_column(DateTime, default=ahora)
    ip_origen: Mapped[str | None] = mapped_column(String(45))

    usuario: Mapped[Usuario | None] = relationship()


class EventoBusqueda(db.Model):
    """Registro liviano de búsquedas para el dashboard analítico (uso de la app por zona/fecha)."""
    __tablename__ = "evento_busqueda"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"))
    latitud: Mapped[float] = mapped_column(Float)
    longitud: Mapped[float] = mapped_column(Float)
    radio_m: Mapped[int] = mapped_column(Integer)
    resultados: Mapped[int] = mapped_column(Integer)
    fecha: Mapped[datetime] = mapped_column(DateTime, default=ahora, index=True)
