"""Errores controlados de la API (RF-07): siempre JSON con código y mensaje en español."""
from flask import jsonify


class ApiError(Exception):
    def __init__(self, mensaje: str, status: int = 400, codigo: str = "error", detalles: dict | None = None):
        super().__init__(mensaje)
        self.mensaje, self.status, self.codigo, self.detalles = mensaje, status, codigo, detalles or {}


def registrar_manejadores(app):
    @app.errorhandler(ApiError)
    def _api_error(e: ApiError):
        cuerpo = {"error": {"codigo": e.codigo, "mensaje": e.mensaje}}
        if e.detalles:
            cuerpo["error"]["detalles"] = e.detalles
        return jsonify(cuerpo), e.status

    def _generico(status, codigo, mensaje):
        def handler(_e):
            from flask import request
            if request.path.startswith("/api/"):
                return jsonify({"error": {"codigo": codigo, "mensaje": mensaje}}), status
            return _e
        return handler

    app.register_error_handler(404, _generico(404, "no_encontrado", "Recurso no encontrado"))
    app.register_error_handler(405, _generico(405, "metodo_no_permitido", "Método no permitido"))

    @app.errorhandler(500)
    def _interno(_e):
        return jsonify({"error": {"codigo": "error_interno",
                                  "mensaje": "Ocurrió un error inesperado, intenta de nuevo"}}), 500
