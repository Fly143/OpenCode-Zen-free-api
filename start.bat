@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul 2>nul
rem ============================================================
rem  start.bat - oc_bridge one-click launcher (Windows)
rem
rem    start.bat                               foreground (port 8790)
rem    start.bat --port 9000 --mode stateful   pass args to oc_bridge.py
rem
rem  Idempotent: it resolves opencode by ABSOLUTE path (PATH, npm
rem  global dir, common locations) and only installs when truly
rem  missing. So normally it installs once, then just starts.
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

rem --- 2. did the user pass --opencode-bin themselves? ---
set "USERBIN="
for %%A in (%*) do (
  echo(%%A | findstr /b /c:"--opencode-bin" >nul && set "USERBIN=1"
)

rem --- 3. resolve opencode (absolute path) ---
set "OCBIN="
if not defined USERBIN call :findoc

rem --- 4. install only if truly missing ---
if not defined USERBIN if not defined OCBIN (
  echo [start] opencode not found, installing via npm ...
  where npm >nul 2>nul
  if errorlevel 1 (
    echo [start] npm not found. Install Node.js, or opencode manually: https://opencode.ai
  ) else (
    call npm i -g opencode-ai
    call :findoc
    if defined OCBIN echo [start] installed: !OCBIN!
  )
)

rem --- 5. launch (pass the resolved absolute path) ---
cd /d "%DIR%"
if defined USERBIN (
  %PY% -u "%DIR%oc_bridge.py" %*
) else if defined OCBIN (
  %PY% -u "%DIR%oc_bridge.py" --opencode-bin "!OCBIN!" %*
) else (
  %PY% -u "%DIR%oc_bridge.py" %*
)
if errorlevel 1 pause
endlocal
exit /b 0

rem ------------------------------------------------------------
:findoc
rem a) on PATH
for /f "delims=" %%P in ('where opencode 2^>nul') do if not defined OCBIN set "OCBIN=%%P"
if defined OCBIN exit /b 0
rem b) npm global prefix dir (not usually on PATH)
set "NP="
for /f "delims=" %%P in ('npm prefix -g 2^>nul') do set "NP=%%P"
if defined NP (
  for %%F in ("!NP!\opencode.cmd" "!NP!\opencode.exe" "!NP!\opencode" "!NP!\node_modules\opencode-ai\bin\opencode.exe") do (
    if not defined OCBIN if exist %%F set "OCBIN=%%~fF"
  )
)
if defined OCBIN exit /b 0
rem c) common locations
for %%F in ("%APPDATA%\npm\opencode.cmd" "%LOCALAPPDATA%\opencode\bin\opencode.exe" "%USERPROFILE%\.opencode\bin\opencode.exe") do (
  if not defined OCBIN if exist %%F set "OCBIN=%%~fF"
)
exit /b 0
