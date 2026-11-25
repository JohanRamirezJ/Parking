# Despliegue y operación

## Requisitos

- Un servidor con **Docker** y **Docker Compose** (en Windows, Docker Desktop; el repositorio trae `iniciar-smartpark.bat`
  para desarrollo local).
- Un dominio con **HTTPS** delante del servicio (Nginx, Caddy o el balanceador del proveedor): en producción la cookie del
  panel admin es `Secure` y solo viaja por HTTPS.
- Salida a internet para Nominatim y Overpass (OpenStreetMap) y, opcionalmente, para Gemini u OpenAI.

## Servicios (`docker-compose.yml`)

| Servicio | Imagen | Puerto (host) | Notas |
|---|---|---|---|
| `db` | `postgres:16` | `5433` → 5432 | Volumen `pgdata`. **En producción quitar la publicación de este puerto** |
| `backend` | Ubuntu 24.04 + Python 3.12 + gunicorn | `5000` | API en `/api`, panel en `/admin`; usuario sin privilegios; healthcheck en `/api/salud` |
| `web` (perfil `web`) | Flutter web + nginx | `8080` | Opcional: `docker compose --profile web up -d --build` |

Al arrancar, `backend/docker/entrypoint.sh`: espera a PostgreSQL → `flask init-db` (crea tablas y agrega columnas nuevas) →
siembra datos demo si `SEED_DEMO=1` → crea el administrador si hay `ADMIN_EMAIL`/`ADMIN_PASSWORD` → lanza gunicorn con
`--preload` (las tablas se crean una sola vez aunque haya varios workers).

## Variables de entorno

Plantilla: [`.env.example`](../.env.example) (copiarla a `.env`; **nunca subir `.env`**).

| Variable | Producción | Defecto | Descripción |
|---|---|---|---|
| `FLASK_ENV` | `production` | `development` | En producción exige claves propias y activa la cookie `Secure` |
| `SECRET_KEY` | obligatoria | valor de ejemplo | Firma de sesiones. Generar: `python3 -c "import secrets;print(secrets.token_hex(32))"` |
| `JWT_SECRET` | obligatoria | valor de ejemplo | Firma de los tokens de la app (distinta de `SECRET_KEY`) |
| `JWT_EXP_MINUTES` | — | `1440` | Vigencia del token (24 h) |
| `POSTGRES_DB` / `POSTGRES_USER` / `POSTGRES_PASSWORD` | cambiar la clave | `smartpark` | Credenciales de PostgreSQL |
| `DATABASE_URL` | — | armada por compose | `postgresql+psycopg://usuario:clave@host:5432/bd`; sin definir usa SQLite |
| `SEED_DEMO` | **`0`** | `1` | `1` carga parqueaderos y usuarios ficticios, incluido el admin `admin@smartpark.co` |
| `ADMIN_EMAIL` / `ADMIN_PASSWORD` | definir | vacío | Crea o actualiza un administrador al arrancar |
| `CORS_ORIGINS` | acotar | `*` | Orígenes permitidos para `/api`, separados por comas |
| `LOGIN_MAX_INTENTOS` / `LOGIN_VENTANA_S` | — | `10` / `900` | Bloqueo de login tras N fallos por IP + correo en la ventana (s) |
| `GEMINI_API_KEY` / `GEMINI_MODEL` | opcional | vacío | Interpreta y redacta en el chat. Ver [modelo-ia.md](modelo-ia.md) |
| `OPENAI_API_KEY` / `OPENAI_MODEL` | opcional | vacío | Tiene prioridad sobre Gemini si ambas están definidas |
| `OVERPASS_URL` / `OVERPASS_TIMEOUT_SECONDS` | — | Overpass público / `6` | Búsqueda de parqueaderos en OpenStreetMap |
| `GEOCODER_URL` | — | Nominatim | Servicio de geocodificación |
| `PRECIO_GALON_COP`, `RENDIMIENTO_KM_GALON`, `COSTO_RODAMIENTO_KM`, `VELOCIDAD_AUTO_KMH` | revisar | ver `.env.example` | Supuestos del costo de manejar de la IA |
| `API_PORT`, `DB_PORT`, `WEB_PORT`, `GUNICORN_WORKERS` | — | `5000`, `5433`, `8080`, `3` | Puertos y workers |

