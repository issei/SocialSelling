@echo off
cd /d "%~dp0"

echo.
echo  SocialSelling — Portal da Operadora
echo  =====================================

if not exist ".venv\Scripts\activate.bat" (
    echo  ERRO: venv nao encontrado. Execute primeiro:
    echo    py -m venv .venv
    echo    .venv\Scripts\activate.bat
    echo    pip install -e ".[portal]"
    pause
    exit /b 1
)

call .venv\Scripts\activate.bat

py scripts\run_portal.py

pause
