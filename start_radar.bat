@echo off
cd /d "%~dp0"
title Flight Radar Service

echo ===================================================
echo   Starting Flight Radar Service (FlightRadar24)
echo   Please DO NOT close the new window that appears.
echo ===================================================
echo.

:: Check and install dependencies
python -c "import FlightRadar24" >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] Installing required dependencies...
    pip install FlightRadarAPI
)

:: Start Flask server in a new window
echo [INFO] Starting Python backend server...
start "Flight Radar Backend" cmd /k "python app.py"

:: Wait for 3 seconds to let server start
timeout /t 3 /nobreak >nul

:: Open browser
echo [INFO] Opening browser...
start http://localhost:5000

echo [SUCCESS] Service started!
pause
