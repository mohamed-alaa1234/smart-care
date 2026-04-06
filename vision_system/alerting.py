import os
import requests
import datetime
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException
from dotenv import load_dotenv

# Secure variable loading
load_dotenv()

def send_telegram_alert(timestamp, details):
    """Sends an immediate alert via Telegram Bot."""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    
    if not token or not chat_id:
        print("Telegram configuration missing in .env. Skipping alert.")
        return
        
    msg = f"⚠️ ALERT: Fall Detected!\nTime: {timestamp}\nDetails: {details}"
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    
    try:
        # Prevents thread deadlocks/hangs if network drops via timeout parameter
        response = requests.post(url, json={"chat_id": chat_id, "text": msg}, timeout=5)
        response.raise_for_status() 
        print("Telegram alert securely sent.")
    except requests.exceptions.RequestException as e:
        print(f"Failed to communicate with Telegram API: {e}")

def send_whatsapp_alert(timestamp, details):
    """Sends an immediate alert via WhatsApp (Twilio)."""
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    to_whatsapp = os.getenv("TWILIO_TO_WHATSAPP")
    
    if not account_sid or not auth_token or not to_whatsapp:
        print("Twilio configuration missing in .env. Skipping WhatsApp alert.")
        return
        
    from_whatsapp = os.getenv("TWILIO_FROM_WHATSAPP", "whatsapp:+14155238886")
    msg = f"⚠️ ALERT: Fall Detected!\nTime: {timestamp}\nDetails: {details}"
    
    try:
        client = Client(account_sid, auth_token)
        client.messages.create(
            body=msg,
            from_=from_whatsapp,
            to=to_whatsapp
        )
        print("WhatsApp alert securely sent.")
    except TwilioRestException as e:
        print(f"Twilio API Error during execution: {e}")
    except Exception as e:
        print(f"Unexpected Twilio client initialization error: {e}")

def trigger_alerts(details):
    """Entry point to dispatch parallel logic."""
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    send_telegram_alert(ts, details)
    send_whatsapp_alert(ts, details)
