# Despliegue y operación

## Requisitos

- Un servidor con **Docker** y **Docker Compose** (o Python 3.12 + PostgreSQL 15 si se despliega sin contenedores).
- Un dominio con **HTTPS** delante del servicio (Nginx, Caddy o el balanceador del proveedor): la cookie del panel
  admin solo viaja por HTTPS en producción.
- Salida a internet para geocodificar destinos (Nominatim) y, opcionalmente, para el chat (OpenAI).

## Variables de entorno

| Variable | Obligatoria | Defecto | Descripción |
|---|---|---|---|
| `FLASK_ENV` | sí en producción | — | `production` activa cookie `Secure` y **exige** `SECRET_KEY` |
| `SECRET_KEY` | sí | valor de desarrollo | Firma de sesiones. Generar: `python -c "import secrets;print(secrets.token_hex(32))"` |
| `JWT_SECRET` | no | `SECRET_KEY` | Clave de firma de los tokens de la app |
| `JWT_EXP_MINUTES` | no | `1440` | Vigencia del token (24 h) |
| `DATABASE_URL` | sí | `sqlite:///smartpark.db` | Producción: `postgresql+psycopg://usuario:clave@host:5432/db` |
| `POSTGRES_PASSWORD` | con compose | `smartpark` | Clave de PostgreSQL en `docker-compose.yml` (**cambiarla**) |
| `CORS_ORIGINS` | no | `*` | Orígenes permitidos para `/api`, separados por comas |
| `LOGIN_MAX_INTENTOS` | no | `10` | Fallos de login antes de bloquear |
| `LOGIN_VENTANA_S` | no | `900` | Ventana (s) del bloqueo y del conteo |
| `OPENAI_API_KEY` | no | vacío | Si se define, el chat redacta con el modelo |
| `OPENAI_MODEL` | no | `gpt-4o-mini` | Modelo usado por el chat |
| `GEOCODER_URL` | no | Nominatim | Servicio de geocodificación compatible |

Nunca subir el archivo `.env` al repositorio (ya está en `.gitignore`); usar `backend/.env.example` como plantilla.

## Despliegue con Docker Compose

```bash
git clone https://github.com/JohanRamirezJ/Parking.git && cd Parking/smartpark

export FLASK_ENV=production
export SECRET_KEY=$(python3 -c "import secrets;print(secrets.token_hex(32))")
export POSTGRES_PASSWORD=<una-clave-fuerte>
docker compose up -d --build

docker compose exec api flask crear-admin correo@dominio.co "ClaveSegura123" --nombre "Nombre"
curl http://localhost:5000/api/salud      # {"estado":"ok","servicio":"smartpark-api"}
```

Guarda `SECRET_KEY` y `POSTGRES_PASSWORD` en un archivo `.env` junto al `docker-compose.yml` (Compose lo lee solo) para
que no se pierdan al reiniciar.

Servicios: `db` (PostgreSQL 15, volumen `pgdata`) y `api` (gunicorn, 3 workers, `--preload`, usuario sin privilegios,
healthcheck en `/api/salud`, reinicio automático). El puerto 5000 es el que debe exponer el proxy HTTPS; PostgreSQL no se
publica al exterior.

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

Las tablas nuevas se crean al arrancar; **los cambios en tablas existentes no se migran automáticamente**
(ver "Pendientes"). Haz copia de seguridad antes de actualizar.

## Copia de seguridad y restauración

```bash
# copia
docker compose exec -T db pg_dump -U smartpark smartpark > respaldo_$(date +%F).sql
# restauración
docker compose exec -T db psql -U smartpark smartpark < respaldo_2026-10-21.sql
```

Programa la copia con `cron` y guárdala fuera del servidor.

## Integración continua

`.github/workflows/ci.yml` se ejecuta en cada push a `main` y en cada pull request:

1. **backend** — instala dependencias y corre `pytest` (Python 3.12).
2. **docker** — construye la imagen, la arranca en modo producción y comprueba `/api/salud`.
3. **mobile** — `flutter pub get`, `flutter analyze` y `flutter test`.

Recomendado: activar en GitHub *Settings → Branches* la protección de `main` exigiendo que estos tres jobs pasen.

## App móvil

La URL del backend se fija al compilar:

```bash
flutter build apk --release --dart-define=API_URL=https://smartpark.tudominio.co
```

En Android, quitar `usesCleartextTraffic` del manifiesto en producción (solo es necesario para `http://` en desarrollo).
Pasos de permisos y primer arranque: [mobile/README.md](../mobile/README.md).

## Lista de verificación antes de publicar

- [ ] `FLASK_ENV=production`, `SECRET_KEY` largo y aleatorio, `POSTGRES_PASSWORD` cambiada.
- [ ] HTTPS activo y `CORS_ORIGINS` acotado si hay clientes web.
- [ ] Administradores reales creados; la cuenta demo `admin@smartpark.co` eliminada o con otra clave.
- [ ] Sin datos demo: el directorio real cargado y verificado desde el panel (los de `flask seed` son ficticios).
- [ ] Copia de seguridad programada y restauración probada.
- [ ] CI en verde en `main`.
- [ ] App móvil compilada contra la URL de producción.

## Pendientes antes de operar con datos reales

- **Migraciones** con Flask-Migrate/Alembic (hoy solo `db.create_all()`).
- **Límite de login global** (Redis) si se escala a varias réplicas.
- Recuperación de contraseña por correo y login con redes sociales (alcance 3.1 del proyecto).
