"""GitHub Storage สำหรับบันทึกข้อมูลถาวรบน Streamlit Cloud"""

import json
import os
from typing import Optional
import requests

# GitHub Repository Settings
GITHUB_REPO = "noy55714085-byte/namtao-pupla-stats"
GITHUB_BRANCH = "main"
GITHUB_FILE_PATH = "data/history.json"

# ดึง GitHub Token จาก environment variable
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")


def get_github_api_url() -> str:
    """สร้าง GitHub API URL สำหรับไฟล์ history.json"""
    return f"https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_FILE_PATH}"


def get_github_raw_url() -> str:
    """สร้าง GitHub Raw URL สำหรับอ่านไฟล์โดยตรง"""
    return f"https://raw.githubusercontent.com/{GITHUB_REPO}/{GITHUB_BRANCH}/{GITHUB_FILE_PATH}"


def load_from_github() -> Optional[dict]:
    """โหลดข้อมูลจาก GitHub (Read-only)"""
    try:
        # ลองอ่านจาก raw URL ก่อน (เร็วกว่า)
        response = requests.get(get_github_raw_url(), timeout=10)
        if response.status_code == 200:
            return json.loads(response.text)
    except Exception:
        pass
    
    # ถ้า raw URL ไม่ได้ ลองใช้ API
    try:
        headers = {}
        if GITHUB_TOKEN:
            headers["Authorization"] = f"token {GITHUB_TOKEN}"
        
        response = requests.get(get_github_api_url(), headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            # ถอดรหัส base64 content
            import base64
            content = base64.b64decode(data["content"]).decode("utf-8")
            return json.loads(content)
    except Exception:
        pass
    
    return None


def save_to_github(db: dict) -> bool:
    """บันทึกข้อมูลลง GitHub (Write) ต้องมี GITHUB_TOKEN"""
    if not GITHUB_TOKEN:
        print("Warning: GITHUB_TOKEN not found - ไม่สามารถบันทึกลง GitHub")
        return False
    
    try:
        # แปลงข้อมูลเป็น JSON string
        content = json.dumps(db, ensure_ascii=False, indent=2) + "\n"
        
        # เข้ารหัส base64
        import base64
        content_b64 = base64.b64encode(content.encode("utf-8")).decode("utf-8")
        
        # ตรวจสอบว่าไฟล์มีอยู่แล้วหรือไม่
        headers = {"Authorization": f"token {GITHUB_TOKEN}"}
        response = requests.get(get_github_api_url(), headers=headers, timeout=10)
        
        data = {
            "message": f"Update history.json - {len(db.get('draws', []))} draws",
            "content": content_b64,
            "branch": GITHUB_BRANCH
        }
        
        if response.status_code == 200:
            # ไฟล์มีอยู่แล้ว - ต้องใส่ sha
            file_data = response.json()
            data["sha"] = file_data["sha"]
        
        # บันทึกลง GitHub
        response = requests.put(get_github_api_url(), headers=headers, json=data, timeout=10)
        
        if response.status_code in [200, 201]:
            print("Successfully saved to GitHub")
            return True
        else:
            print(f"Failed to save to GitHub: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"Error saving to GitHub: {e}")
        return False


def github_storage_available() -> bool:
    """ตรวจสอบว่า GitHub Storage พร้อมใช้งานหรือไม่"""
    return GITHUB_TOKEN is not None


if __name__ == "__main__":
    # ทดสอบการทำงาน
    print("Testing GitHub Storage...")
    print(f"GitHub Token available: {GITHUB_TOKEN is not None}")
    
    if github_storage_available():
        print("Loading from GitHub...")
        data = load_from_github()
        if data:
            print(f"Loaded {len(data.get('draws', []))} draws from GitHub")
        else:
            print("No data found on GitHub or failed to load")
    else:
        print("GitHub Storage not available - missing GITHUB_TOKEN")