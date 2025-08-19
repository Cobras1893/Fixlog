# settings/__init__.py
from flask import Blueprint

settings_bp = Blueprint('settings', __name__, url_prefix='/settings')

from . import routes  # 重要：讓 routes.py 匯入並把路由掛到上面的 settings_bp