@echo off
echo Instalando dependencias...
pip install -r requirements.txt --quiet
echo.
echo Iniciando Gestao de Suprimentos em http://localhost:8000
echo Pressione Ctrl+C para encerrar.
echo.
python run.py
pause
