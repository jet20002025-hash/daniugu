#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Vercel Serverless Function 入口
直接导出 Flask 应用，Vercel 会自动处理 WSGI 应用
"""
import sys
import os

# 添加项目根目录到路径
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

# 设置 Vercel 环境变量（如果还没有设置）
if not os.environ.get('VERCEL'):
    os.environ['VERCEL'] = '1'

# 确保只导入 bull_stock_web，不导入其他 app.py
try:
    # 明确导入 bull_stock_web，避免导入 app.py
    import bull_stock_web
    app = bull_stock_web.app
    print("✅ 成功导入 bull_stock_web")
except Exception as e:
    # 如果导入失败，创建一个简单的错误处理应用
    from flask import Flask, jsonify
    app = Flask(__name__)
    
    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'])
    def error_handler(path):
        import traceback
        error_detail = traceback.format_exc()
        return jsonify({
            'success': False,
            'error': str(e),
            'message': '导入 bull_stock_web 失败',
            'traceback': error_detail
        }), 500
    
    @app.route('/api/health', methods=['GET'])
    def health():
        import traceback
        error_detail = traceback.format_exc()
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': error_detail
        }), 500
    
    print(f"❌ 导入 bull_stock_web 失败: {e}")
    import traceback
    traceback.print_exc()

# Vercel 会自动识别 Flask WSGI 应用
# 直接导出 app 即可，不需要 BaseHTTPRequestHandler
