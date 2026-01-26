#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Vercel Flask 应用入口点（根目录）
重定向到 api/index.py
"""
import sys
import os

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 导入 api/index.py 中的 app
try:
    from api.index import app
    print("✅ 成功从 api.index 导入 app")
except ImportError as e:
    print(f"❌ 无法从 api.index 导入 app: {e}")
    # 如果导入失败，创建一个简单的错误应用
    from flask import Flask, jsonify
    app = Flask(__name__)
    
    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def error_handler(path):
        return jsonify({
            'success': False,
            'error': str(e),
            'message': '无法导入应用'
        }), 500
