from flask import Flask, render_template, request, redirect, url_for, session, abort, jsonify
import json
import os
from uuid import uuid4
from datetime import datetime, timedelta
from templates.settings.user_store import find_user
from templates.settings import settings_bp
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50 MB
UPLOAD_DIR = os.path.join(app.root_path, 'static', 'uploads')
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.secret_key = 'super_secret_key_123'
# 註冊設定頁面
app.register_blueprint(settings_bp)

# 準備資料儲存資料夾與 repairs.json
os.makedirs('data', exist_ok=True)
repairs_path = 'data/repairs.json'

if not os.path.exists(repairs_path):
    with open(repairs_path, 'w', encoding='utf-8') as f:
        json.dump([], f, ensure_ascii=False, indent=2)

with open(repairs_path, encoding='utf-8') as f:
    repair_data = json.load(f)

# 初始化 repair_data 的 views 欄位
for repair in repair_data:
    if 'views' not in repair:
        repair['views'] = 0

# 首頁直接導向到登入頁
@app.route('/')
def home():
    return redirect(url_for('login'))

#主頁面路由
@app.route('/index')
def index():
    username = session.get('username')
    role = session.get('role')
    category = request.args.get('category')
    sort = request.args.get('sort', 'default')
    order = request.args.get('order', 'desc')

    filtered_repairs = [r for r in repair_data if r.get('category') == category] if category else repair_data

    if sort == 'alpha':
        filtered_repairs.sort(key=lambda x: x['title'])
    elif sort == 'date':
        filtered_repairs.sort(key=lambda x: x.get('date', ''), reverse=(order == 'desc'))
    elif sort == 'views':
        filtered_repairs.sort(key=lambda x: x.get('views', 0), reverse=(order == 'desc'))
    elif sort == 'default':
        top3 = sorted(filtered_repairs, key=lambda x: x.get('views', 0), reverse=True)[:3]
        rest = sorted(filtered_repairs, key=lambda x: x.get('date', ''), reverse=True)
        filtered_repairs = top3 + [r for r in rest if r not in top3]

    # 🔥 熱門文章判斷邏輯
    hot_ids = set()
    seven_days_ago = datetime.now() - timedelta(days=7)
    for r in filtered_repairs[:3]:  # 只檢查前 3 名
        try:
            post_time = datetime.strptime(r['date'], '%Y-%m-%d %H:%M')
            if post_time >= seven_days_ago:
                hot_ids.add(r['id'])
        except Exception:
            continue  # 日期格式錯誤則跳過

    # 最後傳給模板
    return render_template('index.html',
                       repairs=filtered_repairs,
                       username=username,
                       role=role,
                       sort=sort,
                       order=order,
                       hot_ids=hot_ids)

#訪客登入路由
@app.route('/visitor')
def visitor_view():
    session['username'] = '訪客'
    session['role'] = 'viewer'
    return redirect(url_for('tools'))

#搜尋路由
@app.route('/search')
def search():
    keyword = request.args.get('q', '').strip()
    sort = request.args.get('sort', 'default')  # 排序類型
    order = request.args.get('order', 'desc')   # 排序順序（desc 或 asc）

    if not keyword:
        return redirect(url_for('index'))

    # 搜尋標題中包含關鍵字的資料
    results = [r for r in repair_data if keyword.lower() in r['title'].lower()]

    # 排序處理
    if sort == 'alpha':
        results.sort(key=lambda x: x['title'])
    elif sort == 'date':
        results.sort(key=lambda x: x.get('date', ''), reverse=(order == 'desc'))
    elif sort == 'views':
        results.sort(key=lambda x: x.get('views', 0), reverse=(order == 'desc'))
    elif sort == 'default':
        # 取前三熱門 + 剩餘按時間排序
        top3 = sorted(results, key=lambda x: x.get('views', 0), reverse=True)[:3]
        rest = sorted([r for r in results if r not in top3], key=lambda x: x.get('date', ''), reverse=True)
        results = top3 + rest

    return render_template(
        'index.html',
        repairs=results,
        username=session.get('username'),
        role=session.get('role'),
        sort=sort,
        order=order,
        keyword=keyword
    )

@app.route('/repair/<repair_id>')
def repair_detail(repair_id):
    repair = next((r for r in repair_data if r['id'] == repair_id), None)
    if not repair:
        abort(404)

    if 'viewed' not in session:
        session['viewed'] = []
    if repair_id not in session['viewed']:
        session['viewed'].append(repair_id)
        session.modified = True
        repair['views'] = repair.get('views', 0) + 1
        with open(repairs_path, 'w', encoding='utf-8') as f:
            json.dump(repair_data, f, ensure_ascii=False, indent=2)

    return render_template('detail.html', repair=repair, username=session.get('username'), role=session.get('role'))

