# utils/user_store.py
import os, json, threading

USERS_FILE = os.path.join('data', 'user_settings.json')  # 统一用这一份
_lock = threading.Lock()

def ensure_file():
    os.makedirs(os.path.dirname(USERS_FILE), exist_ok=True)
    if not os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'w', encoding='utf-8') as f:
            json.dump([{
                "username": "admin",
                "password": "5550",
                "role": "technician",
                "active": True
            }], f, ensure_ascii=False, indent=2)

def load_users():
    ensure_file()
    with open(USERS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_users(users):
    ensure_file()
    with _lock:
        with open(USERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(users, f, ensure_ascii=False, indent=2)

def find_user(username):
    for u in load_users():
        if u.get('username') == username:
            return u
    return None