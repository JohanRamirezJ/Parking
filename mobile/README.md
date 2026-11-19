# SmartPark — App móvil (Flutter)

App para conductores: buscar destino, ver parqueaderos en el mapa, comparar tarifas, calificar y preguntar al asistente.

## Ejecutar en un teléfono Android sin USB (misma Wi-Fi)

El teléfono y el computador deben estar conectados a la misma Wi-Fi. El computador debe permanecer encendido y ejecutar el backend. Esta configuración es para desarrollo/pruebas en una red de confianza, no para publicar la API por Internet. Si la red de invitados bloquea la comunicación entre dispositivos, usa un hotspot personal.

### Opción A: backend en Docker (PostgreSQL)

Desde la raíz del proyecto, inicia Docker Desktop y levanta la base y el backend:

```powershell
docker compose up -d --build
docker compose ps
```

La primera vez (o después de cambiar código del backend) se necesita `--build`. En los siguientes inicios puedes ejecutar `docker compose up -d`; también sirve para volver a iniciar los contenedores detenidos y no reconstruye la imagen. Para detenerlos sin borrar contenedores ni datos:

```powershell
docker compose stop
docker compose up -d
```

Docker Desktop debe permanecer ejecutándose mientras uses la app. La base PostgreSQL se conserva en el volumen `pgdata`; no uses `docker compose down -v` si quieres conservarla. El botón Start de Docker Desktop también puede iniciar los contenedores existentes. El script `iniciar-smartpark.bat` ejecuta `docker compose up -d --build`.

Obtén la IP Wi-Fi del computador con `ipconfig` o con este comando de PowerShell:

```powershell
Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -notlike "127.*" -and $_.IPAddress -notlike "169.254.*" }
```

Usa la IP del computador y el puerto publicado por Compose (por defecto `5000`; puede cambiarse con `API_PORT` en el `.env` raíz). Si el firewall de Windows lo bloquea, permite el puerto de la API solo desde la IP Wi-Fi del teléfono, como en la regla del paso 3 de la opción SQLite. Puedes comprobar la conexión abriendo en el teléfono `http://IP_DEL_COMPUTADOR:5000/api/salud`.

Desde `mobile`, apunta Flutter a la IP del computador, no a `localhost`, `127.0.0.1` ni `10.0.2.2`:

```powershell
flutter run --dart-define=API_URL=http://192.168.0.10:5000
```

Para instalar un APK, usa la misma dirección al compilar:

```powershell
flutter build apk --debug --target-platform android-arm64 --split-per-abi --dart-define=API_URL=http://192.168.0.10:5000
```

Reemplaza `192.168.0.10` por la IP real del computador y conserva el puerto configurado. Los mapas y las búsquedas de lugares también requieren que el teléfono tenga acceso a Internet.

### Opción B: backend local con SQLite (sin Docker)

Los siguientes pasos crean un entorno Python local y ejecutan Flask directamente; esta opción usa SQLite en `backend` y no la base PostgreSQL de Docker.

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

En Mapa, los iconos del borde derecho permiten buscar **cerca de mí** o activar **Desde mi ubicación**; al seleccionarlos, la app muestra una descripción breve. También puedes escribir un lugar para buscar a su alrededor o usarlo como destino. En el modo trayecto, «Ver costos» abre Recomendación inteligente, que estima el viaje desde el GPS hasta cada parqueadero, la caminata al destino y el costo de gasolina, rodamiento y parqueo. Son aproximaciones en línea recta con un factor urbano; no usan rutas ni tráfico en tiempo real.

## Pruebas

```bash
flutter test
flutter analyze
```
