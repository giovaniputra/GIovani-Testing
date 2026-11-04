@echo off
setlocal
REM Jalankan aplikasi web Kurs BI lalu buka browser ke http://localhost:3000
cd /d "%~dp0"
where node >nul 2>nul
if errorlevel 1 (
  echo Node.js tidak ditemukan. Pasang versi LTS dari https://nodejs.org lalu jalankan lagi.
  pause
  exit /b 1
)
start "" http://localhost:3000
node server.js
pause
