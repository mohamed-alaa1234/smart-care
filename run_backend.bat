@echo off
echo Starting Smart Care+ Backend API Server...
cd backend
..\ai_model\venv\Scripts\python.exe -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
pause
