from flask import Blueprint

api_bp = Blueprint("api", __name__, url_prefix="/api")

from . import auth, parqueaderos, resenas, chat  # noqa: E402,F401