> Las claves de Gemini/OpenAI son secretos: van solo en `.env` o en el almacén de secretos del proveedor, nunca en el repositorio.

## Despliegue con Docker Compose

```bash
git clone https://github.com/JohanRamirezJ/Parking.git && cd Parking
cp .env.example .env
# editar .env: FLASK_ENV=production, SECRET_KEY, JWT_SECRET, POSTGRES_PASSWORD, SEED_DEMO=0,
#              ADMIN_EMAIL y ADMIN_PASSWORD, y las claves de IA si se usan
docker compose up -d --build
docker compose ps
curl http://localhost:5000/api/salud      # {"estado":"ok","servicio":"smartpark-api"}
```

Si cambias `POSTGRES_PASSWORD` **después** de que la base ya existe, PostgreSQL conserva la clave anterior (está en el
volumen `pgdata`): cámbiala con `ALTER USER` o elimina el volumen solo si no hay datos que conservar.

### Proxy HTTPS (ejemplo con Caddy)

```
smartpark.tudominio.co {
    reverse_proxy localhost:5000
}
```

## Actualizar a una nueva versión

```bash
git pull && docker compose up -d --build
```

Las tablas y columnas nuevas se aplican solas al arrancar (`flask init-db`). Cambiar o eliminar columnas existentes no está
soportado todavía (ver "Pendientes"). Haz una copia de seguridad antes de actualizar.

## Copia de seguridad y restauración

```bash
# copia
docker compose exec -T db pg_dump -U smartpark smartpark > respaldo_$(date +%F).sql
# restauración
docker compose exec -T db psql -U smartpark smartpark < respaldo_2026-11-25.sql
```

Programa la copia con `cron` y guárdala fuera del servidor.

## Integración continua

`.github/workflows/ci.yml` se ejecuta en cada push a `main` y en cada pull request:

1. **backend** — `pytest` con SQLite y luego con un PostgreSQL 16 de servicio (Python 3.12).
2. **docker** — construye la imagen, la arranca en modo producción y comprueba `/api/salud`.
3. **mobile** — `flutter pub get`, `flutter analyze` y `flutter test`.

Recomendado: en GitHub, *Settings → Branches*, proteger `main` exigiendo que estos tres jobs pasen.

## App móvil

La URL del backend se fija al compilar:

```bash
flutter build apk --release --dart-define=API_URL=https://smartpark.tudominio.co
```

Para la versión web, `docker-compose.yml` pasa `API_URL` como argumento de build del servicio `web`. Permisos y primer
arranque: [mobile/README.md](../mobile/README.md).

## Lista de verificación antes de publicar

- [ ] `FLASK_ENV=production`; `SECRET_KEY`, `JWT_SECRET` y `POSTGRES_PASSWORD` propios (la app no arranca con los de ejemplo).
- [ ] `SEED_DEMO=0` y sin el administrador demo `admin@smartpark.co`; administradores reales creados.
- [ ] Puerto de PostgreSQL sin publicar al exterior (quitar `ports` del servicio `db`).
- [ ] HTTPS activo; `CORS_ORIGINS` acotado si hay clientes web.
- [ ] Directorio real cargado y verificado desde el panel (los datos de `flask seed` son ficticios).
- [ ] Claves de IA solo en `.env`; revisar cuotas del proveedor.
- [ ] Copia de seguridad programada y restauración probada.
- [ ] CI en verde en `main`.
- [ ] App móvil compilada contra la URL de producción.

## Pendientes antes de operar con datos reales

- **Migraciones** con Flask-Migrate/Alembic (hoy solo se agregan columnas nuevas).
- **Límite de login global** (Redis) si se escala a varias réplicas.
- Recuperación de contraseña por correo y login con redes sociales (alcance 3.1 del proyecto).
- Los servicios públicos de OpenStreetMap (Nominatim, Overpass) tienen límites de uso: para tráfico real conviene una
  instancia propia o un proveedor.
