@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul 2>nul
rem ============================================================
rem  start.bat - oc_bridge one-click launcher (Windows)
rem
rem    start.bat                               foreground (port 8790)
rem    start.bat --port 9000 --mode stateful   pass args to oc_bridge.py
rem
rem  It will: find Python -> find/install opencode -> run oc_bridge.py
rem ============================================================

set "DIR=%~dp0"

rem --- 1. python ---
set "PY="
where python >nul 2>nul && set "PY=python"
if not defined PY ( where py >nul 2>nul && set "PY=py" )
if not defined PY (
  echo [start] Python 3 not found. Install from https://www.python.org/downloads/
  pause
  exit /b 1
)

rem --- 2. opencode binary (install via npm if missing) ---
where opencode >nul 2>nul
if errorlevel 1 (
  echo [start] opencode not found, trying: npm i -g opencode-ai ...
  where npm >nul 2>nul
  if errorlevel 1 (
    echo [start] npm not found either. Install Node.js, or opencode manually: https://opencode.ai
  ) else (
    call npm i -g opencode-ai
  )
  set "PATH=%APPDATA%\npm;%PATH%"
)

rem --- 3. launch ---
cd /d "%DIR%"
echo [start] launching oc_bridge.py ...
%PY% -u "%DIR%oc_bridge.py" %*
if errorlevel 1 pause
endlocal
