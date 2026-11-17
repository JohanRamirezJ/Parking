$ErrorActionPreference = 'Stop'

function Esperar-Cierre {
    try { Read-Host 'Presiona Enter para cerrar esta ventana' | Out-Null } catch {}
}

$identidad = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identidad)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    try {
        $argumentos = '-NoProfile -ExecutionPolicy Bypass -File "{0}"' -f $PSCommandPath
        $elevado = Start-Process -FilePath 'powershell.exe' -Verb RunAs -ArgumentList $argumentos -Wait -PassThru
        exit $elevado.ExitCode
    } catch {
        Write-Host '[SmartPark] Se necesitan permisos de administrador para configurar el firewall.' -ForegroundColor Red
        Esperar-Cierre
        exit 1
    }
}

try {
    $raiz = Split-Path -Parent $PSCommandPath
    $rutasPredeterminadas = @(Get-NetRoute -AddressFamily IPv4 -DestinationPrefix '0.0.0.0/0' |
        Sort-Object RouteMetric)
    $interfazPredeterminada = if ($rutasPredeterminadas.Count) {
        $rutasPredeterminadas[0].InterfaceIndex
    } else {
        -1
    }
    $direcciones = @(Get-NetIPAddress -AddressFamily IPv4 -AddressState Preferred |
        Where-Object { $_.IPAddress -notmatch '^(127\.|169\.254\.)' } |
        ForEach-Object {
            [pscustomobject]@{
                Interfaz = $_.InterfaceAlias
                Indice = $_.InterfaceIndex
                IP = $_.IPAddress
                Prefijo = $_.PrefixLength
            }
        } |
        Sort-Object @{ Expression = { if ($_.Indice -eq $interfazPredeterminada) { 0 } else { 1 } } },
                    Interfaz, IP)

    if (-not $direcciones.Count) {
        throw 'No encontré una dirección IPv4 activa. Conecta el computador a la Wi-Fi e inténtalo otra vez.'
    }

    Write-Host 'Direcciones disponibles del computador:'
    for ($i = 0; $i -lt $direcciones.Count; $i++) {
        Write-Host ('  {0}. {1} - {2}' -f ($i + 1), $direcciones[$i].Interfaz, $direcciones[$i].IP)
    }

    $seleccionPredeterminada = 1
    for ($i = 0; $i -lt $direcciones.Count; $i++) {
        if ($direcciones[$i].Indice -eq $interfazPredeterminada) {
            $seleccionPredeterminada = $i + 1
            break
        }
    }
    if ($direcciones.Count -eq 1) {
        $seleccion = 1
    } else {
        $entrada = Read-Host ("Elige la IP del computador en la misma red del teléfono [Enter={0}]" -f $seleccionPredeterminada)
        if ([string]::IsNullOrWhiteSpace($entrada)) {
            $seleccion = $seleccionPredeterminada
        } elseif ($entrada -match '^\d+$' -and [int]$entrada -ge 1 -and [int]$entrada -le $direcciones.Count) {
            $seleccion = [int]$entrada
        } else {
            throw 'La selección de dirección no es válida.'
        }
    }
    $direccionPC = $direcciones[$seleccion - 1]

    $ipTelefono = (Read-Host 'IP IPv4 del teléfono en esta misma Wi-Fi (Ajustes > Wi-Fi)').Trim()
    $octetos = $ipTelefono.Split('.')
    if ($octetos.Count -ne 4) {
        throw 'La IP del teléfono no tiene formato IPv4.'
    }
    foreach ($octeto in $octetos) {
        $numero = 0
        if (-not [int]::TryParse($octeto, [ref]$numero) -or $numero -lt 0 -or $numero -gt 255) {
            throw 'La IP del teléfono no es una dirección IPv4 válida.'
        }
    }
    if ($ipTelefono -match '^(0\.|127\.|169\.254\.)') {
        throw 'La IP del teléfono no parece ser una dirección Wi-Fi utilizable.'
    }

    $urlAPI = 'http://{0}:5000' -f $direccionPC.IP
    $directorioAPK = Join-Path $raiz 'mobile\build\app\outputs\flutter-apk'
    $flutter = Get-Command flutter -ErrorAction Stop

    Write-Host ''
    Write-Host ('[SmartPark] Compilando APK para {0}...' -f $urlAPI)
    Push-Location (Join-Path $raiz 'mobile')
    try {
        & $flutter.Source build apk --debug --target-platform android-arm64 --split-per-abi "--dart-define=API_URL=$urlAPI"
        if ($LASTEXITCODE -ne 0) {
            throw 'Falló la compilación del APK.'
        }
    } finally {
        Pop-Location
    }

    $archivoAPK = Join-Path $directorioAPK 'app-arm64-v8a-debug.apk'
    if (-not (Test-Path $archivoAPK)) {
        throw 'La compilación terminó, pero no encontré el APK esperado.'
    }

    foreach ($regla in @(
        @{ Nombre = 'SmartPark API telefono'; Puerto = 5000 },
        @{ Nombre = 'SmartPark APK telefono'; Puerto = 8000 }
    )) {
        Get-NetFirewallRule -DisplayName $regla.Nombre -ErrorAction SilentlyContinue |
            Remove-NetFirewallRule -ErrorAction SilentlyContinue
        New-NetFirewallRule -DisplayName $regla.Nombre -Direction Inbound -Action Allow `
            -Protocol TCP -LocalPort $regla.Puerto -LocalAddress $direccionPC.IP `
            -RemoteAddress $ipTelefono -Profile Any `
            -Description 'Acceso de SmartPark limitado a la IP actual del telefono'
    }

    $escuchasAPK = @(Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue)
    if (-not $escuchasAPK.Count) {
        $python = Join-Path $raiz 'backend\.venv\Scripts\python.exe'
        if (-not (Test-Path $python)) {
            $python = (Get-Command python -ErrorAction Stop).Source
        }
        Start-Process -FilePath $python -ArgumentList '-m http.server 8000 --bind 0.0.0.0' `
            -WorkingDirectory $directorioAPK -WindowStyle Hidden | Out-Null
    }

    $urlAPKLocal = 'http://127.0.0.1:8000/app-arm64-v8a-debug.apk'
    $servidorAPKListo = $false
    for ($intento = 0; $intento -lt 15; $intento++) {
        try {
            $respuesta = Invoke-WebRequest -UseBasicParsing -Method Head -Uri $urlAPKLocal -TimeoutSec 3
            if ($respuesta.StatusCode -eq 200) {
                $servidorAPKListo = $true
                break
            }
        } catch {}
        Start-Sleep -Seconds 1
    }
    if (-not $servidorAPKListo) {
        throw 'El puerto 8000 no está sirviendo la APK. Revisa si otro proceso lo está usando.'
    }

    $urlDescarga = 'http://{0}:8000/app-arm64-v8a-debug.apk' -f $direccionPC.IP
    Write-Host ''
    Write-Host '[SmartPark] Preparación completada.'
    Write-Host ('  IP del computador: {0}' -f $direccionPC.IP)
    Write-Host ('  IP del teléfono autorizada en el firewall: {0}' -f $ipTelefono)
    Write-Host ('  Backend: {0}' -f $urlAPI)
    Write-Host ('  Descarga e instalación: {0}' -f $urlDescarga)
    Write-Host ''
    Write-Host 'Ahora ejecuta iniciar-smartpark-wifi.bat y luego abre el enlace de descarga desde el teléfono.'
    Write-Host 'Ambos dispositivos deben estar en una Wi-Fi que permita conexiones entre ellos.'
    Esperar-Cierre
} catch {
    Write-Host ''
    Write-Host ('[SmartPark] Error: {0}' -f $_.Exception.Message) -ForegroundColor Red
    Esperar-Cierre
    exit 1
}
