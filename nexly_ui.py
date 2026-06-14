import streamlit as st
import pandas as pd
import sqlite3
import os
import time
import asyncio
import nest_asyncio
import tkinter as tk
from tkinter import filedialog
from nexly_utils import log_activity, get_db_connection
from db_setup import setup_database

# Windows Asyncio Patch
nest_asyncio.apply()

# Initialize DB
DB_PATH = os.path.join(os.path.dirname(__file__), "nexly.db")
setup_database(DB_PATH)

st.set_page_config(page_title="Nexly AI | Autonomous Outreach", layout="wide")

# Custom Glassmorphism CSS
st.markdown("""
<style>
    .main { background: #0e1117; color: white; }
    .stButton>button { border-radius: 8px; background: linear-gradient(45deg, #00d2ff, #3a7bd5); color: white; border: none; }
    .stMetric { background: rgba(255, 255, 255, 0.05); padding: 15px; border-radius: 12px; border: 1px solid rgba(255,255,255,0.1); }
</style>
""", unsafe_allow_html=True)

# Helper for DB Queries
def query_read(q, params=()):
    conn = get_db_connection()
    df = pd.read_sql_query(q, conn, params=params)
    conn.close()
    return df

def query_write(q, params=()):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(q, params)
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        st.error(f"Error saving to DB: {e}")
        return False

# Folder Picker using Tkinter (Windows workaround)
def pick_folder():
    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)
    folder = filedialog.askdirectory(master=root)
    root.destroy()
    return folder

# CSV Sync Logic
def sync_leads_to_csv(campaign_id, folder_path, campaign_name):
    if not folder_path or not os.path.exists(folder_path): return
    df = query_read("SELECT * FROM leads WHERE campaign_id=?", (campaign_id,))
    csv_file = os.path.join(folder_path, f"{campaign_name}_leads.csv")
    df.to_csv(csv_file, index=False)

# Sidebar: Master Control
with st.sidebar:
    st.image("https://img.icons8.com/clouds/150/000000/artificial-intelligence.png")
    st.title("Nexly v3.0")
    
    # Campaign Selector
    c_list = query_read("SELECT id, name, folder_path FROM campaigns")
    current_campaign = st.selectbox("Current Campaign", ["Select One"] + c_list['name'].tolist())
    
    if current_campaign != "Select One":
        row = c_list[c_list['name'] == current_campaign].iloc[0]
        cid = int(row['id'])
        c_folder = row['folder_path']
        c_name = row['name']
        st.info(f"📁 Source: {c_folder}")
    else:
        cid = None
        st.warning("Please select or create a campaign.")

    if st.button("➕ New Project/Campaign"):
        st.session_state.show_new_campaign = True

    if st.session_state.get('show_new_campaign'):
        with st.expander("Configure New Campaign", expanded=True):
            new_name = st.text_input("Name (e.g. Dentists_NY)")
            if st.button("Select Save Folder"):
                st.session_state.temp_folder = pick_folder()
            
            if st.session_state.get('temp_folder'):
                st.write(f"Saving to: {st.session_state.temp_folder}")
                if st.button("Create Campaign"):
                    if new_name and st.session_state.temp_folder:
                        if query_write("INSERT INTO campaigns (name, folder_path) VALUES (?, ?)", (new_name, st.session_state.temp_folder)):
                            st.success("Campaign Ready!")
                            st.session_state.show_new_campaign = False
                            st.rerun()

# Main Tabs
t1, t2, t3, t4, t5 = st.tabs(["📊 Dashboard", "🕵️ Hunting", "📧 Outreach", "🔑 Accounts", "⚙️ Settings"])

