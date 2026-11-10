# Módulo de IA de SmartPark: recomendación multicriterio personalizada

## Problema

Elegir parqueadero obliga a balancear factores que compiten: el más barato puede quedar más lejos, gastar más gasolina y rodamiento, tomar más tiempo o ser menos seguro. Comparar esto a mano es lento y casi siempre se reduce a un solo criterio (precio o cercanía). El módulo calcula para cada parqueadero cercano un **puntaje integral** que combina todos los factores con **pesos de importancia que el usuario ajusta** según su prioridad del momento.

## Criterios

| Criterio | Cómo se calcula el valor | Mejor si… |
|---|---|---|
| **Gasolina** | km manejados ÷ rendimiento (km/galón) × precio del galón | menor |
| **Rodamiento** | km manejados × costo de desgaste por km (llantas, frenos, mantenimiento) | menor |
| **Tiempo** | minutos manejando (km ÷ velocidad urbana) + minutos caminando al destino | menor |
| **Distancia** | metros a pie entre el parqueadero y el destino | menor |
| **Seguridad** | promedio de la calificación de seguridad (1–5) que dan los usuarios en sus reseñas | mayor |
| **Precio** | tarifa por hora × horas de estadía, con tope en la tarifa diaria si existe | menor |

- *km manejados*: desde el origen del usuario hasta el parqueadero. Si no se envía origen, se usa el desvío desde el destino hasta el parqueadero.
- Las distancias en línea recta se multiplican por un **factor de ruta urbana de 1,3** para aproximar el recorrido real por calles.

## Fórmula

1. **Normalización** de cada criterio a un puntaje *s* entre 0 (peor opción) y 1 (mejor opción), comparando contra las demás opciones de la búsqueda:

   - criterio de costo: `s = 1 − (v − mín) / máx(máx − mín, umbral)`
   - criterio de beneficio (seguridad): `s = 1 − (máx − v) / máx(máx − mín, umbral)`

   El **umbral** evita que diferencias insignificantes se conviertan en "la mejor contra la peor": $500 en gasolina y rodamiento, 3 min, 150 m, 1 estrella y $1.000 en precio.

2. **Puntaje integral** (0–100):

   `puntaje = 100 × Σ (wᵢ × sᵢ) / Σ wᵢ`

   donde *wᵢ* es el peso del criterio (0 a 10). Cada criterio aporta `100 × wᵢ × sᵢ / Σw` puntos, y ese aporte se le muestra al usuario en el desglose.

3. **Ordenamiento** de mayor a menor puntaje. Si hay empate, gana la opción con menor tiempo.

## Perfiles de pesos (el usuario puede ajustar cualquiera)

| Perfil | Gasolina | Rodamiento | Tiempo | Distancia | Seguridad | Precio |
|---|---|---|---|---|---|---|
| Equilibrado (defecto) | 2 | 1 | 3 | 3 | 3 | 3 |
| De noche / seguridad | 1 | 1 | 2 | 3 | **8** | 2 |
| Muchas horas / precio | 1 | 1 | 1 | 2 | 3 | **8** |
| Tengo afán | 1 | 1 | **8** | 4 | 2 | 2 |
| Cuidar el carro | **6** | **5** | 2 | 2 | 3 | 3 |

**Prioridad de pesos:** primero los pesos enviados en la petición, después el perfil enviado, luego los pesos guardados por el usuario (`PUT /api/me/preferencias`) y, por último, el perfil Equilibrado.

## Reglas de negocio

- **Horario:** se excluyen los parqueaderos cerrados a la hora estimada de llegada (se pueden incluir con `incluir_cerrados`). Si el parqueadero cierra antes de terminar la estadía, se agrega una alerta.
- **Sin tarifa:** se asume la tarifa más alta de las opciones (criterio conservador), el criterio se marca `estimado` y se avisa al usuario.
- **Sin calificación de seguridad:** se usa la calificación general del parqueadero. Si tampoco la hay, se usa el promedio de la zona, marcado como estimado.
- **0 cupos estimados:** se muestra la alerta "posiblemente lleno".

## Justificación

Cada opción trae un texto generado a partir de sus datos. Incluye:

- el puntaje;
- los dos criterios que más aportan, si de verdad la diferencian de las demás y no son estimados;
- su punto débil;
- una comparación con la siguiente opción en costo total (parqueo + gasolina + rodamiento) y en tiempo.

Ejemplo:

> Puntaje 91/100. Destaca en precio ($15.000) y seguridad (5.0★). Frente a Parqueadero 24 Horas Andino, cuesta $12.265 menos en total y toma 5 min más.

## Supuestos (configurables por variable de entorno o por usuario)

| Parámetro | Valor por defecto | Fuente |
|---|---|---|
| Precio del galón (corriente, Bogotá) | $16.331 | Precio de referencia nov. 2026, [El Colombiano](https://www.elcolombiano.com/negocios/precio-gasolina-colombia-noviembre-2026-galon-ciudades-GD43042206) |
| Rendimiento | 30 km/galón | Supuesto: carro particular en ciudad |
| Costo de rodamiento | $250/km | Supuesto del equipo: debe validarse |
| Velocidad urbana | 18 km/h | Supuesto: promedio de tráfico en Bogotá |
| Velocidad a pie | 4,5 km/h | Supuesto estándar |
| Factor de ruta urbana | 1,3 | Supuesto: calles vs. línea recta |

Cada usuario puede reemplazar el precio del galón, el rendimiento y el costo por km con los datos de su propio carro.

## Integración

- `POST /api/recomendaciones`: ranking con puntaje, desglose por criterio, alertas, justificación y supuestos usados.
- `GET /api/recomendaciones/perfiles`: criterios, perfiles y valores por defecto, para dibujar los controles de la app.
- `GET` / `PUT /api/me/preferencias`: pesos y vehículo guardados por el usuario.
- **Chat (`POST /api/chat`)**: interpreta la consulta y elige el perfil y las horas:
  - "de noche", "seguro" → perfil Seguridad;
  - "barato", "todo el día" → perfil Precio;
  - "tengo afán" → perfil Tiempo;
  - "gasolina" → perfil Cuidar el carro.

  Después recomienda con este mismo modelo. Si hay `OPENAI_API_KEY`, el modelo de lenguaje solo redacta la respuesta a partir del ranking ya calculado y nunca inventa opciones.
- **App**:
  - pestaña **Recomendar**: perfiles, deslizadores de 0 a 10 por criterio, horas de estadía y resultados con desglose;
  - en la reseña se puede calificar la seguridad.

## Limitaciones y siguientes pasos

- Distancias y tiempos aproximados (línea recta × 1,3 y velocidad promedio). Siguiente paso: usar un servicio de rutas, como OSRM u OpenRouteService, para obtener la distancia y el tiempo reales con tráfico.
- La normalización es relativa a las opciones de cada búsqueda: un 100/100 significa "la mejor de las disponibles", no "perfecta".
- El costo de rodamiento y la velocidad urbana son supuestos que conviene validar con datos reales.
- Evolución posible: aprender los pesos de cada usuario a partir de las opciones que termina eligiendo (visitas registradas).
