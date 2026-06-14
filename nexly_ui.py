import streamlit as st
import pandas as pd
import asyncio
import nest_asyncio
import sqlite3
import os
import sys
import time
import tkinter as tk
from tkinter import filedialog
from datetime import datetime
from nexly_utils import get_db_connection, log_activity
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import imaplib
import email as imap_email
import random
import re

# Check and import NexlyHunter
try:
    from nexly_hunter import NexlyHunter
except ImportError:
    NexlyHunter = None

import db_setup
# --- DATABASE HELPERS ---
DB_PATH = os.path.join(os.path.dirname(__file__), "nexly.db")
db_setup.setup_database(DB_PATH)

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

nest_asyncio.apply()

# --- DATABASE HELPERS ---
DB_PATH = os.path.join(os.path.dirname(__file__), "nexly.db")

def query_read(query, params=()):
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    try:
        df = pd.read_sql_query(query, conn, params=params)
        return df
    except Exception as e:
        # st.warning(f"DB Error: {e}")
        return pd.DataFrame()
    finally:
        conn.close()

def query_write(query, params=()):
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    try:
        conn.execute(query, params)
        conn.commit()
        return True
    except Exception as e:
        st.error(f"Error saving to DB: {e}")
        return False
    finally:
        conn.close()

# --- OUTREACH HELPERS FROM ELITE BOT ---
def send_email(smtp_host, smtp_port, sender_name, sender_email, app_password, to_email, subject, body):
    msg = MIMEMultipart()
    safe_subject = str(subject).replace('\n', ' ').replace('\r', '').strip()
    safe_sender_name = str(sender_name).replace('\n', ' ').replace('\r', '').strip()
    msg['From'] = f"{safe_sender_name} <{sender_email}>"
    msg['To'] = to_email
    msg['Subject'] = safe_subject
    msg.attach(MIMEText(body, 'plain'))
    try:
        server = smtplib.SMTP(smtp_host, smtp_port)
        server.starttls()
        server.login(sender_email, app_password)
        text = msg.as_string()
        server.sendmail(sender_email, to_email, text)
        server.quit()
        return True, ""
    except Exception as e:
        return False, str(e)

def apply_spintax_and_identity(text, acc_name):
    greetings = ["Hi", "Hello", "Hey", "Greetings"]
    closings = ["Best", "Regards", "Cheers", "Sincerely"]
    text = re.sub(r'(?i)\bHi\b', random.choice(greetings), text, count=1)
    if re.search(r'(?i)\bBest,\n[^\n]+', text):
        text = re.sub(r'(?i)\bBest,\n[^\n]+', f"{random.choice(closings)},\n{acc_name}", text)
    elif re.search(r'(?i)\bBest,\n?$', text):
        text = re.sub(r'(?i)\bBest,\n?$', f"{random.choice(closings)},\n{acc_name}", text)
    pattern = re.compile(r'\{([^{}]+)\}')
    while True:
        match = pattern.search(text)
        if not match: break
        options = match.group(1).split('|')
        text = text[:match.start()] + random.choice(options) + text[match.end():]
    return text

def fill_placeholders(text, name, company, city, niche, email):
    if not text: return ""
    return text.replace("{{Name}}", str(name)).replace("{{Company}}", str(company))\
               .replace("{{City}}", str(city)).replace("{{Niche}}", str(niche)).replace("{{Email}}", str(email))

def match_niche_profile(company, niche):
    try:
        profiles = query_read("SELECT ProfileType, TargetKeywords FROM niche_scripts WHERE ProfileType != 'General'")
        company = str(company).lower()
        niche = str(niche).lower()
        combined_text = f"{company} {niche}"
        for _, profile in profiles.iterrows():
            p_type, keywords = profile['ProfileType'], profile['TargetKeywords']
            if not keywords: continue
            k_list = [k.strip().lower() for k in keywords.split(',') if k.strip()]
            for k in k_list:
                if k in combined_text: return p_type
        return 'General'
    except: return 'General'

