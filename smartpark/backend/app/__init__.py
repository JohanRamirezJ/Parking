"""SmartPark — backend Flask (API REST + panel web de administración)."""
import os

import click
from flask import Flask, redirect, url_for
from flask_cors import CORS

from .config import SECRET_POR_DEFECTO, get_config
from .extensions import db


def create_app(entorno: str | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_object(get_config(entorno))

    if app.config.get("SECRET_KEY") == SECRET_POR_DEFECTO and not (
            app.config.get("TESTING") or app.debug or os.getenv("FLASK_ENV") == "development"):
        if os.getenv("FLASK_ENV") == "production":
            raise RuntimeError("Define SECRET_KEY (y opcionalmente JWT_SECRET) en producción.")
        app.logger.warning("SECRET_KEY por defecto: solo para desarrollo.")

    db.init_app(app)
    CORS(app, resources={r"/api/*": {"origins": app.config["CORS_ORIGINS"]}})

    from .services.errors import registrar_manejadores
    registrar_manejadores(app)

    from .api import api_bp
    from .admin import admin_bp
    app.register_blueprint(api_bp)
    app.register_blueprint(admin_bp)

    @app.after_request
    def _cabeceras_seguridad(resp):
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("Referrer-Policy", "same-origin")
        return resp

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
