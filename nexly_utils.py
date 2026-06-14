import sqlite3
import datetime
import os
import asyncio
import sys

# Windows Asyncio Fix
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

DB_PATH = os.path.join(os.path.dirname(__file__), "nexly.db")

def log_activity(module, action, details, status="Info"):
    """Professional logging for Nexly Dashboard."""
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] [{module}] {action}: {details}")
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO activity_logs (module, action, details, status)
            VALUES (?, ?, ?, ?)
        ''', (module, action, details, status))
        conn.commit()
        conn.close()
    except:
        pass

def get_db_connection():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def save_lead(lead_data):
    """Saves lead with advanced deduplication."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if already exists in this campaign (By name)
        cursor.execute("SELECT id FROM leads WHERE business_name = ? AND campaign_id = ?", 
                       (lead_data.get('business_name'), lead_data.get('campaign_id')))
        if cursor.fetchone():
            conn.close()
            return False
            
        # Check if email is unique globally (only if it's a real email)
        email = lead_data.get('email')
        if email and email != "N/A":
            cursor.execute("SELECT id FROM leads WHERE email = ?", (email,))
            if cursor.fetchone():
                conn.close()
                return False

        columns = ', '.join(lead_data.keys())
        placeholders = ', '.join(['?' for _ in lead_data])
        query = f"INSERT INTO leads ({columns}) VALUES ({placeholders})"
        cursor.execute(query, list(lead_data.values()))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        log_activity("DB", "Error", str(e), "Error")
        return False
