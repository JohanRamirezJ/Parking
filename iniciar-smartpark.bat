@echo off
REM SmartPark - levanta PostgreSQL + backend en Docker y abre el panel
cd /d "%~dp0"
where docker >nul 2>nul || (echo [SmartPark] Docker no esta instalado. Instala Docker Desktop: https://www.docker.com/products/docker-desktop/ & pause & exit /b 1)
docker info >nul 2>nul || (echo [SmartPark] Docker Desktop no esta corriendo. Abrelo, espera a que diga "Engine running" y vuelve a ejecutar este archivo. & pause & exit /b 1)
if not exist .env copy .env.example .env >nul
echo [SmartPark] Construyendo y levantando contenedores (la primera vez tarda unos minutos)...
docker compose up -d --build || (echo [SmartPark] Error al levantar los contenedores. Revisa el mensaje de arriba. & pause & exit /b 1)
echo [SmartPark] Esperando a que el backend responda...
for /l %%i in (1,1,60) do (
  curl -fsS http://localhost:5000/api/salud >nul 2>nul && goto listo
  timeout /t 2 >nul
)
echo [SmartPark] El backend no respondio a tiempo. Revisa: docker compose logs backend
pause & exit /b 1
:listo
docker compose ps
echo.
echo [SmartPark] Listo:
echo    API ........ http://localhost:5000/api/salud
echo    Panel admin  http://localhost:5000/admin   (admin@smartpark.co / admin12345)
echo    PostgreSQL . localhost:5433  (smartpark / smartpark)
start "" http://localhost:5000/admin
pause
