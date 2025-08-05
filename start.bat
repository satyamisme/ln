@echo off
ECHO Creating Virtual Environment...
IF NOT EXIST venv (
    python -m venv venv
    IF %ERRORLEVEL% NEQ 0 (
        ECHO Failed to create virtual environment. Please make sure Python is installed and in your PATH.
        PAUSE
        EXIT /B 1
    )
)

ECHO Activating Virtual Environment...
CALL venv\Scripts\activate.bat

ECHO Installing Requirements...
pip install -r requirements.txt
IF %ERRORLEVEL% NEQ 0 (
    ECHO Failed to install requirements.
    PAUSE
    EXIT /B 1
)

ECHO Starting Bot...
python -m bot
PAUSE
