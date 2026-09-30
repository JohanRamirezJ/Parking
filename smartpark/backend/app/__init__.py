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

    _registrar_cli(app)
    return app


def _registrar_cli(app: Flask):
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
