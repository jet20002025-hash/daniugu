#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Vercel Serverless Function 入口
将 Flask 应用适配为 Vercel 的 serverless 函数格式
"""
import sys
import os
from http.server import BaseHTTPRequestHandler
from io import BytesIO

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

# Vercel 的 Python serverless 函数需要 handler 类
class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.handle_request()
    
    def do_POST(self):
        self.handle_request()
    
    def do_PUT(self):
        self.handle_request()
    
    def do_DELETE(self):
        self.handle_request()
    
    def do_OPTIONS(self):
        self.handle_request()
    
    def handle_request(self):
        """处理所有 HTTP 请求，将请求转发给 Flask 应用"""
        try:
            # 安全读取请求体
            content_length = self.headers.get('Content-Length', '0')
            try:
                content_length_int = int(content_length) if content_length else 0
            except ValueError:
                content_length_int = 0
            
            request_body = b''
            if content_length_int > 0:
                request_body = self.rfile.read(content_length_int)
            
            # 构建 WSGI 环境
            path_parts = self.path.split('?', 1)
            path_info = path_parts[0]
            query_string = path_parts[1] if len(path_parts) > 1 else ''
            
            environ = {
                'REQUEST_METHOD': self.command,
                'SCRIPT_NAME': '',
                'PATH_INFO': path_info,
                'QUERY_STRING': query_string,
                'CONTENT_TYPE': self.headers.get('Content-Type', ''),
                'CONTENT_LENGTH': str(content_length_int),
                'SERVER_NAME': self.headers.get('Host', 'localhost').split(':')[0],
                'SERVER_PORT': self.headers.get('Host', 'localhost').split(':')[1] if ':' in self.headers.get('Host', '') else '80',
                'SERVER_PROTOCOL': 'HTTP/1.1',
                'wsgi.version': (1, 0),
                'wsgi.url_scheme': 'https' if self.headers.get('X-Forwarded-Proto') == 'https' else 'http',
                'wsgi.input': BytesIO(request_body),
                'wsgi.errors': sys.stderr,
                'wsgi.multithread': False,
                'wsgi.multiprocess': True,
                'wsgi.run_once': False,
            }
            
            # 添加 HTTP 头
            for key, value in self.headers.items():
                key = 'HTTP_' + key.upper().replace('-', '_')
                environ[key] = value
            
            # 调用 Flask 应用
            response_status = []
            response_headers = []
            
            def start_response(status, headers):
                response_status.append(status)
                response_headers.extend(headers)
            
            response_body = app(environ, start_response)
            
            # 发送响应
            if response_status:
                status_code = int(response_status[0].split()[0])
                self.send_response(status_code)
            else:
                self.send_response(500)
            
            for header, value in response_headers:
                self.send_header(header, value)
            self.end_headers()
            
            # 写入响应体
            for chunk in response_body:
                if chunk:
                    self.wfile.write(chunk)
            
        except Exception as e:
            import traceback
            error_detail = traceback.format_exc()
            try:
                self.send_response(500)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.end_headers()
                error_msg = f"<h1>处理请求时出错</h1><pre>{str(e)}</pre><pre>{error_detail}</pre>"
                self.wfile.write(error_msg.encode('utf-8'))
            except:
                # 如果发送错误响应也失败，至少记录错误
                print(f"严重错误：无法发送错误响应: {e}")
                print(error_detail)
