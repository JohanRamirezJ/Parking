# SmartPark — App móvil (Flutter)

App para conductores: buscar destino, ver parqueaderos en el mapa, comparar tarifas, calificar y preguntar al asistente.

## Ejecutar en un teléfono Android sin USB (misma Wi-Fi)

El teléfono y el computador deben estar conectados a la misma Wi-Fi. El computador debe permanecer encendido y ejecutar el backend; la base SQLite y la API siguen estando en él. Esta configuración es para desarrollo/pruebas en una red de confianza, no para publicar la API por Internet.

1. Prepara el backend una vez, desde PowerShell:

   ```powershell
   cd backend
   python -m venv .venv
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   ```

2. Averigua las direcciones IPv4 del computador y del teléfono. En Windows:

   ```powershell
   Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -notlike "127.*" -and $_.IPAddress -notlike "169.254.*" }
   ```

   En Android, consulta los detalles de la red Wi-Fi en Ajustes. Ambos dispositivos deben tener direcciones de la misma red. Sustituye `192.168.0.10` y `192.168.0.5` en los ejemplos por la IP del computador y la IP actual del teléfono.

3. En PowerShell **como administrador**, permite solo al teléfono acceder a la API y al servidor temporal de descarga del APK:

   ```powershell
   New-NetFirewallRule -DisplayName "SmartPark API telefono" -Direction Inbound -Action Allow -Protocol TCP -LocalPort 5000 -RemoteAddress 192.168.0.5 -Profile Any
   New-NetFirewallRule -DisplayName "SmartPark APK telefono" -Direction Inbound -Action Allow -Protocol TCP -LocalPort 8000 -RemoteAddress 192.168.0.5 -Profile Any
   ```

   Limita las reglas a la IP del teléfono y elimínalas al terminar las pruebas:

   ```powershell
   Remove-NetFirewallRule -DisplayName "SmartPark API telefono"
   Remove-NetFirewallRule -DisplayName "SmartPark APK telefono"
   ```

4. Arranca el backend dejando abierta la ventana de consola:

   ```powershell
   .\iniciar-smartpark-wifi.bat
   ```

5. Compila el APK de depuración para el teléfono (Android ARM64), reemplazando la IP por la del computador:

   ```powershell
   cd mobile
   flutter build apk --debug --target-platform android-arm64 --split-per-abi --dart-define=API_URL=http://192.168.0.10:5000
   ```

6. En otra terminal, publica temporalmente el APK solo en la red local:

   ```powershell
   cd build\app\outputs\flutter-apk
   python -m http.server 8000 --bind 0.0.0.0
   ```

   En el teléfono, abre `http://192.168.0.10:8000/app-arm64-v8a-debug.apk` en el navegador, descarga e instala el archivo. Android puede pedir autorización para instalar aplicaciones desde ese navegador. Después de instalarlo, detén el servidor de archivos con `Ctrl+C`; la app seguirá usando el backend en `http://192.168.0.10:5000`.

Puedes arrancar el backend con doble clic en `iniciar-smartpark-wifi.bat`. Si cambia la IP del computador, recompila el APK con la nueva dirección. Si cambia la IP del teléfono, actualiza las reglas del firewall. La excepción HTTP sin cifrar se habilita solo en compilaciones de depuración; para producción hace falta HTTPS.

El backend usa SQLite local y no necesita Docker ni una clave de OpenAI para arrancar. Sin `OPENAI_API_KEY`, el chat responde mediante la plantilla/reglas del proyecto. Usuario demo: `demo1@smartpark.co` / `demo12345`.

### Cambiar de red Wi-Fi

Conecta el computador y el teléfono a la nueva red y ejecuta [`preparar-smartpark-wifi.bat`](../preparar-smartpark-wifi.bat) desde la raíz del proyecto. El asistente detecta la IP del computador, pide la IP Wi-Fi del teléfono, compila el APK con la dirección nueva, actualiza las reglas del firewall limitándolas a ese teléfono y a esa IP del computador, y deja activo el servidor temporal de descarga. Puede solicitar autorización de administrador para configurar el firewall.

Al terminar, ejecuta [`iniciar-smartpark-wifi.bat`](../iniciar-smartpark-wifi.bat) y abre desde el teléfono la URL que imprimió el asistente. Si la red Wi-Fi bloquea la comunicación entre dispositivos (aislamiento de clientes), usa un hotspot personal. Vuelve a ejecutar el asistente si cambia la IP del computador o del teléfono.

### Ejecutar con USB (alternativa de desarrollo)

Conecta el teléfono con **Depuración USB** activada, acepta la autorización RSA y usa `adb reverse tcp:5000 tcp:5000`. Luego ejecuta `flutter run --dart-define=API_URL=http://127.0.0.1:5000`.

Para iOS se necesita generar la plataforma en macOS, añadir el permiso de ubicación a `ios/Runner/Info.plist` y compilar desde Xcode.

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
    recomendar_screen.dart  Módulo de IA: perfiles, pesos 0–10, horas y ranking con desglose
    chat_screen.dart     RF-12 asistente IA
    perfil_screen.dart   HU 3 + notificaciones de moderación
```

Flujo de 3 pasos (RNF-03): escribir destino → ver mapa/lista comparativa → abrir detalle.

## Pruebas

```bash
flutter test
flutter analyze
```
