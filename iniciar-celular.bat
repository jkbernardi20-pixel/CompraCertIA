@echo off
REM Abre o CompraCertIA para acesso pelo celular na mesma rede (Wi-Fi/cabo).
REM Basta dar duplo-clique neste arquivo. A janela mostra o endereco a digitar
REM no navegador do celular. Feche a janela para encerrar.
cd /d "%~dp0"
echo Iniciando o CompraCertIA...
echo.
python -m compracertia web --host 0.0.0.0
echo.
echo (Servidor encerrado.)
pause
