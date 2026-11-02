@echo off
echo ======================================================================
echo Starting VoltGrid Mumbai: FastAPI + Streamlit
echo ======================================================================
if not exist "%~dp0.venv\Scripts\python.exe" (
  echo Project virtual environment not found. Follow the README setup steps first.
  exit /b 1
)
start "VoltGrid FastAPI" /D "%~dp0backend" "%~dp0.venv\Scripts\python.exe" -m app.main
start "VoltGrid Streamlit" /D "%~dp0" "%~dp0.venv\Scripts\streamlit.exe" run "%~dp0streamlit_app.py"
echo Waiting 3 seconds for services to initialize...
timeout /t 3 >nul
start "" "http://localhost:8501"
echo.
echo Both services launched!
echo FastAPI:   http://127.0.0.1:8000/docs
echo Streamlit: http://localhost:8501
echo ======================================================================
