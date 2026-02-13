@echo off
TITLE GKI Bromo FaceID System
COLOR 0A
ECHO ==========================================
ECHO    MEMULAI SISTEM ABSENSI WAJAH...
ECHO    Mohon tunggu sebentar...
ECHO ==========================================
ECHO.

:: 1. Masuk ke Virtual Environment (Sesuaikan path jika beda)
CALL venv\Scripts\activate.bat

:: 2. Buka Browser Otomatis setelah 5 detik
TIMEOUT /T 5 /NOBREAK > NUL
START http://localhost:8000/login

:: 3. Jalankan Server Python
python main.py


PAUSE