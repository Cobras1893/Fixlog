from flask import render_template, request, redirect, url_for, session, abort, Blueprint, jsonify
import json, os
from . import settings_bp
from functools import wraps
from flask import session, redirect, url_for, request, flash, current_app
from .user_store import load_users, save_users, find_user

def login_required(f):
    @wraps(f)
    def wrap(*a, **k):
        if 'username' not in session:
            return redirect(url_for('login', next=request.path))
        return f(*a, **k)
    return wrap

def admin_required(f):
    @wraps(f)
    def wrap(*a, **k):
        # 你定義的管理員角色就是 technician
        if session.get('role') != 'technician':
            # 可選：flash('需要管理員權限', 'error')
            return redirect(url_for('index'))
        return f(*a, **k)
    return wrap

@settings_bp.route('/', endpoint='settings')
@login_required
@admin_required
def settings_page():
    # 再次保險（已由 admin_required 擋過了）
    if 'username' not in session:
        return redirect(url_for('login'))
    if session.get('role') != 'technician':
        abort(403)

    users_path = 'data/user_settings.json'
    if not os.path.exists(users_path):
        default_users = [{
            "username": "admin",
            "password": "5550",
            "role": "technician",
            "active": True
        }]
        os.makedirs('data', exist_ok=True)
        with open(users_path, 'w', encoding='utf-8') as f:
            json.dump(default_users, f, ensure_ascii=False, indent=2)

    with open(users_path, encoding='utf-8') as f:
        users = json.load(f)


    return render_template('settings/settings.html',
                           users=users,
                           username=session.get('username'),
                           role=session.get('role'))

# ====== 使用者管理 ======
@settings_bp.route('/users')
@login_required
@admin_required
def manage_users():
    # 你原本這裡檢查的是 admin，但你的管理員實際是 technician
    users_path = 'data/users.json'
    users = []
    if os.path.exists(users_path):
        with open(users_path, encoding='utf-8') as f:
            users = json.load(f)

    # 這個模板路徑若不存在就保持原樣；目前 settings.html 已顯示清單，
    # 這個 /users 頁面如果你沒用到也不影響。
    return render_template('settings/users.html',
                           users=users,
                           username=session['username'],
                           role=session['role'])

@settings_bp.route('/users/add', methods=['POST'])
@login_required
@admin_required
def add_user():
    # 你原本這裡檢查的是 admin，但你的管理員實際是 technician
    new_user = {
        'username': request.form['username'],
        'password': request.form['password'],
        'role': request.form.get('role', 'technician'),
        # 預設啟用；如要前端可傳 active，就加上 request.form.get('active')
        'active': True
    }

    # 與 settings_page 使用的檔案一致：user_settings.json
    users_path = 'data/user_settings.json'
    users = []
    if os.path.exists(users_path):
        with open(users_path, encoding='utf-8') as f:
            users = json.load(f)

    if any(u.get('username') == new_user['username'] for u in users):
        # 給前端 fetch 友善回應
        return jsonify({'ok': False, 'error': '使用者已存在'}), 409

    users.append(new_user)
    with open(users_path, 'w', encoding='utf-8') as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

    return jsonify({'ok': True})

@settings_bp.route('/api/users', methods=['GET'])
@login_required
@admin_required
def api_users_list():
    return jsonify({"ok": True, "users": load_users()})

@settings_bp.route('/api/users', methods=['POST'])
@login_required
@admin_required
def api_users_add():
    data = request.get_json(silent=True) or request.form
    username = (data.get('username') or '').strip()
    password = (data.get('password') or '').strip()
    role = (data.get('role') or 'technician').strip()
    if not username or not password:
        return jsonify({"ok": False, "error": "username/password 必填"}), 400
    users = load_users()
    if any(u.get('username') == username for u in users):
        return jsonify({"ok": False, "error": "使用者已存在"}), 409
    users.append({
        "username": username,
        "password": password,   # 先保留明文，等你要换 hash 再一起改
        "role": role,
        "active": True
    })
    save_users(users)
    return jsonify({"ok": True})

