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

# ✅ 在导入前设置 USE_GITHUB_DATA_ONLY，确保 DataFetcher 能正确检测
os.environ['USE_GITHUB_DATA_ONLY'] = '1'

# 确保只导入 bull_stock_web，不导入其他 app.py
try:
    # 明确导入 bull_stock_web，避免导入 app.py
    import bull_stock_web
    
    # 获取 Flask app 实例 - 这是 Vercel 检测的关键
    app = bull_stock_web.app
    
    # 确保在 Vercel 环境中也添加全局错误处理器（如果 bull_stock_web 中没有）
    # 注意：这只是一个额外的保护层，主要错误处理器应该在 bull_stock_web.py 中
    @app.errorhandler(Exception)
    def handle_all_exceptions(error):
        """Vercel 环境中的全局错误处理器（额外保护层）"""
        import traceback
        from flask import request, jsonify, has_request_context
        
        # 获取错误详情
        error_detail = traceback.format_exc()
        error_type = type(error).__name__
        error_message = str(error) if error else "未知错误"
        
        print(f"[Vercel Error Handler] ❌ 未捕获的异常 ({error_type}): {error_detail}")
        
        # 检查请求上下文，如果是 API 路径，返回 JSON 格式
        try:
            if has_request_context() and request.path.startswith('/api/'):
                return jsonify({
                    'success': False,
                    'message': f'服务器错误: {error_message}',
                    'error_type': error_type,
                    'path': request.path,
                    'method': request.method
                }), 500
        except Exception as handler_error:
            print(f"[Vercel Error Handler] ⚠️ 错误处理器内部出错: {handler_error}")
            import traceback
            print(f"[Vercel Error Handler] 错误详情: {traceback.format_exc()}")
        
        # 非 API 路径或没有请求上下文，重新抛出异常让 Flask 使用默认错误处理
        from werkzeug.exceptions import HTTPException
        if isinstance(error, HTTPException):
            return error
        raise
    
    print("✅ 成功导入 bull_stock_web，app 对象已准备就绪")
except Exception as e:
    # 如果导入失败，创建一个简单的错误处理应用
    from flask import Flask, jsonify
    app = Flask(__name__)
    
    # 保存导入错误信息，以便在函数内部使用（使用闭包）
    import_error = str(e)
    import_error_type = type(e).__name__
    
    # 添加全局错误处理器，确保所有错误都返回 JSON 格式
    @app.errorhandler(Exception)
    def handle_import_error(error):
        """处理导入失败时的错误"""
        import traceback
        error_detail = traceback.format_exc()
        error_type = type(error).__name__
        from flask import request, has_request_context
        
        print(f"[Import Error Handler] ❌ 错误 ({error_type}): {error_detail}")
        
        if has_request_context() and request.path.startswith('/api/'):
            return jsonify({
                'success': False,
                'error': str(error),
                'message': '导入 bull_stock_web 失败',
                'error_type': error_type,
                'import_error': import_error,
                'import_error_type': import_error_type,
                'path': request.path,
                'method': request.method
            }), 500
        
        # 非 API 路径，返回简单的 HTML 错误页面
        from flask import render_template_string
        return render_template_string(
            '<!DOCTYPE html><html><head><title>500 Internal Server Error</title></head>'
            '<body><h1>Internal Server Error</h1><p>The server encountered an internal error.</p>'
            '<p>Error: {{ error }}</p></body></html>', error=str(error)
        ), 500
    
    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'])
    def error_handler(path):
        from flask import request, has_request_context
        if has_request_context() and request.path.startswith('/api/'):
            return jsonify({
                'success': False,
                'error': import_error,
                'message': '导入 bull_stock_web 失败',
                'import_error_type': import_error_type,
                'path': request.path,
                'method': request.method
            }), 500
        return f"<h1>服务器错误</h1><p>导入 bull_stock_web 失败: {import_error}</p>", 500
    
    @app.route('/api/health', methods=['GET'])
    def health():
        return jsonify({
            'success': False,
            'error': import_error,
            'message': '导入 bull_stock_web 失败',
            'import_error_type': import_error_type
        }), 500
    
    print(f"❌ 导入 bull_stock_web 失败: {import_error}")
    import traceback
    traceback.print_exc()

# ✅ 关键：确保 app 对象在模块级别导出
# Vercel 会检测这个文件中的 'app' 变量
# 这是 Flask 应用的入口点
