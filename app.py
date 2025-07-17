from flask import Flask, render_template, request, redirect, url_for, session, abort, jsonify
import json
import os
from uuid import uuid4
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = 'super_secret_key_123'

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

#主頁面路由
@app.route('/')
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
    return render_template('index.html', repairs=repair_data, username='訪客', role='viewer')

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
        if request.form['username'] == 'admin' and request.form['password'] == '5550':
            session['username'] = 'admin'
            session['role'] = 'technician'
            return redirect(url_for('index'))
        return render_template('login.html', error='帳號或密碼錯誤')
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
        category = request.form['category']
        new_entry = {
            'id': str(uuid4()),
            'title': request.form['title'],
            'category': category,
            'date': request.form['date'],
            'author': session['username'],
            'status': request.form['status'],
            'summary': request.form['summary'],
            'details': request.form['details'],
            'views': 0
        }

        if category == 'tools':
            tools_path = 'data/tools.json'
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

        # 發佈成功後刪除草稿
        draft_path = 'data/drafts.json'
        if os.path.exists(draft_path):
            os.remove(draft_path)

        return redirect(url_for('index'))

    return render_template('new.html', username=session['username'], role=session.get('role'))

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

@app.route('/save_draft', methods=['POST'])
def save_draft():
    draft_path = 'data/drafts.json'
    draft = request.get_json()
    with open(draft_path, 'w', encoding='utf-8') as f:
        json.dump(draft, f, ensure_ascii=False, indent=2)
    return '', 204

@app.route('/load_draft')
def load_draft():
    draft_path = 'data/drafts.json'
    if not os.path.exists(draft_path):
        return {}
    with open(draft_path, encoding='utf-8') as f:
        return jsonify(json.load(f))

if __name__ == '__main__':
    app.run(debug=True)