@settings_bp.route('/api/users/<username>', methods=['DELETE'])
@login_required
@admin_required
def api_users_delete(username):
    # 防止把自己删了把自己锁死；如果你想允许自删就移除此判断
    if username == session.get('username'):
        return jsonify({"ok": False, "error": "不可刪除自身帳號"}), 400
    users = load_users()
    new_users = [u for u in users if u.get('username') != username]
    if len(new_users) == len(users):
        return jsonify({"ok": False, "error": "找不到使用者"}), 404
    save_users(new_users)
    return jsonify({"ok": True})

@settings_bp.route('/api/users/<username>', methods=['PATCH'])
@login_required
@admin_required
def api_users_update(username):
    data = request.get_json(force=True)
    users = load_users()
    for u in users:
        if u.get('username') == username:
            if 'role' in data:   u['role'] = data['role']
            if 'active' in data: u['active'] = bool(data['active'])
            if 'password' in data and data['password']:
                u['password'] = data['password']
            save_users(users)
            return jsonify({"ok": True})
    return jsonify({"ok": False, "error": "找不到使用者"}), 404

@settings_bp.route('/api/drafts', methods=['GET'])
@login_required
def api_drafts_list():
    username = session.get('username')
    drafts = _list_drafts_for_user(username)
    return jsonify({"ok": True, "drafts": drafts})

@settings_bp.route('/api/drafts/<draft_id>', methods=['DELETE'])
@login_required
def api_draft_delete(draft_id):
    username = session.get('username')
    if not draft_id:
        return jsonify({"ok": False, "error": "缺少 draft_id"}), 400
    ok = _delete_draft_for_user(username, draft_id)
    if not ok:
        return jsonify({"ok": False, "error": "草稿不存在或無權限"}), 404
    return jsonify({"ok": True})

import time, uuid

# routes.py 在 Fixlog/templates/settings/，往上兩層就是 Fixlog/
_BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
_DRAFTS_FILE = os.path.join(_BASE_DIR, 'data', 'drafts.json')

def _ensure_drafts_file():
    os.makedirs(os.path.dirname(_DRAFTS_FILE), exist_ok=True)
    if not os.path.exists(_DRAFTS_FILE):
        with open(_DRAFTS_FILE, 'w', encoding='utf-8') as f:
            f.write('{}')  # 默认 { username: [ ... ] }

def _load_raw():
    _ensure_drafts_file()
    try:
        with open(_DRAFTS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}