def get_script_for_step(profile_type, step):
    try:
        if step == 1:
            cols = ['Step1_Subj1', 'Step1_Body1', 'Step1_Subj2', 'Step1_Body2', 'Step1_Subj3', 'Step1_Body3', 'Step1_Subj4', 'Step1_Body4', 'Step1_Subj5', 'Step1_Body5']
            res = query_read(f"SELECT {', '.join(cols)} FROM niche_scripts WHERE ProfileType = ?", (profile_type,))
            if res.empty or res.iloc[0].isna().all():
                res = query_read(f"SELECT {', '.join(cols)} FROM niche_scripts WHERE ProfileType = 'General'")
            if not res.empty:
                row = res.iloc[0]
                valid_pairs = []
                for i in range(5):
                    s, b = row[i*2], row[i*2+1]
                    if s and b: valid_pairs.append((s, b))
                if valid_pairs: return random.choice(valid_pairs)
            return ("", "")
        else:
            col_subj, col_body = f"Step{step}_Subj", f"Step{step}_Body"
            res = query_read(f"SELECT {col_subj}, {col_body} FROM niche_scripts WHERE ProfileType = ?", (profile_type,))
            if not res.empty and res.iloc[0,0] and res.iloc[0,1]:
                return res.iloc[0,0], res.iloc[0,1]
            res = query_read(f"SELECT {col_subj}, {col_body} FROM niche_scripts WHERE ProfileType = 'General'")
            return (res.iloc[0,0], res.iloc[0,1]) if not res.empty and res.iloc[0,0] else ("", "")
    except: return ("", "")

def pick_folder():
    """Opens a native Window pop-up to select a folder."""
    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)
    folder = filedialog.askdirectory(parent=root)
    root.destroy()
    return folder

def sync_leads_to_csv(cid, folder_path, campaign_name):
    """Automatically backs up database leads to the selected folder."""
    if not folder_path or not os.path.exists(folder_path):
        return
    df = query_read("SELECT * FROM leads WHERE campaign_id = ?", (cid,))
    if not df.empty:
        safe_name = "".join([c for c in campaign_name if c.isalpha() or c.isdigit() or c==' ']).rstrip()
        file_path = os.path.join(folder_path, f"{safe_name}_Leads_Backup.csv")
        try:
            df.to_csv(file_path, index=False)
        except Exception:
            pass

# --- PAGE CONFIG ---
st.set_page_config(page_title="Nexly Elite v3.0", layout="wide", page_icon="📈")

