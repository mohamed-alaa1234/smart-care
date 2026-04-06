import sqlite3
import datetime
import os

# Create absolute path for the database relative to this script to prevent creating db files in arbitrary working directories
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "history.db")

def init_db():
    """Initializes the SQLite database with the required schema."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS history 
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                     timestamp DATETIME, 
                     event_type TEXT, 
                     details TEXT)''')
    # Context manager 'with conn:' auto-commits transactions and auto-closes properly

def log_event(event_type, details):
    """Logs an event securely preventing SQL Injection via parameterized queries."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            # Uses ? bindings to protect against SQL injections
            cursor.execute(
                "INSERT INTO history (timestamp, event_type, details) VALUES (?, ?, ?)",
                (datetime.datetime.now().isoformat(), event_type, details)
            )
    except sqlite3.Error as e:
        print(f"Database error while logging event: {e}")

def get_weekly_stats():
    """Retrieves weekly fall detection statistics safely."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT date(timestamp) as day, count(*) 
                FROM history 
                WHERE event_type=? 
                GROUP BY day 
                ORDER BY day DESC 
                LIMIT 7
            """, ("Fall Detected",))
            return cursor.fetchall()
    except sqlite3.Error as e:
        print(f"Database query error: {e}")
        return []
