@echo off
echo ======================================================================
echo Starting VoltGrid Mumbai Services (Backend + Frontend)
echo ======================================================================
start "VoltGrid Backend (FastAPI)" cmd /k "%~dp0run_backend.bat"
start "VoltGrid Frontend (React Vite)" cmd /k "%~dp0run_frontend.bat"
echo Waiting 3 seconds for services to initialize...
timeout /t 3 >nul
start "" "http://localhost:5173"
echo.
echo Both services launched!
echo Backend:  http://127.0.0.1:8000 (Docs: http://127.0.0.1:8000/docs)
echo Frontend: http://localhost:5173
echo ======================================================================
