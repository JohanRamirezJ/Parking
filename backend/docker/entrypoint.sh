#!/usr/bin/env bash
# Arranque del backend: espera a PostgreSQL, prepara la BD y lanza gunicorn.
set -euo pipefail

echo "[smartpark] Esperando la base de datos..."
python - <<'PY'
import os, sys, time
from sqlalchemy import create_engine, text
url = os.environ.get("DATABASE_URL", "sqlite:///smartpark.db")
for intento in range(60):
    try:
        with create_engine(url).connect() as c:
            c.execute(text("SELECT 1"))
        print("[smartpark] Base de datos lista")
        sys.exit(0)
    except Exception as e:
        print(f"[smartpark] ...aún no responde ({type(e).__name__}), reintento {intento + 1}/60")
        time.sleep(2)
sys.exit("[smartpark] La base de datos no respondió en 120 s")
PY

# Crea tablas y aplica las columnas nuevas (idempotente)
flask init-db

if [[ "${SEED_DEMO:-0}" == "1" ]]; then
  flask seed
fi

if [[ -n "${ADMIN_EMAIL:-}" && -n "${ADMIN_PASSWORD:-}" ]]; then
  flask crear-admin "$ADMIN_EMAIL" "$ADMIN_PASSWORD" --nombre "${ADMIN_NOMBRE:-Administrador}"
fi

echo "[smartpark] API en http://0.0.0.0:5000  ·  panel en /admin"
exec gunicorn --preload -w "${GUNICORN_WORKERS:-3}" -b 0.0.0.0:5000 --access-logfile - wsgi:app
