import subprocess
import sys
import os

def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    print("Verifying Database Integrity...")
    subprocess.run([sys.executable, "db_setup.py"])
    # 2. Start Dashboard
    print("Launching Dashboard...")
    try:
        # Using python -m streamlit to ensure we use the same environment
        subprocess.run([sys.executable, "-m", "streamlit", "run", "nexly_ui.py"], shell=True)
    except Exception as e:
        print(f"Error: Could not launch dashboard. {e}")

if __name__ == "__main__":
    main()
