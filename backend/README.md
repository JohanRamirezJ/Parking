# SmartPark — Backend (Flask)

API REST para la app móvil + panel web de administración (Jinja2), en el mismo servicio.

## Arranque rápido (SQLite, sin Docker)

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
export FLASK_APP=wsgi                                # Windows PowerShell: $env:FLASK_APP="wsgi"
flask seed                                           # datos de ejemplo (opcional)
python wsgi.py                                       # http://localhost:5000
```

- Panel admin: http://localhost:5000/admin — con datos demo: `admin@smartpark.co` / `admin12345`
- Crear un admin real: `flask crear-admin correo@dominio.co "ClaveSegura123" --nombre "Nombre"`

## Con Docker (PostgreSQL)

Ver la sección "Levantar todo con Docker" del [README principal](../README.md). La imagen se construye sobre **Ubuntu 24.04** y el `docker/entrypoint.sh` espera a la base de datos, ejecuta `flask init-db`, carga los datos demo si `SEED_DEMO=1`, crea el admin de `ADMIN_EMAIL`/`ADMIN_PASSWORD` si se definen y arranca gunicorn.

## Pruebas

```bash
python -m pytest -q
```

54 pruebas funcionales trazadas a las historias de usuario y RF del documento de especificaciones.

## Endpoints

| Método | Ruta | Auth | Descripción |
|---|---|---|---|
| GET | `/api/salud` | — | Healthcheck |
| POST | `/api/auth/registro` | — | HU 1 · `{email, password, nombre}` → `{token, usuario}` |
| POST | `/api/auth/login` | — | HU 2 · `{email, password}` → `{token, usuario}` |
| GET / PUT | `/api/me` | JWT | HU 3 · perfil (`nombre`, `telefono`, `foto_perfil`, `password`) |
| GET | `/api/me/visitas` | JWT | Historial de visitas |
| GET | `/api/me/notificaciones` | JWT | Avisos de moderación (RF-10) |
| GET | `/api/geocodificar?q=` | — | HU 5 · destino → coordenadas (Nominatim + catálogo local) |
| GET | `/api/parqueaderos?lat&lon&radio&orden&tarifa_min&tarifa_max&abiertos` | opcional | HU 6–9, 12 · búsqueda por proximidad |
| GET | `/api/parqueaderos/<id>` | — | Detalle |
| GET | `/api/parqueaderos/<id>/resenas` | — | HU 11 · reseñas (más recientes primero) |
| POST | `/api/parqueaderos/<id>/visitas` | JWT | Marcar como visitado |
| POST | `/api/parqueaderos/<id>/resenas` | JWT | HU 10 · `{calificacion 1-5, calificacion_seguridad? 1-5, comentario}` (requiere visita) |
| POST | `/api/resenas/<id>/reportar` | JWT | `{motivo}` |
| POST | `/api/recomendaciones` | opcional | **Módulo de IA** · `{destino {lat,lon} \| destino_texto, origen?, horas, perfil?, pesos?, vehiculo?, radio?, hora_llegada?}` → ranking con puntaje 0–100, desglose y justificación |
| GET | `/api/recomendaciones/perfiles` | — | Criterios, perfiles de pesos y supuestos por defecto |
| GET / PUT | `/api/me/preferencias` | JWT | Pesos y vehículo guardados del usuario |
| POST | `/api/chat` | JWT | RF-12 · `{mensaje, lat?, lon?}` → recomendación (usa el módulo de IA) |
| GET | `/api/chat/historial` | JWT | Últimas consultas |

Errores siempre como `{"error": {"codigo": "...", "mensaje": "..."}}`. Token inválido/expirado → `401` (`token_invalido` / `token_expirado`).

`radio` en metros: 200 – 5000 (defecto 1000). `orden`: `distancia` | `tarifa` | `calificacion`. Sin tarifa → `tarifa_hora: null` (la app muestra "Tarifa no disponible").

## Panel admin

- **Dashboard**: KPIs (cobertura de tarifas vs meta 90 %, cobertura de reseñas vs meta 30 %, búsquedas, consultas IA), gráficas con filtro por fecha y estado vacío, exportación CSV (Excel) e impresión a PDF.
- **Directorio**: CRUD con mapa para ubicar el punto; no guarda sin nombre/dirección/ubicación/tarifa ni con coordenadas fuera de Bogotá. Cambiar una tarifa conserva la anterior como no vigente.
- **Reportes**: advertir, suspender (rechaza la reseña y recalcula el promedio) o descartar; el usuario recibe una notificación.
- **Auditoría**: cada cambio queda con admin, fecha, IP y datos antes/después.

## Módulo de IA: recomendación multicriterio

Para cada parqueadero cercano calcula un puntaje integral 0–100 que combina **gasolina, rodamiento, tiempo, distancia, seguridad y precio**, cada uno con un peso de 0 a 10 que el usuario ajusta (perfiles: equilibrado, de noche/seguridad, muchas horas/precio, tengo afán, cuidar el carro). Devuelve el desglose de cada criterio y una justificación en texto. Fórmula, supuestos y reglas: [`docs/modelo-ia.md`](../docs/modelo-ia.md). Código: `app/services/recomendador.py`.

```bash
curl -X POST localhost:5000/api/recomendaciones -H 'Content-Type: application/json' \
  -d '{"destino_texto":"Parque de la 93","horas":5,"perfil":"seguridad"}'
```

## Chat IA

La recomendación sale siempre del directorio (no se inventan parqueaderos). Se interpreta la consulta (perfil: "de noche" → seguridad, "barato"/"todo el día" → precio, "tengo afán" → tiempo; horas "por 3 horas"; presupuesto "menos de 6 mil"; destino "cerca del …"), se puntúan los candidatos reales con el módulo de IA y:
- sin `OPENAI_API_KEY` → respuesta con plantilla;
- con `OPENAI_API_KEY` → el modelo redacta la respuesta usando solo esos candidatos.

## Pendiente / decisiones abiertas

- El documento menciona MongoDB en una sección y SQLAlchemy + PostgreSQL en otra; se implementó **SQLAlchemy (SQLite dev / PostgreSQL prod)** porque es la que tiene el modelo físico definido.
- Redis (caché) no se incluyó aún: con el pre-filtro por caja envolvente la búsqueda responde en milisegundos; conviene medir en las pruebas de carga antes de añadirlo.
- Migraciones: hoy se usa `db.create_all()` más una migración ligera que agrega las columnas nuevas del módulo de IA a bases existentes. Antes de producción, agregar Flask-Migrate/Alembic.
- Recuperación de contraseña por correo y login con redes sociales (alcance 3.1) aún no implementados.
- Los datos de `flask seed` son **ficticios** (nombres con "(demo)"); el directorio real se carga desde el panel.
