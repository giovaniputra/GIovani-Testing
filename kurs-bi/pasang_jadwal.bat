@echo off
setlocal
REM Klik dua kali: pasang jadwal otomatis, setiap hari kerja jam 17:00 (kurs BI sudah terbit).
REM Mau ganti jam? Ubah 17:00 di bawah, lalu klik dua kali lagi.
cd /d "%~dp0"
schtasks /create /f /tn "Kurs BI Harian" /sc weekly /d MON,TUE,WED,THU,FRI /st 17:00 /tr "\"%~dp0ambil_kurs.bat\" auto"
echo.
if errorlevel 1 (echo Gagal memasang jadwal. Coba klik kanan file ini ^> Run as administrator.) else (
  echo Jadwal terpasang: Senin-Jumat jam 17:00 ^(komputer harus menyala^).
  echo Hasil tersimpan di folder "hasil".
)
pause
