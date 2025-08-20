@echo off
set PORT=8080
python -m uvicorn app:app --host 0.0.0.0 --port %PORT% --reload