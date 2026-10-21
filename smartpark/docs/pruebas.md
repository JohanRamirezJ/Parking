# Pruebas

## Resumen

| Capa | Herramienta | Cantidad | Comando |
|---|---|---|---|
| Backend (API + panel + seguridad) | pytest | 37 | `cd backend && python -m pytest -q` |
| App móvil (modelos) | flutter_test | 1 archivo | `cd mobile && flutter test` |
| Estilo/errores estáticos de la app | flutter analyze | — | `cd mobile && flutter analyze` |

Las pruebas del backend usan una base SQLite en memoria (`TestConfig`), crean un conjunto de parqueaderos alrededor del
Hospital San Ignacio y no hacen llamadas de red (la geocodificación externa se desactiva en pruebas). Se ejecutan en cada
push y pull request mediante el workflow `.github/workflows/ci.yml`.

> Estado de la última ejecución local: **37 pruebas del backend aprobadas**. La app Flutter no pudo compilarse ni
> probarse en el entorno donde se escribió la documentación (no había SDK de Flutter); la verifica el job `mobile` del CI.

## Trazabilidad requisito → prueba

### API (`tests/test_api.py`)

| HU / RF | Prueba | Verifica |
|---|---|---|
| HU 1 · RF-01 | `test_registro_exitoso_devuelve_token` | Registro válido devuelve token y usuario |
| HU 1 | `test_registro_email_duplicado` | `409 email_duplicado` |
| HU 1 | `test_registro_formulario_incompleto` | `400` con detalle de los campos que faltan |
| HU 2 | `test_login_ok_y_credenciales_incorrectas` | Login correcto y `401` con clave mala |
| HU 3 · RF-02 | `test_editar_perfil_valido_e_invalido` | Edita datos válidos; con un formato inválido no guarda nada |
| HU 13 · RF-08 | `test_token_requerido_e_invalido` | `401 token_requerido` / `token_invalido` |
| HU 13 | `test_token_expirado` | `401 token_expirado` |
| HU 6, 7, 12 · RF-04 | `test_busqueda_por_radio_ordenada_por_distancia` | Solo dentro del radio, de más cerca a más lejos |
| HU 6 | `test_busqueda_sin_resultados_sugiere_ampliar` | Mensaje guía y `sugerir_ampliar_radio` |
| HU 7 | `test_radio_fuera_de_limites` | Radio < 200 m o > 5000 m rechazado |
| RF-04 | `test_fuera_de_bogota` | `400 fuera_de_cobertura` |
| HU 8 · RF-05 | `test_orden_por_tarifa_sin_tarifa_al_final` | Orden por precio; sin tarifa al final |
| HU 9 | `test_filtro_rango_tarifa` | Filtro por rango de tarifa |
| HU 10 · RF-06 | `test_no_puede_calificar_sin_visita` | `403 sin_visita` |
| HU 10, 11 | `test_resena_actualiza_promedio` | Reseña guardada, promedio recalculado, una por usuario |
| HU 10 | `test_calificacion_fuera_de_rango` | Calificación fuera de 1–5 rechazada |
| RF-12 | `test_chat_recomienda_el_mas_barato_cerca_de_destino` | Recomienda del directorio real según la consulta |
| RF-12 | `test_chat_sin_opciones_sugiere_ampliar` | Sin resultados: sugerencia en lugar de inventar |
| RF-12 | `test_chat_interpreta_presupuesto` | "menos de 6 mil" → tarifa máxima 6000 |
| HU 5 | `test_geocodificar_catalogo_local` | Destino conocido → coordenadas |

### Panel de administración (`tests/test_admin.py`)

| HU / RF | Prueba | Verifica |
|---|---|---|
| HU 14 · RF-09 | `test_requiere_login` | Sin sesión redirige al login |
| RF-09 | `test_usuario_normal_no_entra_al_panel` | Un usuario sin rol admin no accede |
| RF-11 | `test_dashboard_carga` | El dashboard responde con indicadores |
| RF-11 | `test_dashboard_estado_vacio_y_exportacion` | Estado vacío y exportación CSV |
| RF-13 | `test_crear_parqueadero_se_refleja_en_api_y_audita` | Alta visible en la API y registrada en auditoría |
| RF-13 | `test_no_guarda_sin_campos_obligatorios` | Validación de obligatorios |
| RF-13 · RNF-08 | `test_no_publica_coordenadas_fuera_de_bogota` | Coordenadas fuera de Bogotá rechazadas |
| RF-05, RF-13 | `test_editar_tarifa_conserva_historial` | La tarifa anterior queda como no vigente |
| RF-09 | `test_desactivar_oculta_de_la_app` | Un parqueadero desactivado no aparece en la app |
| Seguridad | `test_post_sin_csrf_rechazado` | POST sin token CSRF → `400` |
| RF-10 | `test_suspender_usuario_reportado_notifica` | Suspende, rechaza la reseña y notifica al usuario |

### Seguridad (`tests/test_seguridad.py`)

| Prueba | Verifica |
|---|---|
| `test_salud_y_cabeceras_de_seguridad` | Healthcheck y cabeceras `nosniff` / `DENY` |
| `test_login_api_se_bloquea_tras_demasiados_fallos` | `429 demasiados_intentos`, incluso con la clave correcta durante el bloqueo |
| `test_login_exitoso_reinicia_contador` | Un login correcto pone el contador en cero |
| `test_bloqueo_es_por_correo` | Bloquear un correo no afecta a otros |
| `test_login_admin_se_bloquea` | El mismo límite protege el login del panel |
| `test_produccion_exige_secret_key` | En producción sin `SECRET_KEY` la app no arranca |

## Cobertura que falta

- **Pruebas de carga** del requisito de respuesta < 2 s (la búsqueda está diseñada para cumplirlo, pero no se midió con
  miles de parqueaderos).
- **Pruebas de la app móvil**: solo hay pruebas de modelos; faltan pruebas de widgets y de integración con el API.
- **Chat con el modelo de lenguaje**: la ruta con `OPENAI_API_KEY` no se prueba automáticamente (requiere red y clave).
- **Migraciones** y pruebas contra PostgreSQL real (las pruebas usan SQLite).

## Prueba manual rápida de humo (después de desplegar)

1. `GET /api/salud` → `200`.
2. Registrar un usuario desde la app y volver a entrar.
3. Buscar con un destino ("Hospital San Ignacio") y comprobar mapa y lista.
4. Marcar un parqueadero como visitado y dejar una reseña; ver que cambia el promedio.
5. Preguntar al chat "parqueadero barato cerca del Andino".
6. Entrar a `/admin`, abrir el dashboard y crear/desactivar un parqueadero; revisar la auditoría.
