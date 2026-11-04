@echo off
REM Klik dua kali: hapus jadwal otomatis Kurs BI.
schtasks /delete /f /tn "Kurs BI Harian"
echo.
pause
