@echo off
rem ============================================================================
rem  SocialSelling - inicia a UI local (http://127.0.0.1:8000)
rem  Duplo-clique neste arquivo. Na 1a vez ele prepara o ambiente sozinho.
rem ============================================================================
chcp 65001 >nul
cd /d "%~dp0"
title SocialSelling - UI local

set "PY=.venv\Scripts\python.exe"

rem 1) Cria o ambiente virtual se ainda nao existir
if not exist "%PY%" (
  echo [SocialSelling] Criando ambiente virtual .venv ...
  py -m venv .venv || python -m venv .venv
)
if not exist "%PY%" (
  echo.
  echo ERRO: Python 3.11+ nao encontrado. Instale em https://www.python.org/ e rode de novo.
  echo.
  pause
  exit /b 1
)

rem 2) Instala as dependencias da UI na primeira vez
"%PY%" -c "import fastapi, uvicorn" 1>nul 2>nul
if errorlevel 1 (
  echo [SocialSelling] Instalando dependencias ^(so na primeira vez, pode demorar^)...
  "%PY%" -m pip install --upgrade pip -q
  "%PY%" -m pip install -e ".[web]" -q
  if errorlevel 1 (
    echo.
    echo ERRO: falha ao instalar dependencias.
    pause
    exit /b 1
  )
)

rem 3) Garante o arquivo de chaves .env
if not exist ".env" if exist ".env.example" (
  copy ".env.example" ".env" >nul
  echo [SocialSelling] Criei o .env a partir do exemplo.
  echo                 EDITE o .env e preencha TAVILY_API_KEY e GEMINI_API_KEY.
)

rem 4) Abre o navegador (apos alguns segundos) e sobe o servidor
echo.
echo [SocialSelling] Abrindo http://127.0.0.1:8000 ...
echo [SocialSelling] Para encerrar: feche esta janela ou pressione Ctrl+C.
echo.
start "" /min cmd /c "timeout /t 3 >nul & start "" http://127.0.0.1:8000"
"%PY%" -m socialselling.web

pause
