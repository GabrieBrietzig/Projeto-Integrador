@echo off
REM TestingStudio Web - inicia a aplicacao (Windows)
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Criando ambiente virtual...
    python -m venv .venv || py -m venv .venv
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
)
".venv\Scripts\python.exe" -m streamlit run app.py
