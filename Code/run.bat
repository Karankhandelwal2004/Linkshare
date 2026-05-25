@echo off
REM Create a virtual environment in this folder, install requirements, and run the app
python -m venv .venv
ncall .venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r ..\requirements.txt
python ..\server.py
