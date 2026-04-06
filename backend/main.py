import os
import time
import joblib
import numpy as np
import sqlite3
import json
import struct
import asyncio
from bleak import BleakScanner, BleakClient
from fastapi import FastAPI, BackgroundTasks, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = FastAPI(title="Smart Care+ Backend API", version="1.0.0")

# --- CORS Settings for Web Frontend ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, restrict to your frontend domains!
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- AI Model Loading ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.abspath(os.path.join(BASE_DIR, "..", "ai_model", "saved_models", "fall_detection_rf.joblib"))
SCALER_PATH = os.path.abspath(os.path.join(BASE_DIR, "..", "ai_model", "saved_models", "scaler.joblib"))

fall_model = None
scaler = None

# --- Database & Settings Setup ---
DB_PATH = os.path.join(BASE_DIR, "history.db")
SETTINGS_PATH = os.path.join(BASE_DIR, "settings.json")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS history 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                 timestamp REAL, 
                 event_type TEXT, 
                 details TEXT)''')
    conn.commit()
    conn.close()

def log_history(event_type: str, details: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO history (timestamp, event_type, details) VALUES (?, ?, ?)",
              (time.time(), event_type, details))
    conn.commit()
    conn.close()

def load_settings():
    if os.path.exists(SETTINGS_PATH):
        try:
            with open(SETTINGS_PATH, "r") as f:
                return json.load(f)
        except:
            pass
    return {"elder_name": "Senior User", "emergency_phone": "911"}

def save_settings(settings: dict):
    with open(SETTINGS_PATH, "w") as f:
        json.dump(settings, f)

@app.on_event("startup")
async def startup_event():
    global fall_model, scaler
    init_db()
    # Ensure default settings exist
    if not os.path.exists(SETTINGS_PATH):
        save_settings({"elder_name": "Senior User", "emergency_phone": "911"})
        
    try:
        if os.path.exists(MODEL_PATH) and os.path.exists(SCALER_PATH):
            fall_model = joblib.load(MODEL_PATH)
            scaler = joblib.load(SCALER_PATH)
            print("AI Model successfully attached!")
        else:
            print("Warning: AI Model not found. Did you run the training script?")
    except Exception as e:
        print(f"Error loading AI model: {e}")

# --- Global State for Frontend Polling ---
current_system_state = {
    "heart_rate": 78,
    "status": "Safe",
    "last_updated": time.time(),
    "temperature": 98.6,
    "blood_pressure": "118/79",
    "camera_active": True
}

class AccelerometerData(BaseModel):
    x: float
    y: float
    z: float
    timestamp: float

class VitalData(BaseModel):
    heart_rate: int
    timestamp: float

class WatchPayload(BaseModel):
    user_id: str
    accel_data: List[AccelerometerData]
    vitals: VitalData

class SettingsPayload(BaseModel):
    elder_name: str
    emergency_phone: str

def send_emergency_alert(user_id: str, alert_reason: str):
    settings = load_settings()
    name = settings.get("elder_name", "Senior User")
    phone = settings.get("emergency_phone", "911")
    print("\n" + "="*50)
    print("!!! EMERGENCY SYSTEM ACTIVATED !!!")
    print(f"!!! ALERT FOR: {name} ({user_id}) | REASON: {alert_reason} !!!")
    print(f"!!! CALLING EMERGENCY NUMBER: {phone} !!!")
    print("="*50 + "\n")

def extract_features(window_array):
    mean_vals = np.mean(window_array, axis=0)
    std_vals = np.std(window_array, axis=0)
    max_vals = np.max(window_array, axis=0)
    min_vals = np.min(window_array, axis=0)
    return np.concatenate([mean_vals, std_vals, max_vals, min_vals])

@app.post("/api/monitor")
async def analyze_watch_data(payload: WatchPayload, background_tasks: BackgroundTasks):
    global fall_model, scaler, current_system_state
    
    hr = payload.vitals.heart_rate
    current_system_state["heart_rate"] = hr
    current_system_state["last_updated"] = time.time()
    
    # Analyze Vitals
    if hr > 150 or (40 > hr > 0):
        if current_system_state["status"] != "Emergency":
            log_history("Critical Vitals", f"Abnormal Heart Rate: {hr} BPM")
            current_system_state["status"] = "Emergency"
            background_tasks.add_task(send_emergency_alert, payload.user_id, f"Critical HR: {hr}")
        return {"status": "alert_triggered", "reason": "vitals"}

    if not fall_model or not scaler:
        raise HTTPException(status_code=500, detail="AI Model not connected.")
        
    if len(payload.accel_data) != 50:
        return {"status": "ignored", "message": "Expected exactly 50 samples"}
        
    input_window = [[reading.x, reading.y, reading.z] for reading in payload.accel_data]
    window_array = np.array(input_window)
    
    features = extract_features(window_array)
    features_scaled = scaler.transform([features])
    
    probs = fall_model.predict_proba(features_scaled)
    fall_confidence = float(probs[0][1])
    
    is_fall = fall_confidence > 0.85 
    
    if is_fall:
        print(f"AI Detected a Fall! Confidence: {fall_confidence*100:.2f}%")
        if current_system_state["status"] != "Emergency":
            log_history("Fall Detected", f"Confidence: {fall_confidence*100:.1f}%")
            current_system_state["status"] = "Emergency"
            background_tasks.add_task(send_emergency_alert, payload.user_id, "Fall Detected")
    else:
        # If HR is also normal, status is safe
        if 40 <= hr <= 150:
            current_system_state["status"] = "Safe"
        
    return {
        "status": "success",
        "fall_detected": is_fall,
        "confidence": round(fall_confidence, 4)
    }

@app.get("/status")
def get_dashboard_status():
    st = dict(current_system_state)
    st["settings"] = load_settings() 
    return st

@app.get("/api/history")
def get_history():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT timestamp, event_type, details FROM history ORDER BY timestamp DESC LIMIT 50")
    rows = c.fetchall()
    conn.close()
    return [{"timestamp": r[0], "event_type": r[1], "details": r[2]} for r in rows]

@app.get("/api/settings")
def api_get_settings():
    return load_settings()

@app.post("/api/settings")
def api_update_settings(payload: SettingsPayload):
    save_settings({"elder_name": payload.elder_name, "emergency_phone": payload.emergency_phone})
    return {"status": "success"}

# --- BLE Heart Rate Integration ---
HEART_RATE_SERVICE_UUID = "0000180d-0000-1000-8000-00805f9b34fb"
HEART_RATE_MEASUREMENT_UUID = "00002a37-0000-1000-8000-00805f9b34fb"

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except:
                pass

manager = ConnectionManager()
ble_client = None
is_connected = False

async def heart_rate_handler(sender, data: bytearray):
    flags = data[0]
    hr_format = flags & 0x01
    hr_value = data[1] if hr_format == 0 else struct.unpack("<H", data[1:3])[0]
        
    global current_system_state
    current_system_state["heart_rate"] = hr_value
    current_system_state["last_updated"] = time.time()
        
    await manager.broadcast(f'{{"type": "hr_data", "value": {hr_value}}}')

async def connect_to_heart_rate_monitor():
    global ble_client, is_connected
    if is_connected: return
        
    await manager.broadcast('{"type": "status", "message": "Scanning for Heart Rate monitors..."}')
    
    def match_heart_rate_service(device, adv_data):
        return HEART_RATE_SERVICE_UUID in [str(u).lower() for u in adv_data.service_uuids]

    target_device = await BleakScanner.find_device_by_filter(match_heart_rate_service, timeout=10.0)
            
    if not target_device:
        await manager.broadcast('{"type": "error", "message": "No compatible smartwatch found."}')
        await manager.broadcast('{"type": "status", "connected": false}')
        return
        
    await manager.broadcast(f'{{"type": "status", "message": "Found {target_device.name}, connecting..."}}')
    
    def disconnected_callback(client):
        global is_connected
        is_connected = False
        asyncio.create_task(manager.broadcast('{"type": "error", "message": "Disconnected from smartwatch"}'))
        asyncio.create_task(manager.broadcast('{"type": "status", "connected": false}'))

    ble_client = BleakClient(target_device.address, disconnected_callback=disconnected_callback)
    
    try:
        await ble_client.connect()
        is_connected = True
        await manager.broadcast('{"type": "status", "connected": true, "message": "Connected successfully!"}')
        await ble_client.start_notify(HEART_RATE_MEASUREMENT_UUID, heart_rate_handler)
    except Exception as e:
        is_connected = False
        await manager.broadcast(f'{{"type": "error", "message": "Connection failed."}}')
        await manager.broadcast('{"type": "status", "connected": false}')

@app.websocket("/ws/heartrate")
async def websocket_endpoint(websocket: WebSocket):
    global ble_client, is_connected
    await manager.connect(websocket)
    try:
        await websocket.send_text(f'{{"type": "status", "connected": {"true" if is_connected else "false"}}}')
        while True:
            data = await websocket.receive_text()
            if data == "scan_and_connect":
                asyncio.create_task(connect_to_heart_rate_monitor())
            elif data == "disconnect":
                if ble_client and is_connected:
                    await ble_client.disconnect()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.get("/")
def serve_ui():
    index_path = os.path.abspath(os.path.join(BASE_DIR, "..", "frontend", "index.html"))
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"status": "online", "service": "Smart Care+ Global Brain Controller", "error": "UI file not found"}
