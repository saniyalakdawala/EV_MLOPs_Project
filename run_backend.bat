@echo off
echo ======================================================================
echo Starting FastAPI Backend for Smart EV Charging Infrastructure Database
echo Running at http://127.0.0.1:8000
echo Interactive API Documentation available at http://127.0.0.1:8000/docs
echo ======================================================================
if not exist "%~dp0.venv\Scripts\python.exe" (
  echo Project virtual environment not found. Follow the README setup steps first.
  exit /b 1
)
cd /d "%~dp0backend"
"%~dp0.venv\Scripts\python.exe" -m app.main
