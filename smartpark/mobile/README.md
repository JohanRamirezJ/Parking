# SmartPark — App móvil (Flutter)

App para conductores: buscar destino, ver parqueaderos en el mapa, comparar tarifas, calificar y preguntar al asistente.

## Primer arranque

Esta carpeta trae el código (`lib/`, `test/`, `pubspec.yaml`) pero no las carpetas de plataforma. Genéralas una vez:

```bash
cd mobile
flutter create . --org co.smartpark --project-name smartpark --platforms=android,ios
flutter pub get
```

### Permisos (obligatorio después de `flutter create`)

**Android** — `android/app/src/main/AndroidManifest.xml`, dentro de `<manifest>`:

```xml
<uses-permission android:name="android.permission.INTERNET"/>
<uses-permission android:name="android.permission.ACCESS_FINE_LOCATION"/>
<uses-permission android:name="android.permission.ACCESS_COARSE_LOCATION"/>
```

y en la etiqueta `<application ...>` agrega `android:usesCleartextTraffic="true"` (solo desarrollo, para llamar al backend por `http://`).

**iOS** — `ios/Runner/Info.plist`:

```xml
<key>NSLocationWhenInUseUsageDescription</key>
<string>SmartPark usa tu ubicación para mostrarte parqueaderos cercanos.</string>
```

## Ejecutar

Con el backend corriendo (ver `../backend/README.md`):

```bash
# Emulador Android (10.0.2.2 = localhost del PC) — valor por defecto
flutter run

# Celular físico en la misma red Wi-Fi: usa la IP del PC
flutter run --dart-define=API_URL=http://192.168.1.50:5000
```

Usuario de prueba (si cargaste los datos demo): `demo1@smartpark.co` / `demo12345`.

## Estructura

```
lib/
  main.dart              arranque, providers, sesión → login o home
  config.dart            URL del API y límites de radio
  models.dart            Usuario, Parqueadero, Resena, Destino
  formato.dart           formato COP, distancias, "Tarifa no disponible"
  services/api.dart      cliente REST + JWT + errores controlados (401 → login)
  state/sesion.dart      token persistido (shared_preferences)
  state/busqueda.dart    ubicación, destino, radio, orden, filtros, resultados
  screens/
    login_screen.dart    HU 1, 2
    home_screen.dart     navegación inferior
    mapa_screen.dart     HU 4, 5, 6, 7 (OpenStreetMap vía flutter_map, sin API key)
    lista_screen.dart    HU 8, 9
    detalle_screen.dart  HU 10, 11 + reportar reseña
    chat_screen.dart     RF-12 asistente IA
    perfil_screen.dart   HU 3 + notificaciones de moderación
```

Flujo de 3 pasos (RNF-03): escribir destino → ver mapa/lista comparativa → abrir detalle.

## Pruebas

```bash
flutter test
flutter analyze
```

> Nota: el código se escribió sin poder compilarlo en el entorno donde se generó (no había SDK de Flutter disponible). Corre `flutter analyze` al primer arranque y corrige cualquier detalle menor de versión de paquetes.