st.markdown("""
<style>
    .stApp { background-color: #0A0C10; color: #E0E0E0; }
    .brand { font-size: 2.2rem; font-weight: 900; color: #1FDF64; border-bottom: 2px solid #1FDF64; padding-bottom: 10px; margin-bottom: 20px;}
    .terminal-box { 
        background: #000; border: 1px solid #1FDF64; border-radius: 8px; padding: 15px; 
        font-family: 'Courier New', monospace; height: 350px; overflow-y: auto; color: #1FDF64; font-size: 0.8rem;
    }
    .panel { background: rgba(255,255,255,0.03); border-radius: 10px; padding: 20px; border: 1px solid rgba(255,255,255,0.1); margin-bottom: 15px; }
    .btn-green { background-color: #1FDF64 !important; color: black !important; font-weight: bold; border-radius: 6px; }
    .sidebar .sidebar-content { background-color: #12151A; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# SUPER ARCHITECTURE: SIDEBAR CAMPAIGN SELECTOR
# ==========================================
st.sidebar.markdown("<div class='brand'>NEXLY CORE</div>", unsafe_allow_html=True)
st.sidebar.write("Active Mission Control")

camp_df = query_read("SELECT * FROM campaigns ORDER BY id DESC")
cid = None
c_niche = "Default"
c_city = "New York"
c_folder = ""
c_name = ""

if not camp_df.empty:
    camp_names = camp_df['name'].tolist()
    
    if 'active_camp' not in st.session_state or st.session_state.active_camp not in camp_names:
        st.session_state.active_camp = camp_names[0]
        
    selected_campaign = st.sidebar.selectbox("🔗 Connected Campaign", camp_names, index=camp_names.index(st.session_state.active_camp))
    st.session_state.active_camp = selected_campaign
    
    active_camp_data = camp_df[camp_df['name'] == selected_campaign].iloc[0]
    cid = int(active_camp_data['id'])
    c_name = active_camp_data['name']
    c_folder = str(active_camp_data['folder_path'] or "")
    c_niche = str(active_camp_data['niche'] or "Business")
    c_city = str(active_camp_data.get('city', "New York"))
    
    st.sidebar.success("🟢 System Connected")
    st.sidebar.caption(f"**Drive:** {c_folder}")
    
    if st.sidebar.button("Sync Data to Folder"):
        sync_leads_to_csv(cid, c_folder, c_name)
        st.sidebar.info("CSV Updated!")
else:
    st.sidebar.error("🔴 Disconnected. Create a Campaign!")

st.sidebar.divider()
total_leads = query_read("SELECT COUNT(*) as total FROM leads WHERE campaign_id=?", (cid,)).iloc[0,0] if cid else 0
st.sidebar.metric("Leads Acquired", total_leads)

# ==========================================
# MAIN DASHBOARD 
# ==========================================
t_camp, t_hunt, t_outreach, t_acc, t_set = st.tabs([
    "📁 CAMPAIGN & FOLDERS", 
    "🎯 TARGET ACQUISITION (HUNT)", 
    "📤 GLOBAL OUTREACH", 
    "🔑 ACCOUNTS", 
    "⚙️ SETTINGS"
])

# ----------------- T1: CAMPAIGNS -----------------
with t_camp:
    c1, c2 = st.columns([1, 1.5])
    with c1:
        st.markdown("<div class='panel'>", unsafe_allow_html=True)
        st.subheader("Create New Mission Campaign")
        
        n_name = st.text_input("Campaign Name", placeholder="e.g. NYC Dentists 2026")
        n_niche = st.text_input("Industry / Niche", placeholder="e.g. Dentists")
        n_city = st.text_input("Target City", placeholder="e.g. New York")
        
        st.write("**Folder Save Location**")
        if 'picked_folder' not in st.session_state:
            st.session_state.picked_folder = "C:\\"
            
        fc1, fc2 = st.columns([1, 4])
        with fc1:
            if st.button("📁 Browse"):
                chosen = pick_folder()
                if chosen:
                    st.session_state.picked_folder = chosen
                st.rerun()
        with fc2:
            n_folder = st.text_input("Path", value=st.session_state.picked_folder, disabled=True)

        if st.button("💾 SAVE CAMPAIGN", type="primary", use_container_width=True):
            if n_name.strip():
                # Add columns to query
                res = query_write("INSERT OR IGNORE INTO campaigns (name, folder_path, niche, city) VALUES (?,?,?,?)", 
                                 (n_name, st.session_state.picked_folder, n_niche, n_city))
                if res:
                    st.session_state.active_camp = n_name # auto-connect
                    st.success("Campaign Built Successfully!")
                    time.sleep(1)
                    st.rerun()
            else:
                st.error("Campaign name cannot be empty.")
        st.markdown("</div>", unsafe_allow_html=True)
        
    with c2:
        if cid:
            st.subheader(f"📊 Live Data: {c_name}")
            df_leads = query_read("SELECT business_name, email, phone, status, linkedin_url FROM leads WHERE campaign_id=? ORDER BY id DESC", (cid,))
            if not df_leads.empty:
                st.dataframe(df_leads, use_container_width=True, height=350)
            else:
                st.info("Folder is currently empty. Go to Target Acquisition to find leads.")

# ----------------- T2: HUNTING -----------------
with t_hunt:
    if not cid:
        st.warning("Please connect to a Campaign in the Sidebar first.")
    else:
        h1, h2 = st.columns([1, 2])
        with h1:
            st.markdown("<div class='panel'>", unsafe_allow_html=True)
            st.subheader("Radar Configuration")
            h_niche = st.text_input("Refine Niche", value=c_niche)
            h_city = st.text_input("Refine City", value=c_city)
            h_limit = st.slider("Target Quota", 1, 500, 10)
            
            st.write("**Data Requirements**")
            f_email = st.checkbox("Require Email", value=True)
            f_phone = st.checkbox("Require Phone", value=False)
            f_li = st.checkbox("Require LinkedIn", value=False)
            
            d_view = st.toggle("👁️ Watch Live Engine (Direct View Mode)", value=False)
            
            if st.button("🚀 INITIATE HUNT", type="primary", use_container_width=True):
                st.session_state.is_hunting = True
                log_activity("Hunter", "Start", f"Hunting {h_limit} {h_niche}s in {h_city}...")
                
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
            st.markdown("</div>", unsafe_allow_html=True)
            
        with h2:
            st.subheader("Console Output")
            logs = query_read("SELECT timestamp, module, action, details FROM activity_logs ORDER BY id DESC LIMIT 25")
            log_str = ""
            if not logs.empty:
                for _, r in logs.iterrows():
                    ts = r['timestamp'].split(' ')[1] if ' ' in r['timestamp'] else r['timestamp']
                    log_str += f"[{ts}] [{r['module']}] {r['action']}: {r['details']}\n"
            st.markdown(f"<pre class='terminal-box'>{log_str}</pre>", unsafe_allow_html=True)

# ----------------- T3: OUTREACH -----------------
with t_outreach:
    if not cid:
        st.warning("Connect to Campaign from Sidebar.")
    else:
        o1, o2 = st.columns([1, 1.5])
        with o1:
            st.markdown("<div class='panel'>", unsafe_allow_html=True)
            st.subheader("Elite Outreach Engine")
            
            accs = query_read("SELECT id, name, email, password, bounces FROM accounts WHERE is_selected=1")
            uncontacted = query_read("SELECT id, business_name, email, niche, city FROM leads WHERE campaign_id=? AND status='Found'", (cid,))
            
            if accs.empty:
                st.error("No active/selected sender accounts! Go to Accounts tab.")
            elif uncontacted.empty:
                st.info(f"No leads waiting for Step 1 in **{c_name}**.")
            else:
                st.write(f"Targets waiting: **{len(uncontacted)}**")
                daily_limit = st.number_input("Sends per Account", 1, 500, 50)
                min_delay = st.number_input("Min Delay (sec)", 0, 60, 5)
                max_delay = st.number_input("Max Delay (sec)", 1, 120, 15)
                
                if st.button("🚀 INITIATE BLAST SEQUENCE", type="primary", use_container_width=True):
                    sent_count = 0
                    pb = st.progress(0, "Preparing...")
                    status_text = st.empty()
                    
                    active_acc_list = accs.to_dict('records')
                    account_sends = {acc['id']: 0 for acc in active_acc_list}
                    
                    for i, lead in uncontacted.iterrows():
                        # Find available account
                        available_accs = [a for a in active_acc_list if account_sends[a['id']] < daily_limit]
                        if not available_accs:
                            st.warning("All accounts reached daily limit!")
                            break
                        
                        acc = available_accs[sent_count % len(available_accs)]
                        
                        # Match script
                        p_type = match_niche_profile(lead['business_name'], lead['niche'] or c_niche)
                        subj_raw, body_raw = get_script_for_step(p_type, 1)
                        
                        if not subj_raw:
                            status_text.warning(f"No script for {lead['email']} (Step 1)")
                            continue
                            
                        # Personalize
                        subj = fill_placeholders(subj_raw, lead['business_name'], lead['business_name'], lead['city'] or c_city, lead['niche'] or c_niche, lead['email'])
                        body = fill_placeholders(body_raw, lead['business_name'], lead['business_name'], lead['city'] or c_city, lead['niche'] or c_niche, lead['email'])
                        
                        # Spintax
                        subj_final = apply_spintax_and_identity(subj, acc['name'])
                        body_final = apply_spintax_and_identity(body, acc['name'])
                        
                        status_text.text(f"Sending via {acc['email']} to {lead['email']}...")
                        
                        # Simulate Gmail SMTP (User must use App Password)
                        success, err = send_email("smtp.gmail.com", 587, acc['name'], acc['email'], acc['password'], lead['email'], subj_final, body_final)
                        
                        if success:
                            sent_count += 1
                            account_sends[acc['id']] += 1
                            query_write("UPDATE leads SET status='Contacted', sender_email=?, last_contacted=CURRENT_TIMESTAMP, step=1 WHERE id=?", (acc['email'], lead['id']))
                            pb.progress((i+1)/len(uncontacted), f"Sent {sent_count} emails...")
                            time.sleep(random.randint(min_delay, max_delay))
                        else:
                            query_write("UPDATE accounts SET bounces = bounces + 1 WHERE id=?", (acc['id'],))
                            log_activity("Outreach", "Error", f"Failed to {lead['email']}: {err}")
                    
                    st.success(f"Sequence complete! Sent {sent_count} emails.")
                    sync_leads_to_csv(cid, c_folder, c_name)
                    time.sleep(2)
                    st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
            
        with o2:
            st.subheader("Campaign Delivery Metrics")
            st.write("Current Campaign: **" + c_name + "**")
            stats = query_read("SELECT status, COUNT(*) as c FROM leads WHERE campaign_id=? GROUP BY status", (cid,))
            if not stats.empty:
                st.dataframe(stats, hide_index=True, use_container_width=True)
            else:
                st.info("No data yet.")

# ----------------- T4: ACCOUNTS -----------------
with t_acc:
    a1, a2 = st.columns([1, 2])
    with a1:
        st.markdown("<div class='panel'>", unsafe_allow_html=True)
        st.subheader("Add Sender Account")
        with st.form("acc_form", clear_on_submit=True):
            a_name = st.text_input("Sender Name (Display)", placeholder="Hassan")
            a_email = st.text_input("Gmail Address")
            a_pass = st.text_input("App Password", type="password")
            if st.form_submit_button("💾 LINK ACCOUNT", use_container_width=True):
                if a_name and a_email and a_pass:
                    res = query_write("INSERT OR IGNORE INTO accounts (name, email, password, is_selected) VALUES (?,?,?,1)", (a_name, a_email, a_pass))
                    if res:
                        st.success("Account Linked!")
                        time.sleep(1)
                        st.rerun()
                else:
                    st.error("Please fill all fields.")
        st.markdown("</div>", unsafe_allow_html=True)
    with a2:
        st.subheader("Accounts Pipeline")
        alists = query_read("SELECT id, name, email, bounces, is_selected FROM accounts")
        if not alists.empty:
            for _, r in alists.iterrows():
                col_info, col_sel, col_del = st.columns([3, 1, 1])
                health = "🟢 Healthy" if r['bounces'] < 5 else f"🔴 At Risk ({r['bounces']} Bounces)"
                col_info.write(f"**{r['name']}** ({r['email']})\n{health}")
                
                is_selected = col_sel.checkbox("Use", value=bool(r['is_selected']), key=f"sel_{r['id']}")
                if is_selected != bool(r['is_selected']):
                    query_write("UPDATE accounts SET is_selected=? WHERE id=?", (int(is_selected), r['id']))
                    st.rerun()
                    
                if col_del.button("🗑️", key=f"rm_{r['id']}"):
                    query_write("DELETE FROM accounts WHERE id=?", (r['id'],))
                    st.rerun()
        else:
            st.info("No accounts connected.")

# ----------------- T5: SETTINGS (SMART SCRIPT MANAGER) -----------------
with t_set:
    st.header("⚙️ Smart Script & Niche Manager")
    
    with st.expander("Dynamic Tags Guide"):
        st.info("Use these in Scripts: `{{Name}}, {{Email}}, {{Company}}, {{City}}, {{Niche}}`")

    profiles = query_read("SELECT * FROM niche_scripts")
    if not profiles.empty:
        p_options = {r['ProfileType']: r['ProfileTitle'] for _, r in profiles.iterrows()}
        sel_ptype = st.selectbox("Select Profile Editor:", list(p_options.keys()), format_func=lambda x: p_options[x])
        p_data = profiles[profiles['ProfileType'] == sel_ptype].iloc[0]

        with st.form(f"f_profile_{sel_ptype}"):
            st.subheader(f"Editing: {p_data['ProfileTitle']}")
            new_title = st.text_input("Title", p_data['ProfileTitle'], disabled=(sel_ptype=='General'))
            new_keys = st.text_input("Target Keywords", p_data['TargetKeywords'] or "", disabled=(sel_ptype=='General'))
            
            st.write("#### Step 1 Variations (Shuffle Mode)")
            c1, c2 = st.columns(2)
            with c1:
                v1_s = st.text_input("V1 Subj", p_data['Step1_Subj1'] or "")
                v1_b = st.text_area("V1 Body", p_data['Step1_Body1'] or "", height=100)
                v3_s = st.text_input("V3 Subj", p_data['Step1_Subj3'] or "")
                v3_b = st.text_area("V3 Body", p_data['Step1_Body3'] or "", height=100)
                v5_s = st.text_input("V5 Subj", p_data['Step1_Subj5'] or "")
                v5_b = st.text_area("V5 Body", p_data['Step1_Body5'] or "", height=100)
            with c2:
                v2_s = st.text_input("V2 Subj", p_data['Step1_Subj2'] or "")
                v2_b = st.text_area("V2 Body", p_data['Step1_Body2'] or "", height=100)
                v4_s = st.text_input("V4 Subj", p_data['Step1_Subj4'] or "")
                v4_b = st.text_area("V4 Body", p_data['Step1_Body4'] or "", height=100)
                
            st.write("#### Auto-Followups (Sequence)")
            f1, f2 = st.columns(2)
            with f1:
                s2_s = st.text_input("Step 2 Subj", p_data['Step2_Subj'] or "")
                s2_b = st.text_area("Step 2 Body", p_data['Step2_Body'] or "", height=100)
            with f2:
                s3_s = st.text_input("Step 3 Subj", p_data['Step3_Subj'] or "")
                s3_b = st.text_area("Step 3 Body", p_data['Step3_Body'] or "", height=100)
            
            f3, f4 = st.columns(2)
            with f3:
                s4_s = st.text_input("Step 4 Subj", p_data['Step4_Subj'] or "")
                s4_b = st.text_area("Step 4 Body", p_data['Step4_Body'] or "", height=100)
            with f4:
                s5_s = st.text_input("Step 5 Subj", p_data['Step5_Subj'] or "")
                s5_b = st.text_area("Step 5 Body", p_data['Step5_Body'] or "", height=100)

            if st.form_submit_button("💾 UPDATE PROFILE"):
                query_write("""UPDATE niche_scripts SET 
                    ProfileTitle=?, TargetKeywords=?, 
                    Step1_Subj1=?, Step1_Body1=?, Step1_Subj2=?, Step1_Body2=?, Step1_Subj3=?, Step1_Body3=?, Step1_Subj4=?, Step1_Body4=?, Step1_Subj5=?, Step1_Body5=?,
                    Step2_Subj=?, Step2_Body=?, Step3_Subj=?, Step3_Body=?,
                    Step4_Subj=?, Step4_Body=?, Step5_Subj=?, Step5_Body=?
                    WHERE ProfileType=?""", 
                    (new_title, new_keys, v1_s, v1_b, v2_s, v2_b, v3_s, v3_b, v4_s, v4_b, v5_s, v5_b, s2_s, s2_b, s3_s, s3_b, s4_s, s4_b, s5_s, s5_b, sel_ptype))
                st.success("Profile Updated!")
                st.rerun()
    else:
        st.info("Profiles missing in niche_scripts table.")
