import time
import json
import urllib.request
import random

SERVER_URL = "http://127.0.0.1:8000/api/monitor"

def send_payload(accel_data, heart_rate):
    payload = {
        "user_id": "grandpa_john_001",
        "accel_data": accel_data,
        "vitals": {
            "heart_rate": heart_rate,
            "timestamp": time.time()
        }
    }
    
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(SERVER_URL, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode('utf-8'))
            print(f"Backend Server Processed Data -> {result}")
    except Exception as e:
        print(f"Error connecting to FastAPI backend! Is it running? Error: {e}")

def generate_normal_data():
    # 50 reading samples of perfectly normal movement
    data = []
    for _ in range(50):
        data.append({
            "x": random.uniform(-1, 1),
            "y": random.uniform(-1, 1),
            "z": random.uniform(9, 10),  # Gravity standard pull on Z axis
            "timestamp": time.time()
        })
    return data

def generate_fall_data():
    # 50 reading samples simulating a traumatic physical fall (massive acceleration impact)
    data = []
    for i in range(50):
        if i == 25:
            # Massive sudden acceleration spike (The Fall Impact)
            data.append({"x": 45.0, "y": 90.0, "z": -40.0, "timestamp": time.time()})
        else:
            # Senior is now laying flat on the ground (Gravity shift to Y axis)
            data.append({
                "x": random.uniform(-1, 1),
                "y": random.uniform(8, 10), 
                "z": random.uniform(-1, 1), 
                "timestamp": time.time()
            })
    return data

if __name__ == "__main__":
    print("\n" + "="*50)
    print("--- Smart Care+ End-to-End Test Simulator ---")
    print("="*50 + "\n")
    print(">>> IF YOU HAVEN'T YET, OPEN `frontend/index.html` IN YOUR BROWSER NOW! <<<\n")
    
    # 1. Establish normal baseline connection
    print("[1/2] Sending NORMAL physical data (Heart Rate: 72 BPM)...")
    send_payload(generate_normal_data(), 72)
    print("-> Your browser Dashboard should say 'Safe'.\n")
    
    # Give user a few seconds to watch the browser
    print("Waiting 6 seconds. Please focus your eyes on your Web Dashboard...\n")
    for i in range(6, 0, -1):
        print(f"{i}...")
        time.sleep(1)
        
    # 2. Trigger the extreme emergency to test frontend visually
    print("\n[2/2] FALL SIMULATED! Spiking Accelerometer & Heart Rate to 160 BPM...")
    send_payload(generate_fall_data(), 160)
    print("-> Your browser Dashboard should INSTANTLY turn RED and flash 'EMERGENCY'!")
    
    print("\nEnd-to-End system test successfully broadcasted globally.")
