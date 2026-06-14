import sqlite3
import os

def setup_database(db_path):
    print(f"[DB] Initializing at: {db_path}")
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS campaigns (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE,
        folder_path TEXT,
        niche TEXT,
        city TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS leads (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        campaign_id INTEGER,
        business_name TEXT,
        owner_name TEXT,
        email TEXT,
        phone TEXT,
        website TEXT,
        linkedin_url TEXT,
        niche TEXT,
        city TEXT,
        lead_score INTEGER DEFAULT 0,
        status TEXT DEFAULT 'Found',
        step INTEGER DEFAULT 0,
        sender_email TEXT,
        found_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        last_contacted DATETIME,
        FOREIGN KEY (campaign_id) REFERENCES campaigns(id)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        email TEXT UNIQUE,
        password TEXT,
        type TEXT DEFAULT 'Email',
        status TEXT DEFAULT 'Active',
        daily_limit INTEGER DEFAULT 50,
        sent_today INTEGER DEFAULT 0,
        last_used DATETIME
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS scripts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        niche TEXT,
        step_number INTEGER,
        subject TEXT,
        body TEXT,
        UNIQUE(niche, step_number)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS activity_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        module TEXT,
        action TEXT,
        details TEXT,
        status TEXT DEFAULT 'Info'
    )''')

    c.execute("INSERT OR IGNORE INTO scripts (niche, step_number, subject, body) VALUES (?,?,?,?)",
              ("General", 1, "Quick question about {{Company}}", "Hi {{Owner}},\n\nI noticed your business online and wanted to reach out.\n\nBest regards"))

    # Migration: Add campaign_id to leads if missing
    columns = [col[1] for col in c.execute("PRAGMA table_info(leads)").fetchall()]
    if 'campaign_id' not in columns:
        print("[DB] Migrating: Adding campaign_id to leads")
        c.execute("ALTER TABLE leads ADD COLUMN campaign_id INTEGER REFERENCES campaigns(id)")
    if 'niche' not in columns:
        c.execute("ALTER TABLE leads ADD COLUMN niche TEXT")
    if 'city' not in columns:
        c.execute("ALTER TABLE leads ADD COLUMN city TEXT")
    if 'linkedin_url' not in columns:
        c.execute("ALTER TABLE leads ADD COLUMN linkedin_url TEXT")

    # Migration: Add niche and city to campaigns if missing
    camp_columns = [col[1] for col in c.execute("PRAGMA table_info(campaigns)").fetchall()]
    if 'niche' not in camp_columns:
        c.execute("ALTER TABLE campaigns ADD COLUMN niche TEXT")
    if 'city' not in camp_columns:
        c.execute("ALTER TABLE campaigns ADD COLUMN city TEXT")

    conn.commit()
    conn.close()
    print("[DB] Ready.")

if __name__ == "__main__":
    setup_database(os.path.join(os.path.dirname(__file__), "nexly.db"))
