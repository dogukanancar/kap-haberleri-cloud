@echo off
chcp 65001 >nul
cd /d "C:\Kap Haberleri Cloud"
"C:\Users\MonsterPC\AppData\Local\Programs\Python\Python312\python.exe" worker_once.py
"C:\Users\MonsterPC\AppData\Local\Programs\Python\Python312\python.exe" cds_worker_once.py
"C:\Users\MonsterPC\AppData\Local\Programs\Python\Python312\python.exe" brand_worker_once.py
