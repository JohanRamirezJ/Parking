# Referencia de la API REST

Base: `http://<host>:5000/api` · Formato: JSON UTF-8 · Autenticación: cabecera `Authorization: Bearer <token>`.

## Convenciones

**Errores.** Siempre con esta forma (RF-07):

```json
{ "error": { "codigo": "validacion", "mensaje": "Formulario incompleto o inválido",
             "detalles": { "password": "La contraseña debe tener al menos 8 caracteres" } } }
```

`detalles` solo aparece cuando hay errores por campo.

| HTTP | `codigo` | Cuándo |
|---|---|---|
| 400 | `validacion`, `json_invalido`, `parametro_faltante`, `parametro_invalido`, `radio_fuera_de_rango`, `fuera_de_cobertura` | Entrada inválida |
| 401 | `token_requerido`, `token_invalido`, `token_expirado`, `credenciales_invalidas` | Falta o falla la autenticación; la app debe volver al login |
| 403 | `cuenta_suspendida`, `sin_visita` | Cuenta suspendida o regla de negocio |
| 404 | `no_encontrado`, `destino_no_encontrado` | Recurso inexistente |
| 405 | `metodo_no_permitido` | Método HTTP incorrecto |
| 409 | `email_duplicado`, `reporte_duplicado` | Conflicto |
| 429 | `demasiados_intentos` | Demasiados logins fallidos (espera ~15 min) |
| 500 | `error_interno` | Error inesperado |

**Autenticación.** El token se obtiene en `registro` o `login`, vence a las 24 h (`JWT_EXP_MINUTES`) y se envía en cada
petición protegida. Columna **Auth** de las tablas: `—` pública · `JWT` obligatorio · `opcional` si se envía se valida.

## Resumen de endpoints

| Método | Ruta | Auth | HU / RF |
|---|---|---|---|
| GET | `/salud` | — | Healthcheck |
| POST | `/auth/registro` | — | HU 1 |
| POST | `/auth/login` | — | HU 2 |
| GET · PUT | `/me` | JWT | HU 3 |
| GET | `/me/visitas` | JWT | Historial |
| GET | `/me/notificaciones` | JWT | RF-10 |
| GET | `/geocodificar` | — | HU 5 |
| GET | `/parqueaderos` | opcional | HU 6–9, 12 |
| GET | `/parqueaderos/{id}` | — | Detalle |
| GET | `/parqueaderos/{id}/resenas` | — | HU 11 |
| POST | `/parqueaderos/{id}/visitas` | JWT | Marcar visitado |
| POST | `/parqueaderos/{id}/resenas` | JWT | HU 10 |
| POST | `/resenas/{id}/reportar` | JWT | Moderación |
| POST | `/chat` | JWT | RF-12 |
| GET | `/chat/historial` | JWT | RF-12 |

## Autenticación y perfil

### `POST /auth/registro` → `201`
```json
// petición
{ "email": "ana@correo.co", "password": "clave1234", "nombre": "Ana" }
// respuesta
{ "token": "eyJhbGciOi...", "usuario": { "id": 1, "email": "ana@correo.co", "nombre": "Ana",
  "telefono": null, "foto_perfil": null, "fecha_registro": "2026-10-21T10:00:00", "es_admin": false } }
```
Validaciones: correo con formato válido (≤100), contraseña ≥ 8 caracteres, nombre obligatorio. `409 email_duplicado`
si ya existe.

### `POST /auth/login` → `200`
Misma respuesta que el registro. `401 credenciales_invalidas`, `403 cuenta_suspendida` o `429 demasiados_intentos`.

### `GET /me` · `PUT /me`
`PUT` acepta cualquiera de: `nombre` (≤100), `telefono` (7–15 dígitos), `foto_perfil` (URL `http(s)`), `password` (≥ 8).
Si algún campo es inválido **no se guarda nada** y se responde `400` con `detalles`.

### `GET /me/visitas` · `GET /me/notificaciones`
Listas ordenadas de la más reciente a la más antigua. Las notificaciones son los avisos de moderación (advertencia o
suspensión) dirigidos al usuario.

## Destinos

### `GET /geocodificar?q=hospital san ignacio`
```json
{ "nombre": "Hospital Universitario San Ignacio", "latitud": 4.6283, "longitud": -74.0645, "fuente": "catalogo_local" }
```
`fuente`: `catalogo_local` o `nominatim`. `400 parametro_faltante` si `q` está vacío; `404 destino_no_encontrado`.

## Parqueaderos

### `GET /parqueaderos` — búsqueda por proximidad

