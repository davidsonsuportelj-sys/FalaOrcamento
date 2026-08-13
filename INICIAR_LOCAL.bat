@echo off
cd /d "%~dp0"
echo Instalando dependencias do FalaOrcamento...
python -m pip install -r requirements.txt
if errorlevel 1 (
  echo.
  echo Nao foi possivel instalar as dependencias.
  pause
  exit /b 1
)
echo.
echo Iniciando FalaOrcamento v0.7...
echo Senha local padrao: admin
python app.py
pause
