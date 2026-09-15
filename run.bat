@echo off
cd /d "%~dp0"
".tools\python\python.exe" -m streamlit run app.py --server.headless true
