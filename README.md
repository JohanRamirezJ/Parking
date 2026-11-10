# SmartPark

Aplicación para ubicar, comparar y calificar parqueaderos en Bogotá.
Proyecto de Programación Móvil — Ingeniería de Sistemas, 2026.

```
smartpark/
├── backend/            API REST Flask + panel admin Jinja2 + pruebas (Python) · Dockerfile Ubuntu
├── mobile/             App Flutter (Android / iOS / web) · Dockerfile.web
├── docs/               Documentación técnica (modelo de IA)
├── docker-compose.yml  PostgreSQL + backend (+ web opcional)
└── .env.example        Variables de entorno
```

## Levantar todo con Docker

Requisito: [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Windows/macOS) o Docker Engine + Compose (Linux).

```bash
cp .env.example .env            # en Windows: copy .env.example .env  (ajusta claves si quieres)
docker compose up -d --build    # PostgreSQL 16 + backend (Ubuntu 24.04)
docker compose --profile web up -d --build   # opcional: también la app Flutter compilada para web
```

| Servicio | Imagen | URL en tu computador |
|---|---|---|
| `db` | postgres:16 | `localhost:5433` (usuario/clave/BD: `smartpark`) |
| `backend` | ubuntu:24.04 + Python 3.12 + gunicorn | API http://localhost:5000/api/salud · panel http://localhost:5000/admin |
| `web` (perfil `web`) | Flutter web + nginx | http://localhost:8080 |

Al arrancar, el backend espera a PostgreSQL, crea/actualiza las tablas y (con `SEED_DEMO=1`) carga datos de ejemplo: admin `admin@smartpark.co` / `admin12345`, usuarios `demo1…demo4@smartpark.co` / `demo12345`.

Comandos útiles:

```bash
docker compose ps                     # estado
docker compose logs -f backend        # logs del backend
docker compose exec backend flask crear-admin tu@correo.co "ClaveSegura" --nombre "Tu Nombre"
docker compose exec db psql -U smartpark smartpark   # consola SQL
docker compose down                   # detener (los datos quedan en el volumen pgdata)
docker compose down -v                # detener y BORRAR la base de datos
```

Pruebas del backend contra PostgreSQL: `TEST_DATABASE_URL=postgresql+psycopg://usuario:clave@host:puerto/bd_pruebas python -m pytest`.

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
| Módulo de IA multicriterio (gasolina, rodamiento, tiempo, distancia, seguridad, precio) | `services/recomendador.py`, `api/recomendaciones.py`, `recomendar_screen.dart` · [docs/modelo-ia.md](docs/modelo-ia.md) |
