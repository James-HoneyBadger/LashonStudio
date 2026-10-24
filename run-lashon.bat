@echo off
REM ParserCraft IDE Launch Script for Windows
REM Automatically sets up virtual environment and installs dependencies

setlocal enabledelayedexpansion

set "SCRIPT_DIR=%~dp0"
set "VENV_DIR=%SCRIPT_DIR%.venv"
set "PYTHON_CMD=python"

echo ================================================
echo     ParserCraft IDE Launcher v4.0.0
echo ================================================
echo.

REM Check if Python is available
where %PYTHON_CMD% >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo Error: Python is required but not found.
    echo Please install Python 3.7 or higher from https://www.python.org/
    echo Make sure to add Python to PATH during installation.
    pause
    exit /b 1
)

REM Check Python version
for /f "tokens=2" %%i in ('%PYTHON_CMD% --version 2^>^&1') do set PYTHON_VERSION=%%i
echo [OK] Found Python %PYTHON_VERSION%

REM Create virtual environment if it doesn't exist
if not exist "%VENV_DIR%" (
    echo Creating virtual environment...
    %PYTHON_CMD% -m venv "%VENV_DIR%"
    echo [OK] Virtual environment created
) else (
    echo [OK] Virtual environment exists
)

REM Activate virtual environment
echo Activating virtual environment...
call "%VENV_DIR%\Scripts\activate.bat"

REM Upgrade pip
echo Upgrading pip...
python -m pip install --quiet --upgrade pip

REM Install ParserCraft in development mode
echo Installing ParserCraft and dependencies...
pip install --quiet -e "%SCRIPT_DIR%"

REM Install development dependencies
echo Installing development dependencies...
pip install --quiet pytest black flake8

echo [OK] All dependencies installed
echo.

REM Launch ParserCraft IDE
echo Launching ParserCraft IDE...
echo.

cd /d "%SCRIPT_DIR%"
set "PYTHONPATH=%SCRIPT_DIR%src;%PYTHONPATH%"
python src\parsercraft\launch_ide.py

REM Deactivate virtual environment on exit
call deactivate

endlocal
