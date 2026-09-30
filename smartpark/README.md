# SmartPark

Aplicación para ubicar, comparar y calificar parqueaderos en Bogotá.
Proyecto de Programación Móvil — Ingeniería de Sistemas, 2026.

```
smartpark/
├── backend/          API REST Flask + panel admin Jinja2 + pruebas (Python)
├── mobile/           App Flutter (Android / iOS)
└── docker-compose.yml  API + PostgreSQL
```

- Backend: ver [backend/README.md](backend/README.md)
- App móvil: ver [mobile/README.md](mobile/README.md)

## Cobertura de requisitos

| Requisito | Dónde |
|---|---|
| RF-01 / HU 1–2 Registro e inicio de sesión | `backend/app/api/auth.py`, `mobile/lib/screens/login_screen.dart` |
| RF-02 / HU 3 Perfil | `api/auth.py` (`PUT /api/me`), `perfil_screen.dart` |
| RF-03 / HU 4–5 Ubicación y destino | `services/geocoding.py`, `state/busqueda.dart`, `mapa_screen.dart` |
| RF-04 / HU 6–7 Mapa y radio | `api/parqueaderos.py`, `mapa_screen.dart` |
| RF-05 / HU 8–9 Comparar y filtrar tarifas | `services/directorio.py`, `lista_screen.dart` |
| RF-06 / HU 10–11 Reseñas | `api/resenas.py`, `detalle_screen.dart` |
| RF-07 / RF-08 / HU 12–13 API y JWT | `services/errors.py`, `services/auth.py`, `mobile/lib/services/api.dart` |
| RF-09 / RF-13 / HU 14 Panel y directorio | `backend/app/admin/`, `services/validacion.py` |
| RF-10 Usuarios reportados | `admin/__init__.py` (`accion_reporte`) |
| RF-11 Dashboard y exportación | `admin/__init__.py` (`dashboard`, `exportar`) |
| RF-12 Chat IA | `services/chat.py`, `chat_screen.dart` |
