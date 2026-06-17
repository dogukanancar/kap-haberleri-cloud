@echo off
chcp 65001 >nul
cd /d "%~dp0.."
echo KAP Haberleri Cloud paneli baslatiliyor...
streamlit run app.py
