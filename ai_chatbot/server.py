"""
Smart Care+ AI Medical Chatbot — Standalone Server
Runs independently on port 8001, completely separate from the main dashboard backend.
"""

import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from dotenv import load_dotenv
import google.generativeai as genai

# --- Load API Key ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.abspath(os.path.join(BASE_DIR, "..", "vision_system", ".env"))
load_dotenv(dotenv_path=env_path)
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    print("✅ Gemini API Key loaded successfully.")
else:
    print("⚠️  Warning: GEMINI_API_KEY not found in .env file.")

# --- App Setup ---
app = FastAPI(title="Smart Care+ AI Medical Chatbot", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- System Prompt ---
SYSTEM_PROMPT = """You are "CareBot", a specialized AI medical advisor assistant designed for caregivers using the Smart Care+ elderly monitoring system.

YOUR ROLE:
You are an intelligent, empathetic, and knowledgeable health assistant. Your primary function is to help caregivers understand health data, answer medical questions in simple language, and provide actionable guidance.

CAPABILITIES:
1. Analyze vital signs (heart rate, blood pressure, temperature) when provided by the user.
2. Explain medical terminology in simple, caregiver-friendly language.
3. Provide general wellness advice for elderly patients.
4. Help interpret patterns in health data.
5. Suggest when professional medical attention may be needed.
6. Offer emotional support and reassurance to caregivers.

RESPONSE GUIDELINES:
- Be concise but thorough. Use bullet points for clarity when listing recommendations.
- If the user provides vital signs, always analyze them first before answering the question.
- Use a warm, professional tone appropriate for caregivers who may be stressed.
- If vitals are abnormal (e.g., HR > 100 or < 60, BP > 140/90 or < 90/60, Temp > 100.4°F or < 96.8°F), clearly flag this and recommend contacting a healthcare provider.
- For emergencies (e.g., HR > 150, signs of stroke, severe chest pain), strongly advise calling emergency services immediately.

CRITICAL RULE — MEDICAL DISCLAIMER:
You MUST end EVERY response with the following disclaimer on a new line, formatted in italic:
"_⚕️ Disclaimer: I am an AI assistant and not a licensed medical professional. My responses are for informational purposes only and should not replace professional medical advice, diagnosis, or treatment. In case of emergency, please call your local emergency services immediately._"

LANGUAGE:
- Respond in the same language the user writes in. If the user writes in Arabic, respond in Arabic. If in English, respond in English.
"""

# --- Data Models ---
class ChatMessage(BaseModel):
    message: str
    vitals: dict | None = None  # Optional vitals context

# --- Chat History (in-memory per session) ---
chat_sessions = {}

# --- Endpoints ---
@app.post("/api/chat")
async def chat(payload: ChatMessage):
    if not GEMINI_API_KEY:
        raise HTTPException(status_code=500, detail="Gemini API Key is missing. Add GEMINI_API_KEY to vision_system/.env")

    # Build context with vitals if provided
    user_message = payload.message
    if payload.vitals:
        vitals_context = f"""
[CURRENT PATIENT VITALS PROVIDED BY CAREGIVER]
- Heart Rate: {payload.vitals.get('heart_rate', 'N/A')} BPM
- Blood Pressure: {payload.vitals.get('blood_pressure', 'N/A')}
- Temperature: {payload.vitals.get('temperature', 'N/A')} °F
- System Status: {payload.vitals.get('status', 'N/A')}

Caregiver's Question: {user_message}"""
        user_message = vitals_context

    try:
        model = genai.GenerativeModel(
            model_name="gemini-2.5-flash",
            system_instruction=SYSTEM_PROMPT
        )
        response = model.generate_content(user_message)
        return {"response": response.text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/health")
def health_check():
    return {
        "status": "online",
        "service": "Smart Care+ AI Medical Chatbot",
        "gemini_connected": bool(GEMINI_API_KEY)
    }

@app.get("/")
def serve_ui():
    index_path = os.path.join(BASE_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"error": "UI file not found"}
