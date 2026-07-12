@echo off
REM Abre o CompraCertIA so neste computador (http://127.0.0.1:8000).
REM Duplo-clique para iniciar. Feche a janela para encerrar.
cd /d "%~dp0"
echo Iniciando o CompraCertIA...
echo.
python -m compracertia web
echo.
echo (Servidor encerrado.)
pause
