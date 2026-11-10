"""SmartPark — backend Flask (API REST + panel web de administración)."""
import click
from flask import Flask, redirect, url_for
from flask_cors import CORS

from .config import get_config
from .extensions import db


def create_app(entorno: str | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_object(get_config(entorno))

    db.init_app(app)
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    from .services.errors import registrar_manejadores
    registrar_manejadores(app)

    from .api import api_bp
    from .admin import admin_bp
    app.register_blueprint(api_bp)
    app.register_blueprint(admin_bp)

    @app.get("/")
    def raiz():
        return redirect(url_for("admin.dashboard"))

    with app.app_context():
        from . import models  # noqa: F401
        db.create_all()
        _migraciones_ligeras()

    _registrar_cli(app)
    return app


# Columnas añadidas después de la v0.1. create_all() no altera tablas existentes, así que
# se agregan aquí para no obligar al equipo a borrar su base de datos de desarrollo.
COLUMNAS_NUEVAS = {
    "usuario": {"preferencias": "TEXT"},
    "parqueadero": {"calificacion_seguridad": "FLOAT"},
    "resena": {"calificacion_seguridad": "INTEGER"},
}


def _migraciones_ligeras():
    from sqlalchemy import inspect, text
    insp = inspect(db.engine)
    with db.engine.begin() as con:
        for tabla, cols in COLUMNAS_NUEVAS.items():
            existentes = {c["name"] for c in insp.get_columns(tabla)}
            for col, tipo in cols.items():
                if col not in existentes:
                    con.execute(text(f"ALTER TABLE {tabla} ADD COLUMN {col} {tipo}"))


def _registrar_cli(app: Flask):
    @app.cli.command("init-db")
    def init_db_cmd():
        """Crea las tablas y aplica las columnas nuevas (idempotente)."""
        db.create_all()
        _migraciones_ligeras()
        click.echo("Base de datos lista.")

    @app.cli.command("seed")
    def seed_cmd():
        """Carga parqueaderos de ejemplo y usuarios demo."""
        from .seed import cargar
        n = cargar()
        click.echo(f"Datos de ejemplo cargados ({n} parqueaderos).")

    @app.cli.command("crear-admin")
    @click.argument("email")
    @click.argument("password")
    @click.option("--nombre", default="Administrador")
    def crear_admin(email, password, nombre):
        """Crea (o promueve) un usuario administrador."""
        from sqlalchemy import select
        from .models import Usuario
        u = db.session.scalar(select(Usuario).where(Usuario.email == email.lower()))
        if not u:
            u = Usuario(email=email.lower(), nombre=nombre)
            db.session.add(u)
        u.set_password(password)
        u.es_admin = True
        u.activo = True
        db.session.commit()
        click.echo(f"Administrador listo: {u.email}")
