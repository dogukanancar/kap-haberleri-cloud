@echo off
chcp 65001 >nul
cd /d "C:\Kap Haberleri Cloud"

echo [1/4] Bagimliliklar kontrol ediliyor...
python -m pip install -r requirements.txt -q
if errorlevel 1 (
    echo HATA: pip kurulumu basarisiz. Python kurulu mu?
    pause
    exit /b 1
)

echo [2/4] Uzak veritabani baglantisi test ediliyor...
python scripts\check_db.py
if errorlevel 1 (
    echo.
    echo HATA: Supabase baglantisi kurulamadi.
    echo .env dosyasinda DATABASE_URL dolu olmali.
    pause
    exit /b 1
)

echo [3/4] Eski panel surecleri kapatiliyor...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8501 ^| findstr LISTENING') do taskkill /F /PID %%a >nul 2>&1

echo [4/4] Panel baslatiliyor...
echo.
echo Tarayici otomatik acilacak: http://127.0.0.1:8501
echo.
streamlit run app.py
