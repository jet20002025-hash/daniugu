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

try:
    from bull_stock_web import app
except Exception as e:
    # 如果导入失败，创建一个简单的错误处理应用
    from flask import Flask
    app = Flask(__name__)
    
    @app.route('/')
    def error():
        import traceback
        error_detail = traceback.format_exc()
        return f"<h1>导入错误</h1><pre>{str(e)}</pre><pre>{error_detail}</pre>", 500

# Vercel 的 Python serverless 函数需要这个格式
# 直接导出 app，Vercel 会自动处理
