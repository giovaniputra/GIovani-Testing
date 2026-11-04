@echo off
setlocal enabledelayedexpansion
REM ============================================================
REM  Klik dua kali: ambil kurs terbaru BI -> hasil\kurs_TANGGAL.csv
REM  Argumen "auto" (dipakai penjadwal) = tidak menunggu tombol.
REM  Argumen lain diteruskan ke ambil_kurs.py, contoh:
REM     ambil_kurs.bat --dari 2026-10-01 --sampai 2026-10-31
REM ============================================================
cd /d "%~dp0"

set AUTO=0
set ARGS=
:baca
if "%~1"=="" goto selesai_baca
if /i "%~1"=="auto" (set AUTO=1) else (set ARGS=!ARGS! %1)
shift
goto baca
:selesai_baca

set PY=
where python >nul 2>nul && set PY=python
if not defined PY (where py >nul 2>nul && set PY=py)
if not defined PY (
  echo Python tidak ditemukan. Pasang dari https://www.python.org/downloads/ ^(centang "Add python.exe to PATH"^).
  if "%AUTO%"=="0" pause
  exit /b 1
)

if not exist hasil mkdir hasil
for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd"') do set TGL=%%i
if defined ARGS (set OUT=hasil\kurs_%TGL%_custom.csv) else (set OUT=hasil\kurs_%TGL%.csv)

echo [%date% %time%] mulai >> hasil\log.txt
%PY% ambil_kurs.py%ARGS% --output "%OUT%"
set ERR=%errorlevel%
echo [%date% %time%] selesai, kode=%ERR%, file=%OUT% >> hasil\log.txt

echo.
if not "%ERR%"=="0" (echo GAGAL ^(kode %ERR%^). Lihat hasil\log.txt) else (echo Berhasil. File: %OUT%)
if "%AUTO%"=="0" pause
exit /b %ERR%
