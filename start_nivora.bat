@echo off
title NIVORA - Intelligent Water Supply Complaint Management System
echo ============================================================
echo   Starting NIVORA Application...
echo   Please wait a moment while the server launches.
echo ============================================================
echo.

where py >nul 2>nul
if %errorlevel% == 0 (
    py run.py
    goto end
)

where python >nul 2>nul
if %errorlevel% == 0 (
    python run.py
    goto end
)

echo [ERROR] Python was not found in your system PATH.
echo Please ensure Python 3 is installed.
pause

:end
