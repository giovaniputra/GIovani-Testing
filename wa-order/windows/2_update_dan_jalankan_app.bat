@echo off
rem Ambil versi terbaru, siapkan environment, lalu jalankan aplikasi di http://localhost:8000
cd /d "%~dp0.."
where git >nul 2>nul
if not errorlevel 1 (
  echo Mengambil versi terbaru...
  git pull --ff-only origin claude/upbeat-gauss-sbr6c1
)
set PYCMD=
where py >nul 2>nul && set PYCMD=py
if "%PYCMD%"=="" where python >nul 2>nul && set PYCMD=python
if "%PYCMD%"=="" (
  echo Python belum terpasang. Pasang Python 3.10 atau lebih baru, atau pakai file 1_update_dan_buka_simulator.bat
  pause
  exit /b 1
)
if not exist .venv\Scripts\activate.bat (
  echo Membuat environment...
  %PYCMD% -m venv .venv
)
call .venv\Scripts\activate.bat
%PYCMD% -m pip install -q -r requirements.txt
echo Membuka http://localhost:8000 ...
start "" http://localhost:8000
%PYCMD% -m uvicorn app.main:app --port 8000
pause
