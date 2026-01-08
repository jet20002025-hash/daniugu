#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Vercel Serverless Function 入口
将 Flask 应用适配为 Vercel 的 serverless 函数格式
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
    from flask import Flask
    app = Flask(__name__)
    
    @app.route('/')
    def error():
        import traceback
        error_detail = traceback.format_exc()
        return f"<h1>导入错误</h1><pre>{str(e)}</pre><pre>{error_detail}</pre>", 500
    
    @app.route('/api/health')
    def health():
        import traceback
        error_detail = traceback.format_exc()
        return {
            'success': False,
            'error': str(e),
            'traceback': error_detail
        }, 500
    
    print(f"❌ 导入 bull_stock_web 失败: {e}")

# Vercel 的 Python serverless 函数需要 handler 函数
# 这是 Vercel Python 函数的标准格式
def handler(request):
    """
    Vercel Python serverless 函数的 handler
    request: Vercel 的请求对象
    """
    return app(request.environ, lambda status, headers: None)