with t1:
    st.subheader("System Overview")
    col1, col2, col3, col4 = st.columns(4)
    
    if cid:
        total_leads = query_read("SELECT COUNT(*) as c FROM leads WHERE campaign_id=?", (cid,)).iloc[0,0] if cid else 0
        total_sent = 120 # Placeholder
        active_accs = query_read("SELECT COUNT(*) as c FROM accounts WHERE status='Active'").iloc[0,0]
        
        col1.metric("Leads Acquired", total_leads)
        col2.metric("Emails Sent", total_sent)
        col3.metric("Follow-ups", 45)
        col4.metric("Accounts Active", active_accs)
        
        st.write("### Recent Activity")
        logs = query_read("SELECT timestamp, module, action, details FROM activity_logs ORDER BY id DESC LIMIT 5")
        st.table(logs)
    else:
        st.warning("Choose a campaign in the sidebar to load data.")

with t2:
    st.subheader("Autonomous Lead Hunting")
    if not cid:
        st.error("Please create or select a campaign in the sidebar first!")
    else:
        c1, c2 = st.columns([1, 2])
        with c1:
            h_niche = st.text_input("Target Niche", value="Dentist")
            h_city = st.text_input("Target City", value="New York")
            h_limit = st.number_input("Leads Limit", 1, 500, 10)
            
            st.divider()
            st.markdown("**Data Requirements**")
            f_email = st.checkbox("Require Email", value=True)
            f_phone = st.checkbox("Require Phone", value=False)
            f_li = st.checkbox("Require LinkedIn", value=False)
            
            d_view = st.toggle("👁️ Watch Live Engine (Direct View Mode)", value=False)
            
            if st.button("🚀 INITIATE HUNT", type="primary", use_container_width=True):
                st.session_state.is_hunting = True
                log_activity("Hunter", "Start", f"Hunting {h_limit} {h_niche}s in {h_city}...")
                
                # Import here to avoid circular or early heavy loads
                from nexly_hunter import NexlyHunter
                if NexlyHunter:
                    hunter = NexlyHunter(headless=not d_view, config={
                        "emails": f_email, 
                        "phones": f_phone, 
                        "linkedin": f_li
                    })
                    async def do_hunt():
                        try:
                            await hunter.start()
                            pb = st.progress(0, "Warming up...")
                            def on_update(prog):
                                pb.progress(min(prog, 1.0), text=f"Acquired: {int(prog*h_limit)} / {h_limit}")
                                # Sync DB to CSV immediately after every new lead
                                sync_leads_to_csv(cid, c_folder, c_name)
                                
                            await hunter.hunt(h_niche, h_city, h_limit, cid, on_update)
                        except Exception as e:
                            log_activity("Hunter", "Fatal Error", str(e))
                        finally:
                            await hunter.stop()
                    asyncio.run(do_hunt())
                    st.success("Radar Search Completed. Leads Saved to DB & Folder!")
                    time.sleep(1.5)
                    st.rerun()
                else:
                    st.error("NexlyHunter core is missing or broken.")

        with c2:
            st.markdown(f"**Live Results: {current_campaign}**")
            df_leads = query_read("SELECT business_name, email, phone, status, linkedin_url FROM leads WHERE campaign_id=? ORDER BY id DESC", (cid,))
            st.dataframe(df_leads, use_container_width=True, height=500)

with t3:
    st.subheader("Outreach Engine")
    if not cid:
        st.error("Select campaign first.")
    else:
        st.write(f"Ready to contact {len(df_leads)} leads in queue.")
        st.button("⚡ Start Sending Campaign")

with t4:
    st.subheader("SMTP & Messaging Accounts")
    with st.expander("➕ Add New Account"):
        a_email = st.text_input("Account Email")
        a_pass = st.text_input("App Password", type="password")
        if st.button("Save Account"):
            if query_write("INSERT INTO accounts (email, password) VALUES (?, ?)", (a_email, a_pass)):
                st.success("Account Active!")
                st.rerun()
    
    accs = query_read("SELECT email, type, sent_today, status FROM accounts")
    st.dataframe(accs, use_container_width=True)

with t5:
    st.subheader("System Settings")
    st.text_input("Gemini API Key", type="password")
    st.slider("Max Daily Emails per Account", 10, 500, 50)
    if st.button("Purge All Logs"):
        query_write("DELETE FROM activity_logs")
        st.rerun()
