# Pruebas

El informe formal (para entrega) está en
[`Formulación_Proyectos/Informe de Pruebas Unitarias SmartPark.docx`](../Formulación_Proyectos/Informe%20de%20Pruebas%20Unitarias%20SmartPark.docx);
las pruebas de carga y estrés, en [`Informe Pruebas Carga y Estres SmartPark.pdf`](../Informe%20Pruebas%20Carga%20y%20Estres%20SmartPark.pdf).
Este documento es la guía técnica para ejecutarlas y mantenerlas.

## Resumen

| Capa | Herramienta | Casos | Comando |
|---|---|---|---|
| Backend: unitarias, funcionales, IA/OSM y seguridad | pytest | 186 | `cd backend && python -m pytest -q` |
| App móvil (modelos y pantallas) | flutter_test | 5 archivos | `cd mobile && flutter test` |
| Análisis estático de la app | flutter analyze | — | `cd mobile && flutter analyze` |

Las pruebas del backend usan SQLite en memoria por defecto y no hacen llamadas de red (la geocodificación externa se
desactiva en pruebas y Overpass, Gemini y OpenAI se simulan). Con `TEST_DATABASE_URL` la misma suite corre contra PostgreSQL:

```bash
TEST_DATABASE_URL=postgresql+psycopg://usuario:clave@host:5432/bd_pruebas python -m pytest -q
python -m pytest -q --cov=app --cov-report=term-missing     # con cobertura (requiere pytest-cov)
```

El CI (`.github/workflows/ci.yml`) las ejecuta en cada push y pull request: backend con SQLite y con PostgreSQL 16, imagen
Docker en modo producción y app Flutter.

## Archivos de pruebas del backend

| Archivo | Tipo | Casos | Qué cubre |
|---|---|---|---|
| `test_unit_validacion.py` | Unitaria | 49 | Correo, teléfono, horas y reglas del formulario de parqueaderos |
| `test_unit_modelos.py` | Unitaria | 28 | Contraseñas, horario, tarifas con historial, promedio de calificación y búsqueda por proximidad |
| `test_unit_geo.py` | Unitaria | 22 | Distancia Haversine, caja envolvente, límites de Bogotá y catálogo local de lugares |
| `test_api.py` | Funcional (API) | 30 | Registro, login, perfil, token, búsqueda, tarifas, reseñas, chat y geocodificación |
| `test_admin.py` | Funcional (panel) | 11 | Acceso, directorio, tarifas con historial, reportes, dashboard y CSRF |
| `test_recomendador.py` | IA multicriterio | 23 | Fórmula ponderada, gasolina, rodamiento, seguridad, horario de llegada y preferencias |
| `test_chat_llm.py` | IA / chat | 6 | Interpretación y redacción con Gemini/OpenAI, prioridad de proveedor y avisos de falla |
| `test_openstreetmap.py` | Integración OSM | 6 | Filtrado de privados, tarifa desconocida y alertas de Overpass |
| `test_seguridad.py` | Seguridad | 11 | Bloqueo de login (API y panel), cabeceras, claves de producción y cookie de sesión |

## Trazabilidad requisito → prueba

| HU / RF | Pruebas | Verifican |
|---|---|---|
| HU 1 · RF-01 | `test_registro_*` | Registro, correo duplicado, campos faltantes |
| HU 2 | `test_login_ok_y_credenciales_incorrectas` | Inicio de sesión correcto e incorrecto |
| HU 3 · RF-02 | `test_editar_perfil_valido_e_invalido` | Edición de perfil sin guardar datos inválidos |
| HU 13 · RF-08 | `test_token_requerido_e_invalido`, `test_token_expirado` | Autenticación con token y su vencimiento |
| HU 6, 7, 12 · RF-04 | `test_busqueda_*`, `test_radio_fuera_de_limites`, `test_fuera_de_bogota`, `test_unit_geo.py` | Búsqueda por radio, límites y cobertura |
| HU 8, 9 · RF-05 | `test_orden_por_tarifa_sin_tarifa_al_final`, `test_filtro_rango_tarifa` | Comparación y filtro de tarifas |
| HU 10, 11 · RF-06 | `test_no_puede_calificar_sin_visita`, `test_resena_actualiza_promedio`, `test_calificacion_fuera_de_rango` | Reseñas solo con visita y promedio actualizado |
| RF-12 | `test_chat_*` (`test_api.py`), `test_chat_llm.py`, `test_openstreetmap.py` | Chat con IA, OSM, respaldo local y avisos |
| Módulo de IA | `test_recomendador.py` | Puntaje multicriterio y personalización |
| RF-09, RF-10, RF-11, RF-13 | `test_admin.py` | Panel: directorio, moderación, dashboard |
| RF-05, RF-13 (reglas) | `test_unit_validacion.py`, `test_unit_modelos.py` | Validación de datos, tarifas y horario |
| Seguridad (RNF) | `test_seguridad.py`, `test_post_sin_csrf_rechazado` | Fuerza bruta, CSRF, cabeceras y configuración |

## Cómo agregar pruebas

- **Unitaria** (una función o regla): crea `tests/test_unit_<modulo>.py`. Usa el fixture `app` solo si la función necesita
  el contexto de Flask (por ejemplo `en_bogota`). Para objetos del modelo sin guardar, declara explícitamente los campos con
  valor por defecto de la columna (`vigente=True`): el valor por defecto solo se aplica al insertar en la base.
- **Funcional** (un endpoint): usa los fixtures `client`, `auth` (token) y los datos de `conftest.py`.
- Servicios externos (Overpass, Gemini, OpenAI): simúlalos con `monkeypatch`; las pruebas no deben depender de internet.
- Una prueba nueva debe fallar si rompes la regla que cubre: compruébalo cambiando el código a propósito.

## Cobertura que falta

- **App móvil:** hay pruebas de modelos y pantallas, pero faltan de integración con el API.
- **Chat con modelos reales:** la ruta con claves reales de Gemini/OpenAI no se prueba automáticamente.
- **Carga y estrés:** ver el informe de carga y estrés; no forman parte de la suite automática.
- `seed.py` (datos de ejemplo) y las ramas de error de `errors.py`, `admin` y `chat` tienen cobertura baja.

## Prueba manual rápida de humo (después de desplegar)

1. `GET /api/salud` → `200`.
2. Registrar un usuario desde la app y volver a entrar.
3. Buscar con un destino ("Hospital San Ignacio") y comprobar mapa y lista.
4. Marcar un parqueadero como visitado y dejar una reseña; ver que cambia el promedio.
5. Preguntar al chat "parqueadero barato cerca del Andino" y abrir *Recomendar* con el mismo destino.
6. Entrar a `/admin`, abrir el dashboard y crear/desactivar un parqueadero; revisar la auditoría.
