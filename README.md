# 📈 Nexly Elite : Autonomous AI B2B Outreach System

Nexly is a state-of-the-art, autonomous B2B lead generation and cold outreach suite. Designed for high-performance sales teams and digital agencies, it automates the entire funnel—from hunting leads across the web to sending highly personalized, multi-step email sequences.

![Nexly Banner](https://img.shields.io/badge/Nexly-Elite_v3.0-1FDF64?style=for-the-badge&logo=rocket)
![Python](https://img.shields.io/badge/Python-3.13+-blue?style=for-the-badge&logo=python)
![Playwright](https://img.shields.io/badge/Engine-Playwright-red?style=for-the-badge&logo=playwright)
![Streamlit](https://img.shields.io/badge/UI-Streamlit-FF4B4B?style=for-the-badge&logo=streamlit)

---

## 🌟 Key Features

### 🎯 1. Target Acquisition (Elite Hunter)
- **Recursive Web Crawling**: Deep-scans business websites to find hidden contact data.
- **Persistent Browser Context**: Uses stealth headers to bypass anti-scraping measures.
- **Smart Data Extraction**: Captures Emails, Phones, LinkedIn URLs, and Niche data with high precision.
- **Live Monitoring**: Watch the engine work in real-time with the Direct View Mode toggle.

### 📤 2. Global Outreach Pipeline
- **Smart Rotation Engine**: Rotate between multiple SMTP accounts to prevent spam flagging.
- **Niche-Based Scripts**: Automatically match the perfect script variation based on the lead's industry.
- **Spintax & Dynamic Logic**: Personalize emails with `{{Name}}`, `{{Company}}`, and random spintax `{Hi|Hello}`.
- **Health Tracking**: Integrated bounce tracking and account health monitoring.

### 📁 3. Centralized Control Panel
- **SQLite Persistence**: All leads and campaigns are saved locally.
- **Automatic CSV Synchronization**: Sync your leads to your preferred Windows folder instantly.
- **Campaign Folders**: Organize your outreach by city, niche, or date.

---

## 🛠️ Installation & Setup

### 1. Prerequisites
- **Python 3.13+** installed.
- **Google Chrome** (for Playwright engine).

### 2. Clone and Install
```bash
# Clone the repository
git clone https://github.com/carnoba/nexly.git
cd nexly

# Install dependencies
pip install -r requirements.txt

# Install Playwright browser
playwright install chromium
```

### 3. Database Initialization
Run the database setup script to initialize the SQLite engine:
```bash
python nexly_agent/db_setup.py
```

---

## 🔑 Setting Up Email Accounts (App Passwords)

To send emails through Nexly using a Gmail account, you **must** use an **App Password**.

1. Go to your **Google Account Settings**.
2. Navigate to **Security** > **2-Step Verification** (Ensure this is ON).
3. Scroll to the bottom and click on **App Passwords**.
4. Select **App**: `Other (Custom name)` and type `Nexly`.
5. Copy the **16-character code** provided.
6. In Nexly, go to the **Accounts** tab and enter your Gmail address and this code as the password.

---

## 🚀 How to Run

Launch the Nextly dashboard using Streamlit:

```bash
streamlit run nexly_agent/main.py
```

---

## 📂 Project Structure
- `main.py`: Entry point for the Streamlit UI.
- `nexly_hunter.py`: Recursive web crawler and lead extraction engine.
- `nexly_ui.py`: Core dashboard logic and UI components.
- `db_setup.py`: Database schema and migration manager.
- `nexly_utils.py`: Database helpers and logging utilities.

---

## 🛡️ Privacy & Security
Nexly is designed with security at its core. Your database (`nexly.db`), browser profiles, and local logs are automatically ignored by Git to ensure your sensitive business intelligence and credentials never leave your machine.

---

## 🏷️ SEO Tags
`#B2BOutreach` `#LeadGeneration` `#ColdEmailAutomation` `#SalesEnablement` `#AISalesAgent` `#PlaywrightScraper` `#DigitalMarketingTools` `#SaaSAutomation` `#PythonAutomation`

---

**Developed with ❤️ by the Nexly Team.**
