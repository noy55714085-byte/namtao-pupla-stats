"""GitHub Storage สำหรับบันทึกผลรางวัลและประวัติบิลบน Streamlit Cloud."""

import base64
import json
import os
from typing import Optional

import requests

GITHUB_REPO = "noy55714085-byte/namtao-pupla-stats"
GITHUB_BRANCH = "main"
GITHUB_FILE_PATH = "data/history.json"
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")


def get_github_api_url(file_path: str = GITHUB_FILE_PATH) -> str:
    return f"https://api.github.com/repos/{GITHUB_REPO}/contents/{file_path}"


def get_github_raw_url(file_path: str = GITHUB_FILE_PATH) -> str:
    return f"https://raw.githubusercontent.com/{GITHUB_REPO}/{GITHUB_BRANCH}/{file_path}"


def _headers() -> dict:
    return {"Authorization": f"token {GITHUB_TOKEN}"} if GITHUB_TOKEN else {}


def load_from_github(file_path: str = GITHUB_FILE_PATH) -> Optional[dict]:
    """โหลด JSON จาก GitHub; ใช้ได้กับ history, betting และ draft."""
    try:
        # เมื่อมี token ใช้ Contents API เพื่อรับเวอร์ชันล่าสุด ไม่ติด cache ของ raw URL
        response = requests.get(
            get_github_api_url(file_path) if GITHUB_TOKEN else get_github_raw_url(file_path),
            headers=_headers(),
            timeout=10,
        )
        if response.status_code == 200:
            content = base64.b64decode(response.json()["content"]).decode("utf-8") if GITHUB_TOKEN else response.text
            return json.loads(content)
    except (requests.RequestException, json.JSONDecodeError):
        pass
    try:
        response = requests.get(get_github_api_url(file_path), headers=_headers(), timeout=10)
        if response.status_code == 200:
            return json.loads(base64.b64decode(response.json()["content"]).decode("utf-8"))
    except (requests.RequestException, KeyError, ValueError, json.JSONDecodeError):
        pass
    return None


def save_to_github(data: dict, file_path: str = GITHUB_FILE_PATH, message: str | None = None) -> bool:
    """บันทึก JSON ไป GitHub โดยใช้ sha ล่าสุดของไฟล์เพื่อไม่เขียนทับผิดรุ่น."""
    if not GITHUB_TOKEN:
        print(f"Warning: GITHUB_TOKEN not found - cannot save {file_path}")
        return False
    try:
        response = requests.get(get_github_api_url(file_path), headers=_headers(), timeout=10)
        payload = {
            "message": message or f"Update {file_path}",
            "content": base64.b64encode((json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode("utf-8")).decode("utf-8"),
            "branch": GITHUB_BRANCH,
        }
        if response.status_code == 200:
            payload["sha"] = response.json()["sha"]
        response = requests.put(get_github_api_url(file_path), headers=_headers(), json=payload, timeout=10)
        if response.status_code in (200, 201):
            print(f"Successfully saved {file_path} to GitHub")
            return True
        print(f"Failed to save {file_path}: {response.status_code} - {response.text}")
    except (requests.RequestException, KeyError, ValueError) as error:
        print(f"Error saving {file_path}: {error}")
    return False


def delete_from_github(file_path: str, message: str | None = None) -> bool:
    """ลบไฟล์ JSON จาก GitHub หลังผู้ใช้ยกเลิกหรือบันทึกร่างสำเร็จ."""
    if not GITHUB_TOKEN:
        return False
    try:
        response = requests.get(get_github_api_url(file_path), headers=_headers(), timeout=10)
        if response.status_code == 404:
            return True
        if response.status_code != 200:
            print(f"Failed to find {file_path} for deletion: {response.status_code}")
            return False
        payload = {"message": message or f"Delete {file_path}", "sha": response.json()["sha"], "branch": GITHUB_BRANCH}
        response = requests.delete(get_github_api_url(file_path), headers=_headers(), json=payload, timeout=10)
        return response.status_code == 200
    except (requests.RequestException, KeyError, ValueError) as error:
        print(f"Error deleting {file_path}: {error}")
        return False


def github_storage_available() -> bool:
    return GITHUB_TOKEN is not None
