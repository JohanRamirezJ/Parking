@echo off
cd /d "%~dp0backend"
if exist "%~dp0.env" (
  for /f "usebackq tokens=1,* delims==" %%A in ("%~dp0.env") do (
    if "%%A"=="OPENAI_API_KEY" set "OPENAI_API_KEY=%%B"
    if "%%A"=="OPENAI_MODEL" set "OPENAI_MODEL=%%B"
    if "%%A"=="GEMINI_API_KEY" set "GEMINI_API_KEY=%%B"
    if "%%A"=="GEMINI_MODEL" set "GEMINI_MODEL=%%B"
    if "%%A"=="OVERPASS_URL" set "OVERPASS_URL=%%B"
    if "%%A"=="OVERPASS_TIMEOUT_SECONDS" set "OVERPASS_TIMEOUT_SECONDS=%%B"
  )
)
if not exist .venv\Scripts\python.exe (
  echo [SmartPark] No se encontro backend\.venv. Sigue los pasos de mobile\README.md para instalar dependencias.
  pause
  exit /b 1
)
set FLASK_APP=wsgi
echo [SmartPark] Cargando datos demo si la base esta vacia...
.venv\Scripts\python.exe -m flask seed
if errorlevel 1 (
  echo [SmartPark] No se pudo preparar la base de datos.
  pause
  exit /b 1
)
echo.
echo [SmartPark] Backend disponible en el puerto 5000.
echo [SmartPark] Mantén esta ventana abierta mientras uses la app.
.venv\Scripts\python.exe -m flask run --host 0.0.0.0 --port 5000
pause