def _save_raw(data):
    _ensure_drafts_file()
    with open(_DRAFTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def _normalize_one(d, fallback_owner=None):
    did = d.get('id') or d.get('_id') or d.get('draft_id') or d.get('guid') or str(uuid.uuid4())
    title = d.get('title') or d.get('subject') or '(未命名草稿)'
    owner = d.get('owner') or d.get('username') or d.get('user') or d.get('author') or fallback_owner
    # 统一时间戳（秒）
    ts = d.get('updated_at') or d.get('updatedAt') or d.get('time') or d.get('timestamp') or d.get('modified') or d.get('mtime')
    if isinstance(ts, str) and ts.isdigit():
        ts = int(ts)
    if isinstance(ts, (int, float)) and ts > 1e12:  # 毫秒→秒
        ts = int(ts // 1000)
    if not isinstance(ts, int):
        ts = int(time.time())
    return {
        "id": str(did),
        "title": title,
        "owner": owner,
        "updated_at": ts,
        # 为表格做个轻量摘要（可按需改成纯文字截断）
        "summary": (d.get("summary") or d.get("desc") or d.get("details") or "")[:120]
    }

def _list_all_normalized():
    raw = _load_raw()
    items = []
    if isinstance(raw, dict) and 'drafts' in raw and isinstance(raw['drafts'], list):
        items = raw['drafts']
        out = [_normalize_one(d) for d in items]
    elif isinstance(raw, dict) and all(k in raw for k in ('title','category','details')):
        # 老格式：单一物件
        out = [_normalize_one(raw)]
    elif isinstance(raw, dict):
        out = []
        for owner, lst in raw.items():
            if isinstance(lst, list):
                out.extend(_normalize_one(d, fallback_owner=owner) for d in lst)
    elif isinstance(raw, list):
        out = [_normalize_one(d) for d in raw]
    else:
        out = []
    out.sort(key=lambda x: x['updated_at'], reverse=True)
    return out

def _list_drafts_for_user(username):
    is_tech = (session.get('role') == 'technician')
    all_items = _list_all_normalized()
    return all_items if is_tech else [d for d in all_items if d.get('owner') == username]

def _delete_draft_for_user(username, draft_id):
    """技師可刪任何草稿；一般使用者只能刪自己的。"""
    is_tech = (session.get('role') == 'technician')
    raw = _load_raw()
    changed = False

    def can_delete(d):
        owner = d.get('owner') or d.get('username') or d.get('user') or d.get('author')
        return is_tech or (owner == username)

    if isinstance(raw, dict) and 'drafts' in raw and isinstance(raw['drafts'], list):
        before = len(raw['drafts'])
        raw['drafts'] = [d for d in raw['drafts'] if not (can_delete(d) and str(d.get('id') or d.get('_id') or d.get('draft_id') or d.get('guid')) == str(draft_id))]
        changed = (len(raw['drafts']) != before)
    elif isinstance(raw, dict) and all(k in raw for k in ('title','category','details')):
        # 老格式只有一笔：仅技师可删（避免误删）
        if is_tech:
            raw = {}
            changed = True
    elif isinstance(raw, dict):
        for owner, lst in list(raw.items()):
            if not isinstance(lst, list): 
                continue
            new_lst = [d for d in lst if not (can_delete(d) and str(d.get('id') or d.get('_id')) == str(draft_id))]
            if len(new_lst) != len(lst):
                raw[owner] = new_lst
                changed = True
    elif isinstance(raw, list):
        before = len(raw)
        raw = [d for d in raw if not (can_delete(d) and str(d.get('id') or d.get('_id') or d.get('draft_id') or d.get('guid')) == str(draft_id))]
        changed = (len(raw) != before)

    if changed:
        _save_raw(raw)
        return True
    return False

# === Preferences API（只保留 theme） ===
import os, json
from flask import jsonify, request, session
from . import settings_bp

_BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
_PREFS_FILE = os.path.join(_BASE_DIR, 'data', 'preferences.json')

def _ensure_prefs_file():
    os.makedirs(os.path.dirname(_PREFS_FILE), exist_ok=True)
    if not os.path.exists(_PREFS_FILE):
        with open(_PREFS_FILE, 'w', encoding='utf-8') as f:
            f.write('{}')

def _load_prefs_all():
    _ensure_prefs_file()
    try:
        with open(_PREFS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}

def _save_prefs_all(data):
    _ensure_prefs_file()
    with open(_PREFS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

@settings_bp.route('/api/preferences', methods=['GET'])
def api_get_preferences():
    user = session.get('username') or 'anonymous'
    allp = _load_prefs_all()
    # 只回 theme（默认 light）
    theme = (allp.get(user, {}).get('theme')) or 'light'
    return jsonify({"ok": True, "prefs": {"theme": theme}})

@settings_bp.route('/preferences', methods=['POST'])
def save_preferences():
    user = session.get('username') or 'anonymous'
    data = request.get_json(silent=True) or request.form
    theme = (data.get('theme') or 'light').strip()
    if theme not in ('light', 'dark'):
        theme = 'light'
    allp = _load_prefs_all()
    # 只保存 theme，顺便把旧的 default_sort / show_categories 清掉
    allp[user] = {"theme": theme}
    _save_prefs_all(allp)
    return jsonify({"success": True})