@echo off
echo ======================================================================
echo Starting VoltGrid Streamlit Dashboard
echo Running at http://localhost:8501
echo ======================================================================
if not exist "%~dp0.venv\Scripts\streamlit.exe" (
  echo Project virtual environment not found. Follow the README setup steps first.
  exit /b 1
)
"%~dp0.venv\Scripts\streamlit.exe" run "%~dp0streamlit_app.py"
