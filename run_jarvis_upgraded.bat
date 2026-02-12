@echo off
TITLE J.A.R.V.I.S. Upgraded
ECHO ==================================================
ECHO     INITIALIZING J.A.R.V.I.S. (UPGRADED)
ECHO ==================================================

:: 1. Set Security Keys
SET JARVIS_HMAC_KEY=jarvis_dev_key_2026
SET JARVIS_CODE_MODE=1

:: 2. Resolve paths (use script directory)
SET "SCRIPT_DIR=%~dp0"
CD /D "%SCRIPT_DIR%"

:: 3. Activate Virtual Environment
IF EXIST ".venv\Scripts\activate.bat" (
    ECHO [INFO] Activating .venv...
    CALL ".venv\Scripts\activate.bat"
) ELSE IF EXIST "venv\Scripts\activate.bat" (
    ECHO [INFO] Activating venv...
    CALL "venv\Scripts\activate.bat"
) ELSE (
    ECHO [ERROR] Virtual environment not found in .venv or venv.
    ECHO [INFO] Please ensure '.venv' exists in "%SCRIPT_DIR%"
    PAUSE
    EXIT /B
)

:: 4. Run
ECHO [INFO] Integrity Keys Set.
ECHO [INFO] Code Mode Enabled.
ECHO [INFO] Starting JARVIS...
python jarvis.py --enable-code

PAUSE
