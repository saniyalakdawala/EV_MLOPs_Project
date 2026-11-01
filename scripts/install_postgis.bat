@echo off
setlocal
echo ======================================================================
echo PostGIS Installation Helper for PostgreSQL 17 (Windows x64)
echo ======================================================================
echo.

:: Check for Administrative privileges
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo [INFO] Administrator privileges are required to copy into Program Files.
    echo [INFO] Requesting elevation via UAC...
    powershell -Command "Start-Process cmd.exe -ArgumentList '/k \"\"%~f0\"\" admin' -Verb RunAs"
    exit /b
)

set "SOURCE=C:\Projects\ADBMS\data\postgis_extracted\postgis-bundle-pg17-3.6.2x64"
set "DEST=C:\Program Files\PostgreSQL\17"

if not exist "%SOURCE%" (
    echo [ERROR] Source folder "%SOURCE%" not found!
    pause
    exit /b 1
)

echo [1/4] Stopping PostgreSQL 17 service to release DLL file locks...
net stop postgresql-x64-17

echo.
echo [2/4] Copying PostGIS extension binaries into PostgreSQL 17...
robocopy "%SOURCE%" "%DEST%" /E /XO /R:1 /W:1 /NP /NFL /NDL

echo.
echo [3/4] Restarting PostgreSQL 17 service...
net start postgresql-x64-17
powershell -Command "Start-Sleep -Seconds 2"

echo.
echo [4/4] Verifying copied control files...
if exist "%DEST%\share\extension\postgis.control" (
    echo [SUCCESS] postgis.control found at: %DEST%\share\extension\postgis.control
) else (
    echo [ERROR] postgis.control was not found in %DEST%\share\extension\
    pause
    exit /b 1
)

echo.
echo Activating PostGIS in PostgreSQL database 'ev_db'...
cd /d "C:\Projects\ADBMS"
python scripts\activate_postgis.py

echo.
echo ======================================================================
echo PostGIS Setup Finished!
echo ======================================================================
pause
