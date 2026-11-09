@echo off
rem Ambil versi terbaru lalu buka simulator di browser. Tidak butuh Python.
cd /d "%~dp0.."
where git >nul 2>nul
if errorlevel 1 (
  echo Git tidak ditemukan. Membuka versi yang sudah ada di folder ini.
) else (
  echo Mengambil versi terbaru...
  git pull --ff-only origin claude/upbeat-gauss-sbr6c1
  if errorlevel 1 echo Gagal update. Ada perubahan lokal? Membuka versi yang ada.
)
start "" "%cd%\simulator.html"
