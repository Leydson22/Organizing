@echo off
title Iniciar ScanVid
color 0B
echo ========================================================
echo                 SCANVID - INICIALIZADOR
echo ========================================================
echo.
echo Iniciando o servidor local e a aplicacao...
cd /d "%~dp0"

:: Tenta executar a versao compilada se existir, senao roda o python
if exist "dist\ScanVid.exe" (
    echo [OK] Versao compilada (ScanVid.exe) encontrada.
    start "" "dist\ScanVid.exe"
) else (
    echo [INFO] Versao compilada nao encontrada. Iniciando via Python...
    python app.py
)
exit