@app.route('/repair/<repair_id>/delete', methods=['POST'])
def delete_repair(repair_id):
    global repair_data
    repair_data = [r for r in repair_data if r['id'] != repair_id]
    with open(repairs_path, 'w', encoding='utf-8') as f:
        json.dump(repair_data, f, ensure_ascii=False, indent=2)
    return redirect(url_for('index'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = (request.form.get('username') or '').strip()
        password = (request.form.get('password') or '').strip()
        user = find_user(username)

        ok = bool(user and user.get('active', True) and user.get('password') == password)

        # 若是 AJAX（前端用 fetch 送），就回 JSON，不直接 redirect
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            if ok:
                session['username'] = user['username']
                session['role'] = user.get('role', 'user')
                return jsonify({"ok": True, "next": url_for("tools")})
            else:
                return jsonify({"ok": False, "error": "帳號或密碼錯誤，或帳號未啟用"}), 400

        # 非 AJAX：維持原本傳統流程
        if ok:
            session['username'] = user['username']
            session['role'] = user.get('role', 'user')
            return redirect(url_for('tools'))
        else:
            return render_template('login.html', error='帳號或密碼錯誤，或帳號未啟用')

    # GET
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/new', methods=['GET', 'POST'])
def new_repair():
    if 'username' not in session or session.get('role') != 'technician':
        return redirect(url_for('login'))

    if request.method == 'POST':
        category_raw = request.form['category']            # 可能是 'ERP' 或 'tools_software'
        is_tools = category_raw.startswith('tools')        # 捕捉所有 tools 類別
        # 解析子分類（tools_software -> software）
        tool_subcategory = category_raw.split('_', 1)[1] if category_raw.startswith('tools_') else None

        new_entry = {
            'id': str(uuid4()),
            'title': request.form['title'],
            # 對外主分類：統一寫 'tools'；一般分類維持原值
            'category': 'tools' if is_tools else category_raw,
            # 只有工具類別才有的欄位：子分類（None 表示一般）
            'tool_subcategory': tool_subcategory,          # e.g. software / hardware / network / general
            'date': request.form['date'],
            'author': session['username'],
            'status': request.form['status'],
            'summary': request.form['summary'],
            'details': request.form['details'],
            'views': 0
        }

        if is_tools:
            tools_path = 'data/tools.json'
            os.makedirs(os.path.dirname(tools_path), exist_ok=True)
            if not os.path.exists(tools_path):
                with open(tools_path, 'w', encoding='utf-8') as f:
                    json.dump([], f)
            with open(tools_path, encoding='utf-8') as f:
                tools_data = json.load(f)
            tools_data.insert(0, new_entry)
            with open(tools_path, 'w', encoding='utf-8') as f:
                json.dump(tools_data, f, ensure_ascii=False, indent=2)
        else:
            repair_data.insert(0, new_entry)
            with open(repairs_path, 'w', encoding='utf-8') as f:
                json.dump(repair_data, f, ensure_ascii=False, indent=2)

        return redirect(url_for('index'))

        # 發佈成功後刪除草稿
        draft_path = 'data/drafts.json'
        if os.path.exists(draft_path):
            os.remove(draft_path)

        return redirect(url_for('index'))

    return render_template('new.html', username=session['username'], role=session.get('role'))

@app.errorhandler(RequestEntityTooLarge)
def too_large(e): return "Payload too large", 413

@app.post("/upload")
def upload():
    f = request.files.get('file')
    if not f: return jsonify(error="no file"), 400
    ext = os.path.splitext(f.filename or '')[1].lower()
    name = f"{uuid.uuid4().hex}{ext or '.png'}"
    path = os.path.join(UPLOAD_DIR, secure_filename(name))
    f.save(path)
    return jsonify(url=url_for('static', filename=f'uploads/{name}'))

@app.route('/new')
def new_page():
    # 若 new.html 在 templates 根目錄，保持這樣
    return render_template('new.html')

# 讓 /new.html 也能打到同一頁（避免硬連結 404）
@app.route('/new.html')
def new_page_alias():
    return new_page()

import os, json, time, uuid
from flask import request, session, jsonify

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DRAFTS_FILE = os.path.join(BASE_DIR, 'data', 'drafts.json')

def _ensure_drafts_file():
    os.makedirs(os.path.join(BASE_DIR, 'data'), exist_ok=True)
    if not os.path.exists(DRAFTS_FILE):
        with open(DRAFTS_FILE, 'w', encoding='utf-8') as f:
            f.write('{}')  # 預設 dict 形式：{ username: [ ... ] }

def _load_all():
    if not os.path.exists(os.path.join(BASE_DIR, 'data')):
        os.makedirs(os.path.join(BASE_DIR, 'data'), exist_ok=True)
    if not os.path.exists(DRAFTS_FILE):
        return {}
    try:
        with open(DRAFTS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}

def _save_all(data):
    _ensure_drafts_file()
    with open(DRAFTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

@app.route('/save_draft', methods=['POST'])
def save_draft():
    """相容舊前端：接收 {title, category, details}，自動補 id/owner/updated_at 後寫入"""
    payload = request.get_json(force=True)
    title    = (payload.get('title') or '').strip()
    category = (payload.get('category') or '').strip()
    details  = payload.get('details') or ''

    user = session.get('username') or 'anonymous'
    now  = int(time.time())

    draft = {
        "id": str(uuid.uuid4()),
        "owner": user,
        "title": title or "(未命名草稿)",
        "category": category,
        "details": details,
        "updated_at": now
    }

    data = _load_all()

    # 支援三種儲存形態並盡量往 {username: [ ... ]} 收斂
    if isinstance(data, dict) and 'drafts' in data and isinstance(data['drafts'], list):
        # 早期若是 {"drafts":[...]} 就直接 append
        data['drafts'].append(draft)
    elif isinstance(data, dict):
        data.setdefault(user, [])
        data[user].append(draft)
    elif isinstance(data, list):
        data.append(draft)
    else:
        data = {user: [draft]}

    _save_all(data)
    return jsonify({"ok": True, "id": draft["id"]})

@app.route('/load_draft', methods=['GET'])
def load_draft():
    """
    新增：若帶 ?id=xxx，則回傳該草稿內容
    舊行為：沒帶 id 時，回傳「目前使用者最新一筆」，找不到則回全局最新，再不行回 {}
    """
    data = _load_all()
    draft_id = request.args.get('id', '').strip()
    cur_user = session.get('username')

    # 將資料展平成清單
    def as_list(d):
        items = []
        if isinstance(d, dict) and 'drafts' in d and isinstance(d['drafts'], list):
            items = d['drafts']
        elif isinstance(d, dict) and all(k in d for k in ('title','category','details')):
            items = [d]
        elif isinstance(d, dict):
            for owner, lst in d.items():
                if isinstance(lst, list):
                    items.extend(lst)
        elif isinstance(d, list):
            items = d
        return items

    items = as_list(data)

    # ① 有 id：精準找
    if draft_id:
        for it in items:
            if str(it.get('id')) == draft_id or str(it.get('_id')) == draft_id:
                return jsonify({
                    "title": it.get("title") or "",
                    "category": it.get("category") or "",
                    "details": it.get("details") or ""
                })
        return jsonify({})  # 找不到

    # ② 沒 id：回目前使用者最新一筆
    if cur_user:
        own = [x for x in items if (x.get('owner') == cur_user)]
        own.sort(key=lambda x: x.get('updated_at') or 0, reverse=True)
        if own:
            latest = own[0]
            return jsonify({
                "title": latest.get("title") or "",
                "category": latest.get("category") or "",
                "details": latest.get("details") or ""
            })

    # ③ 退而求其次：全局最新
    if items:
        latest = sorted(items, key=lambda x: x.get('updated_at') or 0, reverse=True)[0]
        return jsonify({
            "title": latest.get("title") or "",
            "category": latest.get("category") or "",
            "details": latest.get("details") or ""
        })

    return jsonify({})

@app.route('/tools')
def tools():
    tools_path = 'data/tools.json'
    tools_data = []
    if os.path.exists(tools_path):
        with open(tools_path, encoding='utf-8') as f:
            tools_data = json.load(f)
    return render_template('tools.html', tools=tools_data, username=session.get('username'), role=session.get('role'))

@app.route('/tool/<tool_id>')
def tool_detail(tool_id):
    tools_path = 'data/tools.json'
    if not os.path.exists(tools_path):
        abort(404)
    with open(tools_path, encoding='utf-8') as f:
        tools_data = json.load(f)
    tool = next((t for t in tools_data if t['id'] == tool_id), None)
    if not tool:
        abort(404)

    if 'viewed_tools' not in session:
        session['viewed_tools'] = []
    if tool_id not in session['viewed_tools']:
        session['viewed_tools'].append(tool_id)
        session.modified = True
        tool['views'] = tool.get('views', 0) + 1
        with open(tools_path, 'w', encoding='utf-8') as f:
            json.dump(tools_data, f, ensure_ascii=False, indent=2)

    return render_template('tool_detail.html', tool=tool, username=session.get('username'), role=session.get('role'))

@app.route('/tool/<tool_id>/delete', methods=['POST'])
def delete_tool(tool_id):
    if session.get('username') != 'admin':
        abort(403)
    tools_path = 'data/tools.json'
    if not os.path.exists(tools_path):
        abort(404)
    with open(tools_path, encoding='utf-8') as f:
        tools_data = json.load(f)
    tools_data = [t for t in tools_data if t['id'] != tool_id]
    with open(tools_path, 'w', encoding='utf-8') as f:
        json.dump(tools_data, f, ensure_ascii=False, indent=2)
    return redirect(url_for('tools'))

if __name__ == '__main__':
    app.run(debug=True)