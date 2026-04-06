@echo off
echo.
echo ============================================
echo   Starting CareBot - AI Medical Assistant
echo   Port: 8001
echo ============================================
echo.
cd ai_chatbot
..\ai_model\venv\Scripts\python.exe -m uvicorn server:app --reload --host 0.0.0.0 --port 8001
pause
