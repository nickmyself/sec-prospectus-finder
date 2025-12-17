@echo off
pushd "%~dp0"
set "PIDFILE=%~dp0streamlit.pid"
if not exist "%PIDFILE%" (
  echo PID file not found: %PIDFILE%
  echo Cannot stop. If Streamlit is running, kill it manually.
  popd
  exit /b 1
)
set /p PID=<"%PIDFILE%"
if "%PID%"=="" (
  echo PID file empty, nothing to stop.
  del "%PIDFILE%" 2>nul
  popd
  exit /b 1
)
echo Stopping Streamlit PID %PID%
taskkill /PID %PID% /F || echo Failed to kill PID %PID%
if exist "%PIDFILE%" del "%PIDFILE%"
popd
