# Manual del panel de administración

Dirección: `http://<host>:5000/admin` (en producción, siempre por HTTPS). Solo entran usuarios con rol administrador.

## Acceso

- **Crear un administrador:** `flask crear-admin correo@dominio.co "ClaveSegura123" --nombre "Nombre"`
  (con Docker: `docker compose exec api flask crear-admin ...`). Si el correo ya existe, lo promueve a administrador.
- Con los datos de ejemplo (`flask seed`) existe `admin@smartpark.co` / `admin12345`. **Cámbiala o elimínala** antes de
  publicar el sistema.
- Tras 10 intentos fallidos con el mismo correo desde la misma IP, el acceso se bloquea unos 15 minutos.
- "Salir" cierra la sesión. La sesión dura 8 horas.

## Dashboard (`/admin/`)

Indicadores del periodo elegido (filtro **Desde / Hasta**, por defecto los últimos 30 días):

| Indicador | Qué mide |
|---|---|
| Parqueaderos activos | Registros visibles en la app |
| Usuarios registrados | Cuentas que no son de administrador |
| Búsquedas / Reseñas / Consultas al chat IA | Actividad en el periodo |
| Con tarifa registrada | % de parqueaderos con alguna tarifa. **Meta: 90 %** |
| Con al menos una reseña | % de parqueaderos con reseñas. **Meta: 30 %** |
| Tarifa promedio por hora | Promedio de las tarifas por hora vigentes |
| Reportes pendientes | Enlace directo a la moderación |

Gráficas: búsquedas por día, distribución de calificaciones, distribución de tarifas por rango, ocupación estimada por
parqueadero y los más recomendados por el chat. Si no hay datos en el periodo, cada gráfica muestra un estado vacío.

**Exportar:** el botón **Exportar Excel (CSV)** descarga un **CSV** (`;` como separador, UTF-8 con BOM, abre bien en Excel) con los
indicadores y el listado de parqueaderos. Para **PDF** usa el botón **Imprimir / PDF** y elige "Guardar como PDF".

## Directorio de parqueaderos (`/admin/parqueaderos`)

- **Nuevo / Editar:** formulario con mapa; haz clic en el mapa para fijar latitud y longitud.
- **No se guarda** si falta nombre, dirección o ubicación, si las coordenadas están fuera de Bogotá, si no hay al menos
  una tarifa (hora o día), si un valor es inválido o si los cupos disponibles superan la capacidad total. El formulario
  marca los campos con error y conserva lo escrito.
- **Cambiar una tarifa** no pisa la anterior: queda como histórico no vigente.
- **Desactivar / Activar:** oculta o muestra el parqueadero en la app sin borrar datos (recomendado).
- **Eliminar:** borra el parqueadero con sus tarifas, reseñas y visitas. No se puede deshacer.

> Los datos de `flask seed` son ficticios (llevan "(demo)" en el nombre). El directorio real debe cargarse desde aquí y
> verificarse antes de publicar.

## Reportes de usuarios (`/admin/reportes`)

Lista los reportes de reseñas (filtro por estado; por defecto, pendientes). Para cada uno:

| Acción | Efecto |
|---|---|
| **Advertir** | Suma una advertencia al usuario reportado, cierra el reporte y le envía una notificación |
| **Suspender** | Desactiva la cuenta, rechaza la reseña (sale de la app y del promedio) y notifica |
| **Descartar** | Cierra el reporte sin consecuencias |

Se puede escribir una observación; si la acción notifica, la nota se incluye en el mensaje al usuario.

## Auditoría (`/admin/auditoria`)

Historial de cambios con administrador, fecha, IP y los datos antes/después de cada alta, edición, baja y acción de
moderación. No se puede editar desde el panel.
