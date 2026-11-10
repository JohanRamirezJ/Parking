@echo off
cd /d "%~dp0"
docker compose down
echo [SmartPark] Contenedores detenidos (los datos se conservan).
pause