| Parámetro | Obligatorio | Descripción |
|---|---|---|
| `lat`, `lon` | sí | Punto de búsqueda; debe estar en Bogotá |
| `radio` | no | Metros, 200–5000 (defecto 1000) |
| `orden` | no | `distancia` (defecto) · `tarifa` · `calificacion` |
| `tarifa_min`, `tarifa_max` | no | Rango de la tarifa por hora (excluye los que no tienen tarifa) |
| `abiertos` | no | `1` o `true`: solo los abiertos ahora |

```json
{ "total": 2, "radio_m": 1000.0, "orden": "distancia",
  "resultados": [ { "id": 7, "nombre": "Parqueadero Central", "direccion": "Cra 7 # 40-10",
    "latitud": 4.6290, "longitud": -74.0640, "horario_apertura": "06:00", "horario_cierre": "22:00",
    "abierto_ahora": true, "capacidad_total": 50, "capacidad_disponible_estimada": 10,
    "calificacion_promedio": 4.5, "total_resenas": 12, "imagen_url": null,
    "tarifa_hora": 5000.0, "tarifa_dia": 25000.0,
    "tarifas": [ { "tipo": "hora", "valor": 5000.0, "unidad": "hora", "fecha_actualizacion": "2026-10-01T09:00:00" } ],
    "distancia_m": 85 } ] }
```
- `tarifa_hora` / `tarifa_dia` en `null` = "Tarifa no disponible" (en `orden=tarifa` van al final).
- `abierto_ahora` es `null` si el parqueadero no tiene horario.
- Sin resultados: se agrega `mensaje` y `sugerir_ampliar_radio` (verdadero si el radio aún puede crecer).
- Cada búsqueda queda registrada para el dashboard.

### `GET /parqueaderos/{id}?lat=&lon=`
Detalle del parqueadero. Con `lat` y `lon` incluye `distancia_m`. `404` si no existe o está desactivado.

## Visitas y reseñas

### `POST /parqueaderos/{id}/visitas` → `201`
Cuerpo opcional: `{ "tarifa_pagada": 5000, "metodo_pago": "efectivo", "comentario_adicional": "..." }`.

### `GET /parqueaderos/{id}/resenas`
```json
{ "total": 1, "resenas": [ { "id": 3, "parqueadero_id": 7, "usuario": { "id": 1, "nombre": "Ana" },
  "calificacion": 5, "comentario": "Muy seguro", "fecha": "2026-10-20T18:30:00" } ] }
```
Más recientes primero. Sin reseñas: `total: 0` y `mensaje: "Aún sin reseñas"`.

### `POST /parqueaderos/{id}/resenas` → `201` (nueva) · `200` (actualiza la existente)
```json
// petición
{ "calificacion": 5, "comentario": "Muy seguro" }
// respuesta
{ "resena": { "id": 3, "...": "..." }, "calificacion_promedio": 4.5 }
```
Requiere una visita previa (`403 sin_visita`). `calificacion` entera de 1 a 5; comentario máx. 1000 caracteres.

### `POST /resenas/{id}/reportar` → `201`
`{ "motivo": "Lenguaje ofensivo", "evidencia": "opcional" }`. No se puede reportar la propia reseña, ni la misma dos veces
(`409 reporte_duplicado`).

## Asistente de IA

### `POST /chat`
```json
// petición (lat y lon opcionales: ubicación actual si el mensaje no nombra un lugar)
{ "mensaje": "parqueadero barato cerca del Hospital San Ignacio por menos de 6 mil", "lat": 4.6283, "lon": -74.0645 }
// respuesta
{ "respuesta": "Te recomiendo **Medio barato** (...): es la opción más económica cerca de ...",
  "parqueadero_recomendado": { "id": 2, "...": "..." }, "alternativas": [ { "...": "..." } ],
  "intencion": { "orden": "tarifa", "tarifa_max": 6000.0, "solo_abiertos": false, "radio_m": null,
                 "destino_texto": "hospital san ignacio" },
  "destino": { "nombre": "...", "latitud": 4.6283, "longitud": -74.0645 },
  "tiempo_respuesta_ms": 12 }
```
Máx. 500 caracteres. Si no hay ubicación ni lugar, la respuesta pregunta dónde; si no hay resultados, sugiere ampliar
el radio o el presupuesto y `parqueadero_recomendado` es `null`. Con `OPENAI_API_KEY` el texto lo redacta el modelo
usando solo los candidatos reales.

### `GET /chat/historial`
Últimas 50 consultas del usuario, de la más antigua a la más reciente.
