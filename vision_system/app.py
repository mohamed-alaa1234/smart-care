import streamlit as st
import cv2
import pandas as pd
import plotly.express as px
import os

from dotenv import load_dotenv
from database import init_db, log_event, get_weekly_stats
from alerting import trigger_alerts
from cv_detector import FallDetectorCV
from esp32_receiver import HardwareReceiver

# Standard Configuration
load_dotenv()
init_db()


# Session States
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "fall_detected" not in st.session_state:
    st.session_state.fall_detected = False

def login_page():
    """Renders Secure Login Screen using Session State."""
    st.title("Smart Care+ Secure Data Access")
    st.write("Authenticate to view live camera feeds & historic logs.")
    user = st.text_input("Username")
    pwd = st.text_input("Password", type="password")
    if st.button("Login"):
        # Re-read env file to sync changes immediately
        load_dotenv(override=True)
        
        # Check if .env file exists and has the required variables
        if not os.path.exists(".env"):
            st.error("Error: .env file is missing. Please create it and add ADMIN_USER and ADMIN_PASSWORD variables.")
            return
            
        admin_user = os.getenv("ADMIN_USER")
        admin_password = os.getenv("ADMIN_PASSWORD")
        
        if not admin_user or not admin_password:
            st.error("Error: Missing ADMIN_USER or ADMIN_PASSWORD in .env file. Please add them.")
            return
            
        # Verifying against env variables instead of hard-coded variables for Data Security
        if user == admin_user and pwd == admin_password:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Invalid secure credentials.")

if not st.session_state.authenticated:
    login_page()
    st.stop()

# Cache thread to act as Singleton resource instance across browser refreshes
@st.cache_resource
def get_hardware_receivers():
    receiver = HardwareReceiver(mode="serial", port="COM3")
    receiver.start()
    return receiver

esp_receiver = get_hardware_receivers()

st.title("Smart Care+ Sentinel Web Dashboard")

# Top Level Buttons (Simple, Clear, Large)
st.header("System Controls")
col_run, col_stop = st.columns(2)
start_cam = col_run.button("Start System", use_container_width=True)
stop_cam = col_stop.button("Halt System", use_container_width=True)

st.divider()

# Live Camera Feed Section with Instant Emergency Alert Placer
st.header("Real-Time Camera Intelligence")
alert_placeholder = st.empty()
frame_placeholder = st.empty()

# Metrics Section directly underneath the Camera
st.header("Live Vitals & Status")
col1, col2 = st.columns(2)
hr_metric = col1.empty()
status_metric = col2.empty()

st.divider()

# Statistics Section vertically appended at the bottom
st.header("Visual Historical Analytics")
stats_placeholder = st.empty()

# Render Statistics
stats = get_weekly_stats()
if stats:
    df = pd.DataFrame(stats, columns=["Date", "Fall Events"])
    # Explicitly declare x data type for bulletproof Plotly plotting
    fig = px.bar(df, x="Date", y="Fall Events", title="Critical Event Frequency", 
                 color_discrete_sequence=["#ef553b"])
    fig.update_xaxes(type='category')
    stats_placeholder.plotly_chart(fig)
else:
    stats_placeholder.info("System healthy. 0 critical occurrences recorded timeline.")

if start_cam and not stop_cam:
    # Resource allocation mapping
    cap = cv2.VideoCapture(0)
    detector = FallDetectorCV(y_threshold=0.6)
    
    # Wrapped in a comprehensive try/finally map: ensures graceful memory de-allocation 
    try:
        while cap.isOpened() and not stop_cam:
            ret, frame = cap.read()
            if not ret:
                alert_placeholder.error("Stream disrupted. Camera hardware disconnected.")
                break
                
            hr = esp_receiver.get_heart_rate()
            processed_frame, is_fall, msg = detector.detect(frame)
            
            # Responsive UI Drawing calls (Metrics before Camera frame)
            hr_metric.metric("Current Heart Rate", f"{hr} BPM")
            
            # Single-event triggering per fall to prevent flooding APIs
            if is_fall and not st.session_state.fall_detected:
                st.session_state.fall_detected = True
                details = f"CV Metric Warning. Latest Heart Rate: {hr} BPM"
                log_event("Fall Detected", details)
                trigger_alerts(details)
                
                # Dynamically update the statistics chart if an event is freshly logged
                updated_stats = get_weekly_stats()
                if updated_stats:
                    df = pd.DataFrame(updated_stats, columns=["Date", "Fall Events"])
                    fig = px.bar(df, x="Date", y="Fall Events", title="Critical Event Frequency", 
                                 color_discrete_sequence=["#ef553b"])
                    fig.update_xaxes(type='category')
                    stats_placeholder.plotly_chart(fig)
                
            elif not is_fall:
                st.session_state.fall_detected = False
                
            if st.session_state.fall_detected:
                status_metric.metric("Current Status", f"💥 {msg}", delta_color="inverse")
                # Immediate Alert above Camera
                alert_placeholder.error(f"🚨 EMERGENCY 🚨: {msg}")
            else:
                status_metric.metric("Current Status", "🛡️ Secured")
                # Clear Emergency Alert when secured
                alert_placeholder.empty()
                
            # BGR -> RGB ensures Streamlit rendering interprets colors securely
            rgb_render = cv2.cvtColor(processed_frame, cv2.COLOR_BGR2RGB)
            frame_placeholder.image(rgb_render, channels="RGB", use_container_width=True)
            
    finally:
        # Memory Protection: Always executed, forcefully dismantling components.
        cap.release()
        detector.close_resources()
        alert_placeholder.empty()
