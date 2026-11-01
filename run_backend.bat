@echo off
echo ======================================================================
echo Starting FastAPI Backend for Smart EV Charging Infrastructure Database
echo Running at http://127.0.0.1:8000
echo Interactive API Documentation available at http://127.0.0.1:8000/docs
echo ======================================================================
cd /d "%~dp0backend"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
pause
