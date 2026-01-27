#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
大牛股分析器Web界面
提供添加大牛股的功能
"""
from flask import Flask, render_template, jsonify, request, session, redirect, url_for, send_file
# 重型模块延后到 init_analyzer/init_v2_model 内导入，避免免费版 10s 冷启动超时
# from bull_stock_analyzer import BullStockAnalyzer
# from technical_analysis import TechnicalAnalysis
# from bull_stock_v2_model import BullStockV2Model
from datetime import datetime
# 根据环境选择使用哪个认证模块
import os

# 检测 Vercel 环境（更可靠的方式）
is_vercel = (
    os.environ.get('VERCEL') == '1' or 
    os.environ.get('VERCEL_ENV') is not None or
    os.environ.get('VERCEL_URL') is not None
)

# 检测 Render 环境（Render的文件系统也是只读的，需要使用Redis）
is_render = (
    os.environ.get('RENDER') == 'true' or
    os.environ.get('RENDER_SERVICE_NAME') is not None or
    os.environ.get('RENDER_EXTERNAL_URL') is not None
)

# 检测本地环境（既不是Vercel也不是Render）
is_local = not is_vercel and not is_render

# 检测是否有Redis配置（如果有，优先使用Redis存储）
has_redis = (
    os.environ.get('UPSTASH_REDIS_REST_URL') is not None and
    os.environ.get('UPSTASH_REDIS_REST_TOKEN') is not None
)

try:
    # 如果是Vercel、Render环境，或者配置了Redis，使用Redis存储版本
    if is_vercel or is_render or has_redis:
        # Vercel/Render环境或配置了Redis：使用Redis存储版本
        from user_auth_vercel import (
            register_user, login_user, is_logged_in, get_current_user,
            require_login, create_invite_code, list_invite_codes, get_user_stats
        )
        if is_render:
            print("[环境检测] Render环境检测到，使用Redis存储（user_auth_vercel）")
    else:
        # 本地环境：使用文件存储版本
        from user_auth import (
            register_user, login_user, is_logged_in, get_current_user,
            require_login, create_invite_code, list_invite_codes, get_user_stats
        )
except ImportError as e:
    # 如果导入失败，尝试使用 Vercel 版本
    print(f"警告：导入认证模块失败，尝试使用 Vercel 版本: {e}")
    try:
        from user_auth_vercel import (
            register_user, login_user, is_logged_in, get_current_user,
            require_login, create_invite_code, list_invite_codes, get_user_stats
        )
    except ImportError:
        # 如果都失败，创建简单的占位函数
        print("错误：无法导入认证模块，使用占位函数")
        def register_user(*args, **kwargs):
            return {'success': False, 'message': '认证模块未加载'}
        def login_user(*args, **kwargs):
            return {'success': False, 'message': '认证模块未加载'}
        def is_logged_in():
            return False
        def get_current_user():
            return None
        def require_login(f):
            return f
        def create_invite_code(*args, **kwargs):
            return {'success': False, 'message': '认证模块未加载'}
        def list_invite_codes():
            return {}
        def get_user_stats():
            return {}
import json
import pandas as pd
import numpy as np
import time
import os
import threading

# ✅ 确保模板文件夹路径正确（Vercel 环境中可能需要绝对路径）
import os
template_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
if not os.path.exists(template_dir):
    # 如果 templates 目录不存在，尝试相对路径
    template_dir = 'templates'
app = Flask(__name__, template_folder=template_dir)
print(f"[Flask Init] 模板文件夹: {template_dir}, 存在: {os.path.exists(template_dir)}")

# 登录日志文件
LOGIN_LOG_FILE = 'login_monitor.log'

def _log_login_attempt(username, success, duration_ms, timestamp, message):
    """记录登录尝试到日志文件"""
    try:
        log_entry = {
            'timestamp': timestamp.isoformat(),
            'username': username,
            'success': success,
            'duration_ms': round(duration_ms, 3),
            'message': message
        }
        
        # 追加到日志文件
        with open(LOGIN_LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
    except Exception as e:
        # 记录失败不应该影响登录流程
        print(f"记录登录日志失败: {e}")
# SECRET_KEY 配置：优先使用环境变量（生产环境），否则生成随机值（开发环境）
# 注意：在 Render 等生产环境中，应该设置固定的 SECRET_KEY 环境变量，避免服务器重启后 session 失效
import uuid
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', f'bull-stock-{uuid.uuid4().hex}')
if is_render or is_vercel:
    # 在生产环境中，如果没有设置环境变量，使用一个固定的默认值（不推荐，但比每次重启失效好）
    if not os.environ.get('FLASK_SECRET_KEY'):
        print("⚠️ 警告：未设置 FLASK_SECRET_KEY 环境变量，使用默认值（不推荐生产环境）")
        app.config['SECRET_KEY'] = 'bull-stock-render-default-secret-key-2024-please-change'
    else:
        print("✅ 使用环境变量 FLASK_SECRET_KEY")

# 添加全局错误处理器，确保所有错误都返回 JSON 格式（而不是 HTML）
# 注意：必须使用 app.errorhandler 注册，不能使用 register_error_handler
# 并且需要先注册具体的错误类型，再注册通用的 Exception

@app.errorhandler(500)
def handle_500_error(error):
    """处理 500 错误，返回 JSON 格式"""
    import traceback
    from flask import request, has_request_context
    
    # 获取错误详情
    error_detail = traceback.format_exc()
    error_type = type(error).__name__ if error else 'UnknownError'
    error_message = str(error) if error else "未知错误"
    
    print(f"[Flask Error Handler] ❌ 500 错误 ({error_type}): {error_detail}")
    
    # 检查请求上下文，如果是 API 路径，返回 JSON 格式
    try:
        if has_request_context() and request.path.startswith('/api/'):
            return jsonify({
                'success': False,
                'message': f'服务器内部错误: {error_message}',
                'error_type': error_type,
                'path': request.path,
                'method': request.method
            }), 500
    except Exception as handler_error:
        print(f"[Flask Error Handler] ⚠️ 错误处理器内部出错: {handler_error}")
        import traceback
        print(f"[Flask Error Handler] 错误详情: {traceback.format_exc()}")
    
    # 非 API 路径或没有请求上下文，使用 Flask 默认错误处理
    # 注意：不能返回 None，需要返回一个响应或重新抛出异常
    # 但对于非 API 路径，我们希望返回 HTML 错误页面
    from flask import render_template_string
    return render_template_string(
        '<!DOCTYPE html><html><head><title>500 Internal Server Error</title></head>'
        '<body><h1>Internal Server Error</h1><p>The server encountered an internal error.</p></body></html>'
    ), 500

@app.errorhandler(Exception)
def handle_all_exceptions(error):
    """处理所有未捕获的异常，返回 JSON 格式"""
    import traceback
    from flask import request, has_request_context
    
    # 获取错误详情
    error_detail = traceback.format_exc()
    error_type = type(error).__name__
    error_message = str(error) if error else "未知错误"
    
    print(f"[Flask Error Handler] ❌ 未捕获的异常 ({error_type}): {error_detail}")
    
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
        print(f"[Flask Error Handler] ⚠️ 错误处理器内部出错: {handler_error}")
        import traceback
        print(f"[Flask Error Handler] 错误详情: {traceback.format_exc()}")
    
    # 非 API 路径或没有请求上下文，重新抛出异常让 Flask 使用默认错误处理
    # 注意：对于 HTTPException（如 404, 401），不应该重新抛出，应该返回默认响应
    from werkzeug.exceptions import HTTPException
    if isinstance(error, HTTPException):
        # HTTPException 已经有自己的响应，直接返回
        return error
    
    # 其他异常，重新抛出让 Flask 使用默认错误处理
    raise

# 应用启动时初始化默认测试用户（永久保留，直到用户明确删除）
try:
    if is_vercel:
        from user_auth_vercel import init_default_test_users
    else:
        from user_auth import init_default_test_users
    # 在应用启动时初始化测试用户
    try:
        init_default_test_users()
    except Exception as e:
        print(f"⚠️ 初始化默认测试用户失败: {e}")
        import traceback
        traceback.print_exc()
except Exception as e:
    print(f"⚠️ 无法导入测试用户初始化函数: {e}")

# 应用启动时确保 super/superzwj 账户存在（自动恢复机制）
def ensure_super_user_exists():
    """确保 super/superzwj 账户存在，如果不存在或密码错误则自动创建/修复"""
    try:
        if is_vercel or is_render or has_redis:
            from user_auth_vercel import load_users, save_users, hash_password
        else:
            from user_auth import load_users, save_users, hash_password
        
        users = load_users()
        username = 'super'
        expected_password = 'superzwj'
        expected_password_hash = hash_password(expected_password)
        
        if username not in users:
            # 用户不存在，创建新用户
            users[username] = {
                'username': username,
                'email': 'super@admin.com',
                'password': expected_password_hash,
                'created_at': datetime.now().isoformat(),
                'last_login': None,
                'invite_code': 'AUTO_CREATED_ON_STARTUP',
                'is_active': True,
                'is_vip': True,
                'is_super': True,
                'is_test_user': True
            }
            save_users(users)
            print(f"✅ 启动时自动创建 super 用户（密码: {expected_password}）")
        else:
            # 用户存在，检查密码是否正确
            user = users[username]
            current_password_hash = user.get('password', '')
            
            if current_password_hash != expected_password_hash:
                # 密码不正确，修复为 superzwj
                user['password'] = expected_password_hash
                user['is_vip'] = True
                user['is_super'] = True
                user['is_active'] = True
                user['updated_at'] = datetime.now().isoformat()
                save_users(users)
                print(f"✅ 启动时自动修复 super 用户密码为 {expected_password}")
            else:
                # 确保权限正确
                needs_update = False
                if not user.get('is_vip', False):
                    user['is_vip'] = True
                    needs_update = True
                if not user.get('is_super', False):
                    user['is_super'] = True
                    needs_update = True
                if not user.get('is_active', True):
                    user['is_active'] = True
                    needs_update = True
                if needs_update:
                    save_users(users)
                    print(f"✅ 启动时自动修复 super 用户权限")
    except Exception as e:
        print(f"⚠️ 启动时确保 super 用户存在失败: {e}")
        import traceback
        traceback.print_exc()

# 在应用启动时执行
try:
    ensure_super_user_exists()
except Exception as e:
    print(f"⚠️ 启动时执行 super 用户检查失败: {e}")

# 创建全局分析器实例（延迟初始化，先启动Flask服务）
# 使用延迟初始化，避免阻塞Flask启动
analyzer = None
# 模型文件上次加载的 mtime，用于检测 trained_model.json 修改后自动重新加载
_model_last_loaded_mtime = 0

# 当前选择的模型文件名（默认使用 trained_model.json）
_current_model_file = 'trained_model.json'

# V2模型实例
v2_model = None

def init_v2_model():
    """初始化V2模型"""
    global v2_model
    if v2_model is None:
        from bull_stock_v2_model import BullStockV2Model
        try:
            v2_model = BullStockV2Model()
            model_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bull_stock_v2.json')
            if os.path.exists(model_path):
                v2_model.load_model(model_path)
                print(f"✅ V2模型加载成功，特征数: {len(v2_model.feature_template)}")
            else:
                print(f"⚠️ V2模型文件不存在: {model_path}")
        except Exception as e:
            print(f"⚠️ V2模型初始化失败: {e}")
            v2_model = None
    return v2_model

def is_premium_user():
    """检查用户是否为付费用户（VIP）"""
    try:
        user = get_current_user()
        if not user:
            return False
        return user.get('is_vip', False) or user.get('is_premium', False)
    except:
        return False

def is_super_user():
    """检查用户是否为超级用户（管理员）"""
    try:
        user = get_current_user()
        if not user:
            return False
        # 超级用户：is_super 为 True，或者用户名为特定管理员用户名
        is_super = user.get('is_super', False) or user.get('is_admin', False)
        username = user.get('username', '').lower()
        # 可以在这里添加特定的管理员用户名列表
        admin_users = ['admin', 'super', 'root']  # 可以根据需要修改
        return is_super or username in admin_users
    except:
        return False

def get_user_tier():
    """获取用户等级：'free'、'premium' 或 'super'"""
    if is_super_user():
        return 'super'
    if is_premium_user():
        return 'premium'
    return 'free'

def get_scan_config():
    """根据用户等级返回扫描配置（优化内存使用）"""
    tier = get_user_tier()
    
    if tier == 'super':
        # 超级用户：最快扫描，无限制（但考虑内存限制）
        return {
            'batch_size': 30,      # 从50降到30，减少内存使用
            'batch_delay': 1,      # 延迟1秒
            'stock_timeout': 10,   # 单股票10秒
            'retry_delay': 2,      # 重试延迟2秒
            'daily_limit': None,   # 无限制
            'scan_interval': 0,    # 无间隔
            'scan_start_hour': 0,  # 0点后即可扫描
            'result_view_hour': 0  # 0点后即可查看结果
        }
    elif tier == 'premium':
        # 收费版（VIP）：系统11:30自动扫描，也可以手动扫描
        return {
            'batch_size': 30,      # 从50降到30，减少内存使用
            'batch_delay': 1,      # 延迟1秒
            'stock_timeout': 10,   # 单股票10秒
            'retry_delay': 2,      # 重试延迟2秒
            'daily_limit': None,   # 无限制
            'scan_interval': 0,    # 无间隔
            'scan_start_hour': 0,  # 0点后即可手动扫描
            'auto_scan_hour': 11,  # 系统自动扫描时间：11:30
            'auto_scan_minute': 30,
            'result_view_hour': 12  # 中午12点后可查看结果
        }
    else:
        # 免费版：系统每天3:00自动扫描，用户直接看结果
        return {
            'batch_size': 15,      # 从20降到15，减少内存使用
            'batch_delay': 3,      # 延迟3秒（更慢）
            'stock_timeout': 8,    # 单股票8秒
            'retry_delay': 5,      # 重试延迟5秒
            'daily_limit': 2000,   # 每日2000只
            'scan_interval': 180,  # 间隔3分钟
            'auto_scan_hour': 15,  # 每天15:00（下午3点）自动扫描
            'auto_scan_minute': 0,  # 15:00整点
            'result_view_hour': 15,  # 下午3点后可查看结果
            'result_view_minute': 0,  # 15:00后即可查看
            'manual_scan_allowed': False  # 不允许手动扫描
        }

def init_analyzer():
    """延迟初始化分析器；若当前模型文件已更新则自动重新加载"""
    global analyzer, _model_last_loaded_mtime, _current_model_file
    project_root = os.path.dirname(os.path.abspath(__file__))
    model_path_to_check = os.path.join(project_root, _current_model_file)
    if os.path.exists(model_path_to_check):
        try:
            current_mtime = os.path.getmtime(model_path_to_check)
        except OSError:
            current_mtime = 0
    else:
        current_mtime = 0
    if analyzer is not None and current_mtime > _model_last_loaded_mtime:
        analyzer = None
        print(f"[init_analyzer] 检测到 {_current_model_file} 已更新，自动重新加载模型")
    if analyzer is None:
        from bull_stock_analyzer import BullStockAnalyzer
        try:
            # 在 Vercel 环境中，完全禁用自动加载和训练
            if is_vercel:
                print("Vercel 环境：禁用自动加载和训练以避免超时")
                # Vercel 环境：不自动加载，不自动训练
                analyzer = BullStockAnalyzer(
                    auto_load_default_stocks=False, 
                    auto_analyze_and_train=False
                )
                
                # 在 Vercel 环境中也要尝试加载已保存的模型
                # 尝试多个可能的路径（Vercel serverless 函数的工作目录可能不同）
                # 获取当前脚本的目录和项目根目录
                current_file_dir = os.path.dirname(os.path.abspath(__file__))
                project_root = current_file_dir  # bull_stock_web.py 在项目根目录
                
                model_paths = [
                    os.path.join(project_root, _current_model_file),  # 项目根目录（最可能）
                    _current_model_file,  # 当前工作目录
                    os.path.join(current_file_dir, _current_model_file),  # 当前文件所在目录
                ]
                
                model_loaded = False
                for model_path in model_paths:
                    abs_path = os.path.abspath(model_path)
                    print(f"尝试加载模型文件: {model_path} (绝对路径: {abs_path})")
                    if os.path.exists(model_path):
                        print(f"  ✓ 文件存在，尝试加载...")
                        # 在 Vercel 环境中，加载模型时跳过网络请求（skip_network=True）
                        if analyzer.load_model(model_path, skip_network=True):
                            print(f"✅ 模型加载成功: {model_path}")
                            # 检查模型完整性
                            if analyzer.trained_features:
                                feature_count = len(analyzer.trained_features.get('common_features', {}))
                                print(f"   - 买点特征数: {feature_count}")
                            if analyzer.trained_sell_features:
                                sell_feature_count = len(analyzer.trained_sell_features.get('common_features', {}))
                                print(f"   - 卖点特征数: {sell_feature_count}")
                            model_loaded = True
                            try:
                                _model_last_loaded_mtime = os.path.getmtime(os.path.abspath(model_path))
                            except OSError:
                                pass
                            break
                        else:
                            print(f"  ⚠️ 文件存在但加载失败: {model_path}")
                    else:
                        print(f"  ✗ 文件不存在: {abs_path}")
                
                if not model_loaded:
                    print("⚠️ 未找到已保存的模型文件，尝试的路径：")
                    for path in model_paths:
                        abs_path = os.path.abspath(path)
                        exists = os.path.exists(path)
                        print(f"   - {path}")
                        print(f"     绝对路径: {abs_path}")
                        print(f"     存在: {exists}")
                    print("⚠️ 需要重新训练模型")
                    print(f"当前工作目录: {os.getcwd()}")
                    print(f"当前文件目录: {current_file_dir}")
                    print(f"项目根目录: {project_root}")
            else:
                # 本地环境：快速初始化（禁用自动加载股票，避免网络请求）
                print("正在初始化分析器（快速模式）...")
                analyzer = BullStockAnalyzer(
                    auto_load_default_stocks=False,  # 禁用自动加载，避免网络请求导致缓慢
                    auto_analyze_and_train=False  # 禁用自动训练
                )
                
                # 尝试加载已保存的模型（本地环境也跳过网络请求，仅加载模型文件）
                print(f"尝试加载已保存的模型: {_current_model_file}...")
                if analyzer.load_model(_current_model_file, skip_network=True):
                    print("✅ 模型加载成功")
                    # 检查模型完整性
                    if analyzer.trained_features:
                        feature_count = len(analyzer.trained_features.get('common_features', {}))
                        print(f"   - 买点特征数: {feature_count}")
                    if analyzer.trained_sell_features:
                        sell_feature_count = len(analyzer.trained_sell_features.get('common_features', {}))
                        print(f"   - 卖点特征数: {sell_feature_count}")
                    try:
                        _model_last_loaded_mtime = os.path.getmtime(os.path.join(project_root, _current_model_file))
                    except OSError:
                        pass
                else:
                    print("⚠️ 未找到已保存的模型，需要重新训练")
            
            print("✅ 分析器初始化完成")
        except Exception as e:
            print(f"⚠️ 分析器初始化失败: {e}")
            import traceback
            traceback.print_exc()
            # 创建一个空的分析器对象，避免后续调用失败
            analyzer = None
    return analyzer


@app.route('/')
def index():
    """主页面"""
    print("[index] 开始处理主页请求...")
    try:
        # 检查是否已登录
        logged_in = False
        try:
            print("[index] 检查登录状态...")
            logged_in = is_logged_in()
            print(f"[index] 登录状态检查结果: {logged_in}")
        except Exception as login_check_error:
            import traceback
            error_detail = traceback.format_exc()
            print(f"[index] ⚠️ 检查登录状态失败: {error_detail}")
            # 如果检查登录状态失败，重定向到登录页面
            logged_in = False
        
        if not logged_in:
            print("[index] 未登录，重定向到登录页面")
            try:
                return redirect(url_for('login_page'))
            except Exception as redirect_error:
                print(f"[index] ⚠️ 重定向失败: {redirect_error}")
                return redirect('/login')
        
        # ✅ 不在主页渲染时初始化分析器，延迟到API调用时初始化（提升页面加载速度）
        # init_analyzer() 会在第一次API调用时自动初始化
        print("[index] 已登录，开始渲染模板...")
        try:
            template_path = os.path.join(template_dir, 'bull_stock_web.html')
            print(f"[index] 模板路径: {template_path}, 存在: {os.path.exists(template_path)}")
            result = render_template('bull_stock_web.html')
            print("[index] ✅ 模板渲染成功")
            return result
        except Exception as template_error:
            import traceback
            error_detail = traceback.format_exc()
            print(f"[index] ❌ 渲染模板失败: {error_detail}")
            return f"""
            <!DOCTYPE html>
            <html>
            <head><title>页面加载失败</title></head>
            <body>
                <h1>页面加载失败</h1>
                <p>错误: {str(template_error)}</p>
                <p><a href="/login">前往登录页面</a></p>
            </body>
            </html>
            """, 500
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"[index] ❌ 主页错误: {error_detail}")
        return f"""
        <!DOCTYPE html>
        <html>
        <head><title>服务器错误</title></head>
        <body>
            <h1>服务器错误</h1>
            <p>错误: {str(e)}</p>
            <p><a href="/login">前往登录页面</a></p>
        </body>
        </html>
        """, 500

@app.route('/favicon.ico')
def favicon():
    """处理favicon请求，返回204 No Content；加短缓存减轻重复请求"""
    try:
        r = app.make_response(('', 204))
        r.headers['Cache-Control'] = 'public, max-age=3600'
        return r
    except Exception as e:
        return '', 204

@app.route('/login')
def login_page():
    """登录页面"""
    print("[login_page] 开始处理登录页面请求...")
    try:
        # 检查是否已登录
        try:
            logged_in = is_logged_in()
            print(f"[login_page] 登录状态检查结果: {logged_in}")
        except Exception as login_check_error:
            import traceback
            error_detail = traceback.format_exc()
            print(f"[login_page] ⚠️ 检查登录状态失败: {error_detail}")
            logged_in = False
        
        if logged_in:
            print("[login_page] 已登录，重定向到主页")
            try:
                return redirect(url_for('index'))
            except Exception as redirect_error:
                print(f"[login_page] ⚠️ 重定向失败: {redirect_error}")
                return redirect('/')
        
        # 渲染登录模板
        print("[login_page] 开始渲染登录模板...")
        try:
            # 检查模板文件是否存在
            template_path = os.path.join(template_dir, 'login.html')
            print(f"[login_page] 模板路径: {template_path}, 存在: {os.path.exists(template_path)}")
            if not os.path.exists(template_path):
                print(f"[login_page] ❌ 模板文件不存在: {template_path}")
                # 尝试其他可能的路径
                alt_paths = [
                    'templates/login.html',
                    os.path.join(os.path.dirname(__file__), 'templates', 'login.html'),
                    os.path.join(os.getcwd(), 'templates', 'login.html'),
                ]
                for alt_path in alt_paths:
                    abs_alt_path = os.path.abspath(alt_path)
                    print(f"[login_page] 尝试备用路径: {abs_alt_path}, 存在: {os.path.exists(abs_alt_path)}")
                    if os.path.exists(abs_alt_path):
                        template_path = abs_alt_path
                        break
                else:
                    raise FileNotFoundError(f"找不到 login.html 模板文件。尝试的路径: {template_path}, {alt_paths}")
            
            result = render_template('login.html')
            print("[login_page] ✅ 模板渲染成功")
            return result
        except Exception as template_error:
            import traceback
            error_detail = traceback.format_exc()
            print(f"[login_page] ❌ 渲染模板失败: {error_detail}")
            return f"""
            <!DOCTYPE html>
            <html>
            <head><title>登录错误</title></head>
            <body>
                <h1>登录页面加载失败</h1>
                <p>错误: {str(template_error)}</p>
                <p>模板路径: {template_dir}</p>
                <p><a href="/">返回首页</a></p>
            </body>
            </html>
            """, 500
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"[login_page] ❌ 登录页面错误: {error_detail}")
        return f"""
        <!DOCTYPE html>
        <html>
        <head><title>服务器错误</title></head>
        <body>
            <h1>服务器错误</h1>
            <p>错误: {str(e)}</p>
            <p><a href="/">返回首页</a></p>
        </body>
        </html>
        """, 500

@app.route('/register')
def register_page():
    """注册页面"""
    try:
        if is_logged_in():
            return redirect(url_for('index'))
        return render_template('register.html')
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"注册页面错误: {error_detail}")
        return f"<h1>服务器错误</h1><pre>{error_detail}</pre>", 500


@app.route('/near_new_high')
def near_new_high_page():
    """新高附近选股页面：前高间隔≥5周、附近±5%。"""
    try:
        if not is_logged_in():
            return redirect(url_for('login_page'))
        return render_template('near_new_high.html')
    except Exception as e:
        import traceback
        return f"<h1>页面错误</h1><pre>{traceback.format_exc()}</pre>", 500


# ==================== 认证相关 API ====================

@app.route('/api/register', methods=['POST'])
def api_register():
    """用户注册API（邮箱注册，无需邀请码）"""
    try:
        data = request.get_json(silent=True) or {}
        username = data.get('username', '').strip()
        email = data.get('email', '').strip()
        password = data.get('password', '')
        invite_code = data.get('invite_code', '').strip().upper() or None  # 邀请码改为可选
        
        if not username or not email or not password:
            return jsonify({
                'success': False,
                'message': '请填写用户名、邮箱和密码'
            }), 400
        
        result = register_user(username, email, password, invite_code)
        
        if result['success']:
            # 注册成功后自动登录
            session['username'] = username
            return jsonify({
                'success': True,
                'message': '注册成功',
                'user': {
                    'username': username,
                    'email': email
                }
            })
        else:
            return jsonify(result), 400
            
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"注册错误: {error_detail}")
        return jsonify({
            'success': False,
            'message': f'服务器错误: {str(e)}'
        }), 500

@app.route('/api/login', methods=['POST'])
def api_login():
    """用户登录API"""
    # 记录登录开始时间
    login_start_time = time.time()
    login_start_datetime = datetime.now()
    
    try:
        data = request.get_json(silent=True) or {}
        username = data.get('username', '').strip()
        password = data.get('password', '')
        
        if not username or not password:
            login_end_time = time.time()
            login_duration = (login_end_time - login_start_time) * 1000
            _log_login_attempt(username, False, login_duration, login_start_datetime, "请输入用户名和密码")
            return jsonify({
                'success': False,
                'message': '请输入用户名和密码'
            }), 400
        
        # 本地环境快速登录：如果用户名是 'test' 且密码是 'test123'，直接登录
        if not is_vercel and username == 'test' and password == 'test123':
            # 确保测试用户存在
            if is_vercel:
                from user_auth_vercel import load_users, save_users, hash_password
            else:
                from user_auth import load_users, save_users, hash_password
            
            users = load_users()
            if 'test' not in users:
                # 自动创建测试用户
                users['test'] = {
                    'username': 'test',
                    'email': 'test@local.com',
                    'password': hash_password('test123'),
                    'created_at': datetime.now().isoformat(),
                    'last_login': datetime.now().isoformat(),
                    'invite_code': 'LOCAL_TEST',
                    'is_active': True,
                    'is_vip': True,
                    'is_super': False
                }
                save_users(users)
            
            session['username'] = 'test'
            login_end_time = time.time()
            login_duration = (login_end_time - login_start_time) * 1000
            _log_login_attempt('test', True, login_duration, login_start_datetime, "快速登录成功（本地测试模式）")
            return jsonify({
                'success': True,
                'message': '快速登录成功（本地测试模式）',
                'user': {
                    'username': 'test',
                    'email': 'test@local.com',
                    'is_vip': True
                }
            })
        
        result = login_user(username, password)
        
        login_end_time = time.time()
        login_duration = (login_end_time - login_start_time) * 1000
        
        if result['success']:
            session['username'] = username
            _log_login_attempt(username, True, login_duration, login_start_datetime, result.get('message', '登录成功'))
            response = jsonify(result)
            # 禁止缓存登录响应，避免浏览器缓存导致的问题
            response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'
            return response
        else:
            # 详细记录登录失败原因
            error_msg = result.get('message', '登录失败')
            print(f"❌ 登录失败 - 用户名: {username}, 原因: {error_msg}, 耗时: {login_duration:.2f}ms")
            
            # 对于 super 用户登录失败，尝试自动恢复
            if username == 'super':
                print(f"⚠️ super 用户登录失败，尝试自动恢复账户...")
                try:
                    if is_vercel or is_render or has_redis:
                        from user_auth_vercel import load_users, save_users, hash_password
                    else:
                        from user_auth import load_users, save_users, hash_password
                    
                    users = load_users()
                    if 'super' not in users:
                        # 创建 super 用户
                        users['super'] = {
                            'username': 'super',
                            'email': 'super@admin.com',
                            'password': hash_password('superzwj'),
                            'created_at': datetime.now().isoformat(),
                            'last_login': None,
                            'invite_code': 'AUTO_RECOVERED',
                            'is_active': True,
                            'is_vip': True,
                            'is_super': True,
                            'is_test_user': True
                        }
                        save_users(users)
                        print(f"✅ 已自动恢复 super 用户账户")
                        # 重新尝试登录
                        result = login_user(username, password)
                        if result['success']:
                            session['username'] = username
                            _log_login_attempt(username, True, login_duration, login_start_datetime, '登录成功（账户已自动恢复）')
                            response = jsonify(result)
                            response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
                            response.headers['Pragma'] = 'no-cache'
                            response.headers['Expires'] = '0'
                            return response
                except Exception as e:
                    print(f"❌ 自动恢复 super 用户失败: {e}")
                    import traceback
                    traceback.print_exc()
            
            _log_login_attempt(username, False, login_duration, login_start_datetime, error_msg)
            response = jsonify(result)
            # 禁止缓存错误响应
            response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'
            return response, 401
            
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"登录错误: {error_detail}")
        login_end_time = time.time()
        login_duration = (login_end_time - login_start_time) * 1000
        _log_login_attempt(username if 'username' in locals() else 'unknown', False, login_duration, login_start_datetime, f'服务器错误: {str(e)}')
        return jsonify({
            'success': False,
            'message': f'服务器错误: {str(e)}'
        }), 500

@app.route('/api/logout', methods=['POST'])
@require_login
def api_logout():
    """用户登出API"""
    session.clear()
    return jsonify({
        'success': True,
        'message': '已退出登录'
    })

# ========== 数据自动更新功能 ==========
data_update_progress = {
    'status': 'idle',  # idle, running, completed, error
    'processed': 0,
    'total': 0,
    'percentage': 0,
    'current_stock': '',
    'message': '',
    'updated_count': 0,
    'failed_count': 0,
    'start_time': None
}
data_update_stop_flag = False

# 过前高全市场扫描进度（仅本地/Render 单进程有效）
near_high_scan_progress = {
    'status': 'idle',   # idle, running, completed, error
    'current': 0,
    'total': 0,
    'percentage': 0,
    'message': '',
    'list': [],
    'scan_date': None,
    'total_scanned': 0,
}

# 数据更新时间戳文件路径
DATA_UPDATE_TIMESTAMP_FILE = 'cache/data_update_timestamp.json'

def _format_time(seconds):
    """格式化时间为可读格式（例如：1分30秒、2小时15分）"""
    if seconds < 60:
        return f'{int(seconds)}秒'
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f'{minutes}分{secs}秒'
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f'{hours}小时{minutes}分{secs}秒'

def _load_data_update_timestamp():
    """加载数据更新时间戳"""
    import json as json_module
    import os
    if os.path.exists(DATA_UPDATE_TIMESTAMP_FILE):
        try:
            with open(DATA_UPDATE_TIMESTAMP_FILE, 'r', encoding='utf-8') as f:
                return json_module.load(f)
        except Exception:
            return {}
    return {}

def _save_data_update_timestamp(timestamp_str):
    """保存数据更新时间戳"""
    import json as json_module
    import os
    try:
        os.makedirs('cache', exist_ok=True)
        with open(DATA_UPDATE_TIMESTAMP_FILE, 'w', encoding='utf-8') as f:
            json_module.dump({
                'last_update_time': timestamp_str,
                'last_update_date': timestamp_str.split()[0] if ' ' in timestamp_str else timestamp_str[:10]
            }, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[_save_data_update_timestamp] 保存时间戳失败: {e}")

def _should_skip_update_after_trading_hours():
    """检查是否应该跳过更新（交易日15:00后已更新过）
    重要：不仅检查时间戳，还要检查实际数据是否真的更新到今天"""
    from datetime import datetime, timezone, timedelta
    import os
    import pandas as pd
    
    # 获取北京时间（UTC+8）
    utc_now = datetime.now(timezone.utc)
    beijing_tz = timezone(timedelta(hours=8))
    beijing_now = utc_now.astimezone(beijing_tz)
    
    current_hour = beijing_now.hour
    current_minute = beijing_now.minute
    today_str = beijing_now.strftime('%Y-%m-%d')
    
    # ✅ 检查是否是交易日15:00之后
    if current_hour < 15:
        return False, None  # 还没到15:00，可以更新
    
    # ✅ 15:00之后，检查今天是否已经更新过
    timestamp_data = _load_data_update_timestamp()
    if timestamp_data:
        last_update_date = timestamp_data.get('last_update_date')
        last_update_time_str = timestamp_data.get('last_update_time', '')
        
        # 如果今天已经更新过
        if last_update_date == today_str:
            # ✅ 关键修复：检查实际数据是否真的更新到今天
            # 检查几个样本股票的最新数据日期
            sample_codes = ['000001', '000002', '600000', '600519']
            actual_latest_date = None
            for code in sample_codes:
                csv_path = os.path.join('cache', 'daily_kline', f'{code}.csv')
                if os.path.exists(csv_path):
                    try:
                        df = pd.read_csv(csv_path, usecols=['日期'], encoding='utf-8')
                        if len(df) > 0:
                            df['日期'] = pd.to_datetime(df['日期'], errors='coerce')
                            df = df.dropna(subset=['日期'])
                            if len(df) > 0:
                                latest = df['日期'].max()
                                latest_str = latest.strftime('%Y-%m-%d')
                                if actual_latest_date is None or latest_str > actual_latest_date:
                                    actual_latest_date = latest_str
                    except:
                        pass
            
            # 如果实际数据最新日期不是今天，说明数据没有真正更新
            if actual_latest_date and actual_latest_date < today_str:
                return False, f'时间戳显示已更新，但实际数据最新日期是 {actual_latest_date}，需要重新更新'
            
            # 检查更新时间是否在15:00之后
            if last_update_time_str:
                try:
                    # 解析时间戳（假设是北京时间）
                    update_time = datetime.strptime(last_update_time_str, '%Y-%m-%d %H:%M:%S')
                    update_hour = update_time.hour
                    if update_hour >= 15:
                        # ✅ 只有实际数据也更新到今天，才跳过更新
                        if actual_latest_date == today_str:
                            return True, f'今日 {last_update_time_str} 已更新，交易已结束，无需再次更新'
                        else:
                            return False, f'时间戳显示已更新，但实际数据最新日期是 {actual_latest_date}，需要重新更新'
                except:
                    pass
        
        # 如果昨天15:00后更新过，今天15:00后也认为不需要更新（但也要检查实际数据）
        if last_update_date:
            try:
                last_date = datetime.strptime(last_update_date, '%Y-%m-%d')
                days_diff = (beijing_now.date() - last_date.date()).days
                if days_diff == 1:  # 昨天
                    if last_update_time_str:
                        try:
                            update_time = datetime.strptime(last_update_time_str, '%Y-%m-%d %H:%M:%S')
                            if update_time.hour >= 15:
                                # ✅ 检查实际数据是否更新到今天
                                sample_codes = ['000001', '000002', '600000', '600519']
                                actual_latest_date = None
                                for code in sample_codes:
                                    csv_path = os.path.join('cache', 'daily_kline', f'{code}.csv')
                                    if os.path.exists(csv_path):
                                        try:
                                            df = pd.read_csv(csv_path, usecols=['日期'], encoding='utf-8')
                                            if len(df) > 0:
                                                df['日期'] = pd.to_datetime(df['日期'], errors='coerce')
                                                df = df.dropna(subset=['日期'])
                                                if len(df) > 0:
                                                    latest = df['日期'].max()
                                                    latest_str = latest.strftime('%Y-%m-%d')
                                                    if actual_latest_date is None or latest_str > actual_latest_date:
                                                        actual_latest_date = latest_str
                                        except:
                                            pass
                                
                                if actual_latest_date == today_str:
                                    return True, f'{last_update_date} {last_update_time_str.split()[1] if " " in last_update_time_str else ""} 已更新，今日交易已结束'
                                else:
                                    return False, f'时间戳显示已更新，但实际数据最新日期是 {actual_latest_date}，需要重新更新'
                        except:
                            pass
            except:
                pass
    
    return False, None  # 暂时允许，但会在 check_data_freshness 和 start_data_update 中再次检查

def check_data_freshness(target_date: str = None) -> dict:
    """
    检查本地数据是否满足扫描需求
    :param target_date: 目标扫描日期，如果为None则使用今天
    :return: {'fresh': bool, 'outdated_count': int, 'total': int, 'latest_data_date': str}
    """
    import os
    import pandas as pd
    from datetime import datetime
    
    if target_date is None:
        target_date = datetime.now().strftime('%Y-%m-%d')
    
    weekly_dir = 'cache/weekly_kline'
    if not os.path.exists(weekly_dir):
        return {'fresh': False, 'outdated_count': 0, 'total': 0, 'latest_data_date': None, 'message': '缓存目录不存在'}
    
    target_ts = pd.to_datetime(target_date)
    # 允许7天的误差（周K线数据可能滞后）
    min_acceptable_date = target_ts - pd.Timedelta(days=7)
    
    total = 0
    outdated = 0
    dates = []
    
    for f in os.listdir(weekly_dir):
        if f.endswith('.csv'):
            total += 1
            try:
                df = pd.read_csv(os.path.join(weekly_dir, f))
                if '日期' in df.columns and len(df) > 0:
                    max_date = pd.to_datetime(str(df['日期'].max())[:10])
                    dates.append(max_date)
                    if max_date < min_acceptable_date:
                        outdated += 1
            except:
                outdated += 1
    
    latest_data_date = max(dates).strftime('%Y-%m-%d') if dates else None
    # 如果超过10%的股票数据过期，认为需要更新
    need_update = outdated > total * 0.1 if total > 0 else True
    
    return {
        'fresh': not need_update,
        'outdated_count': outdated,
        'total': total,
        'latest_data_date': latest_data_date,
        'target_date': target_date,
        'message': f'共{total}只股票，{outdated}只数据过期' if need_update else '数据已是最新'
    }

def _load_data_markers():
    """加载数据标记文件，记录每只股票的最新数据日期和更新时间戳"""
    import json as json_module
    marker_file = 'cache/data_markers.json'
    if os.path.exists(marker_file):
        try:
            with open(marker_file, 'r', encoding='utf-8') as f:
                return json_module.load(f)
        except Exception:
            return {}
    return {}

def _save_data_markers(markers):
    """保存数据标记文件"""
    import json as json_module
    os.makedirs('cache', exist_ok=True)
    marker_file = 'cache/data_markers.json'
    with open(marker_file, 'w', encoding='utf-8') as f:
        json_module.dump(markers, f, ensure_ascii=False, indent=2)

def _get_stock_latest_dates(code):
    """获取股票的最新数据日期（从标记文件或CSV文件）"""
    markers = _load_data_markers()
    
    # 优先从标记文件读取
    if code in markers:
        return {
            'daily': markers[code].get('daily_latest_date'),
            'weekly': markers[code].get('weekly_latest_date'),
            'last_update_timestamp': markers[code].get('last_update_timestamp')
        }
    
    # 如果标记文件没有，从CSV文件读取并更新标记
    result = {'daily': None, 'weekly': None, 'last_update_timestamp': None}
    
    # 读取日K线最新日期
    daily_path = f'cache/daily_kline/{code}.csv'
    if os.path.exists(daily_path):
        try:
            df = pd.read_csv(daily_path)
            if len(df) > 0 and '日期' in df.columns:
                result['daily'] = str(df['日期'].max())[:10]
        except Exception:
            pass
    
    # 读取周K线最新日期
    weekly_path = f'cache/weekly_kline/{code}.csv'
    if os.path.exists(weekly_path):
        try:
            df = pd.read_csv(weekly_path)
            if len(df) > 0 and '日期' in df.columns:
                result['weekly'] = str(df['日期'].max())[:10]
        except Exception:
            pass
    
    # 更新标记文件
    if code not in markers:
        markers[code] = {}
    markers[code]['daily_latest_date'] = result['daily']
    markers[code]['weekly_latest_date'] = result['weekly']
    _save_data_markers(markers)
    
    return result

def _update_stock_marker(code, daily_latest_date=None, weekly_latest_date=None):
    """更新股票的数据标记（包含时间戳）"""
    from datetime import datetime
    markers = _load_data_markers()
    if code not in markers:
        markers[code] = {}
    if daily_latest_date:
        markers[code]['daily_latest_date'] = daily_latest_date
    if weekly_latest_date:
        markers[code]['weekly_latest_date'] = weekly_latest_date
    # ✅ 更新时记录时间戳
    markers[code]['last_update_timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    _save_data_markers(markers)

def _is_data_up_to_date(code, latest_date=None, last_update_timestamp=None):
    """
    判断数据是否已是最新（智能判断）
    规则：
    - 如果最新日期是今天 → 认为是最新
    - 如果最新日期是昨天，且更新时间在当天15:00后，在第二天9:30前都认为是最新
    - 如果最新日期是2天前或更早 → 需要更新
    """
    from datetime import datetime, timedelta
    
    if not latest_date:
        return False
    
    today = datetime.now()
    today_str = today.strftime('%Y-%m-%d')
    
    # 如果最新日期是今天，认为是最新
    if latest_date >= today_str:
        return True
    
    # 如果最新日期是昨天，检查更新时间
    yesterday = (today - timedelta(days=1)).strftime('%Y-%m-%d')
    if latest_date == yesterday:
        if last_update_timestamp:
            try:
                update_time = datetime.strptime(last_update_timestamp, '%Y-%m-%d %H:%M:%S')
                update_date = update_time.strftime('%Y-%m-%d')
                
                # 如果更新日期是今天或昨天，且更新时间在当天15:00后
                if update_date in [today_str, yesterday]:
                    update_hour = update_time.hour
                    if update_hour >= 15:  # 15:00后（3点后）
                        # 检查当前时间：如果是第二天9:30以后，需要更新
                        current_hour = today.hour
                        current_minute = today.minute
                        if current_hour < 9 or (current_hour == 9 and current_minute < 30):
                            # 第二天9:30前，认为是最新
                            return True
                        # 第二天9:30后，需要更新
                        return False
            except Exception:
                pass
        # 如果没有时间戳，但日期是昨天，也认为是最新（兼容旧数据）
        return True
    
    # 如果最新日期是2天前或更早，需要更新
    latest_dt = datetime.strptime(latest_date, '%Y-%m-%d')
    days_diff = (today - latest_dt).days
    return days_diff <= 1  # 1天内认为是最新，超过1天需要更新

def _get_sina_daily_kline(code, datalen=500):
    """从新浪获取日K线数据（支持指定数据条数）"""
    try:
        import requests
        import json as json_module
        import pandas as pd
        
        # 转换代码格式
        if code.startswith('6'):
            symbol = f'sh{code}'
        else:
            symbol = f'sz{code}'
        
        url = f'https://quotes.sina.cn/cn/api/jsonp_v2.php/data/CN_MarketDataService.getKLineData?symbol={symbol}&scale=240&datalen={datalen}'
        
        session = requests.Session()
        session.trust_env = False
        session.headers.update({'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'})
        
        resp = session.get(url, timeout=5)
        if resp.status_code == 200:
            text = resp.text
            if 'data(' in text:
                json_str = text.split('data(')[1].rsplit(')', 1)[0]
                data = json_module.loads(json_str)
                if data:
                    df = pd.DataFrame(data)
                    df = df.rename(columns={
                        'day': '日期',
                        'open': '开盘',
                        'close': '收盘',
                        'high': '最高',
                        'low': '最低',
                        'volume': '成交量'
                    })
                    df = df[['日期', '开盘', '收盘', '最高', '最低', '成交量']]
                    df['日期'] = pd.to_datetime(df['日期'], errors='coerce')
                    df = df.dropna(subset=['日期'])
                    df = df.sort_values('日期').reset_index(drop=True)
                    df['日期'] = df['日期'].dt.strftime('%Y-%m-%d')
                    return df
        return None
    except Exception:
        return None

def _get_sina_weekly_kline(code, datalen=200):
    """从新浪获取周K线数据（支持指定数据条数）"""
    try:
        import requests
        import json as json_module
        import pandas as pd
        
        # 转换代码格式
        if code.startswith('6'):
            symbol = f'sh{code}'
        else:
            symbol = f'sz{code}'
        
        url = f'https://quotes.sina.cn/cn/api/jsonp_v2.php/data/CN_MarketDataService.getKLineData?symbol={symbol}&scale=1200&datalen={datalen}'
        
        session = requests.Session()
        session.trust_env = False
        session.headers.update({'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'})
        
        resp = session.get(url, timeout=5)
        if resp.status_code == 200:
            text = resp.text
            if 'data(' in text:
                json_str = text.split('data(')[1].rsplit(')', 1)[0]
                data = json_module.loads(json_str)
                if data:
                    df = pd.DataFrame(data)
                    df = df.rename(columns={
                        'day': '日期',
                        'open': '开盘',
                        'close': '收盘',
                        'high': '最高',
                        'low': '最低',
                        'volume': '周成交量'
                    })
                    df = df[['日期', '开盘', '收盘', '最高', '最低', '周成交量']]
                    df['日期'] = pd.to_datetime(df['日期'], errors='coerce')
                    df = df.dropna(subset=['日期'])
                    df = df.sort_values('日期').reset_index(drop=True)
                    df['日期'] = df['日期'].dt.strftime('%Y-%m-%d')
                    return df
        return None
    except Exception:
        return None

def _data_update_worker():
    """后台数据更新工作线程：调用 update_data_sina.py 更新数据，完成后自动融合
    默认：today-only（只补齐今天日K），历史数据已存在时速度更快。"""
    global data_update_progress, data_update_stop_flag
    import subprocess
    import sys
    import time
    import os
    
    try:
        data_update_progress['status'] = 'running'
        data_update_progress['message'] = '正在启动批量数据下载...'
        data_update_progress['start_time'] = time.time()
        
        # 调用 update_data_sina.py 脚本进行批量下载
        script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'update_data_sina.py')
        
        if not os.path.exists(script_path):
            data_update_progress['status'] = 'error'
            data_update_progress['message'] = f'更新脚本不存在: {script_path}'
            return
        
        data_update_progress['message'] = '正在更新今日数据（日K，仅今天；使用新浪财经API）...'
        data_update_progress['data_source'] = 'sina'
        
        # 运行脚本（实时输出进度）
        process = subprocess.Popen(
            [sys.executable, script_path, '--today-only'],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True,
            cwd=os.path.dirname(os.path.abspath(__file__))
        )
        
        # 实时读取输出并更新进度
        output_lines = []
        for line in process.stdout:
            if data_update_stop_flag:
                process.terminate()
                data_update_progress['status'] = 'stopped'
                data_update_progress['message'] = '更新已停止'
                return
            
            line = line.strip()
            if line:
                output_lines.append(line)
                # ✅ 实时计算已用时间
                elapsed = time.time() - data_update_progress['start_time']
                data_update_progress['elapsed_time'] = elapsed
                
                # 解析总股票数（例如：📊 参与更新股票数: 5007（全部））
                if '参与更新股票数:' in line and '（全部）' in line:
                    try:
                        parts = line.split('参与更新股票数:')[1].split('（')[0].strip()
                        total = int(parts)
                        data_update_progress['total'] = total
                    except:
                        pass
                # 解析进度信息（例如：进度: 200/5007 (4.0%)）
                if '进度:' in line and '/' in line:
                    try:
                        parts = line.split('进度:')[1].split('|')[0].strip()
                        if '/' in parts:
                            current, total = parts.split('/')
                            current = int(current.split()[0])
                            total = int(total.split()[0])
                            data_update_progress['processed'] = current
                            if not data_update_progress.get('total'):
                                data_update_progress['total'] = total
                            data_update_progress['percentage'] = round(current / total * 100, 1) if total > 0 else 0
                            # 解析速度信息
                            speed_info = ''
                            if '速度:' in line:
                                try:
                                    speed_part = line.split('速度:')[1].split('|')[0].strip()
                                    speed = float(speed_part.split()[0])
                                    speed_info = f' | 速度: {speed:.1f}只/秒'
                                except:
                                    pass
                            # ✅ 在消息中包含已用时间
                            elapsed_str = _format_time(elapsed)
                            data_update_progress['message'] = f'正在批量下载: {current}/{total} ({data_update_progress["percentage"]:.1f}%){speed_info} | 已用时间: {elapsed_str}'
                    except:
                        pass
                # 解析新增记录数
                if '日K新增:' in line:
                    try:
                        parts = line.split('日K新增:')[1].split('|')[0].strip()
                        daily_new = int(parts.split()[0])
                        data_update_progress['updated_count'] = daily_new
                    except:
                        pass
                if '周K新增:' in line:
                    try:
                        parts = line.split('周K新增:')[1].split('|')[0].strip()
                        weekly_new = int(parts.split()[0])
                        # 可以记录周K新增数，但主要用日K新增作为 updated_count
                    except:
                        pass
        
        # 等待进程完成
        return_code = process.wait()
        
        if return_code != 0:
            error_msg = '\n'.join(output_lines[-10:])  # 最后10行
            elapsed = time.time() - data_update_progress['start_time']
            elapsed_str = _format_time(elapsed)
            data_update_progress['status'] = 'error'
            data_update_progress['message'] = f'下载失败（返回码: {return_code}）: {error_msg[:200]}'
            data_update_progress['elapsed_time'] = elapsed
            return
        
        # ✅ 检查实际是否有新数据被下载
        daily_total_new = 0
        weekly_total_new = 0
        for line in output_lines:
            # 解析最终统计：日K线新增记录: XXX
            if '日K线新增记录:' in line:
                try:
                    parts = line.split('日K线新增记录:')[1].strip()
                    daily_total_new = int(parts.split()[0])
                except:
                    pass
            # 解析最终统计：周K线新增记录: XXX
            if '周K线新增记录:' in line:
                try:
                    parts = line.split('周K线新增记录:')[1].strip()
                    weekly_total_new = int(parts.split()[0])
                except:
                    pass
        
        # 如果没有任何新数据，不更新时间戳
        if daily_total_new == 0 and weekly_total_new == 0:
            elapsed = time.time() - data_update_progress['start_time']
            elapsed_str = _format_time(elapsed)
            data_update_progress['status'] = 'completed'
            data_update_progress['message'] = f'⚠️ 下载完成，但未发现新数据（可能数据已是最新或API失败）。耗时 {elapsed_str}。'
            data_update_progress['elapsed_time'] = elapsed
            print(f"[数据更新] ⚠️ 未发现新数据，不更新时间戳")
            return
        
        elapsed = time.time() - data_update_progress['start_time']
        data_update_progress['elapsed_time'] = elapsed
        
        # ✅ 下载完成后，自动融合数据（重建 data_markers.json）
        elapsed_str = _format_time(elapsed)
        data_update_progress['message'] = f'下载完成！新增日K: {daily_total_new}条，周K: {weekly_total_new}条。耗时 {elapsed_str}。正在融合数据到个股数据...'
        data_update_progress['status'] = 'merging'  # 融合中状态
        
        try:
            # 调用 merge_data_markers.py 进行数据融合
            merge_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'merge_data_markers.py')
            if os.path.exists(merge_script):
                merge_result = subprocess.run(
                    [sys.executable, merge_script],
                    capture_output=True,
                    text=True,
                    timeout=300,  # 5分钟超时
                    cwd=os.path.dirname(os.path.abspath(__file__))
                )
                if merge_result.returncode == 0:
                    # 解析融合结果
                    merge_output = merge_result.stdout
                    daily_info = ''
                    weekly_info = ''
                    total_markers = ''
                    if '日 K:' in merge_output:
                        daily_info = merge_output.split('日 K:')[1].split('\n')[0].strip()
                    if '周 K:' in merge_output:
                        weekly_info = merge_output.split('周 K:')[1].split('\n')[0].strip()
                    if 'data_markers 总条数:' in merge_output:
                        total_markers = merge_output.split('data_markers 总条数:')[1].split('\n')[0].strip()
                    
                    # ✅ 融合完成后，重新计算总时间
                    elapsed = time.time() - data_update_progress['start_time']
                    elapsed_str = _format_time(elapsed)
                    
                    data_update_progress['status'] = 'completed'
                    summary = f'✅ 更新完成！新增日K: {daily_total_new}条，周K: {weekly_total_new}条。耗时 {elapsed_str}。数据已融合到个股数据。'
                    if daily_info:
                        summary += f' {daily_info}'
                    if weekly_info:
                        summary += f' {weekly_info}'
                    if total_markers:
                        summary += f' 总条数: {total_markers}'
                    data_update_progress['message'] = summary
                    data_update_progress['elapsed_time'] = elapsed
                    
                    # ✅ 只有真正有新数据时才记录更新时间戳
                    from datetime import datetime
                    timestamp_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    _save_data_update_timestamp(timestamp_str)
                    print(f"[数据更新] ✅ 有新数据更新（日K: {daily_total_new}条，周K: {weekly_total_new}条），更新时间戳: {timestamp_str}")
                else:
                    # ✅ 融合完成后，重新计算总时间
                    elapsed = time.time() - data_update_progress['start_time']
                    elapsed_str = _format_time(elapsed)
                    
                    data_update_progress['status'] = 'completed'
                    data_update_progress['message'] = f'✅ 下载完成！新增日K: {daily_total_new}条，周K: {weekly_total_new}条。耗时 {elapsed_str}。⚠️ 融合过程有警告: {merge_result.stderr[:200] if merge_result.stderr else "无错误信息"}'
                    data_update_progress['elapsed_time'] = elapsed
                    # ✅ 只有真正有新数据时才记录更新时间戳
                    if daily_total_new > 0 or weekly_total_new > 0:
                        from datetime import datetime
                        timestamp_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        _save_data_update_timestamp(timestamp_str)
                        print(f"[数据更新] ✅ 有新数据更新（日K: {daily_total_new}条，周K: {weekly_total_new}条），更新时间戳: {timestamp_str}")
                    else:
                        print(f"[数据更新] ⚠️ 融合有警告但无新数据，不更新时间戳")
            else:
                data_update_progress['status'] = 'completed'
                data_update_progress['message'] = f'✅ 下载完成！新增日K: {daily_total_new}条，周K: {weekly_total_new}条。耗时 {elapsed_str}。⚠️ 融合脚本不存在，跳过融合。'
                data_update_progress['elapsed_time'] = elapsed
                # ✅ 只有真正有新数据时才记录更新时间戳
                if daily_total_new > 0 or weekly_total_new > 0:
                    from datetime import datetime
                    timestamp_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    _save_data_update_timestamp(timestamp_str)
                    print(f"[数据更新] ✅ 有新数据更新（日K: {daily_total_new}条，周K: {weekly_total_new}条），更新时间戳: {timestamp_str}")
                else:
                    print(f"[数据更新] ⚠️ 融合脚本不存在且无新数据，不更新时间戳")
        except subprocess.TimeoutExpired:
            # ✅ 融合超时后，重新计算总时间
            elapsed = time.time() - data_update_progress['start_time']
            elapsed_str = _format_time(elapsed)
            
            data_update_progress['status'] = 'completed'
            data_update_progress['message'] = f'✅ 下载完成！新增日K: {daily_total_new}条，周K: {weekly_total_new}条。耗时 {elapsed_str}。⚠️ 融合超时（5分钟），但数据已下载完成。'
            data_update_progress['elapsed_time'] = elapsed
            # ✅ 只有真正有新数据时才记录更新时间戳
            if daily_total_new > 0 or weekly_total_new > 0:
                from datetime import datetime
                timestamp_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                _save_data_update_timestamp(timestamp_str)
                print(f"[数据更新] ✅ 有新数据更新（日K: {daily_total_new}条，周K: {weekly_total_new}条），更新时间戳: {timestamp_str}")
            else:
                print(f"[数据更新] ⚠️ 融合超时且无新数据，不更新时间戳")
        except Exception as merge_error:
            # ✅ 融合失败后，重新计算总时间
            elapsed = time.time() - data_update_progress['start_time']
            elapsed_str = _format_time(elapsed)
            
            data_update_progress['status'] = 'completed'
            data_update_progress['message'] = f'✅ 下载完成！新增日K: {daily_total_new}条，周K: {weekly_total_new}条。耗时 {elapsed_str}。⚠️ 融合失败: {str(merge_error)[:100]}'
            data_update_progress['elapsed_time'] = elapsed
            # ✅ 只有真正有新数据时才记录更新时间戳
            if daily_total_new > 0 or weekly_total_new > 0:
                from datetime import datetime
                timestamp_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                _save_data_update_timestamp(timestamp_str)
                print(f"[数据更新] ✅ 有新数据更新（日K: {daily_total_new}条，周K: {weekly_total_new}条），更新时间戳: {timestamp_str}")
            else:
                print(f"[数据更新] ⚠️ 融合失败且无新数据，不更新时间戳")
        
    except Exception as e:
        elapsed = time.time() - data_update_progress.get('start_time', time.time())
        elapsed_str = _format_time(elapsed) if 'start_time' in data_update_progress else '未知'
        data_update_progress['status'] = 'error'
        data_update_progress['message'] = f'更新出错: {str(e)}'
        if 'start_time' in data_update_progress:
            data_update_progress['elapsed_time'] = elapsed

@app.route('/api/start_data_update', methods=['POST'])
@require_login
def start_data_update():
    """启动数据更新"""
    global data_update_progress, data_update_stop_flag
    import threading  # ✅ 添加 threading 导入
    
    if data_update_progress['status'] == 'running':
        return jsonify({'success': False, 'message': '数据更新正在进行中'})
    
    # ✅ 检查是否强制更新（silent=True 避免空 body 导致 400）
    data = request.get_json(silent=True) or {}
    force_update = data.get('force', False)  # 强制更新选项
    # ✅ 最早加载 markers，避免任意分支使用未定义变量导致 500
    markers = _load_data_markers()
    
    # ✅ 检查是否应该跳过更新（交易日15:00后已更新过），除非强制更新
    if not force_update:
        should_skip, skip_reason = _should_skip_update_after_trading_hours()
        if should_skip:
            return jsonify({
                'success': False,
                'message': skip_reason or '交易已结束，今日已更新，无需再次更新',
                'skip_reason': 'trading_hours_ended',
                'can_force': True  # 允许强制更新
            })
    
    # ✅ 额外检查：如果当前时间已经是15:00后，且没有时间戳文件，也阻止更新
    from datetime import datetime, timezone, timedelta
    utc_now = datetime.now(timezone.utc)
    beijing_tz = timezone(timedelta(hours=8))
    beijing_now = utc_now.astimezone(beijing_tz)
    if beijing_now.hour >= 15:
        timestamp_data = _load_data_update_timestamp()
        if not timestamp_data or not timestamp_data.get('last_update_date'):
            # 15:00后且没有时间戳记录，阻止更新（交易已结束）
            return jsonify({
                'success': False,
                'message': f'当前时间 {beijing_now.strftime("%H:%M")}，交易已结束。如需更新数据，请稍后再试或手动点击"更新数据"按钮',
                'skip_reason': 'trading_hours_ended_no_timestamp'
            })
    
    # ✅ 先检查数据是否已是最新（使用标记文件快速检查）
    from datetime import datetime
    today = datetime.now()
    today_str = today.strftime('%Y-%m-%d')
    markers = _load_data_markers()
    
    if markers:
        # 统计已是最新的股票数量
        up_to_date_count = 0
        total_marked = len(markers)
        
        for code, marker_data in markers.items():
            daily_date = marker_data.get('daily_latest_date')
            weekly_date = marker_data.get('weekly_latest_date')
            last_update_timestamp = marker_data.get('last_update_timestamp')
            
            # 使用智能判断函数
            daily_is_up_to_date = _is_data_up_to_date(code, daily_date, last_update_timestamp)
            weekly_is_up_to_date = _is_data_up_to_date(code, weekly_date, last_update_timestamp)
            
            # 如果日K线和周K线都已是最新，认为该股票已是最新
            if daily_is_up_to_date and weekly_is_up_to_date:
                up_to_date_count += 1
        
        # 如果超过90%的股票已是最新，提示用户不需要更新
        if total_marked > 0:
            up_to_date_pct = (up_to_date_count / total_marked) * 100
            # ✅ 降低阈值到85%，因为通达信导入的数据没有时间戳，但日期是最新的
            if up_to_date_pct >= 85:
                return jsonify({
                    'success': False,
                    'message': f'数据已是最新！{up_to_date_count}/{total_marked} ({up_to_date_pct:.1f}%) 只股票数据已是最新，无需更新',
                    'up_to_date_count': up_to_date_count,
                    'total_marked': total_marked,
                    'up_to_date_pct': round(up_to_date_pct, 1)
                })
    
    # 重置状态
    data_update_stop_flag = False
    data_update_progress = {
        'status': 'running',
        'processed': 0,
        'total': 0,
        'percentage': 0,
        'current_stock': '',
        'message': '正在启动...',
        'updated_count': 0,
        'failed_count': 0,
        'start_time': None
    }
    
    # 启动后台线程
    update_thread = threading.Thread(target=_data_update_worker)
    update_thread.daemon = True
    update_thread.start()
    
    return jsonify({'success': True, 'message': '数据更新已启动'})

@app.route('/api/get_data_update_timestamp', methods=['GET'])
@require_login
def get_data_update_timestamp():
    """获取数据更新时间戳"""
    try:
        timestamp_data = _load_data_update_timestamp()
        should_skip, skip_reason = _should_skip_update_after_trading_hours()
        
        return jsonify({
            'success': True,
            'last_update_time': timestamp_data.get('last_update_time', ''),
            'last_update_date': timestamp_data.get('last_update_date', ''),
            'should_skip': should_skip,
            'message': skip_reason
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'获取时间戳失败: {str(e)}',
            'should_skip': False
        }), 500

@app.route('/api/get_data_update_progress', methods=['GET'])
@require_login
def get_data_update_progress():
    """获取数据更新进度"""
    global data_update_progress
    import time
    
    # ✅ 如果正在运行或融合中，实时计算已用时间
    if data_update_progress.get('status') in ['running', 'merging'] and 'start_time' in data_update_progress:
        elapsed = time.time() - data_update_progress['start_time']
        data_update_progress['elapsed_time'] = elapsed
    
    return jsonify(data_update_progress)

@app.route('/api/stop_data_update', methods=['POST'])
@require_login
def stop_data_update():
    """停止数据更新"""
    global data_update_stop_flag
    data_update_stop_flag = True
    return jsonify({'success': True, 'message': '已发送停止请求'})

@app.route('/api/check_data_freshness', methods=['POST'])
@require_login
def api_check_data_freshness():
    """检查数据新鲜度"""
    # silent=True：允许空/非JSON body，避免直接抛 400 Bad Request
    data = request.get_json(silent=True) or {}
    target_date = data.get('scan_date', None)
    # ✅ 最早加载 markers，避免任意分支使用未定义变量导致 500
    markers = _load_data_markers()
    
    # ✅ 先检查是否应该跳过更新（交易日15:00后已更新过）
    should_skip, skip_reason = _should_skip_update_after_trading_hours()
    print(f"[api_check_data_freshness] _should_skip_update_after_trading_hours() 返回: should_skip={should_skip}, skip_reason={skip_reason}")
    if should_skip:
        print(f"[api_check_data_freshness] ✅ 返回 should_skip=True（通过 _should_skip_update_after_trading_hours）")
        return jsonify({
            'success': True,
            'fresh': True,  # 标记为已是最新，避免触发更新
            'message': skip_reason or '交易已结束，今日已更新，无需更新',
            'skip_reason': 'trading_hours_ended',
            'should_skip': True
        })
    
    # ✅ 额外检查：如果当前时间已经是15:00后，且没有时间戳文件，也阻止自动更新
    # （因为交易已结束，不应该自动更新）
    from datetime import datetime, timezone, timedelta
    utc_now = datetime.now(timezone.utc)
    beijing_tz = timezone(timedelta(hours=8))
    beijing_now = utc_now.astimezone(beijing_tz)
    print(f"[api_check_data_freshness] 当前北京时间: {beijing_now.strftime('%Y-%m-%d %H:%M:%S')}, 小时: {beijing_now.hour}")
    if beijing_now.hour >= 15:
        timestamp_data = _load_data_update_timestamp()
        print(f"[api_check_data_freshness] 时间戳数据: {timestamp_data}")
        if not timestamp_data or not timestamp_data.get('last_update_date'):
            # 15:00后且没有时间戳记录，阻止自动更新
            print(f"[api_check_data_freshness] ✅ 15:00后且没有时间戳，返回 should_skip=True")
            return jsonify({
                'success': True,
                'fresh': True,
                'message': f'当前时间 {beijing_now.strftime("%H:%M")}，交易已结束。如需更新数据，请手动点击"更新数据"按钮',
                'skip_reason': 'trading_hours_ended_no_timestamp',
                'should_skip': True
            })
        else:
            print(f"[api_check_data_freshness] 有时间戳: {timestamp_data.get('last_update_date')}")
    
    # ✅ 优先使用标记文件快速检查
    from datetime import datetime
    today = datetime.now()
    today_str = today.strftime('%Y-%m-%d')
    # ✅ 必须先加载 markers，否则会 NameError
    markers = _load_data_markers()
    
    if markers:
        # 统计已是最新的股票数量
        up_to_date_count = 0
        total_marked = len(markers)
        outdated_count = 0
        
        for code, marker_data in markers.items():
            daily_date = marker_data.get('daily_latest_date')
            weekly_date = marker_data.get('weekly_latest_date')
            last_update_timestamp = marker_data.get('last_update_timestamp')
            
            # 使用智能判断函数
            daily_is_up_to_date = _is_data_up_to_date(code, daily_date, last_update_timestamp)
            weekly_is_up_to_date = _is_data_up_to_date(code, weekly_date, last_update_timestamp)
            
            # 如果日K线和周K线都已是最新，认为该股票已是最新
            if daily_is_up_to_date and weekly_is_up_to_date:
                up_to_date_count += 1
            else:
                outdated_count += 1
        
        # 如果超过85%的股票已是最新，认为数据已是最新
        if total_marked > 0:
            up_to_date_pct = (up_to_date_count / total_marked) * 100
            latest_date = today_str  # 使用今天作为最新日期
            
            # ✅ 降低阈值到85%，因为通达信导入的数据没有时间戳，但日期是最新的
            if up_to_date_pct >= 85:
                # ✅ 即使数据是最新的，如果是15:00后，也要标记 should_skip
                should_skip_after_check = False
                skip_reason_after_check = None
                if beijing_now.hour >= 15:
                    timestamp_data_after = _load_data_update_timestamp()
                    if not timestamp_data_after or not timestamp_data_after.get('last_update_date'):
                        should_skip_after_check = True
                        skip_reason_after_check = f'当前时间 {beijing_now.strftime("%H:%M")}，交易已结束'
                
                return jsonify({
                    'fresh': True,
                    'outdated_count': outdated_count,
                    'total': total_marked,
                    'latest_data_date': latest_date,
                    'target_date': target_date or today_str,
                    'message': f'数据已是最新（{up_to_date_count}/{total_marked}，{up_to_date_pct:.1f}%已是最新）',
                    'up_to_date_count': up_to_date_count,
                    'up_to_date_pct': round(up_to_date_pct, 1),
                    'should_skip': should_skip_after_check,  # ✅ 添加 should_skip 字段
                    'skip_reason': skip_reason_after_check  # ✅ 添加 skip_reason 字段
                })
    
    # 如果标记文件检查不通过，使用原来的CSV文件检查方法
    # ✅ 但在调用前，再次检查时间（确保15:00后不会触发更新）
    # 注意：这里的时间检查已经在前面执行过了，但为了保险，再次检查
    print(f"[api_check_data_freshness] 标记文件检查不通过，准备调用 check_data_freshness()，当前时间: {beijing_now.strftime('%Y-%m-%d %H:%M:%S')}, 小时: {beijing_now.hour}")
    if beijing_now.hour >= 15:
        timestamp_data_final = _load_data_update_timestamp()
        print(f"[api_check_data_freshness] 时间戳数据: {timestamp_data_final}")
        if not timestamp_data_final or not timestamp_data_final.get('last_update_date'):
            # 15:00后且没有时间戳记录，阻止更新
            print(f"[api_check_data_freshness] ✅ 标记文件检查不通过，但15:00后且没有时间戳，返回 should_skip=True")
            return jsonify({
                'success': True,
                'fresh': True,  # 标记为已是最新，避免触发更新
                'message': f'当前时间 {beijing_now.strftime("%H:%M")}，交易已结束。如需更新数据，请手动点击"更新数据"按钮',
                'skip_reason': 'trading_hours_ended_no_timestamp',
                'should_skip': True
            })
    
    print(f"[api_check_data_freshness] 调用 check_data_freshness() 函数")
    result = check_data_freshness(target_date)
    print(f"[api_check_data_freshness] check_data_freshness() 返回结果: fresh={result.get('fresh')}, message={result.get('message')}")
    # ✅ 确保返回结果包含 should_skip 字段
    if isinstance(result, dict):
        # 如果15:00后且没有时间戳，强制设置 should_skip
        if beijing_now.hour >= 15:
            timestamp_data_result = _load_data_update_timestamp()
            if not timestamp_data_result or not timestamp_data_result.get('last_update_date'):
                print(f"[api_check_data_freshness] ✅ 强制设置 should_skip=True（15:00后且没有时间戳）")
                result['should_skip'] = True
                result['skip_reason'] = 'trading_hours_ended_no_timestamp'
                result['fresh'] = True  # 强制标记为已是最新
                result['message'] = f'当前时间 {beijing_now.strftime("%H:%M")}，交易已结束。如需更新数据，请手动点击"更新数据"按钮'
        else:
            result['should_skip'] = result.get('should_skip', False)
    print(f"[api_check_data_freshness] 最终返回结果: should_skip={result.get('should_skip') if isinstance(result, dict) else 'N/A'}")
    return jsonify(result)

@app.route('/api/update_and_scan', methods=['POST'])
@require_login
def api_update_and_scan():
    """先更新数据再扫描（如果需要）"""
    global data_update_progress, data_update_stop_flag
    
    data = request.get_json(silent=True) or {}
    scan_date = data.get('scan_date', None)
    
    # 检查数据新鲜度
    freshness = check_data_freshness(scan_date)
    
    if freshness['fresh']:
        # 数据足够新，直接返回可以扫描
        return jsonify({
            'success': True,
            'need_update': False,
            'message': '数据已是最新，可以开始扫描',
            'freshness': freshness
        })
    
    # 数据需要更新
    if data_update_progress['status'] == 'running':
        return jsonify({
            'success': True,
            'need_update': True,
            'already_running': True,
            'message': '数据更新正在进行中，请等待完成后扫描',
            'freshness': freshness
        })
    
    # 启动数据更新
    data_update_stop_flag = False
    data_update_progress = {
        'status': 'running',
        'processed': 0,
        'total': 0,
        'percentage': 0,
        'current_stock': '',
        'message': '准备更新数据...',
        'updated_count': 0,
        'failed_count': 0,
        'start_time': None
    }
    
    import threading
    update_thread = threading.Thread(target=_data_update_worker)
    update_thread.daemon = True
    update_thread.start()
    
    return jsonify({
        'success': True,
        'need_update': True,
        'already_running': False,
        'message': f'数据需要更新（{freshness["outdated_count"]}/{freshness["total"]}只过期），已启动更新任务',
        'freshness': freshness
    })

@app.route('/api/check_login', methods=['GET'])
def api_check_login():
    """检查登录状态API"""
    try:
        if is_logged_in():
            user = get_current_user()
            return jsonify({
                'success': True,
                'logged_in': True,
                'user': user
            })
        else:
            return jsonify({
                'success': True,
                'logged_in': False
            })
    except Exception as e:
        return jsonify({
            'success': False,
            'logged_in': False,
            'error': str(e)
        }), 500

@app.route('/api/version', methods=['GET'])
def api_version():
    """获取版本信息API"""
    try:
        import subprocess
        import os
        
        # 尝试获取 Git commit SHA
        version_info = {
            'success': True,
            'environment': 'vercel' if is_vercel else 'local',
            'commit_sha': 'unknown',
            'commit_short': 'unknown',
            'commit_message': 'unknown',
            'commit_date': 'unknown'
        }
        
        try:
            # 方法1: 从 Vercel 环境变量获取（优先，Vercel 自动提供）
            vercel_commit_sha = os.environ.get('VERCEL_GIT_COMMIT_SHA')
            if vercel_commit_sha:
                version_info['commit_sha'] = vercel_commit_sha
                version_info['commit_short'] = vercel_commit_sha[:7]
                
                # Vercel 还可能提供其他 Git 信息
                vercel_git_commit_message = os.environ.get('VERCEL_GIT_COMMIT_MESSAGE', '')
                if vercel_git_commit_message:
                    version_info['commit_message'] = vercel_git_commit_message
                
                vercel_git_commit_ref = os.environ.get('VERCEL_GIT_COMMIT_REF', '')
                if vercel_git_commit_ref:
                    version_info['branch'] = vercel_git_commit_ref
            
            # 方法2: 从 .git-version 文件读取（如果存在，作为备用）
            if version_info['commit_sha'] == 'unknown':
                version_file = os.path.join(os.path.dirname(__file__), '.git-version')
                if os.path.exists(version_file):
                    with open(version_file, 'r') as f:
                        commit_sha = f.read().strip()
                        if commit_sha and commit_sha != 'unknown':
                            version_info['commit_sha'] = commit_sha
                            version_info['commit_short'] = commit_sha[:7]
            
            # 方法3: 直接从 Git 获取（本地环境，如果前两种方法都失败）
            if version_info['commit_sha'] == 'unknown' and not is_vercel:
                try:
                    result = subprocess.run(
                        ['git', 'rev-parse', 'HEAD'],
                        capture_output=True,
                        text=True,
                        cwd=os.path.dirname(__file__),
                        timeout=2
                    )
                    if result.returncode == 0:
                        commit_sha = result.stdout.strip()
                        version_info['commit_sha'] = commit_sha
                        version_info['commit_short'] = commit_sha[:7]
                    
                    # 获取 commit 信息
                    result = subprocess.run(
                        ['git', 'log', '-1', '--pretty=format:%s|%ci'],
                        capture_output=True,
                        text=True,
                        cwd=os.path.dirname(__file__),
                        timeout=2
                    )
                    if result.returncode == 0:
                        parts = result.stdout.strip().split('|')
                        if len(parts) == 2:
                            version_info['commit_message'] = parts[0]
                            version_info['commit_date'] = parts[1]
                except Exception:
                    pass
        except Exception as e:
            print(f"获取版本信息失败: {e}")
        
        return jsonify(version_info)
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/health', methods=['GET'])
def api_health():
    """健康检查API"""
    try:
        return jsonify({
            'success': True,
            'status': 'ok',
            'environment': 'vercel' if is_vercel else 'local',
            'analyzer_initialized': analyzer is not None
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'status': 'error',
            'error': str(e)
        }), 500


@app.route('/api/cache_debug', methods=['GET'])
def cache_debug():
    """免登录：查看 Vercel 上缓存路径与实际目录状态；若 /tmp/cache 不存在则在此请求内拉取一次"""
    try:
        import os
        has_url = bool(os.environ.get('STOCK_DATA_URL'))
        local_dir = os.environ.get('LOCAL_CACHE_DIR') or '(not set)'
        tmp_cache = '/tmp/cache'
        tmp_ok = os.path.exists(tmp_cache)
        fetch_attempted = False
        fetch_ok = None
        fetch_error = None
        # 若在 Vercel、有 URL、且 /tmp/cache 不存在，则在本请求内拉取（可能耗时 1–2 分钟）
        if is_vercel and has_url and not tmp_ok:
            try:
                import fetch_github_cache as _fetch_mod
                fetch_attempted = True
                fetch_ok = _fetch_mod.fetch_github_cache(skip_if_exists=False, root_dir='/tmp', timeout=120)
                tmp_ok = os.path.exists(tmp_cache)
                if not fetch_ok:
                    fetch_error = getattr(_fetch_mod, '_last_error', None)
                    if not fetch_error:
                        fetch_error = 'fetch_github_cache 返回 False（可能为请求超时、网络错误或解压失败）'
            except Exception as fe:
                import traceback
                fetch_attempted = True
                fetch_ok = False
                fetch_error = str(fe)
                print("[cache_debug] fetch_github_cache 失败:", fetch_error)
                traceback.print_exc()
        entries = []
        stock_list_ok = False
        weekly_ok = False
        daily_ok = False
        if tmp_ok:
            try:
                entries = os.listdir(tmp_cache)[:30]
            except Exception:
                entries = ['(listdir failed)']
            stock_list_ok = os.path.exists(os.path.join(tmp_cache, 'stock_list_all.json'))
            weekly_ok = os.path.exists(os.path.join(tmp_cache, 'weekly_kline'))
            daily_ok = os.path.exists(os.path.join(tmp_cache, 'daily_kline'))
        # 若 /tmp/cache 已存在但本次未拉取（例如 before_request 已拉取），推断 fetch_ok=True
        if tmp_ok and not fetch_attempted and fetch_ok is None:
            fetch_ok = True
        resp = {
            'success': True,
            'vercel': is_vercel,
            'has_stock_data_url': has_url,
            'local_cache_dir': local_dir,
            'tmp_cache_exists': tmp_ok,
            'tmp_cache_entries_sample': entries,
            'tmp_has_stock_list': stock_list_ok,
            'tmp_has_weekly_kline': weekly_ok,
            'tmp_has_daily_kline': daily_ok,
            'fetch_attempted': fetch_attempted,
            'fetch_ok': fetch_ok,
            'fetch_error': fetch_error,
        }
        if is_vercel and tmp_ok:
            resp['instance_note'] = (
                'Vercel 每个实例有独立 /tmp。若扫描仍报缓存不存在，多为命中其他实例；'
                '请先访问 /api/cache_debug 完成后再扫描，或重试扫描。'
            )
        return jsonify(resp)
    except Exception as e:
        import traceback
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500


@app.route('/api/check_cache_status', methods=['GET'])
@require_login
def check_cache_status():
    """检查股票列表缓存状态API。免费版优先走轻量路径（仅查文件），避免 init_analyzer 冷启动导致 504。"""
    try:
        # 轻量快速路径：仅根据 stock_list_all.json 是否存在且非空判断，不调用 init_analyzer，降低免费版 10s 超时概率
        cache_dir = os.environ.get('LOCAL_CACHE_DIR') or os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cache')
        stock_list_path = os.path.join(cache_dir, 'stock_list_all.json')
        if os.path.exists(stock_list_path):
            try:
                with open(stock_list_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if isinstance(data, list) and len(data) > 0:
                    return jsonify({
                        'success': True,
                        'cache_exists': True,
                        'cached_stock_count': len(data),
                        'message': f'缓存存在，股票数: {len(data)} 只',
                        'source': 'fast_path'
                    }), 200
            except Exception:
                pass  # 解析失败则走下面的完整逻辑
        # 完整路径：需要分析器与 fetcher（可能触发 init_analyzer 冷启动）
        try:
            init_analyzer()
        except Exception as init_error:
            import traceback
            error_detail = traceback.format_exc()
            print(f"[check_cache_status] ❌ 初始化分析器失败: {error_detail}")
            return jsonify({
                'success': False,
                'message': f'初始化分析器失败: {str(init_error)}',
                'cache_exists': False,
                'cached_stock_count': 0,
                'error_type': 'init_error',
                'error_detail': error_detail
            }), 500
        
        # 检查分析器是否初始化成功
        if analyzer is None or analyzer.fetcher is None:
            return jsonify({
                'success': False,
                'message': '分析器未初始化或初始化失败',
                'cache_exists': False,
                'cached_stock_count': 0,
                'error_type': 'analyzer_not_initialized'
            }), 500
        
        # 检测缓存是否存在
        cache_exists = False
        cached_stock_count = 0
        try:
            # 不检查缓存年龄，只检查是否存在
            cached_stocks = analyzer.fetcher._get_stock_list_from_cache(check_age=False)
            if cached_stocks is not None and len(cached_stocks) > 0:
                cache_exists = True
                cached_stock_count = len(cached_stocks)
                print(f"[check_cache_status] ✅ 缓存存在，股票数: {cached_stock_count} 只")
            else:
                print(f"[check_cache_status] ⚠️ 缓存不存在或为空")
                # ✅ 如果缓存不存在，尝试从K线文件列表生成
                if not cache_exists:
                    print(f"[check_cache_status] 🔄 尝试从K线文件列表生成股票列表...")
                    try:
                        from generate_stock_list_from_files import generate_stock_list_from_kline_files
                        if generate_stock_list_from_kline_files():
                            # 重新检查缓存
                            cached_stocks = analyzer.fetcher._get_stock_list_from_cache(check_age=False)
                            if cached_stocks is not None and len(cached_stocks) > 0:
                                cache_exists = True
                                cached_stock_count = len(cached_stocks)
                                print(f"[check_cache_status] ✅ 已从K线文件生成股票列表，股票数: {cached_stock_count} 只")
                    except Exception as gen_error:
                        print(f"[check_cache_status] ⚠️ 生成股票列表失败: {gen_error}")
        except Exception as e:
            import traceback
            error_detail = traceback.format_exc()
            print(f"[check_cache_status] ⚠️ 检测缓存时出错: {e}")
            print(f"[check_cache_status] 错误详情: {error_detail}")
        
        return jsonify({
            'success': True,
            'cache_exists': cache_exists,
            'cached_stock_count': cached_stock_count,
            'message': f'缓存{"存在" if cache_exists else "不存在"}，股票数: {cached_stock_count} 只'
        }), 200
        
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"[check_cache_status] ❌ 错误: {error_detail}")
        return jsonify({
            'success': False,
            'message': f'检查缓存状态失败: {str(e)}',
            'cache_exists': False,
            'cached_stock_count': 0
        }), 500


@app.route('/api/add_stock', methods=['POST'])
@require_login
def add_stock():
    """添加大牛股API"""
    try:
        init_analyzer()  # 确保分析器已初始化
        data = request.get_json(silent=True)
        if not data:
            return jsonify({
                'success': False,
                'message': '请求数据为空'
            }), 400
        
        # 安全地获取和清理数据
        stock_code = (data.get('code') or '').strip()
        stock_name_raw = data.get('name')
        stock_name = stock_name_raw.strip() if stock_name_raw else None
        
        if not stock_code:
            return jsonify({
                'success': False,
                'message': '股票代码不能为空'
            }), 400
        
        # 添加股票
        result = analyzer.add_bull_stock(stock_code, stock_name)
        
        return jsonify(result)
        
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"添加股票错误: {error_detail}")
        return jsonify({
            'success': False,
            'message': f'服务器错误: {str(e)}'
        }), 500


@app.route('/api/user_info')
@require_login
def get_user_info():
    """获取当前用户信息（包括等级）- 优化版本（快速响应）"""
    try:
        user = get_current_user()
        if not user:
            return jsonify({
                'success': False,
                'message': '未登录'
            }), 401
        
        # ✅ 快速返回基本用户信息（不等待复杂的扫描限制检查）
        is_premium = user.get('is_vip', False) or user.get('is_premium', False)
        tier = get_user_tier()
        
        # ✅ 简化响应，移除复杂的扫描限制检查（这些可以在需要时单独调用）
        return jsonify({
            'success': True,
            'user': {
                'username': user.get('username', 'unknown'),
                'email': user.get('email', ''),
                'tier': tier,
                'is_premium': is_premium,
                'is_super': is_super_user(),
                'scan_config': get_scan_config(),
                'scan_restrictions': {
                    'can_scan_now': True,
                    'scan_time_error': None,
                    'can_view_now': True,
                    'view_time_error': None,
                    'can_scan_daily': True,
                    'daily_error': None,
                    'today_scan_count': 0,
                    'current_time': ''
                }
            }
        })
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"[get_user_info] ❌ 获取用户信息错误: {error_detail}")
        # 即使出错，也尝试返回基本用户信息
        try:
            user = get_current_user()
            if user:
                tier = get_user_tier()
                return jsonify({
                    'success': True,
                    'user': {
                        'username': user.get('username', 'unknown'),
                        'email': user.get('email', ''),
                        'tier': tier,
                        'is_premium': user.get('is_vip', False) or user.get('is_premium', False),
                        'is_super': is_super_user(),
                        'scan_config': {},
                        'scan_restrictions': {
                            'can_scan_now': True,
                            'scan_time_error': None,
                            'can_view_now': True,
                            'view_time_error': None,
                            'can_scan_daily': True,
                            'daily_error': None,
                            'today_scan_count': 0,
                            'current_time': ''
                        }
                    }
                })
        except Exception as fallback_error:
            print(f"[get_user_info] ❌ 备用方案也失败: {fallback_error}")
        
        return jsonify({
            'success': False,
            'message': f'服务器错误: {str(e)}'
        }), 500

@app.route('/cs')
@require_login
def admin_page():
    """管理员页面（客服页面）"""
    return render_template('admin.html')

@app.route('/api/admin/users')
@require_login
def admin_get_users():
    """获取所有用户列表（管理员）"""
    try:
        if is_vercel:
            from user_auth_vercel import load_users
        else:
            from user_auth import load_users
        
        users = load_users()
        
        # 调试：打印用户数据
        print(f"[admin_get_users] 当前用户数: {len(users)}")
        if users:
            print(f"[admin_get_users] 用户列表: {list(users.keys())}")
            for username, user_data in users.items():
                print(f"  - {username}: VIP={user_data.get('is_vip', False)}, Email={user_data.get('email', 'N/A')}")
        
        # 转换为列表格式，隐藏敏感信息
        users_list = []
        for username, user_data in users.items():
            users_list.append({
                'username': username,
                'email': user_data.get('email', ''),
                'is_vip': user_data.get('is_vip', False),
                'created_at': user_data.get('created_at', ''),
                'last_login': user_data.get('last_login', ''),
                'invite_code': user_data.get('invite_code', ''),
                'is_active': user_data.get('is_active', True)
            })
        
        return jsonify({
            'success': True,
            'users': users_list,
            'total': len(users_list)
        })
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"获取用户列表错误: {error_detail}")
        return jsonify({
            'success': False,
            'message': f'服务器错误: {str(e)}'
        }), 500

@app.route('/api/admin/create_super_user', methods=['POST'])
def admin_create_super_user():
    """创建或更新超级用户（需要密钥验证）"""
    try:
        data = request.get_json(silent=True) or {}
        
        # 验证密钥（从环境变量获取，如果没有设置则使用默认密钥）
        secret = os.environ.get('SUPER_USER_SECRET', 'create_super_user_2024')
        provided_secret = data.get('secret')
        
        if provided_secret != secret:
            return jsonify({
                'success': False,
                'message': '密钥验证失败'
            }), 403
        
        # 获取用户信息（默认值）
        username = data.get('username', 'super')
        password = data.get('password', 'superzwj')
        email = data.get('email', 'super@admin.com')
        
        # 加载用户数据
        if is_vercel or is_render or has_redis:
            from user_auth_vercel import load_users, save_users, hash_password
        else:
            from user_auth import load_users, save_users, hash_password
        
        users = load_users()
        
        # 检查用户是否已存在
        if username in users:
            # 更新现有用户
            users[username]['password'] = hash_password(password)
            users[username]['is_vip'] = True
            users[username]['is_super'] = True
            users[username]['is_active'] = True
            users[username]['email'] = email
            users[username]['updated_at'] = datetime.now().isoformat()
            action = '更新'
        else:
            # 创建新用户
            users[username] = {
                'username': username,
                'email': email,
                'password': hash_password(password),
                'created_at': datetime.now().isoformat(),
                'last_login': None,
                'invite_code': 'ADMIN_CREATED',
                'is_active': True,
                'is_vip': True,
                'is_super': True,
                'is_test_user': False
            }
            action = '创建'
        
        # 保存用户数据
        save_users(users)
        
        print(f"✅ {action}超级用户成功: {username}")
        
        return jsonify({
            'success': True,
            'message': f'超级用户已{action}成功',
            'user': {
                'username': username,
                'email': email,
                'is_vip': True,
                'is_super': True
            }
        })
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"创建超级用户错误: {error_detail}")
        return jsonify({
            'success': False,
            'message': f'服务器错误: {str(e)}'
        }), 500

@app.route('/api/admin/set_vip', methods=['POST'])
@require_login
def admin_set_vip():
    """管理员设置用户VIP状态（手动收费）"""
    try:
        # 检查是否为管理员（可以根据需要添加管理员判断）
        user = get_current_user()
        if not user:
            return jsonify({
                'success': False,
                'message': '未登录'
            }), 401
        
        data = request.get_json(silent=True) or {}
        target_username = data.get('username')
        is_vip = data.get('is_vip', False)
        
        if not target_username:
            return jsonify({
                'success': False,
                'message': '缺少用户名参数'
            }), 400
        
        # 加载用户数据
        if is_vercel:
            from user_auth_vercel import load_users, save_users
        else:
            from user_auth import load_users, save_users
        
        users = load_users()
        
        if target_username not in users:
            return jsonify({
                'success': False,
                'message': '用户不存在'
            }), 404
        
        # 更新VIP状态
        users[target_username]['is_vip'] = bool(is_vip)
        if is_vip:
            users[target_username]['vip_set_at'] = datetime.now().isoformat()
        
        if is_vercel:
            from user_auth_vercel import save_users
        else:
            from user_auth import save_users
        
        save_users(users)
        
        return jsonify({
            'success': True,
            'message': f'已{"设置" if is_vip else "取消"}用户 {target_username} 的VIP状态',
            'user': {
                'username': target_username,
                'is_vip': is_vip
            }
        })
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"设置VIP状态错误: {error_detail}")
        return jsonify({
            'success': False,
            'message': f'服务器错误: {str(e)}'
        }), 500

@app.route('/api/vip/apply', methods=['POST'])
@require_login
def vip_apply():
    """提交VIP升级申请"""
    try:
        user = get_current_user()
        if not user:
            return jsonify({
                'success': False,
                'message': '未登录'
            }), 401
        
        # 检查是否已经是VIP
        if is_premium_user() or is_super_user():
            return jsonify({
                'success': False,
                'message': '您已经是VIP会员，无需再次申请'
            }), 400
        
        data = request.get_json(silent=True) or {}
        plan = data.get('plan', 'monthly')  # 'monthly' 或 'yearly'
        contact = data.get('contact', '').strip()
        note = data.get('note', '').strip()
        
        if plan not in ['monthly', 'yearly']:
            return jsonify({
                'success': False,
                'message': '无效的套餐类型'
            }), 400
        
        if not contact:
            return jsonify({
                'success': False,
                'message': '请输入联系方式（微信/QQ/手机号）'
            }), 400
        
        # 导入VIP申请存储模块
        try:
            from vip_upgrade_store import save_vip_application, get_user_application
        except ImportError:
            # 如果导入失败，尝试使用本地版本
            import vip_upgrade_store
            save_vip_application = vip_upgrade_store.save_vip_application
            get_user_application = vip_upgrade_store.get_user_application
        
        # 获取用户邮箱
        if is_vercel:
            from user_auth_vercel import load_users
        else:
            from user_auth import load_users
        
        users = load_users()
        user_email = users.get(user['username'], {}).get('email', '')
        
        # 保存申请
        success = save_vip_application(
            username=user['username'],
            email=user_email,
            plan=plan,
            contact=contact,
            note=note
        )
        
        if success:
            return jsonify({
                'success': True,
                'message': 'VIP升级申请已提交，我们会在24小时内处理并联系您'
            })
        else:
            return jsonify({
                'success': False,
                'message': '提交申请失败，请稍后重试'
            }), 500
            
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"提交VIP申请错误: {error_detail}")
        return jsonify({
            'success': False,
            'message': f'服务器错误: {str(e)}'
        }), 500

@app.route('/api/vip/check_application', methods=['GET'])
@require_login
def vip_check_application():
    """检查用户的VIP申请状态"""
    try:
        user = get_current_user()
        if not user:
            return jsonify({
                'success': False,
                'message': '未登录'
            }), 401
        
        try:
            from vip_upgrade_store import get_user_application
        except ImportError:
            import vip_upgrade_store
            get_user_application = vip_upgrade_store.get_user_application
        
        application = get_user_application(user['username'])
        
        if application:
            return jsonify({
                'success': True,
                'has_application': True,
                'application': {
                    'status': application.get('status', 'pending'),
                    'plan': application.get('plan'),
                    'plan_name': application.get('plan_name'),
                    'amount': application.get('amount'),
                    'created_at': application.get('created_at')
                }
            })
        else:
            return jsonify({
                'success': True,
                'has_application': False
            })
            
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"检查VIP申请状态错误: {error_detail}")
        return jsonify({
            'success': False,
            'message': f'服务器错误: {str(e)}'
        }), 500

@app.route('/api/admin/vip_applications', methods=['GET'])
@require_login
def admin_get_vip_applications():
    """获取所有VIP升级申请列表（管理员）"""
    try:
        user = get_current_user()
        if not user:
            return jsonify({
                'success': False,
                'message': '未登录'
            }), 401
        
        # 检查是否为管理员（可以根据需要添加管理员判断）
        # 暂时允许所有登录用户查看（实际应该只允许管理员）
        
        status = request.args.get('status')  # 可选：'pending', 'approved', 'rejected', 'completed'
        
        try:
            from vip_upgrade_store import get_vip_applications
        except ImportError:
            import vip_upgrade_store
            get_vip_applications = vip_upgrade_store.get_vip_applications
        
        applications = get_vip_applications(status=status)
        
        return jsonify({
            'success': True,
            'applications': applications,
            'total': len(applications)
        })
        
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"获取VIP申请列表错误: {error_detail}")
        return jsonify({
            'success': False,
            'message': f'服务器错误: {str(e)}'
        }), 500

@app.route('/api/admin/vip_application/<application_id>/status', methods=['POST'])
@require_login
def admin_update_application_status(application_id):
    """更新VIP申请状态（管理员）"""
    try:
        user = get_current_user()
        if not user:
            return jsonify({
                'success': False,
                'message': '未登录'
            }), 401
        
        data = request.get_json(silent=True) or {}
        status = data.get('status')  # 'pending', 'approved', 'rejected', 'completed'
        
        if status not in ['pending', 'approved', 'rejected', 'completed']:
            return jsonify({
                'success': False,
                'message': '无效的状态值'
            }), 400
        
        try:
            from vip_upgrade_store import update_application_status
        except ImportError:
            import vip_upgrade_store
            update_application_status = vip_upgrade_store.update_application_status
        
        success = update_application_status(
            application_id=application_id,
            status=status,
            processed_by=user['username']
        )
        
        if success:
            # 如果状态是 'approved' 或 'completed'，自动设置用户为VIP
            if status in ['approved', 'completed']:
                try:
                    from vip_upgrade_store import get_vip_applications
                    applications = get_vip_applications()
                    application = next((app for app in applications if app.get('application_id') == application_id), None)
                    
                    if application:
                        target_username = application.get('username')
                        
                        # 设置用户为VIP
                        if is_vercel:
                            from user_auth_vercel import load_users, save_users
                        else:
                            from user_auth import load_users, save_users
                        
                        users = load_users()
                        if target_username in users:
                            users[target_username]['is_vip'] = True
                            users[target_username]['vip_set_at'] = datetime.now().isoformat()
                            save_users(users)
                            
                except Exception as e2:
                    print(f"自动设置VIP状态失败: {e2}")
            
            return jsonify({
                'success': True,
                'message': f'申请状态已更新为: {status}'
            })
        else:
            return jsonify({
                'success': False,
                'message': '更新申请状态失败'
            }), 500
            
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"更新VIP申请状态错误: {error_detail}")
        return jsonify({
            'success': False,
            'message': f'服务器错误: {str(e)}'
        }), 500

@app.route('/api/vip/payment_info', methods=['GET'])
def vip_payment_info():
    """获取VIP付费账号信息（支付宝/微信）"""
    try:
        # 从环境变量读取付款账号信息，如果没有则使用默认值
        alipay_account = os.environ.get('VIP_ALIPAY_ACCOUNT', '522168878@qq.com')  # 支付宝账号（默认值）
        wechat_account = os.environ.get('VIP_WECHAT_ACCOUNT', '')  # 微信账号
        
        # 如果环境变量为空，使用默认值
        if not alipay_account:
            alipay_account = '522168878@qq.com'
        
        return jsonify({
            'success': True,
            'alipay_account': alipay_account,
            'wechat_account': wechat_account if wechat_account else '请等待管理员配置'
        })
        
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"获取付款信息错误: {error_detail}")
        return jsonify({
            'success': False,
            'message': f'服务器错误: {str(e)}'
        }), 500

@app.route('/api/get_stocks', methods=['GET'])
@require_login
def get_stocks():
    """获取所有已添加的大牛股API"""
    try:
        init_analyzer()  # 确保分析器已初始化
        
        # 检查 analyzer 是否已初始化
        if analyzer is None:
            return jsonify({
                'success': True,
                'stocks': [],
                'count': 0
            })
        
        stocks = analyzer.get_bull_stocks()
        
        # 转换为可序列化的格式
        stocks_list = []
        for stock in stocks:
            try:
                # 处理添加时间字段
                add_time = stock.get('添加时间')
                if isinstance(add_time, datetime):
                    add_time_str = add_time.strftime('%Y-%m-%d %H:%M:%S')
                elif isinstance(add_time, str):
                    add_time_str = add_time
                else:
                    add_time_str = str(add_time) if add_time else ''
                
                stocks_list.append({
                    '代码': stock.get('代码', ''),
                    '名称': stock.get('名称', ''),
                    '添加时间': add_time_str,
                    '数据条数': stock.get('数据条数', 0)
                })
            except Exception as e:
                print(f"处理股票数据时出错: {stock} - {e}")
                continue
        
        return jsonify({
            'success': True,
            'stocks': stocks_list,
            'count': len(stocks_list)
        })
        
    except AttributeError as e:
        # analyzer 未初始化或方法不存在
        print(f"获取股票列表错误 (AttributeError): {e}")
        return jsonify({
            'success': True,
            'stocks': [],
            'count': 0
        })
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"获取股票列表错误: {error_detail}")
        return jsonify({
            'success': False,
            'message': f'服务器错误: {str(e)}',
            'error_detail': error_detail if is_vercel else None  # 仅在 Vercel 环境中返回详细错误
        }), 500


@app.route('/api/remove_stock', methods=['POST'])
@require_login
def remove_stock():
    init_analyzer()  # 确保分析器已初始化
    """移除大牛股API"""
    try:
        data = request.get_json(silent=True)
        if not data:
            return jsonify({
                'success': False,
                'message': '请求数据为空'
            }), 400
        
        # 安全地获取和清理数据
        stock_code = (data.get('code') or '').strip()
        
        if not stock_code:
            return jsonify({
                'success': False,
                'message': '股票代码不能为空'
            }), 400
        
        # 移除股票
        success = analyzer.remove_bull_stock(stock_code)
        
        return jsonify({
            'success': success,
            'message': f'已移除股票 {stock_code}' if success else f'未找到股票 {stock_code}'
        })
        
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"移除股票错误: {error_detail}")
        return jsonify({
            'success': False,
            'message': f'服务器错误: {str(e)}'
        }), 500


@app.route('/api/clear_stocks', methods=['POST'])
@require_login
def clear_stocks():
    """清空所有大牛股API"""
    try:
        analyzer.clear_bull_stocks()
        return jsonify({
            'success': True,
            'message': '已清空所有大牛股'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'服务器错误: {str(e)}'
        }), 500


@app.route('/api/analyze_stock', methods=['POST'])
@require_login
def analyze_stock():
    """分析单只大牛股API"""
    try:
        data = request.get_json(silent=True)
        if not data:
            return jsonify({
                'success': False,
                'message': '请求数据为空'
            }), 400
        
        stock_code = (data.get('code') or '').strip()
        
        if not stock_code:
            return jsonify({
                'success': False,
                'message': '股票代码不能为空'
            }), 400
        
        # 分析股票
        result = analyzer.analyze_bull_stock(stock_code)
        
        # 转换为可序列化的格式
        if result['success'] and result.get('interval'):
            interval = result['interval']
            result['interval'] = {
                '股票代码': interval.get('股票代码'),
                '起点日期': str(interval.get('起点日期', '')),
                '起点价格': float(interval.get('起点价格', 0)) if interval.get('起点价格') is not None else 0,
                '起点索引': int(interval.get('起点索引')) if interval.get('起点索引') is not None else None,
                '终点日期': str(interval.get('终点日期', '')),
                '终点价格': float(interval.get('终点价格', 0)) if interval.get('终点价格') is not None else 0,
                '终点索引': int(interval.get('终点索引')) if interval.get('终点索引') is not None else None,
                '涨幅': float(interval.get('涨幅', 0)) if interval.get('涨幅') is not None else 0,
                '翻倍倍数': float(interval.get('翻倍倍数', 0)) if interval.get('翻倍倍数') is not None else 0,
                '实际周数': int(interval.get('实际周数')) if interval.get('实际周数') is not None else None,
                '查找窗口周数': int(interval.get('查找窗口周数', 10)) if interval.get('查找窗口周数') is not None else 10
            }
        
        return jsonify(result)
        
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"分析股票错误: {error_detail}")
        return jsonify({
            'success': False,
            'message': f'服务器错误: {str(e)}'
        }), 500


@app.route('/api/analyze_all', methods=['POST'])
@require_login
def analyze_all():
    init_analyzer()  # 确保分析器已初始化
    """分析所有大牛股API"""
    try:
        # 分析所有股票
        result = analyzer.analyze_all_bull_stocks()
        
        # 转换为可序列化的格式
        if result.get('results'):
            for item in result['results']:
                analysis_result = item.get('分析结果', {})
                if analysis_result.get('success') and analysis_result.get('interval'):
                    interval = analysis_result['interval']
                    analysis_result['interval'] = {
                        '股票代码': interval.get('股票代码'),
                        '起点日期': str(interval.get('起点日期', '')),
                        '起点价格': float(interval.get('起点价格', 0)) if interval.get('起点价格') is not None else 0,
                        '起点索引': int(interval.get('起点索引')) if interval.get('起点索引') is not None else None,
                        '终点日期': str(interval.get('终点日期', '')),
                        '终点价格': float(interval.get('终点价格', 0)) if interval.get('终点价格') is not None else 0,
                        '终点索引': int(interval.get('终点索引')) if interval.get('终点索引') is not None else None,
                        '涨幅': float(interval.get('涨幅', 0)) if interval.get('涨幅') is not None else 0,
                        '翻倍倍数': float(interval.get('翻倍倍数', 0)) if interval.get('翻倍倍数') is not None else 0,
                        '周数': int(interval.get('周数')) if interval.get('周数') is not None else None,
                        '区间周数': int(interval.get('区间周数', 4)) if interval.get('区间周数') is not None else 4
                    }
        
        return jsonify(result)
        
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"分析所有股票错误: {error_detail}")
        return jsonify({
            'success': False,
            'message': f'服务器错误: {str(e)}'
        }), 500


@app.route('/api/analyze_stock_detail', methods=['POST'])
@require_login
def analyze_stock_detail():
    """个股深度分析API（VIP专享功能）"""
    try:
        # 获取用户信息和等级
        user = get_current_user()
        if not user:
            return jsonify({
                'success': False,
                'message': '请先登录'
            }), 401
        
        user_tier = get_user_tier()
        
        # 检查用户等级（仅VIP和超级用户可以使用深度分析）
        if user_tier != 'premium' and user_tier != 'super':
            is_super = user.get('is_super', False)
            if not is_super:
                return jsonify({
                    'success': False,
                    'message': '个股深度分析功能仅限VIP用户使用，请升级为VIP会员'
                }), 403
        
        data = request.get_json(silent=True) or {}
        stock_code = (data.get('stock_code') or '').strip()
        stock_name = data.get('stock_name', '').strip()
        buy_date = data.get('buy_date', '')
        buy_price = float(data.get('buy_price', 0))
        match_score = float(data.get('match_score', 0))
        
        if not stock_code:
            return jsonify({
                'success': False,
                'message': '股票代码不能为空'
            }), 400
        
        init_analyzer()
        
        if analyzer is None or not hasattr(analyzer, 'fetcher'):
            return jsonify({
                'success': False,
                'message': '分析器未初始化'
            }), 500
        
        # 获取股票的详细信息
        features = {}
        match_details = {}
        predictions = {}
        kline_data = None
        
        try:
            # 如果已训练特征模型，计算特征匹配详情
            if analyzer.trained_features and analyzer.trained_features.get('common_features'):
                common_features = analyzer.trained_features.get('common_features', {})
                
                # 获取股票周线数据
                weekly_df = analyzer.fetcher.get_weekly_kline(stock_code, weeks=100)
                if weekly_df is not None and len(weekly_df) >= 40:
                    # 找到买点日期对应的索引
                    buy_idx = None
                    if buy_date:
                        try:
                            buy_date_obj = pd.to_datetime(buy_date)
                            for i in range(len(weekly_df)):
                                date_col = weekly_df.iloc[i]['日期'] if '日期' in weekly_df.columns else weekly_df.index[i]
                                if isinstance(date_col, pd.Timestamp):
                                    if date_col >= buy_date_obj:
                                        buy_idx = i
                                        break
                                elif isinstance(date_col, str):
                                    if pd.to_datetime(date_col) >= buy_date_obj:
                                        buy_idx = i
                                        break
                        except Exception as e:
                            print(f"[analyze_stock_detail] 查找买点日期失败: {e}")
                            buy_idx = len(weekly_df) - 40
                    else:
                        buy_idx = len(weekly_df) - 40
                    
                    if buy_idx and buy_idx >= 40:
                        # 提取买点前的特征
                        features = analyzer.extract_features_at_start_point(
                            stock_code, buy_idx, lookback_weeks=40, weekly_df=weekly_df
                        )
                        
                        if features:
                            # 计算特征匹配详情
                            match_details_dict = analyzer._calculate_match_score(
                                features, common_features, analyzer.tolerance
                            )
                            
                            match_details = {
                                'total_match_score': match_details_dict.get('总匹配度', match_score),
                                'matched_features_count': match_details_dict.get('匹配特征数', 0),
                                'core_features_match': match_details_dict.get('核心特征匹配', {}),
                                'all_features_match': match_details_dict.get('所有特征匹配', {})
                            }
                            
                            # 计算涨跌幅预测
                            if buy_idx < len(weekly_df):
                                buy_price_actual = float(weekly_df.iloc[buy_idx]['收盘'])
                                
                                if buy_idx + 4 < len(weekly_df):
                                    price_4w = float(weekly_df.iloc[buy_idx + 4]['收盘'])
                                    gain_4w = (price_4w - buy_price_actual) / buy_price_actual * 100
                                    predictions['gain_4w'] = round(gain_4w, 2)
                                
                                if buy_idx + 10 < len(weekly_df):
                                    price_10w = float(weekly_df.iloc[buy_idx + 10]['收盘'])
                                    gain_10w = (price_10w - buy_price_actual) / buy_price_actual * 100
                                    predictions['gain_10w'] = round(gain_10w, 2)
                                    
                                    max_price_10w = float(weekly_df.iloc[buy_idx+1:buy_idx+11]['最高'].max())
                                    max_gain_10w = (max_price_10w - buy_price_actual) / buy_price_actual * 100
                                    predictions['max_gain_10w'] = round(max_gain_10w, 2)
                                
                                if buy_idx + 20 < len(weekly_df):
                                    price_20w = float(weekly_df.iloc[buy_idx + 20]['收盘'])
                                    gain_20w = (price_20w - buy_price_actual) / buy_price_actual * 100
                                    predictions['gain_20w'] = round(gain_20w, 2)
                                
                                stop_loss_price = buy_price_actual * 0.90
                                if 'MA20' in weekly_df.columns:
                                    ma20 = float(weekly_df.iloc[buy_idx]['MA20'])
                                    if ma20 > 0:
                                        stop_loss_price = min(stop_loss_price, ma20 * 0.95)
                                predictions['stop_loss_price'] = round(stop_loss_price, 2)
                                
                                if buy_idx + 1 < len(weekly_df):
                                    future_window = weekly_df.iloc[buy_idx+1:]
                                    if len(future_window) > 0:
                                        max_price_pos = future_window['最高'].values.argmax()
                                        max_price = float(future_window.iloc[max_price_pos]['最高'])
                                        max_date = future_window.iloc[max_price_pos]['日期']
                                        if isinstance(max_date, pd.Timestamp):
                                            max_date_str = max_date.strftime('%Y-%m-%d')
                                        else:
                                            max_date_str = str(max_date)
                                        predictions['best_sell_price'] = round(max_price, 2)
                                        predictions['best_sell_date'] = max_date_str
                                
                                # 获取K线数据
                                try:
                                    start_idx = max(0, buy_idx - 20)
                                    end_idx = min(len(weekly_df), buy_idx + 40)
                                    kline_window = weekly_df.iloc[start_idx:end_idx]
                                    
                                    dates = []
                                    values = []
                                    for i, row in kline_window.iterrows():
                                        date_col = row['日期'] if '日期' in row else row.index[0]
                                        if isinstance(date_col, pd.Timestamp):
                                            dates.append(date_col.strftime('%Y-%m-%d'))
                                        else:
                                            dates.append(str(date_col))
                                        
                                        open_price = float(row.get('开盘', 0))
                                        close_price = float(row.get('收盘', 0))
                                        high_price = float(row.get('最高', 0))
                                        low_price = float(row.get('最低', 0))
                                        values.append([open_price, close_price, low_price, high_price])
                                    
                                    kline_data = {
                                        'dates': dates,
                                        'values': values,
                                        'buy_point_idx': buy_idx - start_idx
                                    }
                                except Exception as e:
                                    print(f"[analyze_stock_detail] 获取K线数据失败: {e}")
        except Exception as e:
            import traceback
            error_detail = traceback.format_exc()
            print(f"[analyze_stock_detail] 获取股票详细信息失败: {error_detail}")
        
        # 获取股票名称
        if not stock_name:
            stock_name = analyzer._get_stock_name(stock_code) or stock_code
        
        # 构建返回数据
        result_data = {
            'stock_code': stock_code,
            'stock_name': stock_name,
            'match_score': match_score,
            'buy_date': buy_date,
            'buy_price': buy_price,
            'features': features,
            'match_details': match_details,
            'predictions': predictions,
            'kline_data': kline_data
        }
        
        return jsonify({
            'success': True,
            'message': '深度分析数据获取成功',
            'data': result_data
        })
        
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"[analyze_stock_detail] ❌ 深度分析失败: {error_detail}")
        return jsonify({
            'success': False,
            'message': f'深度分析失败: {str(e)}'
        }), 500


@app.route('/api/get_analysis/<stock_code>', methods=['GET'])
@require_login
def get_analysis(stock_code):
    """获取指定股票的分析结果API"""
    try:
        result = analyzer.get_analysis_result(stock_code)
        
        if result is None:
            return jsonify({
                'success': False,
                'message': f'股票 {stock_code} 尚未分析',
                'result': None
            })
        
        # 转换为可序列化的格式
        analysis_data = {
            'stock_info': result.get('stock_info'),
            'interval': result.get('interval'),
            'analyzed_at': result.get('analyzed_at').strftime('%Y-%m-%d %H:%M:%S') if result.get('analyzed_at') else None
        }
        
        if analysis_data['stock_info'] and '添加时间' in analysis_data['stock_info']:
            if isinstance(analysis_data['stock_info']['添加时间'], datetime):
                analysis_data['stock_info']['添加时间'] = analysis_data['stock_info']['添加时间'].strftime('%Y-%m-%d %H:%M:%S')
        
        return jsonify({
            'success': True,
            'result': analysis_data
        })
        
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"获取分析结果错误: {error_detail}")
        return jsonify({
            'success': False,
            'message': f'服务器错误: {str(e)}'
        }), 500


@app.route('/api/train_features', methods=['POST'])
@require_login
def train_features():
    init_analyzer()  # 确保分析器已初始化
    """训练特征模型API"""
    try:
        result = analyzer.train_features()
        
        # 转换为可序列化的格式
        if result.get('common_features'):
            common_features = {}
            for feature_name, stats in result['common_features'].items():
                common_features[feature_name] = {
                    '均值': float(stats['均值']),
                    '中位数': float(stats['中位数']),
                    '最小值': float(stats['最小值']),
                    '最大值': float(stats['最大值']),
                    '标准差': float(stats['标准差']),
                    '样本数': int(stats['样本数'])
                }
            result['common_features'] = common_features
        
        return jsonify(result)
        
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"训练特征错误: {error_detail}")
        return jsonify({
            'success': False,
            'message': f'服务器错误: {str(e)}'
        }), 500


@app.route('/api/get_progress', methods=['GET'])
@require_login
def get_progress():
    """获取当前进度API"""
    # 添加 CORS 和缓存控制头
    response_headers = {
        'Cache-Control': 'no-cache, no-store, must-revalidate',
        'Pragma': 'no-cache',
        'Expires': '0'
    }
    
    # 在 Vercel serverless 环境中，从 Redis 读取进度（Render环境也使用 scan_progress_store）
    if is_vercel or is_render:
        scan_id = request.args.get('scan_id')
        
        # 获取当前用户信息
        current_user = get_current_user()
        username = current_user.get('username', 'anonymous') if current_user else 'anonymous'
        
        import scan_progress_store
        
        # 如果提供了 scan_id，直接获取
        if scan_id:
            try:
                progress = scan_progress_store.get_scan_progress(scan_id)
                if progress:
                    # 验证进度是否属于当前用户（多用户隔离）
                    progress_username = progress.get('username', 'anonymous')
                    if progress_username != username:
                        print(f"[get_progress] ⚠️ 用户 {username} 尝试访问其他用户 {progress_username} 的扫描进度: {scan_id}")
                        # 返回空闲状态，而不是错误，避免前端显示错误
                        response = jsonify({
                            'success': True,
                            'progress': {
                                'type': None,
                                'current': 0,
                                'total': 0,
                                'status': '空闲',
                                'detail': '无权访问此扫描任务',
                                'percentage': 0,
                                'found': 0
                            }
                        })
                        for key, value in response_headers.items():
                            response.headers[key] = value
                        return response
                    
                    response = jsonify({
                        'success': True,
                        'progress': progress
                    })
                    for key, value in response_headers.items():
                        response.headers[key] = value
                    return response
            except Exception as e:
                print(f"[get_progress] 从 scan_progress_store 读取进度失败: {e}")
        
        # 如果没有提供 scan_id，尝试查找当前用户的最新扫描任务
        # scan_id 格式: username_timestamp_uuid
        try:
            latest_scan_key = f'latest_scan:{username}'
            latest_scan_id = None
            
            # 尝试从 Redis 获取（如果支持）
            if hasattr(scan_progress_store, '_upstash_redis_get'):
                try:
                    latest_scan_id = scan_progress_store._upstash_redis_get(latest_scan_key)
                except Exception as e:
                    print(f"[get_progress] 从 Redis 获取最新 scan_id 失败: {e}")
            
            # 如果 Redis 获取失败，尝试从内存缓存获取（Render 环境）
            if not latest_scan_id and hasattr(scan_progress_store, '_memory_cache'):
                try:
                    latest_scan_id = scan_progress_store._memory_cache.get(latest_scan_key)
                except Exception as e:
                    print(f"[get_progress] 从内存缓存获取最新 scan_id 失败: {e}")
            
            if latest_scan_id:
                progress = scan_progress_store.get_scan_progress(latest_scan_id)
                if progress:
                    # 验证进度是否属于当前用户
                    progress_username = progress.get('username', 'anonymous')
                    if progress_username == username:
                        # 检查状态是否为活跃（不是"空闲"或"已完成"）
                        status = progress.get('status', '空闲')
                        if status not in ['空闲', '已完成', '已停止', '错误', '失败']:
                            response = jsonify({
                                'success': True,
                                'progress': progress
                            })
                            for key, value in response_headers.items():
                                response.headers[key] = value
                            return response
        except Exception as e:
            print(f"[get_progress] 查找最新扫描任务失败: {e}")
        
        # 如果没有提供 scan_id 或找不到进度，返回空闲状态
        response = jsonify({
            'success': True,
            'progress': {
                'type': None,
                'current': 0,
                'total': 0,
                'status': '空闲',
                'detail': '',
                'percentage': 0,
                'found': 0
            }
        })
        for key, value in response_headers.items():
            response.headers[key] = value
        return response
    
    try:
        # 优化：如果analyzer已初始化，直接使用，避免重复初始化导致阻塞
        if analyzer is None:
            # 快速初始化，如果失败则返回默认值
            try:
                init_analyzer()
            except Exception as e:
                print(f"[get_progress] 初始化analyzer失败: {e}")
                # 初始化失败时返回默认值，不阻塞
                response = jsonify({
                    'success': True,
                    'progress': {
                        'type': None,
                        'current': 0,
                        'total': 0,
                        'status': '空闲',
                        'detail': '分析器未初始化',
                        'percentage': 0,
                        'found': 0
                    }
                })
                for key, value in response_headers.items():
                    response.headers[key] = value
                return response
        
        # 检查 analyzer 是否已初始化
        if analyzer is None:
            print("[get_progress] analyzer 未初始化，返回默认值")
            response = jsonify({
                'success': True,
                'progress': {
                    'type': None,
                    'current': 0,
                    'total': 0,
                    'status': '空闲',
                    'detail': '',
                    'percentage': 0,
                    'found': 0
                }
            })
            for key, value in response_headers.items():
                response.headers[key] = value
            return response
        
        # 获取进度信息（添加异常保护）
        try:
            progress = analyzer.get_progress() if hasattr(analyzer, 'get_progress') else {}
            if not isinstance(progress, dict):
                print(f"[get_progress] progress 不是字典类型: {type(progress)}")
                progress = {'type': None, 'current': 0, 'total': 0, 'status': '空闲', 'detail': '', 'percentage': 0, 'found': 0}
            
            # 【不可变】找到一只显示一只：found>0 时若 candidates 为空，从 analyzer.progress 直接补全，保证实时显示
            if (progress.get('found') or 0) > 0 and (not progress.get('candidates') or len(progress.get('candidates', [])) == 0):
                raw = getattr(analyzer, 'progress', None) or {}
                if isinstance(raw, dict) and raw.get('candidates'):
                    progress['candidates'] = list(raw['candidates'])
            
            # ✅ 若本轮扫描指定了 scan_date，实时结果也只展示「最佳买点日期」= 该日的候选（搜哪一天就只出那一天）
            if progress.get('scan_date') and progress.get('candidates'):
                sd = (str(progress.get('scan_date')).strip() or '')[:10]
                if sd:
                    orig = progress['candidates']
                    progress['candidates'] = [
                        c for c in orig
                        if (str((c.get('最佳买点日期') or c.get('buy_date') or ''))[:10] == sd)
                    ]
                    progress['found'] = len(progress['candidates'])
            
            import json
            import math
            import numpy as np
            
            def _safe_float(v):
                """将可能为 nan/inf 的数值转为 None，保证 JSON 可序列化"""
                if v is None: return None
                if hasattr(pd, 'isna') and pd.isna(v): return None
                try:
                    f = float(v)
                    return None if (math.isnan(f) or math.isinf(f)) else f
                except (TypeError, ValueError): return None
            
            # 【不可变】candidates 必须返回给前端，不能清空。见 扫描显示不可变逻辑.md
            if progress.get('candidates'):
                cleaned_candidates = []
                for candidate in progress['candidates']:
                    try:
                        cleaned = {}
                        for key, value in (candidate or {}).items():
                            if key in ('特征', '核心特征匹配'):
                                continue
                            if isinstance(value, (np.integer, np.int64, np.int32)):
                                cleaned[key] = int(value)
                            elif isinstance(value, (np.floating, np.float64, np.float32)):
                                cleaned[key] = _safe_float(value) if (hasattr(pd, 'isna') and pd.isna(value)) else _safe_float(float(value))
                            elif hasattr(pd, 'isna') and pd.isna(value):
                                cleaned[key] = None
                            elif hasattr(value, 'isoformat') and callable(getattr(value, 'isoformat', None)):
                                try:
                                    cleaned[key] = value.isoformat()[:19] if value is not None and not (hasattr(pd, 'isna') and pd.isna(value)) else None
                                except Exception:
                                    cleaned[key] = str(value) if value is not None else None
                            elif isinstance(value, (int, float)):
                                cleaned[key] = _safe_float(value) if isinstance(value, float) else value
                            else:
                                cleaned[key] = value
                        # 二次清理：防止遗漏的 nan/inf 导致 JSON 序列化失败
                        for k in list(cleaned.keys()):
                            v = cleaned[k]
                            if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
                                cleaned[k] = None
                        cleaned_candidates.append(cleaned)
                    except Exception as ex:
                        cleaned_candidates.append({
                            '股票代码': str((candidate or {}).get('股票代码') or (candidate or {}).get('code') or ''),
                            '股票名称': str((candidate or {}).get('股票名称') or (candidate or {}).get('name') or ''),
                            '匹配度': _safe_float((candidate or {}).get('匹配度') or (candidate or {}).get('match_score') or 0) or 0,
                            '最佳买点日期': (str((candidate or {}).get('最佳买点日期') or (candidate or {}).get('buy_date') or ''))[:10],
                        })
                progress['candidates'] = cleaned_candidates
            
            try:
                json.dumps(progress, default=str)
            except (TypeError, ValueError) as e:
                print(f"[get_progress] 序列化测试失败: {e}，尝试只保留 candidates 标量字段")
                # 不直接清空：尝试只保留可序列化标量，保证实时显示
                try:
                    simple = []
                    for c in progress.get('candidates', []):
                        simple.append({
                            '股票代码': str(c.get('股票代码') or c.get('code') or ''),
                            '股票名称': str(c.get('股票名称') or c.get('name') or ''),
                            '匹配度': _safe_float(c.get('匹配度') or c.get('match_score') or 0) or 0,
                            '最佳买点日期': str(c.get('最佳买点日期') or c.get('buy_date') or '')[:10],
                            '最佳买点价格': _safe_float(c.get('最佳买点价格') or c.get('buy_price')),
                            '当前价格': _safe_float(c.get('当前价格') or c.get('current_price')),
                            '市值': _safe_float(c.get('市值')) if (c.get('市值') is not None and isinstance(c.get('市值'), (int, float))) else (_safe_float(c.get('market_cap')) if (c.get('market_cap') is not None and isinstance(c.get('market_cap'), (int, float))) else None),
                        })
                    progress['candidates'] = simple
                    json.dumps(progress, default=str)
                except Exception as ex2:
                    print(f"[get_progress] 警告: candidates 简化序列化仍失败，已清空。{ex2}")
                    progress['candidates'] = []
            
            response = jsonify({
                'success': True,
                'progress': progress
            })
            for key, value in response_headers.items():
                response.headers[key] = value
            return response
        except AttributeError as e:
            # analyzer 未初始化或 get_progress 方法不存在
            print(f"[get_progress] AttributeError: {e}")
            return jsonify({
                'success': True,
                'progress': {
                    'type': None,
                    'current': 0,
                    'total': 0,
                    'status': '空闲',
                    'detail': '',
                    'percentage': 0,
                    'found': 0
                }
            })
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"[get_progress] 错误: {error_detail}")
        # 即使出错，也返回成功响应（但带错误状态），避免前端不断重试
        return jsonify({
            'success': True,
            'progress': {
                'type': None,
                'current': 0,
                'total': 0,
                'status': '错误',
                'detail': f'获取进度失败: {str(e)}',
                'percentage': 0,
                'found': 0
            },
            'error': str(e) if is_vercel else None  # 仅在 Vercel 环境中返回错误详情
        })


def _normalize_trained_at(val):
    """将 trained_at 转为 YYYY-MM-DD 显示；无效则返回 None。"""
    if not val:
        return None
    s = str(val).strip()
    if not s:
        return None
    # ISO: 2026-01-24T09:15:41... 或 2026-01-24
    if len(s) >= 10 and s[4] == '-' and s[7] == '-':
        return s[:10]
    return None

def _parse_date_from_model_filename(filename):
    """从 trained_model_*_YYYYMMDD_HHMMSS.json 解析日期，返回 YYYY-MM-DD 或 None。"""
    import re
    m = re.search(r'_(\d{4})(\d{2})(\d{2})_(\d{6})\.json$', filename)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    return None

@app.route('/api/list_models', methods=['GET'])
@require_login
def list_models():
    """列出所有可用的模型文件"""
    try:
        import os
        import json
        from datetime import datetime
        
        project_root = os.path.dirname(os.path.abspath(__file__))
        model_files = []
        
        # 查找 trained_model*.json 与 model*.json（排除 model_comparison、model_structure）
        exclude = {'model_comparison.json', 'model_structure.json'}
        for filename in os.listdir(project_root):
            if not filename.endswith('.json'):
                continue
            if filename in exclude:
                continue
            if filename.startswith('trained_model') or filename.startswith('model'):
                filepath = os.path.join(project_root, filename)
                try:
                    # 读取模型文件获取基本信息
                    with open(filepath, 'r', encoding='utf-8') as f:
                        model_data = json.load(f)
                    
                    buy_features = model_data.get('buy_features', {})
                    common_features = buy_features.get('common_features', {})
                    raw_at = model_data.get('trained_at') or buy_features.get('trained_at')
                    trained_at = _normalize_trained_at(raw_at)
                    if not trained_at:
                        trained_at = _parse_date_from_model_filename(filename)
                    if not trained_at:
                        trained_at = '未知'
                    bull_stocks = model_data.get('bull_stocks', [])
                    mtime = os.path.getmtime(filepath)
                    
                    model_info = {
                        'filename': filename,
                        'trained_at': trained_at,
                        'feature_count': len(common_features),
                        'stock_count': len(bull_stocks),
                        'is_current': filename == _current_model_file,
                        '_mtime': mtime,
                        '_sort_date': trained_at if trained_at != '未知' else None
                    }
                    model_files.append(model_info)
                except Exception as e:
                    print(f"[list_models] 读取 {filename} 失败: {e}")
                    mtime = os.path.getmtime(filepath) if os.path.exists(filepath) else 0
                    model_files.append({
                        'filename': filename,
                        'trained_at': '未知',
                        'feature_count': 0,
                        'stock_count': 0,
                        'is_current': filename == _current_model_file,
                        '_mtime': mtime,
                        '_sort_date': None,
                        'error': str(e)
                    })
        
        # 排序：当前模型置顶，其余按日期从新到旧，再按文件名
        def _sort_key(m):
            is_cur = 0 if m['is_current'] else 1
            sd = m.get('_sort_date')
            date_str = sd if sd else None
            if not date_str:
                mtime = m.get('_mtime', 0)
                date_str = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d') if mtime else '1970-01-01'
            parts = [int(x) for x in date_str.split('-')]
            # 日期从新到旧：(-年,-月,-日)
            return (is_cur, -parts[0], -parts[1], -parts[2], m['filename'])
        
        model_files.sort(key=_sort_key)
        for m in model_files:
            m.pop('_mtime', None)
            m.pop('_sort_date', None)
        
        return jsonify({
            'success': True,
            'models': model_files,
            'current_model': _current_model_file
        })
    except Exception as e:
        import traceback
        print(f"[list_models] 错误: {traceback.format_exc()}")
        return jsonify({
            'success': False,
            'message': f'获取模型列表失败: {str(e)}'
        }), 500

@app.route('/api/switch_model', methods=['POST'])
@require_login
def switch_model():
    """切换使用的模型文件"""
    global analyzer, _current_model_file, _model_last_loaded_mtime
    try:
        data = request.get_json(silent=True) or {}
        model_filename = data.get('model_filename', '').strip()
        
        if not model_filename:
            return jsonify({
                'success': False,
                'message': '请指定模型文件名'
            }), 400
        
        # 检查文件是否存在
        import os
        project_root = os.path.dirname(os.path.abspath(__file__))
        model_path = os.path.join(project_root, model_filename)
        
        if not os.path.exists(model_path):
            return jsonify({
                'success': False,
                'message': f'模型文件不存在: {model_filename}'
            }), 404
        
        # 切换模型
        _current_model_file = model_filename
        analyzer = None  # 清空缓存，迫使重新加载
        _model_last_loaded_mtime = 0  # 重置 mtime
        
        # 重新加载模型
        a = init_analyzer()
        if a is None:
            return jsonify({
                'success': False,
                'message': '模型加载失败'
            }), 500
        
        buy_n = len(a.trained_features.get('common_features', {})) if a.trained_features else 0
        sell_n = len(a.trained_sell_features.get('common_features', {})) if a.trained_sell_features else 0
        
        return jsonify({
            'success': True,
            'message': f'已切换到模型: {model_filename}',
            'current_model': _current_model_file,
            'buy_features': buy_n,
            'sell_features': sell_n
        })
    except Exception as e:
        import traceback
        print(f"[switch_model] 错误: {traceback.format_exc()}")
        return jsonify({
            'success': False,
            'message': f'切换模型失败: {str(e)}'
        }), 500

@app.route('/api/delete_model', methods=['POST'])
@require_login
def delete_model():
    """删除模型文件"""
    global analyzer, _current_model_file, _model_last_loaded_mtime
    try:
        data = request.get_json(silent=True) or {}
        model_filename = data.get('model_filename', '').strip()
        
        if not model_filename:
            return jsonify({
                'success': False,
                'message': '请指定模型文件名'
            }), 400
        
        # 不允许删除默认模型 trained_model.json
        if model_filename == 'trained_model.json':
            return jsonify({
                'success': False,
                'message': '不能删除默认模型 trained_model.json'
            }), 400
        
        # 检查文件是否存在
        import os
        project_root = os.path.dirname(os.path.abspath(__file__))
        model_path = os.path.join(project_root, model_filename)
        
        if not os.path.exists(model_path):
            return jsonify({
                'success': False,
                'message': f'模型文件不存在: {model_filename}'
            }), 404
        
        # 如果删除的是当前模型，先切换到默认模型
        was_current_model = model_filename == _current_model_file
        if was_current_model:
            _current_model_file = 'trained_model.json'
            analyzer = None
            _model_last_loaded_mtime = 0
            # 重新加载默认模型
            a = init_analyzer()
            if a is None:
                return jsonify({
                    'success': False,
                    'message': '删除当前模型后，切换到默认模型失败'
                }), 500
        
        # 删除文件
        try:
            os.remove(model_path)
            print(f"[delete_model] ✅ 已删除模型文件: {model_filename}")
        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'删除文件失败: {str(e)}'
            }), 500
        
        return jsonify({
            'success': True,
            'message': f'模型 {model_filename} 已删除',
            'current_model': _current_model_file,
            'switched_to_default': was_current_model
        })
    except Exception as e:
        import traceback
        print(f"[delete_model] 错误: {traceback.format_exc()}")
        return jsonify({
            'success': False,
            'message': f'删除模型失败: {str(e)}'
        }), 500

@app.route('/api/reload_model', methods=['GET', 'POST'])
@require_login
def reload_model():
    """强制重新加载当前模型（用于重训后无需重启服务）"""
    global analyzer
    try:
        analyzer = None  # 清空缓存，迫使 init_analyzer 重新从磁盘加载
        a = init_analyzer()
        if a is None:
            return jsonify({'success': False, 'message': '模型加载失败'}), 500
        buy_n = len(a.trained_features.get('common_features', {})) if a.trained_features else 0
        sell_n = len(a.trained_sell_features.get('common_features', {})) if a.trained_sell_features else 0
        return jsonify({
            'success': True,
            'message': '模型已重新加载',
            'current_model': _current_model_file,
            'buy_features': buy_n,
            'sell_features': sell_n
        })
    except Exception as e:
        import traceback
        print(f"reload_model 错误: {traceback.format_exc()}")
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/save_model', methods=['POST'])
@require_login
def save_model():
    """保存模型到文件API"""
    try:
        init_analyzer()  # 确保分析器已初始化
        success = analyzer.save_model('trained_model.json')
        if success:
            return jsonify({
                'success': True,
                'message': '模型已保存到 trained_model.json'
            })
        else:
            return jsonify({
                'success': False,
                'message': '保存模型失败'
            }), 500
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"保存模型错误: {error_detail}")
        return jsonify({
            'success': False,
            'message': f'服务器错误: {str(e)}'
        }), 500

@app.route('/api/get_trained_features', methods=['GET'])
@require_login
def get_trained_features():
    """获取训练好的特征模板API"""
    try:
        init_analyzer()  # 确保分析器已初始化
        trained = analyzer.get_trained_features()
        
        print(f"[get_trained_features] trained 是否为 None: {trained is None}")
        if trained is not None:
            print(f"[get_trained_features] trained 有 common_features: {trained.get('common_features') is not None}")
            if trained.get('common_features'):
                print(f"[get_trained_features] common_features 数量: {len(trained.get('common_features', {}))}")
        
        if trained is None:
            print("[get_trained_features] 返回：模型不存在")
            return jsonify({
                'success': False,
                'message': '尚未训练特征模型',
                'common_features': None,
                'match_score_ready': False,
                'max_match_score': 0.0
            })
        
        # 转换为可序列化的格式
        result = {
            'success': True,
            'sample_count': trained.get('sample_count', 0),
            'trained_at': trained.get('trained_at').strftime('%Y-%m-%d %H:%M:%S') if trained.get('trained_at') else None,
            'sample_stocks': trained.get('sample_stocks', []),
            'common_features': {}
        }
        
        if trained.get('common_features'):
            for feature_name, stats in trained['common_features'].items():
                result['common_features'][feature_name] = {
                    '均值': float(stats['均值']),
                    '中位数': float(stats['中位数']),
                    '最小值': float(stats['最小值']),
                    '最大值': float(stats['最大值']),
                    '标准差': float(stats['标准差']),
                    '样本数': int(stats['样本数'])
                }
        
        print(f"[get_trained_features] 返回 common_features 数量: {len(result['common_features'])}")
        
        # 检查匹配度状态
        try:
            is_ready, max_score = analyzer._check_match_score()
            result['match_score_ready'] = is_ready
            result['max_match_score'] = max_score
        except Exception as e:
            print(f"[get_trained_features] 检查匹配度状态失败: {e}")
            result['match_score_ready'] = False
            result['max_match_score'] = 0.0
        
        return jsonify(result)
        
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"获取训练特征错误: {error_detail}")
        return jsonify({
            'success': False,
            'message': f'服务器错误: {str(e)}',
            'common_features': None,
            'match_score_ready': False,
            'max_match_score': 0.0
        }), 500


@app.route('/api/find_sell_points', methods=['POST'])
@require_login
def find_sell_points():
    init_analyzer()  # 确保分析器已初始化
    """查找卖点API"""
    try:
        data = request.get_json(silent=True)
        if not data:
            return jsonify({
                'success': False,
                'message': '请求数据为空',
                'sell_points': []
            }), 400
        
        stock_code = (data.get('code') or '').strip()
        buy_date = data.get('buy_date', '').strip()
        buy_price = float(data.get('buy_price', 0))
        search_weeks = int(data.get('search_weeks', 20))
        match_threshold = float(data.get('match_threshold', 0.85))
        
        if not stock_code:
            return jsonify({
                'success': False,
                'message': '股票代码不能为空',
                'sell_points': []
            }), 400
        
        if not buy_date:
            return jsonify({
                'success': False,
                'message': '买入日期不能为空',
                'sell_points': []
            }), 400
        
        if buy_price <= 0:
            return jsonify({
                'success': False,
                'message': '买入价格必须大于0',
                'sell_points': []
            }), 400
        
        # 查找卖点
        result = analyzer.find_sell_points(
            stock_code,
            buy_date=buy_date,
            buy_price=buy_price,
            search_weeks=search_weeks,
            match_threshold=match_threshold
        )
        
        # 转换为可序列化的格式
        if result.get('success') and result.get('sell_points'):
            sell_points = []
            for sp in result['sell_points']:
                sell_point = {
                    '日期': str(sp.get('日期', '')),
                    '价格': float(sp.get('价格', 0)) if sp.get('价格') is not None else 0,
                    '收盘价': float(sp.get('收盘价', 0)) if sp.get('收盘价') is not None else 0,
                    '匹配度': float(sp.get('匹配度', 0)) if sp.get('匹配度') is not None else 0,
                    '累计涨幅': float(sp.get('累计涨幅', 0)) if sp.get('累计涨幅') is not None else 0,
                    '翻倍倍数': float(sp.get('翻倍倍数', 0)) if sp.get('翻倍倍数') is not None else 0,
                    '买入后周数': int(sp.get('买入后周数', 0)) if sp.get('买入后周数') is not None else 0,
                    '1周后回调': float(sp.get('1周后回调', 0)) if sp.get('1周后回调') is not None else None,
                    '2周后回调': float(sp.get('2周后回调', 0)) if sp.get('2周后回调') is not None else None
                }
                sell_points.append(sell_point)
            
            return jsonify({
                'success': True,
                'message': result.get('message', ''),
                'sell_points': sell_points,
                'buy_date': result.get('buy_date', ''),
                'buy_price': result.get('buy_price', 0)
            })
        else:
            return jsonify({
                'success': False,
                'message': result.get('message', '查找卖点失败'),
                'sell_points': []
            })
    
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"查找卖点API出错: {error_detail}")
        return jsonify({
            'success': False,
            'message': f'查找卖点失败: {str(e)}',
            'sell_points': []
        }), 500


@app.route('/api/scan_near_new_high', methods=['GET', 'POST'])
@require_login
def api_scan_near_new_high():
    """新高附近选股：前高间隔≥5周、附近±5%。返回符合条件的个股列表。"""
    try:
        max_stocks = None
        max_market_cap = None
        if request.method == 'GET':
            max_stocks = request.args.get('max', type=int)
            try:
                mc = request.args.get('max_market_cap', type=float)
                if mc is not None and mc > 0:
                    max_market_cap = mc
            except (TypeError, ValueError):
                pass
        else:
            data = request.get_json(silent=True) or {}
            max_stocks = data.get('max')
            mc = data.get('max_market_cap')
            if mc is not None and (isinstance(mc, (int, float)) and mc > 0):
                max_market_cap = float(mc)
        base_dir = os.path.dirname(os.path.abspath(__file__))
        import scan_near_new_high as snh
        rows = snh.run_step2_batch(
            lookback_weeks=snh.DEFAULT_LOOKBACK_WEEKS,
            min_gap_weeks=snh.DEFAULT_MIN_GAP_WEEKS,
            max_gap_weeks=snh.DEFAULT_MAX_GAP_WEEKS,
            pct_range=snh.DEFAULT_PCT_RANGE,
            max_stocks=max_stocks,
            out_path=None,
            csv_path=None,
            require_today_yang=True,
            require_above_ma10=True,
            max_market_cap=max_market_cap
        )
        out = [
            {'code': c, 'name': n, 'curr_close': r['curr_close'], 'prev_high': r['prev_high'],
             'pct_diff': r['pct_diff'], 'gap_weeks': r['gap_weeks'],
             'curr_date': str(r.get('curr_date')), 'prev_high_date': str(r.get('prev_high_date')),
             '当天阳线': r.get('当天阳线'), 'no_higher_in_between': r.get('no_higher_in_between'), '市值亿': r.get('市值亿')}
            for c, n, r in rows
        ]
        return jsonify({'ok': True, 'list': out, 'count': len(out)})
    except Exception as e:
        import traceback
        print(f"[api_scan_near_new_high] 错误: {traceback.format_exc()}")
        return jsonify({'ok': False, 'message': str(e), 'list': [], 'count': 0}), 500


@app.route('/api/scan_all_stocks', methods=['POST'])
@require_login
def scan_all_stocks():
    """扫描所有A股API"""
    try:
        # 确保分析器已初始化（在 try 块内，以便捕获异常）
        try:
            init_analyzer()
        except Exception as init_error:
            import traceback
            error_detail = traceback.format_exc()
            print(f"[scan_all_stocks] ❌ 初始化分析器失败: {error_detail}")
            return jsonify({
                'success': False,
                'message': f'初始化分析器失败: {str(init_error)}',
                'error_type': 'init_error',
                'error_detail': error_detail
            }), 500
        
        # 检查分析器是否初始化成功
        if analyzer is None or analyzer.fetcher is None:
            return jsonify({
                'success': False,
                'message': '分析器未初始化或初始化失败',
                'error_type': 'analyzer_not_initialized'
            }), 500
        # 获取用户信息和等级
        user = get_current_user()
        if not user:
            return jsonify({
                'success': False,
                'message': '请先登录'
            }), 401
        
        username = user.get('username', 'anonymous')
        user_tier = get_user_tier()
        
        # 免费用户不允许手动扫描，只能查看自动扫描的结果
        if user_tier == 'free':
            return jsonify({
                'success': False,
                'message': '免费用户无需手动扫描，系统每天下午3:00自动扫描，您可以直接查看结果。',
                'error_code': 'AUTO_SCAN_ONLY'
            }), 403
        
        # VIP用户和超级用户可以手动扫描
        scan_config = get_scan_config()
        
        # VIP用户和超级用户：无扫描限制（无限次扫描）
        # VIP用户已经移除了每日扫描次数限制，可以无限次手动扫描
        
        data = request.get_json(silent=True) or {}
        min_match_score = float(data.get('min_match_score', 0.93))  # 默认0.93，更严格；若过少可调低
        max_market_cap = float(data.get('max_market_cap', 100.0))
        # ✅ 关键：打印接收到的市值参数，确保正确传递
        print(f"[scan_all_stocks] 接收到的扫描参数: min_match_score={min_match_score}, max_market_cap={max_market_cap}, 参数类型: {type(max_market_cap)}")
        limit = data.get('limit')
        scan_date = (data.get('scan_date') or '').strip() if isinstance(data.get('scan_date'), str) else data.get('scan_date')
        scan_session = (data.get('scan_session') or 'close').strip() if isinstance(data.get('scan_session'), str) else data.get('scan_session')
        if limit:
            limit = int(limit)
        
        # 扫描前检查数据完整性（仅检查，不阻止扫描）
        print(f"\n[scan_all_stocks] 检查数据完整性（扫描日期: {scan_date or '今天'}）...")
        freshness = check_data_freshness(scan_date)
        
        # 如果数据严重不足（超过50%过期），给出警告但不阻止扫描
        if not freshness['fresh']:
            outdated_pct = (freshness['outdated_count'] / freshness['total'] * 100) if freshness['total'] > 0 else 100
            print(f"[scan_all_stocks] ⚠️  数据不足警告")
            print(f"   - 过期数据: {freshness['outdated_count']}/{freshness['total']} ({outdated_pct:.1f}%)")
            print(f"   - 最新数据日期: {freshness.get('latest_data_date', '未知')}")
            print(f"   - 目标扫描日期: {scan_date or '今天'}")
            print(f"   - 注意：扫描将仅使用本地数据，缺少数据的股票将被跳过")
            
            # 如果超过50%的数据过期，建议先下载数据
            if outdated_pct > 50:
                print(f"[scan_all_stocks] ⚠️  超过50%的数据过期，强烈建议先下载数据")
        else:
            print(f"[scan_all_stocks] ✅ 数据完整性检查通过")
            print(f"   - 过期数据: {freshness['outdated_count']}/{freshness['total']}")
            print(f"   - 最新数据日期: {freshness.get('latest_data_date', '未知')}")
        
        # 并行处理配置（默认启用，提升扫描速度）
        use_parallel = data.get('use_parallel', True)  # 默认启用并行处理
        # 本地环境：使用更多线程提升速度；Render环境：平衡性能和内存使用
        if is_local:
            default_workers = 50  # 本地环境默认50线程，加速扫描
        elif is_render:
            default_workers = 20
        else:
            default_workers = 10
        max_workers = int(data.get('max_workers', default_workers))
        if is_local:
            if max_workers > 80:
                max_workers = 80
                print(f"[scan_all_stocks] ⚠️ 本地线程数已限制为80")
        else:
            if max_workers > 30:
                max_workers = 30
                print(f"[scan_all_stocks] ⚠️ 线程数已限制为30，避免内存溢出")
        
        # VIP用户自定义参数（第二阶段功能）
        exclude_st = data.get('exclude_st', True)  # 默认排除ST股票
        exclude_suspended = data.get('exclude_suspended', True)  # 默认排除停牌股票（暂不支持，预留）
        industry_filter = data.get('industry_filter', '').strip()  # 行业筛选（暂不支持，预留）
        custom_stock_pool = data.get('custom_stock_pool', '').strip()  # 自定义股票池（暂不支持，预留）
        
        # 在 Vercel serverless 环境中，使用分批处理方案（Render环境使用本地并行处理）
        if is_vercel and not is_render:
            import uuid
            import scan_progress_store
            
            # 获取当前用户信息，确保每个用户的扫描任务独立
            current_user = get_current_user()
            username = current_user.get('username', 'anonymous') if current_user else 'anonymous'
            
            # 生成扫描任务ID，包含用户名前缀，确保多用户并发时不会冲突
            # 格式: username_timestamp_uuid
            import time as time_module
            timestamp = int(time_module.time())
            unique_id = str(uuid.uuid4())[:8]  # 使用 UUID 的前8位，减少长度
            scan_id = f"{username}_{timestamp}_{unique_id}"
            
            print(f"[scan_all_stocks] 生成扫描任务ID: {scan_id} (用户: {username})")
            
            # 获取股票列表，计算批次
            if analyzer is None:
                return jsonify({
                    'success': False,
                    'message': '分析器未初始化'
                }), 500
            
            if not hasattr(analyzer, 'fetcher') or analyzer.fetcher is None:
                return jsonify({
                    'success': False,
                    'message': '数据获取器未初始化'
                }), 500
            
            # 提前创建初始进度（标记为"准备中"），这样即使获取股票列表失败，前端也能检测到扫描任务
            import scan_progress_store
            import time
            try:
                preparing_progress = {
                    'type': 'scan',
                    'scan_id': scan_id,
                    'username': username,
                    'user_tier': user_tier,
                    'is_auto_scan': False,
                    'current': 0,
                    'total': 0,  # 暂时为0，获取股票列表后更新
                    'status': '准备中',
                    'detail': '正在获取股票列表...',
                    'percentage': 0,
                    'found': 0,
                    'batch': 0,
                    'total_batches': 0,  # 暂时为0，获取股票列表后更新
                    'min_match_score': min_match_score,
                    'max_market_cap': max_market_cap,
                    'candidates': [],
                    'start_time': time.time()
                }
                scan_progress_store.save_scan_progress(scan_id, preparing_progress)
                
                # 保存用户的最新 scan_id（用于后续查找）
                try:
                    latest_scan_key = f'latest_scan:{username}'
                    if hasattr(scan_progress_store, '_upstash_redis_set'):
                        scan_progress_store._upstash_redis_set(latest_scan_key, scan_id, ttl=86400)  # 24小时TTL
                except Exception as e:
                    print(f"[scan_all_stocks] ⚠️ 保存最新 scan_id 失败: {e}")
                
                print(f"[scan_all_stocks] ✅ 已创建初始进度（准备中），scan_id: {scan_id}")
            except Exception as e:
                print(f"[scan_all_stocks] ⚠️ 创建初始进度失败（继续执行）: {e}")
            
            # 每次扫描前先检测缓存是否存在（建议每次使用前都检测）
            print("[scan_all_stocks] 🔍 检测缓存是否存在...")
            cache_exists = False
            cached_stock_count = 0
            cache_status = "未知"
            try:
                # 明确传递 check_age=False，确保返回 DataFrame 或 None
                cached_stocks = analyzer.fetcher._get_stock_list_from_cache(check_age=False)
                if cached_stocks is not None:
                    try:
                        # 确保 cached_stocks 是 DataFrame，可以使用 len()
                        if hasattr(cached_stocks, '__len__'):
                            cached_stock_count = len(cached_stocks)
                            if cached_stock_count > 0:
                                cache_exists = True
                                cache_status = f"缓存存在（{cached_stock_count} 只股票）"
                                print(f"[scan_all_stocks] ✅ 缓存存在，股票数: {cached_stock_count} 只，可以直接使用")
                            else:
                                cache_status = "缓存为空"
                                print(f"[scan_all_stocks] ⚠️ 缓存存在但为空（长度为0）")
                        else:
                            cache_status = "缓存数据格式错误（不是可迭代对象）"
                            print(f"[scan_all_stocks] ⚠️ 缓存数据格式错误: {type(cached_stocks)}")
                    except Exception as len_error:
                        cache_status = f"检查缓存长度时出错: {len_error}"
                        print(f"[scan_all_stocks] ⚠️ {cache_status}")
                else:
                    cache_status = "缓存不存在"
                    print(f"[scan_all_stocks] ⚠️ 缓存不存在（返回 None）")
            except Exception as e:
                import traceback
                error_detail = traceback.format_exc()
                cache_status = f"检测缓存时出错: {e}"
                print(f"[scan_all_stocks] ⚠️ {cache_status}")
                print(f"[scan_all_stocks] 错误详情: {error_detail}")
            
            # ✅ 如果缓存不存在，先尝试从K线文件列表自动生成（与本地版本行为一致）
            if not cache_exists:
                print(f"[scan_all_stocks] ⚠️ 缓存不存在，尝试从K线文件列表自动生成...")
                try:
                    from generate_stock_list_from_files import generate_stock_list_from_kline_files
                    if generate_stock_list_from_kline_files():
                        # 重新检查缓存
                        cached_stocks_retry = analyzer.fetcher._get_stock_list_from_cache(check_age=False)
                        if cached_stocks_retry is not None and len(cached_stocks_retry) > 0:
                            cache_exists = True
                            cached_stock_count = len(cached_stocks_retry)
                            print(f"[scan_all_stocks] ✅ 已从K线文件生成股票列表，股票数: {cached_stock_count} 只")
                        else:
                            print(f"[scan_all_stocks] ⚠️ 生成股票列表后，缓存仍为空")
                    else:
                        print(f"[scan_all_stocks] ⚠️ 生成股票列表失败")
                except Exception as gen_error:
                    import traceback
                    error_detail = traceback.format_exc()
                    print(f"[scan_all_stocks] ⚠️ 生成股票列表时出错: {gen_error}")
                    print(f"[scan_all_stocks] 错误详情: {error_detail}")
            
            # 如果缓存仍然不存在，在 Vercel 环境中显示警告（与本地版本行为一致：本地版本会尝试从 API 获取，但 Vercel 环境由于 USE_GITHUB_DATA_ONLY 模式，不能从 API 获取）
            if not cache_exists and is_vercel:
                from datetime import datetime, timezone, timedelta
                try:
                    utc_now = datetime.now(timezone.utc)
                    beijing_tz = timezone(timedelta(hours=8))
                    beijing_now = utc_now.astimezone(beijing_tz)
                    current_hour = beijing_now.hour
                    current_minute = beijing_now.minute
                    current_time_str = beijing_now.strftime('%Y-%m-%d %H:%M:%S')
                    
                    # 判断是否在交易时间（9:30-11:30, 13:00-15:00）
                    is_in_trading_time = (
                        (current_hour == 9 and current_minute >= 30) or
                        (current_hour == 10) or
                        (current_hour == 11 and current_minute <= 30) or
                        (current_hour == 13) or
                        (current_hour == 14) or
                        (current_hour == 15 and current_minute <= 0)
                    )
                    
                    # 只有在交易时间段内，才提前返回错误（避免超时和数据不一致）
                    # 非交易时间段，也显示警告（因为 USE_GITHUB_DATA_ONLY 模式下不能从 API 获取）
                    error_msg = '⚠️ **缓存未生成（股票列表缓存不存在）**\n\n'
                    error_msg += f'当前时间: {current_time_str}（{"交易时间段内" if is_in_trading_time else "非交易时间段"}）\n\n'
                    error_msg += '💡 **解决方案：**\n'
                    error_msg += '**方案1（推荐）：** 手动触发缓存刷新：访问 https://www.daniugu.online/api/refresh_stock_cache?force=true\n'
                    error_msg += '   - 手动刷新可能需要30秒，请耐心等待\n'
                    error_msg += '   - 刷新成功后，再尝试扫描\n\n'
                    if is_in_trading_time:
                        error_msg += '**方案2：** 等待几分钟，系统会在下次扫描时自动刷新缓存\n'
                    else:
                        error_msg += '**方案2：** 等待到交易时间段（9:30-11:30, 13:00-15:00）后重试\n'
                        error_msg += '   - 交易时间段内，系统会自动刷新缓存（中午11:30，下午15:00）\n'
                    error_msg += '\n📌 **说明：**\n'
                    if is_in_trading_time:
                        error_msg += '- 交易时间段内（9:30-11:30, 13:00-15:00）数据变化频繁\n'
                        error_msg += '- 建议等待缓存生成后再扫描，避免数据不一致和超时\n'
                    else:
                        error_msg += '- 系统使用 GitHub 数据包模式，不连接实时 API\n'
                        error_msg += '- 需要先手动刷新缓存，才能继续扫描\n'
                    
                    print(f"[scan_all_stocks] ❌ 缓存不存在（Vercel环境），已尝试自动生成但失败，建议手动刷新缓存")
                    return jsonify({
                        'success': False,
                        'message': error_msg,
                        'cache_exists': False,
                        'current_time': current_time_str,
                        'is_in_trading_time': is_in_trading_time,
                        'is_vercel': True,
                        'suggestion': '手动刷新缓存'
                    }), 400
                except Exception as e:
                    print(f"[scan_all_stocks] ⚠️ 检查交易时间时出错: {e}，继续执行")
            elif not cache_exists:
                # 本地环境，允许从 API 获取数据（虽然可能慢，但应该允许用户扫描）
                print(f"[scan_all_stocks] ⚠️ 缓存不存在（本地环境），将从 API 获取数据（可能需要较长时间，但允许扫描）")
            
            try:
                import time as time_module
                scan_start_time = time_module.time()
                
                # 根据缓存状态显示不同的提示信息
                # 注意：get_all_stocks 内部已实现智能缓存检查，在交易时间段内会自动刷新过期缓存
                if cache_exists:
                    print("[scan_all_stocks] 正在从缓存获取股票列表（如果过期会自动刷新）...")
                    status_msg = f"正在从缓存获取股票数据（{cached_stock_count} 只股票，交易时间段内会自动刷新过期缓存）..."
                else:
                    print("[scan_all_stocks] 正在从 API 获取股票列表...")
                    status_msg = "正在获取股票数据（从 API）..."
                
                # 在 Vercel 环境中，使用更短的超时时间（避免超过执行时间限制）
                # get_all_stocks 内部会根据环境自动调整超时和重试次数，并且会智能检查缓存年龄
                # 注意：即使在非交易时间段允许从 API 获取，Vercel 环境仍有 10 秒限制，可能超时
                # Vercel 中：超时5秒（留出5秒给其他处理），只尝试1次；本地：超时15秒，最多重试3次
                # 交易时间段内，如果缓存超过5分钟，会自动从API获取最新数据
                # 非交易时间段，如果缓存不存在，会尝试从 API 获取（但可能超时，建议先手动刷新缓存）
                stock_list = analyzer.fetcher.get_all_stocks(timeout=5 if is_vercel else 15, max_retries=1 if is_vercel else 3)
                
                elapsed = time_module.time() - scan_start_time
                if cache_exists:
                    print(f"[scan_all_stocks] ✅ 从缓存获取成功，股票数: {len(stock_list) if stock_list is not None else 0}, 耗时 {elapsed:.2f}秒")
                else:
                    print(f"[scan_all_stocks] ✅ 从 API 获取成功，股票数: {len(stock_list) if stock_list is not None else 0}, 耗时 {elapsed:.2f}秒")
            except Exception as e:
                import traceback
                error_detail = traceback.format_exc()
                print(f"[scan_all_stocks] ❌ 获取股票列表失败: {error_detail}")
                
                # 检查当前时间和缓存状态，提供更详细的错误信息
                from datetime import datetime, timezone, timedelta
                try:
                    utc_now = datetime.now(timezone.utc)
                    beijing_tz = timezone(timedelta(hours=8))
                    beijing_now = utc_now.astimezone(beijing_tz)
                    current_time_str = beijing_now.strftime('%Y-%m-%d %H:%M:%S')
                    current_hour = beijing_now.hour
                    current_minute = beijing_now.minute
                    is_in_trading_time = (
                        (current_hour == 9 and current_minute >= 30) or
                        (current_hour == 10) or
                        (current_hour == 11 and current_minute <= 30) or
                        (current_hour == 13) or
                        (current_hour == 14) or
                        (current_hour == 15 and current_minute <= 0)
                    )
                except Exception:
                    current_time_str = "未知"
                    is_in_trading_time = False
                
                # 检查缓存是否存在
                cache_exists_check = False
                try:
                    cached_stocks_check = analyzer.fetcher._get_stock_list_from_cache(check_age=False)
                    if cached_stocks_check is not None and len(cached_stocks_check) > 0:
                        cache_exists_check = True
                except Exception:
                    pass
                
                error_msg = f'获取股票列表失败: {str(e)}\n\n'
                error_msg += f'当前时间: {current_time_str}\n'
                error_msg += f'时间段: {"交易时间段内" if is_in_trading_time else "非交易时间段"}\n'
                error_msg += f'缓存状态: {"存在" if cache_exists_check else "不存在"}\n\n'
                
                error_msg += '⚠️ **问题分析：**\n'
                if not cache_exists_check:
                    error_msg += '缓存不存在，从 API 获取数据时失败或超时。\n\n'
                    if is_in_trading_time:
                        error_msg += '💡 **解决方案（按优先级）：**\n'
                        error_msg += '**方案1（推荐）：** 手动触发缓存刷新：访问 https://www.daniugu.online/api/refresh_stock_cache?force=true\n'
                        error_msg += '   - 手动刷新可能需要30秒，请耐心等待\n'
                        error_msg += '   - 刷新成功后，再尝试扫描\n\n'
                        error_msg += '**方案2：** 等待几分钟后重试（系统可能正在刷新缓存）\n\n'
                    else:
                        error_msg += '💡 **解决方案（按优先级）：**\n'
                        error_msg += '**方案1（推荐）：** 手动触发缓存刷新：访问 https://www.daniugu.online/api/refresh_stock_cache?force=true\n'
                        error_msg += '   - 手动刷新可能需要30秒，请耐心等待\n'
                        error_msg += '   - 刷新成功后，再尝试扫描\n\n'
                        error_msg += '**方案2：** 等待到交易时间段（9:30-11:30, 13:00-15:00）后重试\n'
                        error_msg += '   - 交易时间段内，系统会自动刷新缓存\n\n'
                        error_msg += '**方案3：** 稍后重试（可能是网络问题）\n\n'
                else:
                    error_msg += '缓存存在，但从 API 获取数据时失败（可能是网络问题或 akshare 服务暂时不可用）。\n\n'
                    error_msg += '💡 **解决方案：**\n'
                    error_msg += '**方案1（推荐）：** 稍后重试（可能是网络波动）\n\n'
                    error_msg += '**方案2：** 手动触发缓存刷新：访问 https://www.daniugu.online/api/refresh_stock_cache?force=true\n'
                    error_msg += '   - 手动刷新可能需要30秒，请耐心等待\n'
                    error_msg += '   - 刷新成功后，再尝试扫描\n\n'
                
                error_msg += '📌 **可能的原因：**\n'
                if is_vercel:
                    error_msg += '1. 超时（Vercel 函数执行时间限制为 10 秒，从 akshare API 获取数据可能需要较长时间）\n'
                    error_msg += '2. 网络连接问题（Vercel 环境网络限制）\n'
                    error_msg += '3. akshare 服务暂时不可用\n'
                else:
                    error_msg += '1. 网络连接问题\n'
                    error_msg += '2. akshare 服务暂时不可用\n'
                    error_msg += '3. 超时（获取数据可能需要较长时间）\n'
                
                return jsonify({
                    'success': False,
                    'message': error_msg,
                    'cache_exists': cache_exists_check,
                    'is_in_trading_time': is_in_trading_time,
                    'current_time': current_time_str,
                    'error_type': str(type(e).__name__)
                }), 500
            
            if stock_list is None or len(stock_list) == 0:
                print(f"[scan_all_stocks] ❌ 股票列表为空: stock_list={stock_list}, len={len(stock_list) if stock_list is not None else 0}")
                
                # 检查当前时间，判断是否在交易时间段
                from datetime import datetime, timezone, timedelta
                try:
                    utc_now = datetime.now(timezone.utc)
                    beijing_tz = timezone(timedelta(hours=8))
                    beijing_now = utc_now.astimezone(beijing_tz)
                    current_time_str = beijing_now.strftime('%Y-%m-%d %H:%M:%S')
                    current_hour = beijing_now.hour
                    current_minute = beijing_now.minute
                    is_in_trading_time = (
                        (current_hour == 9 and current_minute >= 30) or
                        (current_hour == 10) or
                        (current_hour == 11 and current_minute <= 30) or
                        (current_hour == 13) or
                        (current_hour == 14) or
                        (current_hour == 15 and current_minute <= 0)
                    )
                except Exception as e:
                    print(f"[scan_all_stocks] ⚠️ 获取当前时间失败: {e}")
                    is_in_trading_time = False
                    current_time_str = "未知"
                
                # 检查缓存是否存在
                cache_exists = False
                try:
                    cached_stocks = analyzer.fetcher._get_stock_list_from_cache(check_age=False)
                    if cached_stocks is not None and len(cached_stocks) > 0:
                        cache_exists = True
                        print(f"[scan_all_stocks] ⚠️ 缓存中存在股票列表，但 get_all_stocks 返回为空，可能是 API 调用失败")
                    else:
                        print(f"[scan_all_stocks] ⚠️ 缓存中不存在股票列表")
                except Exception as e:
                    print(f"[scan_all_stocks] ⚠️ 检查缓存时出错: {e}")
                
                error_msg = '无法获取股票列表\n\n'
                error_msg += f'当前时间: {current_time_str}\n'
                error_msg += f'时间段: {"交易时间段内" if is_in_trading_time else "非交易时间段"}\n'
                error_msg += f'缓存状态: {"存在" if cache_exists else "不存在"}\n\n'
                
                if not cache_exists:
                    if is_in_trading_time:
                        error_msg += '⚠️ **问题分析：**\n'
                        error_msg += '当前在交易时间段内，缓存不存在，从 API 获取数据时超时或失败。\n\n'
                        error_msg += '💡 **解决方案（按优先级）：**\n'
                        error_msg += '**方案1（推荐）：** 手动触发缓存刷新：访问 https://www.daniugu.online/api/refresh_stock_cache?force=true\n'
                        error_msg += '   - 手动刷新可能需要30秒，请耐心等待\n'
                        error_msg += '   - 刷新成功后，再尝试扫描\n\n'
                        error_msg += '**方案2：** 等待几分钟后重试（系统可能正在刷新缓存）\n\n'
                    else:
                        error_msg += '⚠️ **问题分析：**\n'
                        error_msg += '当前不在交易时间段，缓存不存在，从 API 获取数据时超时或失败。\n'
                        error_msg += '非交易时间段，akshare API 可能响应较慢，导致超时。\n\n'
                        error_msg += '💡 **解决方案（按优先级）：**\n'
                        error_msg += '**方案1（推荐）：** 手动触发缓存刷新：访问 https://www.daniugu.online/api/refresh_stock_cache?force=true\n'
                        error_msg += '   - 手动刷新可能需要30秒，请耐心等待\n'
                        error_msg += '   - 刷新成功后，再尝试扫描\n\n'
                        error_msg += '**方案2：** 等待到交易时间段（9:30-11:30, 13:00-15:00）后重试\n'
                        error_msg += '   - 交易时间段内，系统会自动刷新缓存\n\n'
                        error_msg += '**方案3：** 稍后重试（可能是网络问题）\n\n'
                else:
                    error_msg += '⚠️ **问题分析：**\n'
                    error_msg += '缓存存在，但从 API 获取数据时失败（可能是网络问题或 akshare 服务暂时不可用）。\n\n'
                    error_msg += '💡 **解决方案：**\n'
                    error_msg += '**方案1（推荐）：** 稍后重试（可能是网络波动或 akshare 服务暂时不可用）\n\n'
                    error_msg += '**方案2：** 手动触发缓存刷新：访问 https://www.daniugu.online/api/refresh_stock_cache?force=true\n'
                    error_msg += '   - 手动刷新可能需要30秒，请耐心等待\n'
                    error_msg += '   - 刷新成功后，再尝试扫描\n\n'
                
                error_msg += '📌 **技术说明：**\n'
                if is_vercel:
                    error_msg += '- Vercel 环境有 10 秒执行时间限制\n'
                    error_msg += '- 从 akshare API 获取股票列表可能需要较长时间\n'
                    error_msg += '- 如果缓存不存在，从 API 获取可能超时\n'
                error_msg += '- 建议在交易时间段（9:30-11:30, 13:00-15:00）使用，此时缓存会自动刷新\n'
                
                return jsonify({
                    'success': False,
                    'message': error_msg,
                    'cache_exists': cache_exists,
                    'is_in_trading_time': is_in_trading_time,
                    'current_time': current_time_str,
                    'suggestion': '手动刷新缓存' if not cache_exists else '稍后重试'
                }), 500
            
            # VIP用户自定义筛选：排除ST股票
            if exclude_st:
                # 获取股票名称列（可能是 'name' 或 '名称'）
                name_col = None
                for col in stock_list.columns:
                    col_lower = str(col).lower()
                    if 'name' in col_lower or '名称' in col:
                        name_col = col
                        break
                if name_col:
                    stock_list = stock_list[~stock_list[name_col].astype(str).str.contains('ST', na=False)]
                    print(f"[scan_all_stocks] 排除ST股票后，剩余股票数: {len(stock_list)}")
            
            # VIP用户自定义筛选：自定义股票池（如果指定）
            if custom_stock_pool:
                try:
                    stock_codes = [code.strip() for code in custom_stock_pool.split(',') if code.strip()]
                    if stock_codes:
                        # 获取股票代码列
                        code_col = None
                        for col in stock_list.columns:
                            col_lower = str(col).lower()
                            if 'code' in col_lower or '代码' in col:
                                code_col = col
                                break
                        if code_col:
                            # 只保留指定代码的股票（去除前缀和后缀，只匹配6位数字）
                            filtered_list = stock_list[stock_list[code_col].astype(str).str.replace(r'\.(SZ|SH)$', '', regex=True).str.replace(r'[^0-9]', '', regex=True).isin([code.replace('.SZ', '').replace('.SH', '').replace(r'[^0-9]', '') for code in stock_codes])]
                            if len(filtered_list) > 0:
                                stock_list = filtered_list
                                print(f"[scan_all_stocks] 使用自定义股票池，股票数: {len(stock_list)}")
                            else:
                                print(f"[scan_all_stocks] ⚠️ 自定义股票池未找到匹配的股票")
                except Exception as e:
                    print(f"[scan_all_stocks] ⚠️ 处理自定义股票池失败: {e}")
            
            # VIP用户自定义筛选：行业筛选（暂不支持，预留接口）
            # TODO: 实现行业筛选功能（需要获取股票行业信息）
            if industry_filter:
                print(f"[scan_all_stocks] ⚠️ 行业筛选功能暂未实现，参数: {industry_filter}")
            
            # VIP用户自定义筛选：排除停牌股票（暂不支持，预留接口）
            # TODO: 实现停牌股票判断（需要实时查询股票状态）
            if exclude_suspended:
                print(f"[scan_all_stocks] ⚠️ 排除停牌股票功能暂未实现")
            
            total_stocks = len(stock_list)
            if limit:
                stock_list = stock_list.head(limit)
                total_stocks = min(total_stocks, limit)
            
            # 根据用户等级获取扫描配置
            scan_config = get_scan_config()
            batch_size = scan_config['batch_size']
            total_batches = (total_stocks + batch_size - 1) // batch_size  # 向上取整
            
            # 初始化扫描进度并保存到 Redis
            import time
            initial_progress = {
                'type': 'scan',
                'scan_id': scan_id,
                'username': username,  # 添加用户名，用于多用户隔离
                'user_tier': user_tier,  # 添加用户等级，用于判断是否需要保存历史记录
                'is_auto_scan': False,  # 标记为手动扫描（VIP用户手动扫描）
                'current': 0,
                'total': total_stocks,
                'status': '准备中',
                'detail': f'准备扫描 {total_stocks} 只股票（分 {total_batches} 批）...',
                'percentage': 0,
                'found': 0,
                'batch': 0,
                'total_batches': total_batches,
                'min_match_score': min_match_score,
                'max_market_cap': max_market_cap,
                'candidates': [],
                'start_time': time.time()
            }
            scan_progress_store.save_scan_progress(scan_id, initial_progress)
            
            # 保存用户的最新 scan_id（用于后续查找）
            try:
                latest_scan_key = f'latest_scan:{username}'
                if hasattr(scan_progress_store, '_upstash_redis_set'):
                    scan_progress_store._upstash_redis_set(latest_scan_key, scan_id, ttl=86400)  # 24小时TTL
            except Exception as e:
                print(f"[scan_all_stocks] ⚠️ 保存最新 scan_id 失败: {e}")
            
            # VIP用户无限制扫描，不需要记录扫描次数（已移除限制）
            # 但可以保留记录功能用于统计（不限制扫描）
            if user_tier == 'premium':
                # VIP用户：可选记录统计信息（不影响扫描权限）
                print(f"[scan_all_stocks] VIP用户 {username} 开始扫描（无限制）")
            
            # 处理第一批（在请求中同步处理，避免超时）
            try:
                # 获取特征模板
                if analyzer.trained_features is None:
                    return jsonify({
                        'success': False,
                        'message': '尚未训练特征模型，请先训练'
                    }), 400
                
                common_features = analyzer.trained_features.get('common_features', {})
                if len(common_features) == 0:
                    return jsonify({
                        'success': False,
                        'message': '特征模板为空'
                    }), 400
                
                # 获取扫描配置
                scan_config = get_scan_config()
                
                # 处理第一批股票
                from vercel_scan_helper import process_scan_batch_vercel
                first_batch = stock_list.head(batch_size)
                batch_result = process_scan_batch_vercel(
                    analyzer, first_batch, common_features, scan_id, 1, total_batches, 
                    total_stocks, min_match_score, max_market_cap, 0, [], scan_config
                )
                
                return jsonify({
                    'success': True,
                    'scan_id': scan_id,
                    'message': f'扫描已开始（共 {total_batches} 批），已处理第 1 批',
                    'progress': batch_result.get('progress', {}),
                    'batch': 1,
                    'total_batches': total_batches,
                    'has_more': total_batches > 1
                })
            except Exception as e:
                import traceback
                error_detail = traceback.format_exc()
                print(f"处理第一批失败: {error_detail}")
                # 更新进度为失败状态
                error_progress = initial_progress.copy()
                error_progress['status'] = '失败'
                error_progress['detail'] = f'扫描失败: {str(e)[:100]}'
                scan_progress_store.save_scan_progress(scan_id, error_progress)
                return jsonify({
                    'success': False,
                    'message': f'扫描启动失败: {str(e)}'
                }), 500
        
        # 本地环境：使用原来的方式（后台线程）
        # ✅ 为本地环境也创建 scan_id，方便前端检测扫描状态
        import uuid
        import time as time_module
        timestamp = int(time_module.time())
        unique_id = str(uuid.uuid4())[:8]
        scan_id = f"{username}_{timestamp}_{unique_id}"
        
        print(f"[scan_all_stocks] 生成扫描任务ID: {scan_id} (用户: {username}, 本地环境)")
        
        # ✅ 提前创建初始进度（标记为"准备中"），这样即使请求超时，前端也能检测到扫描任务
        try:
            import scan_progress_store
            preparing_progress = {
                'type': 'scan',
                'scan_id': scan_id,
                'username': username,
                'user_tier': user_tier,
                'is_auto_scan': False,
                'current': 0,
                'total': 0,  # 暂时为0，获取股票列表后更新
                'status': '准备中',
                'detail': '正在获取股票列表...',
                'percentage': 0,
                'found': 0,
                'batch': 0,
                'total_batches': 0,  # 暂时为0，获取股票列表后更新
                'min_match_score': min_match_score,
                'max_market_cap': max_market_cap,
                'candidates': [],
                'start_time': time_module.time()
            }
            scan_progress_store.save_scan_progress(scan_id, preparing_progress)
            
            # 保存用户的最新 scan_id（用于后续查找）
            try:
                latest_scan_key = f'latest_scan:{username}'
                if hasattr(scan_progress_store, '_upstash_redis_set'):
                    scan_progress_store._upstash_redis_set(latest_scan_key, scan_id, ttl=86400)  # 24小时TTL
            except Exception as e:
                print(f"[scan_all_stocks] ⚠️ 保存最新 scan_id 失败: {e}")
            
            print(f"[scan_all_stocks] ✅ 已创建初始进度（准备中），scan_id: {scan_id}")
        except Exception as e:
            print(f"[scan_all_stocks] ⚠️ 创建初始进度失败（继续执行）: {e}")
        
        # 在后台线程中执行扫描（避免阻塞）
        import threading
        
        def run_scan():
            try:
                start_time = time_module.time()
                max_scan_time = 3600 * 2  # 最大扫描时间：2小时
                
                print(f"\n🔄 开始扫描，匹配度阈值: {min_match_score:.3f}, scan_id: {scan_id}")
                
                # ✅ 更新进度：正在获取股票列表
                try:
                    import scan_progress_store
                    getting_stocks_progress = preparing_progress.copy()
                    getting_stocks_progress['detail'] = '正在获取股票列表...'
                    scan_progress_store.save_scan_progress(scan_id, getting_stocks_progress)
                except Exception as e:
                    print(f"[scan_all_stocks] ⚠️ 更新进度失败: {e}")
                
                # 只执行一次扫描，不再自动调整阈值
                # 本地环境：默认优先使用缓存（稳定、可复现），需要强制刷新时再由前端传参控制
                force_refresh = bool(data.get('force_refresh', False))
                # ✅ 关键：本地环境默认严格只使用本地缓存，避免网络下载导致速度慢
                strict_local_only = data.get('strict_local_only', None)  # None表示自动判断
                result = analyzer.scan_all_stocks(
                    min_match_score=min_match_score,
                    max_market_cap=max_market_cap,
                    limit=limit,
                    use_parallel=use_parallel,
                    max_workers=max_workers,
                    scan_date=scan_date,
                    scan_session=scan_session,
                    force_refresh=force_refresh,
                    strict_local_only=strict_local_only  # ✅ 传递严格本地模式参数
                )
                
                # ✅ 若指定了扫描日期，只保留「最佳买点日期」= 该日的候选（搜哪一天就只出那一天的数据）
                if scan_date:
                    scan_date_str = (scan_date if isinstance(scan_date, str) else str(scan_date)).strip()[:10]
                    if scan_date_str:
                        orig = result.get('candidates', [])
                        filtered = [
                            c for c in orig
                            if (str((c.get('最佳买点日期') or c.get('buy_date') or ''))[:10] == scan_date_str)
                        ]
                        result['candidates'] = filtered
                        result['found_count'] = len(filtered)
                        if hasattr(analyzer, 'progress') and isinstance(analyzer.progress, dict):
                            analyzer.progress['candidates'] = filtered
                            analyzer.progress['found'] = len(filtered)
                        print(f"[scan_all_stocks] 已按扫描日期 {scan_date_str} 过滤：{len(orig)} → {len(filtered)} 只")
                
                # ✅ 更新进度：扫描完成
                try:
                    import scan_progress_store
                    found_count = result.get('found_count', 0)
                    if result.get('stopped', False):
                        final_progress = preparing_progress.copy()
                        final_progress['status'] = '已停止'
                        final_progress['detail'] = f'扫描已停止: 找到 {found_count} 只符合条件的股票'
                        final_progress['found'] = found_count
                        final_progress['percentage'] = 100.0
                        scan_progress_store.save_scan_progress(scan_id, final_progress)
                    else:
                        final_progress = preparing_progress.copy()
                        final_progress['status'] = '完成'
                        final_progress['detail'] = f'扫描完成: 找到 {found_count} 只符合条件的股票'
                        final_progress['found'] = found_count
                        final_progress['percentage'] = 100.0
                        scan_progress_store.save_scan_progress(scan_id, final_progress)
                except Exception as e:
                    print(f"[scan_all_stocks] ⚠️ 更新最终进度失败: {e}")
                
                # 如果被停止，直接保存结果
                if result.get('stopped', False):
                    analyzer.scan_results = result
                    found_count = result.get('found_count', 0)
                    print(f"\n✅ 扫描已停止，结果已保存（找到 {found_count} 只股票）")
                    # 更新进度状态为已停止（已经在scan_all_stocks中设置，这里确保一致性）
                    analyzer.progress['status'] = '已停止'
                    analyzer.progress['detail'] = f'扫描已停止: 找到 {found_count} 只符合条件的股票'
                    analyzer.progress['found'] = found_count
                    analyzer.progress['last_update_time'] = time_module.time()
                else:
                    # 保存扫描结果
                    analyzer.scan_results = result
                    found_count = result.get('found_count', 0)
                    print(f"\n📊 扫描完成，找到 {found_count} 只股票（阈值: {min_match_score:.3f}）")
                    
                    # 确保扫描完成后，更新进度状态为"完成"
                    if analyzer.progress.get('status') != '已停止':
                        analyzer.progress['status'] = '完成'
                        analyzer.progress['percentage'] = 100.0
                        analyzer.progress['detail'] = f'扫描完成: 找到 {found_count} 只符合条件的股票'
                        analyzer.progress['found'] = found_count
                        analyzer.progress['last_update_time'] = time_module.time()
                    
                    print(f"\n✅ 扫描完成，最终状态: {analyzer.progress.get('status')}")
                    
            except Exception as e:
                import traceback
                error_detail = traceback.format_exc()
                print(f"扫描过程出错: {error_detail}")
                
                # ✅ 更新进度：扫描失败
                try:
                    import scan_progress_store
                    error_progress = preparing_progress.copy()
                    error_progress['status'] = '失败'
                    error_progress['detail'] = f'扫描出错: {str(e)[:100]}'
                    scan_progress_store.save_scan_progress(scan_id, error_progress)
                except Exception as update_error:
                    print(f"[scan_all_stocks] ⚠️ 更新错误进度失败: {update_error}")
                
                # 即使出错，也尝试保存当前结果（如果有）
                if hasattr(analyzer, 'scan_results') and analyzer.scan_results:
                    pass  # 结果已保存
                # 出错时也要更新状态
                if analyzer.progress.get('status') != '已停止':
                    analyzer.progress['status'] = '失败'
                    analyzer.progress['detail'] = f'扫描出错: {str(e)[:50]}'
                    analyzer.progress['last_update_time'] = time_module.time()
        
        # 启动扫描线程
        scan_thread = threading.Thread(target=run_scan)
        scan_thread.daemon = True
        scan_thread.start()
        
        return jsonify({
            'success': True,
            'message': '扫描已开始，请通过进度API查看进度',
            'scan_id': scan_id  # ✅ 返回 scan_id，方便前端检测扫描状态
        })
        
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"扫描所有股票错误: {error_detail}")
        return jsonify({
            'success': False,
            'message': f'服务器错误: {str(e)}'
        }), 500


@app.route('/api/continue_scan', methods=['POST'])
@require_login
def continue_scan():
    """继续扫描下一批次（Vercel 环境）"""
    try:
        # 记录请求信息（用于调试）
        data = request.get_json(silent=True) or {}
        scan_id = data.get('scan_id')
        print(f"[continue_scan] 收到请求: scan_id={scan_id}, 用户={get_current_user().get('username') if get_current_user() else 'None'}")
        
        if not is_vercel:
            return jsonify({
                'success': False,
                'message': '此API仅在 Vercel 环境中可用'
            }), 400
        
        if not scan_id:
            return jsonify({
                'success': False,
                'message': '缺少 scan_id 参数'
            }), 400
        
        # 获取当前用户信息，用于验证权限
        current_user = get_current_user()
        current_username = current_user.get('username', 'anonymous') if current_user else 'anonymous'
        
        # 从scan_id中提取用户名（格式: username_timestamp_uuid）
        # 这样即使session有问题，也能正确验证
        scan_id_parts = scan_id.split('_', 1)  # 分割用户名和其余部分
        scan_id_username = scan_id_parts[0] if scan_id_parts else 'unknown'
        
        print(f"[continue_scan] scan_id={scan_id}, scan_id中的用户名={scan_id_username}, 当前用户={current_username}")
        
        import scan_progress_store
        from vercel_scan_helper import process_scan_batch_vercel
        
        # 获取当前进度
        progress = scan_progress_store.get_scan_progress(scan_id)
        if not progress:
            # 提供更详细的错误信息
            print(f"⚠️ 找不到扫描任务 scan_id={scan_id} (scan_id中的用户: {scan_id_username}, 当前用户: {current_username})")
            print(f"   可能原因：1) Redis 数据过期（TTL 24小时） 2) scan_id 错误 3) Redis 连接问题 4) 数据保存失败")
            
            # 尝试检查是否有其他相关的扫描任务（可能是同一个用户的另一个扫描）
            # 这里我们提供一个更友好的错误消息，并建议用户重新开始扫描
            # 返回400而不是404，因为路由存在，只是数据不存在
            return jsonify({
                'success': False,
                'message': f'找不到扫描任务（scan_id: {scan_id}）。可能原因：1) 数据已过期（超过24小时） 2) 任务已删除 3) Redis连接问题。部分结果可能已保存，请查看扫描结果。如需要，请重新开始扫描。',
                'error_code': 'SCAN_NOT_FOUND',
                'scan_id': scan_id,
                'retry': False,  # 标识是否应该重试
                'hint': '扫描任务可能已过期或被删除。如果之前有部分结果，请尝试查看扫描结果页面。'
            }), 400
        
        # 验证扫描任务是否属于当前用户（多用户隔离）
        # 优先使用scan_id中的用户名进行验证，因为它是创建时的真实用户名，不会受session影响
        progress_username = progress.get('username') or scan_id_username
        
        # 验证逻辑：
        # 1. 如果scan_id中的用户名和当前用户匹配，允许访问（最常见的情况）
        # 2. 如果progress中的用户名和当前用户匹配，允许访问（备用验证）
        # 3. 如果session丢失（current_user为None），但scan_id和progress中的用户名匹配，允许访问（容错处理）
        # 4. 如果scan_id中的用户名和progress中的用户名匹配，也允许访问（双重验证通过）
        
        # 如果scan_id中的用户名是"unknown"，说明scan_id格式不对，使用传统验证方式
        if scan_id_username == 'unknown':
            # 传统验证：只检查progress中的用户名和当前用户
            is_authorized = (progress_username == current_username and current_username != 'anonymous')
        else:
            # 新验证方式：优先使用scan_id中的用户名
            # 如果当前用户存在且匹配scan_id中的用户名，允许访问
            if current_user and current_username != 'anonymous':
                is_authorized = (scan_id_username == current_username or progress_username == current_username)
            else:
                # 如果session丢失，但scan_id和progress中的用户名匹配，允许访问（容错）
                is_authorized = (scan_id_username == progress_username and scan_id_username != 'unknown')
        
        if not is_authorized:
            print(f"⚠️ 权限验证失败: scan_id={scan_id}")
            print(f"   scan_id格式: {scan_id}")
            print(f"   scan_id中的用户名={scan_id_username}")
            print(f"   进度中的用户名={progress_username}")
            print(f"   当前用户={current_username}")
            print(f"   当前用户对象是否存在={current_user is not None}")
            return jsonify({
                'success': False,
                'message': f'无权访问此扫描任务。scan_id中的用户: {scan_id_username}, 当前用户: {current_username}, 进度中的用户: {progress_username}',
                'error_code': 'ACCESS_DENIED',
                'scan_id': scan_id,
                'scan_id_username': scan_id_username,
                'current_username': current_username,
                'progress_username': progress_username,
                'hint': '请确保使用相同的账号继续扫描任务'
            }), 403
        
        # 使用正确的用户名（优先使用scan_id中的，因为它是创建时的真实用户名）
        username = scan_id_username if scan_id_username != 'unknown' else (progress_username or current_username)
        print(f"[continue_scan] ✅ 权限验证通过，使用用户名: {username} (scan_id: {scan_id_username}, progress: {progress_username}, current: {current_username})")
        
        # 检查是否已完成
        if progress.get('status') == '完成':
            results = scan_progress_store.get_scan_results(scan_id)
            return jsonify({
                'success': True,
                'message': '扫描已完成',
                'progress': progress,
                'results': results,
                'is_complete': True
            })
        
        # 在处理批次之前，先刷新TTL，确保进度不会过期
        # 这很重要，因为在处理批次时可能会花费较长时间
        progress['last_refresh_time'] = time.time()
        progress['username'] = username  # 确保用户名正确
        refresh_success = scan_progress_store.save_scan_progress(scan_id, progress)
        if not refresh_success:
            print(f"⚠️ [continue_scan] 刷新进度TTL失败，但继续处理（scan_id={scan_id}）")
        
        # 获取参数
        batch_num = progress.get('batch', 0) + 1
        total_batches = progress.get('total_batches', 1)
        total_stocks = progress.get('total', 0)
        min_match_score = progress.get('min_match_score', 0.93)
        max_market_cap = progress.get('max_market_cap', 100.0)
        current_idx = progress.get('current', 0)
        existing_candidates = progress.get('candidates', [])
        
        # 检查是否还有更多批次
        if batch_num > total_batches:
            return jsonify({
                'success': True,
                'message': '所有批次已完成',
                'progress': progress,
                'is_complete': True
            })
        
        # 获取股票列表
        init_analyzer()
        stock_list = analyzer.fetcher.get_all_stocks()
        if stock_list is None or len(stock_list) == 0:
            return jsonify({
                'success': False,
                'message': '无法获取股票列表'
            }), 500
        
        # 获取特征模板
        if analyzer.trained_features is None:
            return jsonify({
                'success': False,
                'message': '尚未训练特征模型，请先训练'
            }), 400
        
        common_features = analyzer.trained_features.get('common_features', {})
        if len(common_features) == 0:
            return jsonify({
                'success': False,
                'message': '特征模板为空'
            }), 400
        
        # 根据用户等级获取扫描配置
        scan_config = get_scan_config()
        batch_size = scan_config['batch_size']
        start_idx = (batch_num - 1) * batch_size
        end_idx = min(start_idx + batch_size, total_stocks)
        
        if start_idx >= total_stocks:
            return jsonify({
                'success': True,
                'message': '所有批次已完成',
                'progress': progress,
                'is_complete': True
            })
        
        # 获取当前批次股票
        current_batch = stock_list.iloc[start_idx:end_idx]
        
        # 处理批次
        batch_result = process_scan_batch_vercel(
            analyzer, current_batch, common_features, scan_id, batch_num, total_batches,
            total_stocks, min_match_score, max_market_cap, start_idx, existing_candidates
        )
        
        return jsonify({
            'success': True,
            'message': f'第 {batch_num}/{total_batches} 批处理完成',
            'progress': batch_result.get('progress', {}),
            'batch': batch_num,
            'total_batches': total_batches,
            'has_more': not batch_result.get('is_complete', False),
            'is_complete': batch_result.get('is_complete', False)
        })
    
    except KeyError as e:
        # 处理数据格式错误
        import traceback
        error_detail = traceback.format_exc()
        print(f"继续扫描数据格式错误: {error_detail}")
        return jsonify({
            'success': False,
            'message': f'数据格式错误: {str(e)}',
            'error_code': 'DATA_FORMAT_ERROR'
        }), 400
        
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"继续扫描错误: {error_detail}")
        return jsonify({
            'success': False,
            'message': f'服务器错误: {str(e)}'
        }), 500


@app.route('/api/stop_scan', methods=['POST'])
@require_login
def stop_scan():
    """停止扫描API"""
    try:
        # 在 Vercel 环境中，更新 Redis 中的进度状态
        if is_vercel:
            data = request.get_json(silent=True) or {}
            scan_id = data.get('scan_id')
            
            print(f"[stop_scan] Vercel 环境，收到停止请求，scan_id: {scan_id}")
            
            if scan_id:
                try:
                    # 获取当前用户信息，用于验证权限
                    current_user = get_current_user()
                    username = current_user.get('username', 'anonymous') if current_user else 'anonymous'
                    
                    import scan_progress_store
                    progress = scan_progress_store.get_scan_progress(scan_id)
                    if progress:
                        # 验证扫描任务是否属于当前用户（多用户隔离）
                        progress_username = progress.get('username', 'anonymous')
                        if progress_username != username:
                            print(f"[stop_scan] ⚠️ 用户 {username} 尝试停止其他用户 {progress_username} 的扫描任务: {scan_id}")
                            return jsonify({
                                'success': False,
                                'message': '无权停止此扫描任务（不属于当前用户）',
                                'error_code': 'ACCESS_DENIED',
                                'scan_id': scan_id
                            }), 403
                        
                        progress['status'] = '已停止'
                        progress['detail'] = '扫描已停止（用户请求）'
                        import time
                        progress['last_update_time'] = time.time()
                        scan_progress_store.save_scan_progress(scan_id, progress)
                        print(f"[stop_scan] ✅ 成功停止扫描任务: {scan_id} (用户: {username})")
                        return jsonify({
                            'success': True,
                            'message': '停止扫描请求已发送',
                            'scan_id': scan_id
                        })
                    else:
                        print(f"[stop_scan] ⚠️ 找不到扫描任务: {scan_id} (用户: {username})")
                        return jsonify({
                            'success': False,
                            'message': f'找不到扫描任务（scan_id: {scan_id}），可能已过期或已完成'
                        }), 404
                except Exception as e:
                    import traceback
                    error_detail = traceback.format_exc()
                    print(f"[stop_scan] ❌ 停止扫描时出错: {error_detail}")
                    return jsonify({
                        'success': False,
                        'message': f'停止扫描失败: {str(e)}'
                    }), 500
            else:
                # 如果没有提供 scan_id，尝试从当前窗口的全局变量获取
                print(f"[stop_scan] ⚠️ 未提供 scan_id，尝试查找当前扫描任务...")
                # 在 Vercel 环境中，如果没有 scan_id，无法停止特定的扫描
                # 但我们可以返回一个友好的错误消息
                return jsonify({
                    'success': False,
                    'message': '未提供扫描任务ID（scan_id），无法停止扫描。请刷新页面后重试。'
                }), 400
        
        # 本地环境
        init_analyzer()  # 确保分析器已初始化
        
        if analyzer is None:
            return jsonify({
                'success': False,
                'message': '分析器未初始化'
            }), 500
        
        if not hasattr(analyzer, 'stop_scanning'):
            return jsonify({
                'success': False,
                'message': '分析器不支持停止扫描功能'
            }), 500
        
        analyzer.stop_scanning()
        print(f"[stop_scan] ✅ 本地环境，已发送停止扫描请求")
        return jsonify({
            'success': True,
            'message': '停止扫描请求已发送'
        })
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"[stop_scan] ❌ 停止扫描错误: {error_detail}")
        return jsonify({
            'success': False,
            'message': f'服务器错误: {str(e)}',
            'error_detail': error_detail if not is_vercel else None  # Vercel 环境不返回详细错误
        }), 500


@app.route('/api/find_buy_points', methods=['POST'])
@require_login
def find_buy_points():
    init_analyzer()  # 确保分析器已初始化
    """查找买点API"""
    try:
        data = request.get_json(silent=True)
        if not data:
            return jsonify({
                'success': False,
                'message': '请求数据为空',
                'buy_points': []
            }), 400
        
        stock_code = (data.get('code') or '').strip()
        tolerance = float(data.get('tolerance', 0.3))
        search_years = int(data.get('search_years', 5))  # 默认搜索5年历史
        
        if not stock_code:
            return jsonify({
                'success': False,
                'message': '股票代码不能为空',
                'buy_points': []
            }), 400
        
        if len(stock_code) != 6 or not stock_code.isdigit():
            return jsonify({
                'success': False,
                'message': '股票代码必须是6位数字',
                'buy_points': []
            }), 400
        
        # 获取股票名称
        stock_name = analyzer._get_stock_name(stock_code)
        if stock_name is None or stock_name == '':
            # 如果获取失败，尝试从已加载的大牛股列表中查找
            for stock in analyzer.bull_stocks:
                if stock.get('代码') == stock_code:
                    stock_name = stock.get('名称', stock_code)
                    break
            # 如果还是找不到，使用代码作为名称
            if stock_name is None or stock_name == '':
                stock_name = stock_code
                print(f"⚠️ 无法获取 {stock_code} 的股票名称，使用代码作为名称")
        
        # 查找历史买点（用于测试系统准确性）
        # 使用匹配度阈值0.95（与训练模型一致）
        match_threshold = float(data.get('match_threshold', 0.95))
        result = analyzer.find_buy_points(
            stock_code, 
            tolerance=tolerance, 
            search_years=search_years,
            match_threshold=match_threshold
        )
        
        # 在返回结果中添加股票名称
        if result.get('success'):
            result['stock_code'] = stock_code
            result['stock_name'] = stock_name
        
        # 转换为可序列化的格式
        if result.get('success') and result.get('buy_points'):
            buy_points = []
            for bp in result['buy_points']:
                buy_point = {
                    '日期': str(bp.get('日期', '')),
                    '价格': float(bp.get('价格', 0)) if bp.get('价格') is not None else 0,
                    '匹配度': float(bp.get('匹配度', 0)) if bp.get('匹配度') is not None else 0,
                    # 4周表现
                    '买入后4周涨幅': float(bp.get('买入后4周涨幅', 0)) if bp.get('买入后4周涨幅') is not None else None,
                    # 最佳卖点信息
                    '最佳卖点价格': float(bp.get('最佳卖点价格')) if bp.get('最佳卖点价格') is not None else None,
                    '最佳卖点日期': str(bp.get('最佳卖点日期', '')) if bp.get('最佳卖点日期') else None,
                    '最佳卖点周数': int(bp.get('最佳卖点周数')) if bp.get('最佳卖点周数') is not None else None,
                    '卖点类型': str(bp.get('卖点类型', '')) if bp.get('卖点类型') else None,
                    '止损价格': float(bp.get('止损价格')) if bp.get('止损价格') is not None else None,
                    '4周是否盈利': bool(bp.get('4周是否盈利', False)) if bp.get('4周是否盈利') is not None else None,
                    '4周是否翻倍': bool(bp.get('4周是否翻倍', False)) if bp.get('4周是否翻倍') is not None else None,
                    # 10周表现
                    '买入后10周涨幅': float(bp.get('买入后10周涨幅', 0)) if bp.get('买入后10周涨幅') is not None else None,
                    '10周是否盈利': bool(bp.get('10周是否盈利', False)) if bp.get('10周是否盈利') is not None else None,
                    '10周是否翻倍': bool(bp.get('10周是否翻倍', False)) if bp.get('10周是否翻倍') is not None else None,
                    '10周内最大涨幅': float(bp.get('10周内最大涨幅', 0)) if bp.get('10周内最大涨幅') is not None else None,
                    # 20周表现
                    '买入后20周涨幅': float(bp.get('买入后20周涨幅', 0)) if bp.get('买入后20周涨幅') is not None else None,
                    '20周是否盈利': bool(bp.get('20周是否盈利', False)) if bp.get('20周是否盈利') is not None else None,
                    # 最佳买点标记
                    '是否最佳买点': bool(bp.get('是否最佳买点', False))
                }
                buy_points.append(buy_point)
            result['buy_points'] = buy_points
        
        # 确保返回统计信息和匹配度信息（即使没有找到买点）
        if result.get('success'):
            if 'statistics' not in result or not result.get('statistics'):
                result['statistics'] = {
                    'total': len(result.get('buy_points', [])),
                    'best_buy_points': sum(1 for bp in result.get('buy_points', []) if bp.get('是否最佳买点', False)),
                    'profitable_4w': sum(1 for bp in result.get('buy_points', []) if bp.get('4周是否盈利', False)),
                    'profitable_10w': sum(1 for bp in result.get('buy_points', []) if bp.get('10周是否盈利', False))
                }
            # 保留匹配度信息
            if 'max_match_score' not in result:
                result['max_match_score'] = result.get('max_match_score', 0)
            if 'avg_match_score' not in result:
                result['avg_match_score'] = result.get('avg_match_score', 0)
        
        return jsonify(result)
        
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"查找买点错误: {error_detail}")
        return jsonify({
            'success': False,
            'message': f'服务器错误: {str(e)}',
            'buy_points': []
        }), 500


@app.route('/api/stocks_near_previous_high', methods=['POST'])
@require_login
def stocks_near_previous_high():
    """股价在前高附近：今日价格在「至少 N 周前的前高」的正负 pct% 之间"""
    init_analyzer()
    try:
        data = request.get_json(silent=True) or {}
        min_weeks_ago = int(data.get('min_weeks_ago', 6))   # 前高距今至少几周，默认 6
        pct_range = float(data.get('pct_range', 5))         # 正负百分比，默认 5
        stock_code = (data.get('code') or '').strip()
        scan_date = (data.get('scan_date') or '').strip()
        max_market_cap = None
        if data.get('max_market_cap') is not None:
            try:
                mc = float(data.get('max_market_cap'))
                if mc > 0:
                    max_market_cap = mc
            except (TypeError, ValueError):
                pass
        
        if min_weeks_ago < 1:
            min_weeks_ago = 1
        if pct_range <= 0 or pct_range > 50:
            pct_range = 5
        
        import pandas as pd
        from datetime import datetime as dt_now
        
        as_of = scan_date if scan_date else dt_now.now().strftime('%Y-%m-%d')
        as_of_ts = pd.to_datetime(as_of, errors='coerce')
        as_of_ymd = as_of_ts.strftime('%Y%m%d') if pd.notna(as_of_ts) else dt_now.now().strftime('%Y%m%d')
        
        def check_one(stock_code: str, stock_name: str):
            w = analyzer.fetcher.get_weekly_kline(stock_code, period='2y', use_cache=True, local_only=True)
            if w is None or len(w) < min_weeks_ago + 1:
                return None
            w = w.copy()
            w['日期'] = pd.to_datetime(w['日期'], errors='coerce')
            w = w.dropna(subset=['日期']).sort_values('日期').reset_index(drop=True)
            w = w[w['日期'] <= as_of_ts].reset_index(drop=True)
            if len(w) < min_weeks_ago + 1:
                return None
            # 前高区间：至少 min_weeks_ago 周以前（索引 0 到 len-1-min_weeks）
            past = w.iloc[: len(w) - min_weeks_ago]
            if '最高' in past.columns:
                high_col = '最高'
            elif 'high' in past.columns:
                high_col = 'high'
            else:
                past['_close'] = past['收盘'] if '收盘' in past.columns else past['close']
                high_col = '_close'
            prev_high = float(past[high_col].max())
            idx_high = int(past[high_col].idxmax())
            week_high = past.loc[idx_high, '日期']
            weeks_ago = len(w) - 1 - idx_high
            # 中间无破前高：从前高当周之后到当前周，中间任一最高价不得高于前高（如 000859 前高 11.56、中间曾到 14.08 则不符合）
            no_higher_in_between = True
            mid = w.iloc[idx_high + 1:]
            mid_high_col = '最高' if '最高' in w.columns else ('high' if 'high' in w.columns else None)
            if len(mid) > 0 and mid_high_col:
                mid_max = float(mid[mid_high_col].max())
                no_higher_in_between = mid_max <= prev_high * 1.0001
            # 当前价：优先用 scan_date 的日收盘
            current_price = None
            daily_df = analyzer.fetcher.get_daily_kline_range(
                stock_code, start_date=(as_of_ts - pd.Timedelta(days=30)).strftime('%Y%m%d'),
                end_date=as_of_ymd, use_cache=True, local_only=True
            )
            if daily_df is not None and len(daily_df) > 0 and '收盘' in daily_df.columns:
                daily_df = daily_df.copy()
                daily_df['日期'] = pd.to_datetime(daily_df['日期'], errors='coerce')
                daily_df = daily_df[daily_df['日期'] <= as_of_ts].sort_values('日期').reset_index(drop=True)
                if len(daily_df) > 0:
                    current_price = float(daily_df['收盘'].iloc[-1])
            if current_price is None:
                current_price = float(w['收盘'].iloc[-1]) if '收盘' in w.columns else float(w['close'].iloc[-1])
            low_bound = prev_high * (1 - pct_range / 100)
            high_bound = prev_high * (1 + pct_range / 100)
            near = (low_bound <= current_price <= high_bound) and no_higher_in_between
            return {
                '股票代码': stock_code,
                '股票名称': stock_name,
                '前高': round(prev_high, 2),
                '前高日期': week_high.strftime('%Y-%m-%d') if hasattr(week_high, 'strftime') else str(week_high)[:10],
                '距今周数': weeks_ago,
                '当前价': round(current_price, 2),
                '区间下限': round(low_bound, 2),
                '区间上限': round(high_bound, 2),
                '在前高附近': near,
                '中间无破前高': no_higher_in_between,
            }
        
        # 单只查询
        if stock_code:
            if len(stock_code) != 6 or not stock_code.isdigit():
                return jsonify({'success': False, 'message': '股票代码必须是6位数字', 'list': []}), 400
            name = getattr(analyzer, '_get_stock_name', lambda c: c)(stock_code) or stock_code
            row = check_one(stock_code, name)
            if row is None:
                return jsonify({
                    'success': True,
                    'message': '数据不足或区间内无前高',
                    'single': None,
                    'list': [],
                })
            return jsonify({
                'success': True,
                'single': row,
                'list': [row] if row['在前高附近'] else [],
            })
        
        # 全市场扫描：从 cache 取列表，限制数量避免超时
        cache_dir = os.environ.get('LOCAL_CACHE_DIR') or os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cache')
        stock_list_path = os.path.join(cache_dir, 'stock_list_all.json')
        stocks = []
        if os.path.exists(stock_list_path):
            try:
                with open(stock_list_path, 'r', encoding='utf-8') as f:
                    raw = json.load(f)
                if isinstance(raw, list):
                    for s in raw[:6000]:
                        code = (s.get('code') or s.get('代码') or '').strip()
                        name = (s.get('name') or s.get('名称') or code)
                        if code and len(code) == 6 and code.isdigit():
                            stocks.append((code, str(name)))
                elif isinstance(raw, dict) and 'data' in raw:
                    for s in raw['data'][:6000]:
                        code = (s.get('code') or s.get('代码') or '').strip()
                        name = (s.get('name') or s.get('名称') or code)
                        if code and len(code) == 6 and code.isdigit():
                            stocks.append((code, str(name)))
            except Exception:
                pass
        if not stocks:
            return jsonify({
                'success': False,
                'message': '未找到股票列表，请先下载或生成 stock_list_all.json',
                'list': [],
            }), 400
        
        # 全市场扫描：若已有任务在跑则拒绝；否则在后台线程跑并写进度
        global near_high_scan_progress
        if near_high_scan_progress.get('status') == 'running':
            return jsonify({
                'success': True,
                'started': False,
                'message': '已有过前高扫描在进行，请等待完成或稍后再试',
                'list': [],
            })
        total = len(stocks)
        near_high_scan_progress['status'] = 'running'
        near_high_scan_progress['total'] = total
        near_high_scan_progress['current'] = 0
        near_high_scan_progress['percentage'] = 0
        near_high_scan_progress['message'] = f'已扫描 0 / {total} 只'
        near_high_scan_progress['list'] = []
        near_high_scan_progress['scan_date'] = as_of
        near_high_scan_progress['total_scanned'] = 0

        def run_scan():
            out = []
            try:
                for i, (code, name) in enumerate(stocks):
                    near_high_scan_progress['current'] = i + 1
                    near_high_scan_progress['percentage'] = round((i + 1) / total * 100, 1)
                    near_high_scan_progress['message'] = f'已扫描 {i + 1} / {total} 只'
                    row = check_one(code, name)
                    if row and row.get('在前高附近'):
                        if max_market_cap is not None:
                            try:
                                cap = analyzer.fetcher.get_market_cap(code, timeout=2)
                                if cap is None or cap > max_market_cap:
                                    continue
                                row['市值亿'] = round(cap, 2)
                            except Exception:
                                continue
                        out.append(row)
                near_high_scan_progress['status'] = 'completed'
                near_high_scan_progress['message'] = f'扫描完成，共 {len(out)} 只（已扫描 {total} 只）'
                near_high_scan_progress['list'] = out
                near_high_scan_progress['total_scanned'] = total
            except Exception as e:
                near_high_scan_progress['status'] = 'error'
                near_high_scan_progress['message'] = str(e)[:200]
                near_high_scan_progress['list'] = []

        t = threading.Thread(target=run_scan, daemon=True)
        t.start()
        return jsonify({
            'success': True,
            'started': True,
            'message': '全市场扫描已启动，请查看下方进度',
            'list': [],
        })
    except Exception as e:
        import traceback
        print(f"[stocks_near_previous_high] {traceback.format_exc()}")
        return jsonify({'success': False, 'message': str(e), 'list': []}), 500


@app.route('/api/get_near_high_scan_progress', methods=['GET'])
@require_login
def get_near_high_scan_progress():
    """过前高全市场扫描进度：返回 status/current/total/percentage/message/list（完成时含 list）"""
    try:
        global near_high_scan_progress
        # 返回副本，避免前端持有引用时被并发修改
        p = dict(near_high_scan_progress)
        if p.get('list') is not None and isinstance(p['list'], list):
            p['list'] = list(p['list'])
        return jsonify(p)
    except Exception as e:
        return jsonify({
            'status': 'idle',
            'current': 0,
            'total': 0,
            'percentage': 0,
            'message': '',
            'list': [],
            'total_scanned': 0,
        })


@app.route('/api/get_scan_progress', methods=['GET'])
@require_login
def get_scan_progress():
    """获取扫描进度API"""
    try:
        init_analyzer()  # 确保分析器已初始化
        
        # 检查 analyzer 是否已初始化
        if analyzer is None:
            return jsonify({
                'type': 'scan',
                'current': 0,
                'total': 0,
                'status': '空闲',
                'detail': '',
                'percentage': 0,
                'found': 0
            })
        
        # 使用 get_progress() 方法，而不是直接访问 progress 属性
        progress = analyzer.get_progress().copy()
        
        # 添加最后更新时间，用于检测是否卡住
        if 'last_update_time' in progress:
            import time
            last_update = progress['last_update_time']
            current_time = time.time()
            time_since_update = current_time - last_update
            
            progress['time_since_last_update'] = round(time_since_update, 1)  # 距离最后更新的秒数
            
            # 如果超过30秒没有更新，标记为可能卡住
            if time_since_update > 30:
                progress['status'] = '可能卡住'
                progress['warning'] = f'已超过 {int(time_since_update)} 秒未更新，当前股票: {progress.get("current_stock", "未知")}'
        
        return jsonify(progress)
    except AttributeError as e:
        # analyzer 未初始化或方法不存在
        print(f"获取扫描进度错误 (AttributeError): {e}")
        return jsonify({
            'type': 'scan',
            'current': 0,
            'total': 0,
            'status': '空闲',
            'detail': '',
            'percentage': 0,
            'found': 0
        })
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"获取扫描进度错误: {error_detail}")
        return jsonify({
            'type': 'scan',
            'current': 0,
            'total': 0,
            'status': '错误',
            'detail': f'获取进度失败: {str(e)}',
            'percentage': 0,
            'found': 0,
            'error_detail': error_detail if is_vercel else None  # 仅在 Vercel 环境中返回详细错误
        })

@app.route('/api/get_scan_debug_log', methods=['GET'])
@require_login
def get_scan_debug_log():
    """获取扫描调试日志API"""
    try:
        import os
        log_file = 'scan_debug.log'
        
        if not os.path.exists(log_file):
            return jsonify({
                'success': False,
                'message': '日志文件不存在',
                'logs': []
            })
        
        # 读取最后100行日志
        with open(log_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            last_lines = lines[-100:] if len(lines) > 100 else lines
        
        return jsonify({
            'success': True,
            'logs': last_lines,
            'total_lines': len(lines)
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'读取日志失败: {str(e)}',
            'logs': []
        }), 500

@app.route('/api/get_scan_results', methods=['GET'])
@require_login
def get_scan_results():
    """获取扫描结果API"""
    try:
        # 获取用户信息和等级
        user = get_current_user()
        if not user:
            return jsonify({
                'success': False,
                'message': '请先登录',
                'candidates': []
            }), 401
        
        user_tier = get_user_tier()
        scan_config = get_scan_config()
        
        # 检查结果查看时间限制
        from scan_limit_helper import check_result_view_time
        can_view, view_error = check_result_view_time(user_tier, scan_config)
        if not can_view:
            return jsonify({
                'success': False,
                'message': view_error,
                'error_code': 'VIEW_TIME_LIMIT',
                'candidates': []
            }), 403
        
        # 在 Vercel 环境中，从 Redis 读取结果
        if is_vercel:
            import scan_progress_store
            from scan_limit_helper import get_beijing_time
            
            scan_id = request.args.get('scan_id') or request.args.get('scanId')
            
            # 如果没有提供 scan_id，尝试查找最新的自动扫描结果
            if not scan_id and user_tier in ['free', 'premium']:
                # 查找今天该用户等级的最新自动扫描任务
                beijing_now = get_beijing_time()
                today_str = beijing_now.strftime('%Y-%m-%d')
                
                # 自动扫描的 scan_id 格式: auto_{user_tier}_{timestamp}_{uuid}
                # 我们需要查找所有以 auto_{user_tier}_ 开头的扫描任务
                # 由于 Redis 不支持模式匹配，我们使用一个固定的键来存储今天的自动扫描ID
                auto_scan_key = f'auto_scan_{user_tier}_{today_str}'
                auto_scan_id = scan_progress_store._upstash_redis_get(auto_scan_key) if hasattr(scan_progress_store, '_upstash_redis_get') else None
                
                if auto_scan_id:
                    scan_id = auto_scan_id
                    print(f"[get_scan_results] 找到今天的自动扫描任务: {scan_id} (用户等级: {user_tier})")
            
            if scan_id:
                # 获取当前用户信息，用于验证权限
                current_user = get_current_user()
                username = current_user.get('username', 'anonymous') if current_user else 'anonymous'
                
                import scan_progress_store
                results = scan_progress_store.get_scan_results(scan_id)
                if results:
                    # 验证结果是否属于当前用户（从进度中获取用户名）
                    progress = scan_progress_store.get_scan_progress(scan_id)
                    if progress:
                        progress_username = progress.get('username', 'anonymous')
                        if progress_username != username:
                            print(f"[get_scan_results] ⚠️ 用户 {username} 尝试访问其他用户 {progress_username} 的扫描结果: {scan_id}")
                            return jsonify({
                                'success': False,
                                'message': '无权访问此扫描结果（不属于当前用户）',
                                'error_code': 'ACCESS_DENIED',
                                'candidates': []
                            }), 403
                    
                    return jsonify({
                        'success': True,
                        'message': results.get('message', '扫描完成'),
                        'candidates': results.get('candidates', []),
                        'found_count': results.get('found_count', 0),
                        'total_scanned': results.get('total_scanned', 0),
                        'scan_id': scan_id
                    })
                else:
                    # 如果找不到结果，尝试从进度中获取候选股票
                    progress = scan_progress_store.get_scan_progress(scan_id)
                    if progress:
                        # 验证进度是否属于当前用户
                        progress_username = progress.get('username', 'anonymous')
                        if progress_username != username:
                            print(f"[get_scan_results] ⚠️ 用户 {username} 尝试访问其他用户 {progress_username} 的扫描进度: {scan_id}")
                            return jsonify({
                                'success': False,
                                'message': '无权访问此扫描进度（不属于当前用户）',
                                'error_code': 'ACCESS_DENIED',
                                'candidates': []
                            }), 403
                        
                        if progress.get('candidates'):
                            return jsonify({
                                'success': True,
                                'message': '扫描进行中，返回当前已找到的股票',
                                'candidates': progress.get('candidates', []),
                                'found_count': len(progress.get('candidates', [])),
                                'total_scanned': progress.get('current', 0),
                                'scan_id': scan_id
                            })
            
            return jsonify({
                'success': False,
                'message': '未提供 scan_id 或找不到扫描结果',
                'candidates': []
            })
        
        # 本地环境：从 analyzer 获取结果
        scan_results = getattr(analyzer, 'scan_results', None)
        
        # 如果scan_results为空，尝试从progress中获取candidates
        if scan_results is None:
            progress = analyzer.get_progress() if hasattr(analyzer, 'get_progress') else {}
            if progress and progress.get('candidates'):
                # 从进度中构建结果
                candidates = progress.get('candidates', [])
                scan_results = {
                    'success': True,
                    'message': '扫描完成',
                    'candidates': candidates,
                    'found_count': len(candidates),
                    'total_scanned': progress.get('current', progress.get('total', 0))
                }
            else:
                return jsonify({
                    'success': False,
                    'message': '尚未开始扫描或扫描未完成',
                    'candidates': []
                })
        
        # 转换为可序列化的格式
        if scan_results.get('candidates'):
            for candidate in scan_results['candidates']:
                # 确保所有数值都是可序列化的
                if '特征' in candidate:
                    features = candidate['特征']
                    for key, value in list(features.items()):
                        if isinstance(value, (np.integer, np.int64, np.int32)):
                            features[key] = int(value)
                        elif isinstance(value, (np.floating, np.float64, np.float32)):
                            features[key] = float(value) if not pd.isna(value) else None
                        elif pd.isna(value):
                            features[key] = None
                
                if '核心特征匹配' in candidate:
                    core_match = candidate['核心特征匹配']
                    for key, value in list(core_match.items()):
                        if isinstance(value, (np.integer, np.int64, np.int32)):
                            core_match[key] = int(value)
                        elif isinstance(value, (np.floating, np.float64, np.float32)):
                            core_match[key] = float(value) if not pd.isna(value) else None
                        elif pd.isna(value):
                            core_match[key] = None
        
        return jsonify(scan_results)
        
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"获取扫描结果错误: {error_detail}")
        return jsonify({
            'success': False,
            'message': f'服务器错误: {str(e)}'
        }), 500


@app.route('/api/get_free_user_scan_results', methods=['GET'])
@require_login
def get_free_user_scan_results():
    """获取免费用户的扫描结果（根据当前时间自动选择）"""
    try:
        # 获取用户信息和等级
        user = get_current_user()
        if not user:
            return jsonify({
                'success': False,
                'message': '请先登录',
                'results': []
            }), 401
        
        user_tier = get_user_tier()
        
        # 只有免费用户可以查看此接口
        if user_tier != 'free':
            return jsonify({
                'success': False,
                'message': '此接口仅限免费用户使用',
                'results': []
            }), 403
        
        # 获取北京时间
        from scan_limit_helper import get_beijing_time
        from datetime import timedelta
        import scan_progress_store
        
        beijing_now = get_beijing_time()
        current_hour = beijing_now.hour
        current_date = beijing_now.strftime('%Y-%m-%d')
        
        results = []
        
        # 如果12点前进入，显示昨天下午和中午的结果
        # 如果12点后进入，显示当天中午和前一天下午的结果
        if current_hour < 12:
            # 12点前：显示昨天下午和中午的结果
            yesterday = (beijing_now - timedelta(days=1)).strftime('%Y-%m-%d')
            
            # 获取昨天下午的扫描结果
            afternoon_result = scan_progress_store.get_global_scan_results('afternoon', yesterday)
            if afternoon_result:
                results.append({
                    'scan_type': 'afternoon',
                    'scan_date': yesterday,
                    'scan_time': '15:00',
                    'title': f'{yesterday} 下午3:00扫描结果',
                    'result': afternoon_result
                })
            
            # 获取昨天中午的扫描结果
            noon_result = scan_progress_store.get_global_scan_results('noon', yesterday)
            if noon_result:
                results.append({
                    'scan_type': 'noon',
                    'scan_date': yesterday,
                    'scan_time': '11:30',
                    'title': f'{yesterday} 中午11:30扫描结果',
                    'result': noon_result
                })
        else:
            # 12点后：显示当天中午和前一天下午的结果
            # 获取当天中午的扫描结果
            noon_result = scan_progress_store.get_global_scan_results('noon', current_date)
            if noon_result:
                results.append({
                    'scan_type': 'noon',
                    'scan_date': current_date,
                    'scan_time': '11:30',
                    'title': f'{current_date} 中午11:30扫描结果',
                    'result': noon_result
                })
            
            # 获取前一天下午的扫描结果
            yesterday = (beijing_now - timedelta(days=1)).strftime('%Y-%m-%d')
            afternoon_result = scan_progress_store.get_global_scan_results('afternoon', yesterday)
            if afternoon_result:
                results.append({
                    'scan_type': 'afternoon',
                    'scan_date': yesterday,
                    'scan_time': '15:00',
                    'title': f'{yesterday} 下午3:00扫描结果',
                    'result': afternoon_result
                })
        
        return jsonify({
            'success': True,
            'message': f'找到 {len(results)} 组扫描结果',
            'results': results,
            'current_time': beijing_now.strftime('%Y-%m-%d %H:%M:%S')
        })
        
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"获取免费用户扫描结果错误: {error_detail}")
        return jsonify({
            'success': False,
            'message': f'服务器错误: {str(e)}',
            'results': []
        }), 500


@app.route('/api/scan_v2', methods=['POST'])
@require_login
def scan_v2():
    """使用V2模型扫描大牛股API"""
    try:
        init_v2_model()  # 确保V2模型已初始化
        
        if v2_model is None or not v2_model.feature_template:
            return jsonify({
                'success': False,
                'message': 'V2模型未初始化或未训练'
            }), 500
        
        data = request.get_json(silent=True) or {}
        min_match_score = float(data.get('min_match_score', 0.90))
        min_bottom_score = int(data.get('min_bottom_score', 2))
        min_launch_score = int(data.get('min_launch_score', 2))
        limit = int(data.get('limit', 20))
        
        print(f"\n🚀 V2模型扫描开始...")
        print(f"   匹配度阈值: {min_match_score}")
        print(f"   底部蓄势得分阈值: {min_bottom_score}")
        print(f"   启动信号得分阈值: {min_launch_score}")
        
        # 加载股票列表（Vercel 下从 LOCAL_CACHE_DIR 读 /tmp/cache）
        cache_dir = os.environ.get('LOCAL_CACHE_DIR') or os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cache')
        stock_list_path = os.path.join(cache_dir, 'stock_list_all.json')
        
        if not os.path.exists(stock_list_path):
            return jsonify({
                'success': False,
                'message': '股票列表缓存不存在'
            }), 500
        
        with open(stock_list_path, 'r', encoding='utf-8') as f:
            stock_list = json.load(f)
        
        candidates = []
        weekly_cache_dir = os.path.join(cache_dir, 'weekly_kline')
        
        for stock_info in stock_list:
            code = stock_info.get('code', '')
            name = stock_info.get('name', '')
            
            # 排除ST和北交所
            if 'ST' in name.upper() or code.startswith('8') or code.startswith('9'):
                continue
            
            csv_path = os.path.join(weekly_cache_dir, f'{code}.csv')
            if not os.path.exists(csv_path):
                continue
            
            try:
                weekly_df = pd.read_csv(csv_path)
                if len(weekly_df) < 50:
                    continue
                
                idx = len(weekly_df) - 1
                volume_col = '周成交量' if '周成交量' in weekly_df.columns else '成交量'
                
                features = v2_model.extract_features(weekly_df, idx, volume_col)
                
                if features:
                    score = v2_model.calculate_score(features)
                    bottom = features.get('底部蓄势得分', 0)
                    launch = features.get('启动信号得分', 0)
                    
                    if score >= min_match_score and bottom >= min_bottom_score and launch >= min_launch_score:
                        candidates.append({
                            '代码': code,
                            '名称': name,
                            '匹配度': round(score, 3),
                            '价格': round(weekly_df['收盘'].iloc[idx], 2),
                            '底部得分': bottom,
                            '启动得分': launch,
                            '均线多头': features.get('均线多头', 0),
                            'OBV趋势': round(features.get('OBV趋势', 0), 2),
                            '近期金叉': features.get('近期金叉', 0),
                            '突破20周高点': features.get('突破20周高点', 0),
                            '当周量比': round(features.get('当周量比', 0), 2),
                        })
            except Exception:
                continue
        
        # 按综合得分排序
        candidates.sort(key=lambda x: (x['底部得分'] + x['启动得分'], x['匹配度']), reverse=True)
        top_candidates = candidates[:limit]
        
        print(f"✅ V2扫描完成: 找到 {len(candidates)} 只候选，返回前 {len(top_candidates)} 只")
        
        return jsonify({
            'success': True,
            'message': f'找到 {len(candidates)} 只符合条件的个股',
            'total': len(candidates),
            'candidates': top_candidates,
            'model_info': {
                'model_type': 'bull_stock_v2',
                'feature_count': len(v2_model.feature_template),
                'sample_stocks': v2_model.sample_stocks
            }
        })
        
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"V2扫描错误: {error_detail}")
        return jsonify({
            'success': False,
            'message': f'扫描失败: {str(e)}'
        }), 500


@app.route('/api/scan_reversal_stocks', methods=['POST'])
@require_login
def scan_reversal_stocks():
    """搜索上周阴线+本周阳线的反转个股API"""
    init_analyzer()  # 确保分析器已初始化
    try:
        # 获取请求参数
        data = request.get_json(silent=True) or {}
        market_cap_max = float(data.get('market_cap_max', 100.0))  # 默认100亿
        
        # 在后台线程中执行扫描（避免阻塞）
        import threading
        
        def run_reversal_scan():
            from technical_analysis import TechnicalAnalysis
            try:
                print(f"\n🔍 开始搜索：上周阴线+本周阳线的反转个股（市值 < {market_cap_max}亿元）...")
                
                # 获取所有股票列表
                stock_list = analyzer.fetcher.get_all_stocks()
                if stock_list is None or len(stock_list) == 0:
                    analyzer.reversal_scan_results = {
                        'success': False,
                        'message': '无法获取股票列表',
                        'stocks': []
                    }
                    return
                
                total_stocks = len(stock_list)
                candidates = []
                
                # 更新进度
                analyzer.progress = {
                    'type': 'reversal_scan',
                    'current': 0,
                    'total': total_stocks,
                    'status': '进行中',
                    'detail': '开始搜索反转个股...',
                    'percentage': 0,
                    'found': 0
                }
                
                import time as time_module
                for idx, (_, row) in enumerate(stock_list.iterrows(), 1):
                    # 检查是否被停止
                    if hasattr(analyzer, 'stop_scan') and analyzer.stop_scan:
                        analyzer.progress['status'] = '已停止'
                        break
                    
                    stock_code = str(row['code']) if 'code' in row else str(row.iloc[0])
                    stock_name = str(row['name']) if 'name' in row else stock_code
                    
                    # 更新进度
                    if idx % 10 == 0 or idx == total_stocks:
                        percentage = (idx / total_stocks) * 100
                        analyzer.progress['current'] = idx
                        analyzer.progress['percentage'] = round(percentage, 1)
                        analyzer.progress['detail'] = f'正在扫描 {stock_code} {stock_name}... ({idx}/{total_stocks}) | 已找到: {len(candidates)} 只'
                        analyzer.progress['found'] = len(candidates)
                        analyzer.progress['last_update_time'] = time_module.time()
                        print(f"[进度] {percentage:.1f}% - {idx}/{total_stocks} - 已找到: {len(candidates)} 只")
                    
                    try:
                        # 获取周K线数据（至少需要5周以计算5周均线）
                        weekly_df = analyzer.fetcher.get_weekly_kline(stock_code, period="3m")
                        if weekly_df is None or len(weekly_df) < 5:
                            continue
                        
                        # 获取最新两周的数据
                        last_week = weekly_df.iloc[-2]  # 上周
                        this_week = weekly_df.iloc[-1]  # 本周
                        
                        # 判断上周是否为阴线（收盘价 < 开盘价）
                        last_week_open = float(last_week.get('开盘', 0))
                        last_week_close = float(last_week.get('收盘', 0))
                        last_week_is_negative = last_week_close < last_week_open
                        
                        # 判断本周是否为阳线（收盘价 > 开盘价）
                        this_week_open = float(this_week.get('开盘', 0))
                        this_week_close = float(this_week.get('收盘', 0))
                        this_week_is_positive = this_week_close > this_week_open
                        
                        # 判断是否止跌（本周收盘价 >= 上周收盘价，或者本周涨幅 > 0）
                        this_week_change = float(this_week.get('涨跌幅', 0))
                        is_reversal = this_week_close >= last_week_close or this_week_change > 0
                        
                        # 计算5周均线（MA5）
                        ma5_series = TechnicalAnalysis.calculate_ma(weekly_df, period=5)
                        if ma5_series is None or len(ma5_series) == 0:
                            continue
                        
                        # 获取本周的5周均线值
                        ma5_value = ma5_series.iloc[-1]
                        if pd.isna(ma5_value) or ma5_value <= 0:
                            continue
                        
                        # 判断本周收盘价是否在5周均线之上
                        price_above_ma5 = this_week_close > ma5_value
                        
                        # 如果上周是阴线，本周是阳线，且止跌，且股价在5周均线之上，则检查市值
                        if last_week_is_negative and this_week_is_positive and is_reversal and price_above_ma5:
                            # 检查市值（市值 < market_cap_max亿）
                            # 使用线程和超时机制，避免阻塞
                            import threading
                            market_cap_result = [None]
                            
                            def fetch_market_cap():
                                try:
                                    market_cap_result[0] = analyzer.fetcher.get_market_cap(stock_code, timeout=2)
                                except Exception:
                                    pass  # 静默失败
                            
                            cap_thread = threading.Thread(target=fetch_market_cap)
                            cap_thread.daemon = True
                            cap_thread.start()
                            cap_thread.join(timeout=2.5)  # 最多等待2.5秒，给足够时间获取市值
                            
                            market_cap = None
                            if not cap_thread.is_alive():
                                market_cap = market_cap_result[0]
                            
                            # 如果市值获取失败或超时，跳过该股票（无法确认是否符合条件）
                            if market_cap is None:
                                continue  # 市值获取失败，跳过
                            
                            # 如果市值获取成功且 >= market_cap_max，跳过
                            if market_cap >= market_cap_max:
                                continue  # 市值 >= market_cap_max，跳过
                            
                            last_week_date = str(last_week.get('日期', ''))
                            this_week_date = str(this_week.get('日期', ''))
                            
                            # 计算涨幅
                            last_week_change = float(last_week.get('涨跌幅', 0))
                            this_week_change = float(this_week.get('涨跌幅', 0))
                            
                            # 计算价格相对MA5的百分比
                            price_to_ma5_ratio = (this_week_close - ma5_value) / ma5_value * 100
                            
                            # 只有市值获取成功且小于market_cap_max的股票才会被加入结果
                            candidates.append({
                                '股票代码': stock_code,
                                '股票名称': stock_name,
                                '上周日期': last_week_date,
                                '上周开盘': round(last_week_open, 2),
                                '上周收盘': round(last_week_close, 2),
                                '上周涨跌幅': round(last_week_change, 2),
                                '本周日期': this_week_date,
                                '本周开盘': round(this_week_open, 2),
                                '本周收盘': round(this_week_close, 2),
                                '本周涨跌幅': round(this_week_change, 2),
                                '当前价格': round(this_week_close, 2),
                                '5周均线': round(ma5_value, 2),
                                '价格相对MA5': round(price_to_ma5_ratio, 2),
                                '市值': round(market_cap, 2)  # 此时market_cap一定不为None
                            })
                            
                            print(f"✅ 找到反转个股: {stock_code} {stock_name} (上周: {last_week_change:.2f}%, 本周: {this_week_change:.2f}%, MA5: {ma5_value:.2f}, 价格相对MA5: {price_to_ma5_ratio:.2f}%, 市值: {market_cap:.2f}亿)")
                    
                    except Exception as e:
                        # 单个股票出错，继续扫描下一个
                        if idx % 100 == 0:
                            print(f"⚠️ {stock_code} 扫描出错: {str(e)[:50]}")
                        continue
                
                # 扫描完成
                analyzer.reversal_scan_results = {
                    'success': True,
                    'message': f'扫描完成，找到 {len(candidates)} 只反转个股',
                    'stocks': candidates,
                    'total_scanned': total_stocks,
                    'found_count': len(candidates),
                    'market_cap_max': market_cap_max,
                    'conditions': {
                        '上周阴线': '收盘价 < 开盘价',
                        '本周阳线': '收盘价 > 开盘价',
                        '本周止跌': '本周收盘价 ≥ 上周收盘价，或本周涨幅 > 0',
                        '股价在MA5之上': '当前价格 > 5周均线',
                        '市值限制': f'市值 < {market_cap_max}亿元'
                    }
                }
                
                # 更新进度为完成
                analyzer.progress['status'] = '完成'
                analyzer.progress['percentage'] = 100.0
                analyzer.progress['current'] = total_stocks
                analyzer.progress['found'] = len(candidates)
                analyzer.progress['detail'] = f'扫描完成: 找到 {len(candidates)} 只反转个股'
                analyzer.progress['last_update_time'] = time_module.time()
                
                print(f"\n✅ 反转个股扫描完成！找到 {len(candidates)} 只符合条件的股票")
                
            except Exception as e:
                import traceback
                error_detail = traceback.format_exc()
                print(f"反转个股扫描过程出错: {error_detail}")
                analyzer.reversal_scan_results = {
                    'success': False,
                    'message': f'扫描出错: {str(e)}',
                    'stocks': []
                }
                analyzer.progress['status'] = '失败'
                analyzer.progress['detail'] = f'扫描出错: {str(e)[:50]}'
        
        # 启动扫描线程
        scan_thread = threading.Thread(target=run_reversal_scan)
        scan_thread.daemon = True
        scan_thread.start()
        
        return jsonify({
            'success': True,
            'message': '反转个股扫描已开始，请通过进度API查看进度'
        })
        
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"反转个股扫描错误: {error_detail}")
        return jsonify({
            'success': False,
            'message': f'服务器错误: {str(e)}'
        }), 500


@app.route('/api/get_reversal_scan_results', methods=['GET'])
@require_login
def get_reversal_scan_results():
    """获取反转个股扫描结果API"""
    try:
        init_analyzer()  # 确保分析器已初始化
        results = getattr(analyzer, 'reversal_scan_results', None)
        
        if results is None:
            return jsonify({
                'success': False,
                'message': '暂无扫描结果',
                'stocks': []
            })
        
        return jsonify(results)
        
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"获取反转个股扫描结果错误: {error_detail}")
        return jsonify({
            'success': False,
            'message': f'服务器错误: {str(e)}',
            'stocks': []
        }), 500

@app.route('/api/export_scan_results', methods=['POST'])
@require_login
def export_scan_results():
    """导出扫描结果API（支持Excel/CSV/JSON格式）- VIP专享功能"""
    try:
        import pandas as pd
        import json as json_module
        from datetime import datetime
        import io
        
        # 获取用户信息和等级
        user = get_current_user()
        if not user:
            return jsonify({
                'success': False,
                'message': '请先登录'
            }), 401
        
        user_tier = get_user_tier()
        
        # 检查用户等级（仅VIP和超级用户可以导出）
        if user_tier != 'premium' and user_tier != 'super':
            is_super = user.get('is_super', False)
            if not is_super:
                return jsonify({
                    'success': False,
                    'message': '导出功能仅限VIP用户使用，请升级为VIP会员'
                }), 403
        
        data = request.get_json(silent=True) or {}
        
        # 获取参数
        export_format = data.get('format', 'excel').lower()  # excel, csv, json
        scan_id = data.get('scan_id') or request.args.get('scan_id')
        candidates = data.get('candidates', [])
        
        # 如果没有提供candidates，尝试从scan_id获取
        if not candidates and scan_id and is_vercel:
            import scan_progress_store
            results = scan_progress_store.get_scan_results(scan_id)
            if results:
                candidates = results.get('candidates', [])
        
        # 如果还是没有数据，返回错误
        if not candidates:
            return jsonify({
                'success': False,
                'message': '没有可导出的数据，请先扫描股票或提供扫描结果'
            }), 400
        
        # 转换为DataFrame（处理不同的数据格式）
        df_data = []
        for candidate in candidates:
            # 处理两种数据格式：{'code': '...', 'name': '...'} 或 {'股票代码': '...', '股票名称': '...'}
            row = {
                '股票代码': candidate.get('code') or candidate.get('股票代码', ''),
                '股票名称': candidate.get('name') or candidate.get('股票名称', ''),
                '匹配度': float(candidate.get('match_score') or candidate.get('匹配度') or 0),
                '买点价格': float(candidate.get('buy_price') or candidate.get('买点价格') or candidate.get('最佳买点价格') or 0),
                '买点日期': candidate.get('buy_date') or candidate.get('买点日期') or candidate.get('最佳买点日期') or '',
                '当前价格': float(candidate.get('current_price') or candidate.get('当前价格') or 0),
                '市值(亿)': float(candidate.get('market_cap') or candidate.get('市值') or candidate.get('市值(亿)') or 0),
            }
            
            # 可选字段
            if candidate.get('gain_4w') is not None or candidate.get('4周涨幅') is not None:
                row['4周涨幅(%)'] = float(candidate.get('gain_4w') or candidate.get('4周涨幅') or 0)
            if candidate.get('gain_10w') is not None or candidate.get('10周涨幅') is not None:
                row['10周涨幅(%)'] = float(candidate.get('gain_10w') or candidate.get('10周涨幅') or 0)
            if candidate.get('gain_20w') is not None or candidate.get('20周涨幅') is not None:
                row['20周涨幅(%)'] = float(candidate.get('gain_20w') or candidate.get('20周涨幅') or 0)
            if candidate.get('max_gain_10w') is not None or candidate.get('最大涨幅') is not None:
                row['最大涨幅(%)'] = float(candidate.get('max_gain_10w') or candidate.get('最大涨幅') or 0)
            if candidate.get('stop_loss_price') is not None or candidate.get('止损价格') is not None:
                row['止损价格'] = float(candidate.get('stop_loss_price') or candidate.get('止损价格') or 0)
            if candidate.get('best_sell_price') is not None or candidate.get('最佳卖点价格') is not None:
                row['最佳卖点价格'] = float(candidate.get('best_sell_price') or candidate.get('最佳卖点价格') or 0)
            if candidate.get('best_sell_date') is not None or candidate.get('最佳卖点日期') is not None:
                row['最佳卖点日期'] = candidate.get('best_sell_date') or candidate.get('最佳卖点日期') or ''
            
            df_data.append(row)
        
        df = pd.DataFrame(df_data)
        
        # 按匹配度排序
        if '匹配度' in df.columns and len(df) > 0:
            df = df.sort_values('匹配度', ascending=False)
        
        # 生成文件名
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        if export_format == 'excel':
            # Excel格式
            filename = f'扫描结果_{timestamp}.xlsx'
            output = io.BytesIO()
            
            # 使用openpyxl引擎
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='扫描结果')
            
            output.seek(0)
            
            return send_file(
                output,
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                as_attachment=True,
                download_name=filename
            )
            
        elif export_format == 'csv':
            # CSV格式
            filename = f'扫描结果_{timestamp}.csv'
            output = io.StringIO()
            df.to_csv(output, index=False, encoding='utf-8-sig')  # utf-8-sig用于Excel正确识别中文
            csv_content = output.getvalue()
            output.close()
            
            # 创建BytesIO对象
            output_bytes = io.BytesIO()
            output_bytes.write(csv_content.encode('utf-8-sig'))
            output_bytes.seek(0)
            
            return send_file(
                output_bytes,
                mimetype='text/csv; charset=utf-8',
                as_attachment=True,
                download_name=filename
            )
            
        elif export_format == 'json':
            # JSON格式
            filename = f'扫描结果_{timestamp}.json'
            output = io.BytesIO()
            
            # 转换为JSON（确保可以序列化）
            json_data = df.to_dict(orient='records')
            json_str = json_module.dumps(json_data, ensure_ascii=False, indent=2, default=str)
            output.write(json_str.encode('utf-8'))
            output.seek(0)
            
            return send_file(
                output,
                mimetype='application/json; charset=utf-8',
                as_attachment=True,
                download_name=filename
            )
        else:
            return jsonify({
                'success': False,
                'message': f'不支持的导出格式: {export_format}，支持格式: excel, csv, json'
            }), 400
            
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"导出扫描结果错误: {error_detail}")
        return jsonify({
            'success': False,
            'message': f'导出失败: {str(e)}'
        }), 500


@app.route('/api/get_vip_scan_history', methods=['GET'])
@require_login
def get_vip_scan_history():
    """获取VIP用户扫描历史记录（30天）- VIP专享功能"""
    try:
        import json as json_module
        from scan_limit_helper import get_beijing_time
        from datetime import timedelta
        import scan_progress_store
        
        # 获取用户信息和等级
        user = get_current_user()
        if not user:
            return jsonify({
                'success': False,
                'message': '请先登录'
            }), 401
        
        user_tier = get_user_tier()
        username = user.get('username', 'anonymous')
        
        # 检查用户等级（仅VIP和超级用户可以查看历史记录）
        if user_tier != 'premium' and user_tier != 'super':
            is_super = user.get('is_super', False)
            if not is_super:
                return jsonify({
                    'success': False,
                    'message': '历史记录功能仅限VIP用户使用，请升级为VIP会员'
                }), 403
        
        beijing_now = get_beijing_time()
        history_results = []
        
        # 获取最近30天的扫描历史
        for i in range(30):
            date = (beijing_now - timedelta(days=i))
            date_str = date.strftime('%Y-%m-%d')
            
            # 查找该用户的扫描结果（格式：user_scan_history:{username}:{date}）
            user_scan_key = f'user_scan_history:{username}:{date_str}'
            
            if is_vercel:
                # Vercel环境：从Redis获取
                scan_ids = []
                try:
                    # 尝试获取该用户当天的所有扫描ID列表
                    scan_ids_data = scan_progress_store._upstash_redis_get(user_scan_key) if hasattr(scan_progress_store, '_upstash_redis_get') else None
                    if scan_ids_data:
                        if isinstance(scan_ids_data, list):
                            scan_ids = scan_ids_data
                        elif isinstance(scan_ids_data, str):
                            try:
                                scan_ids = json_module.loads(scan_ids_data)
                            except:
                                scan_ids = [scan_ids_data]
                        else:
                            scan_ids = [scan_ids_data]
                except Exception as e:
                    print(f"[get_vip_scan_history] 获取扫描ID列表失败: {e}")
                    scan_ids = []
                
                # 获取每个扫描的结果
                for scan_id in scan_ids[:5]:  # 每天最多显示5次扫描
                    if not scan_id:
                        continue
                    results = scan_progress_store.get_scan_results(scan_id)
                    if results:
                        progress = scan_progress_store.get_scan_progress(scan_id)
                        if progress and progress.get('username') == username:
                            # 格式化时间
                            scan_time = progress.get('last_update_time') or progress.get('completed_at', '')
                            if isinstance(scan_time, (int, float)):
                                from datetime import datetime
                                scan_time_str = datetime.fromtimestamp(scan_time).strftime('%Y-%m-%d %H:%M:%S') if scan_time > 1000000000 else ''
                            else:
                                scan_time_str = str(scan_time)
                            
                            history_results.append({
                                'date': date_str,
                                'scan_id': scan_id,
                                'found_count': results.get('found_count', 0),
                                'total_scanned': results.get('total_scanned', 0),
                                'scan_time': scan_time_str,
                                'completed_at': results.get('completed_at', scan_time_str),
                                'candidates_count': len(results.get('candidates', [])),
                                'candidates': results.get('candidates', [])[:10]  # 只返回前10只股票
                            })
            else:
                # 本地环境：从文件读取（TODO: 实现本地历史记录存储）
                pass
        
        # 按日期和扫描时间排序（最新的在前）
        history_results.sort(key=lambda x: (x.get('date', ''), x.get('scan_time', '')), reverse=True)
        
        return jsonify({
            'success': True,
            'message': f'找到 {len(history_results)} 条历史记录',
            'history': history_results,
            'total_days': 7
        })
        
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"获取VIP扫描历史错误: {error_detail}")
        return jsonify({
            'success': False,
            'message': f'获取历史记录失败: {str(e)}',
            'history': []
        }), 500


@app.route('/api/add_to_watchlist', methods=['POST'])
@require_login
def add_to_watchlist():
    """添加到关注列表（VIP专享功能）"""
    try:
        import watchlist_store
        
        # 获取用户信息和等级
        user = get_current_user()
        if not user:
            return jsonify({
                'success': False,
                'message': '请先登录'
            }), 401
        
        user_tier = get_user_tier()
        username = user.get('username', 'anonymous')
        
        # 检查用户等级（仅VIP和超级用户可以使用关注列表）
        if user_tier != 'premium' and user_tier != 'super':
            is_super = user.get('is_super', False)
            if not is_super:
                return jsonify({
                    'success': False,
                    'message': '关注列表功能仅限VIP用户使用，请升级为VIP会员'
                }), 403
        
        data = request.get_json(silent=True) or {}
        stock_info = data.get('stock_info', {})
        
        if not stock_info:
            return jsonify({
                'success': False,
                'message': '股票信息不能为空'
            }), 400
        
        # 添加到关注列表
        success = watchlist_store.add_to_watchlist(username, stock_info)
        
        if success:
            return jsonify({
                'success': True,
                'message': '已添加到关注列表'
            })
        else:
            # 检查是否是已存在或已达到上限
            watchlist = watchlist_store.get_watchlist(username)
            if len(watchlist) >= 50:
                return jsonify({
                    'success': False,
                    'message': '关注列表已满（最多50只股票），请先删除一些股票'
                }), 400
            else:
                return jsonify({
                    'success': False,
                    'message': '该股票已在关注列表中'
                }), 400
        
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"[add_to_watchlist] ❌ 添加关注列表失败: {error_detail}")
        return jsonify({
            'success': False,
            'message': f'添加关注列表失败: {str(e)}'
        }), 500


@app.route('/api/remove_from_watchlist', methods=['POST'])
@require_login
def remove_from_watchlist():
    """从关注列表删除（VIP专享功能）"""
    try:
        import watchlist_store
        
        # 获取用户信息和等级
        user = get_current_user()
        if not user:
            return jsonify({
                'success': False,
                'message': '请先登录'
            }), 401
        
        user_tier = get_user_tier()
        username = user.get('username', 'anonymous')
        
        # 检查用户等级（仅VIP和超级用户可以使用关注列表）
        if user_tier != 'premium' and user_tier != 'super':
            is_super = user.get('is_super', False)
            if not is_super:
                return jsonify({
                    'success': False,
                    'message': '关注列表功能仅限VIP用户使用，请升级为VIP会员'
                }), 403
        
        data = request.get_json(silent=True) or {}
        stock_code = (data.get('stock_code') or '').strip()
        
        if not stock_code:
            return jsonify({
                'success': False,
                'message': '股票代码不能为空'
            }), 400
        
        # 从关注列表删除
        success = watchlist_store.remove_from_watchlist(username, stock_code)
        
        if success:
            return jsonify({
                'success': True,
                'message': '已从关注列表删除'
            })
        else:
            return jsonify({
                'success': False,
                'message': '删除失败'
            }), 400
        
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"[remove_from_watchlist] ❌ 删除关注列表失败: {error_detail}")
        return jsonify({
            'success': False,
            'message': f'删除关注列表失败: {str(e)}'
        }), 500


@app.route('/api/get_watchlist', methods=['GET'])
@require_login
def get_watchlist():
    """获取关注列表（VIP专享功能）"""
    try:
        import watchlist_store
        
        # 获取用户信息和等级
        user = get_current_user()
        if not user:
            return jsonify({
                'success': False,
                'message': '请先登录'
            }), 401
        
        user_tier = get_user_tier()
        username = user.get('username', 'anonymous')
        
        # 检查用户等级（仅VIP和超级用户可以使用关注列表）
        if user_tier != 'premium' and user_tier != 'super':
            is_super = user.get('is_super', False)
            if not is_super:
                return jsonify({
                    'success': False,
                    'message': '关注列表功能仅限VIP用户使用，请升级为VIP会员'
                }), 403
        
        # 获取关注列表
        watchlist = watchlist_store.get_watchlist(username)
        
        # 可选：更新当前价格（如果需要）
        # 这里暂时不更新，用户可以在查看时手动刷新
        
        return jsonify({
            'success': True,
            'message': f'找到 {len(watchlist)} 只关注的股票',
            'watchlist': watchlist,
            'count': len(watchlist),
            'max_count': 50
        })
        
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"[get_watchlist] ❌ 获取关注列表失败: {error_detail}")
        return jsonify({
            'success': False,
            'message': f'获取关注列表失败: {str(e)}',
            'watchlist': []
        }), 500


@app.route('/api/set_price_alert', methods=['POST'])
@require_login
def set_price_alert():
    """设置价格预警（VIP专享功能）"""
    try:
        import watchlist_store
        
        # 获取用户信息和等级
        user = get_current_user()
        if not user:
            return jsonify({
                'success': False,
                'message': '请先登录'
            }), 401
        
        user_tier = get_user_tier()
        username = user.get('username', 'anonymous')
        
        # 检查用户等级（仅VIP和超级用户可以使用价格预警）
        if user_tier != 'premium' and user_tier != 'super':
            is_super = user.get('is_super', False)
            if not is_super:
                return jsonify({
                    'success': False,
                    'message': '价格预警功能仅限VIP用户使用，请升级为VIP会员'
                }), 403
        
        data = request.get_json(silent=True) or {}
        stock_code = (data.get('stock_code') or '').strip()
        stock_name = data.get('stock_name', '').strip()
        price_high = data.get('price_high')  # 价格上限（可选）
        price_low = data.get('price_low')  # 价格下限（可选）
        
        if not stock_code:
            return jsonify({
                'success': False,
                'message': '股票代码不能为空'
            }), 400
        
        if price_high is None and price_low is None:
            return jsonify({
                'success': False,
                'message': '请至少设置价格上限或下限'
            }), 400
        
        # 构建预警信息
        alert_info = {
            'stock_code': stock_code,
            'stock_name': stock_name,
            'price_high': float(price_high) if price_high is not None else None,
            'price_low': float(price_low) if price_low is not None else None
        }
        
        # 保存价格预警
        success = watchlist_store.save_price_alert(username, alert_info)
        
        if success:
            return jsonify({
                'success': True,
                'message': '价格预警设置成功'
            })
        else:
            return jsonify({
                'success': False,
                'message': '价格预警设置失败'
            }), 500
        
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"[set_price_alert] ❌ 设置价格预警失败: {error_detail}")
        return jsonify({
            'success': False,
            'message': f'设置价格预警失败: {str(e)}'
        }), 500


@app.route('/api/get_price_alerts', methods=['GET'])
@require_login
def get_price_alerts():
    """获取价格预警列表（VIP专享功能）"""
    try:
        import watchlist_store
        
        # 获取用户信息和等级
        user = get_current_user()
        if not user:
            return jsonify({
                'success': False,
                'message': '请先登录'
            }), 401
        
        user_tier = get_user_tier()
        username = user.get('username', 'anonymous')
        
        # 检查用户等级（仅VIP和超级用户可以使用价格预警）
        if user_tier != 'premium' and user_tier != 'super':
            is_super = user.get('is_super', False)
            if not is_super:
                return jsonify({
                    'success': False,
                    'message': '价格预警功能仅限VIP用户使用，请升级为VIP会员'
                }), 403
        
        # 获取价格预警列表
        alerts = watchlist_store.get_price_alerts(username)
        
        return jsonify({
            'success': True,
            'message': f'找到 {len(alerts)} 个价格预警',
            'alerts': alerts,
            'count': len(alerts)
        })
        
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"[get_price_alerts] ❌ 获取价格预警失败: {error_detail}")
        return jsonify({
            'success': False,
            'message': f'获取价格预警失败: {str(e)}',
            'alerts': []
        }), 500


@app.route('/api/remove_price_alert', methods=['POST'])
@require_login
def remove_price_alert():
    """删除价格预警（VIP专享功能）"""
    try:
        import watchlist_store
        
        # 获取用户信息和等级
        user = get_current_user()
        if not user:
            return jsonify({
                'success': False,
                'message': '请先登录'
            }), 401
        
        user_tier = get_user_tier()
        username = user.get('username', 'anonymous')
        
        # 检查用户等级（仅VIP和超级用户可以使用价格预警）
        if user_tier != 'premium' and user_tier != 'super':
            is_super = user.get('is_super', False)
            if not is_super:
                return jsonify({
                    'success': False,
                    'message': '价格预警功能仅限VIP用户使用，请升级为VIP会员'
                }), 403
        
        data = request.get_json(silent=True) or {}
        stock_code = (data.get('stock_code') or '').strip()
        
        if not stock_code:
            return jsonify({
                'success': False,
                'message': '股票代码不能为空'
            }), 400
        
        # 删除价格预警
        success = watchlist_store.remove_price_alert(username, stock_code)
        
        if success:
            return jsonify({
                'success': True,
                'message': '价格预警已删除'
            })
        else:
            return jsonify({
                'success': False,
                'message': '删除失败'
            }), 400
        
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"[remove_price_alert] ❌ 删除价格预警失败: {error_detail}")
        return jsonify({
            'success': False,
            'message': f'删除价格预警失败: {str(e)}'
        }), 500


@app.route('/api/search_stock', methods=['POST'])
@require_login
def search_stock():
    """个股检索API - 根据代码或名称搜索股票"""
    try:
        data = request.get_json(silent=True)
        if not data:
            return jsonify({
                'success': False,
                'message': '请求数据为空'
            }), 400
        
        search_keyword = (data.get('keyword') or '').strip()
        if not search_keyword:
            return jsonify({
                'success': False,
                'message': '请输入股票代码或名称'
            }), 400
        
        init_analyzer()
        if analyzer is None or analyzer.fetcher is None:
            return jsonify({
                'success': False,
                'message': '分析器未初始化'
            }), 500
        
        # 获取所有股票列表
        stock_list = analyzer.fetcher.get_all_stocks(timeout=15, max_retries=3)
        if stock_list is None or len(stock_list) == 0:
            return jsonify({
                'success': False,
                'message': '无法获取股票列表'
            }), 500
        
        # 搜索匹配的股票
        results = []
        search_keyword_lower = search_keyword.lower()
        
        for _, row in stock_list.iterrows():
            code = str(row.get('code', '')).strip()
            name = str(row.get('name', '')).strip()
            
            # 匹配代码或名称
            if (search_keyword_lower in code.lower() or 
                search_keyword_lower in name.lower()):
                results.append({
                    'code': code,
                    'name': name
                })
                
                # 限制返回结果数量，避免过多
                if len(results) >= 50:
                    break
        
        return jsonify({
            'success': True,
            'results': results,
            'count': len(results),
            'keyword': search_keyword
        })
        
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"个股检索错误: {error_detail}")
        return jsonify({
            'success': False,
            'message': f'检索失败: {str(e)}'
        }), 500


@app.route('/api/update_data_from_sina', methods=['GET', 'POST'])
def update_data_from_sina():
    """
    午盘/尾盘后从新浪更新 K 线数据的 API
    支持分批处理（适配 Vercel 10 秒限制）
    
    使用方式：
    - 手动触发：GET /api/update_data_from_sina?force=true
    - 分批处理：GET /api/update_data_from_sina?batch=0&batch_size=50
    - Cron 自动：由 vercel.json 配置的 cron job 调用（注意：Vercel Hobby 每天只能运行 1 次 cron，建议使用外部服务）
    """
    try:
        from api.update_data_from_sina import handler
        # 将 Flask request 对象传递给 handler
        return handler(request)
    except ImportError as e:
        # 如果导入失败，返回错误
        import traceback
        error_detail = traceback.format_exc()
        print(f"[update_data_from_sina] ❌ 导入失败: {error_detail}")
        return jsonify({
            'success': False,
            'message': f'更新模块导入失败: {str(e)}',
            'error_detail': error_detail[:500] if len(error_detail) > 500 else error_detail
        }), 500
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"[update_data_from_sina] ❌ 错误: {error_detail}")
        return jsonify({
            'success': False,
            'message': f'更新数据失败: {str(e)}',
            'error_detail': error_detail[:500] if len(error_detail) > 500 else error_detail
        }), 500

@app.route('/api/refresh_stock_cache', methods=['GET', 'POST'])
def refresh_stock_cache():
    """
    刷新股票列表缓存的 Cron Job 端点
    
    注意：由于 Vercel Hobby 账户限制每天只能运行一次 cron job，
    因此配置为每个交易日 9:25（开盘前）自动刷新一次。
    
    如果需要更频繁的刷新（如交易时间段内每5分钟），可以：
    1. 手动访问 /api/refresh_stock_cache?force=true
    2. 使用外部服务（如 GitHub Actions、UptimeRobot）定期调用此API
    3. 升级到 Vercel Pro 计划以解锁更多 cron job 功能
    
    也允许手动触发刷新（无需登录，建议在交易时间段使用）
    """
    try:
        from datetime import datetime, timezone, timedelta
        
        def get_beijing_time():
            """获取北京时间（UTC+8）"""
            utc_now = datetime.now(timezone.utc)
            beijing_tz = timezone(timedelta(hours=8))
            beijing_now = utc_now.astimezone(beijing_tz)
            return beijing_now
        
        def is_trading_time(beijing_now):
            """
            判断是否在交易时间段（9:30-11:30, 13:00-15:00）或盘后时间（15:05）
            也允许在开盘前（9:25）执行，因为Hobby账户限制每天只能运行一次cron job
            """
            current_hour = beijing_now.hour
            current_minute = beijing_now.minute
            
            # 开盘前：9:25（允许执行，因为cron job在这个时间运行）
            if current_hour == 9 and current_minute == 25:
                return True
            
            # 上午交易时间：9:30-11:30
            if current_hour == 9 and current_minute >= 30:
                return True
            if current_hour == 10:
                return True
            if current_hour == 11 and current_minute <= 30:
                return True
            
            # 下午交易时间：13:00-15:00
            if current_hour == 13 or current_hour == 14:
                return True
            if current_hour == 15 and current_minute == 0:
                return True
            
            # 盘后时间：15:05（允许手动触发）
            if current_hour == 15 and current_minute == 5:
                return True
            
            return False
        
        beijing_now = get_beijing_time()
        current_time_str = beijing_now.strftime('%Y-%m-%d %H:%M:%S')
        
        # 检查是否在交易时间或盘后时间（如果不是，仍然允许手动触发，但给出警告）
        is_in_trading_time = is_trading_time(beijing_now)
        _j = request.get_json(silent=True)
        force_refresh = request.args.get('force', '').lower() == 'true' or (_j and _j.get('force', False))
        
        if not is_in_trading_time and not force_refresh:
            return jsonify({
                'success': False,
                'message': f'当前时间不在允许的执行时间（当前时间: {current_time_str}）\n\n允许的时间：\n- 9:25（开盘前，自动cron job）\n- 9:30-11:30, 13:00-15:00（交易时间段，需手动触发）\n- 15:05（盘后，需手动触发）\n\n如需强制刷新，请使用 ?force=true 参数',
                'current_time': current_time_str,
                'allowed_times': {
                    'auto_cron': '9:25（开盘前，每天一次）',
                    'trading_hours': '9:30-11:30, 13:00-15:00（需手动触发或使用外部服务）',
                    'after_market': '15:05（盘后，需手动触发）'
                },
                'note': '由于 Vercel Hobby 账户限制每天只能运行一次 cron job，交易时间段内的刷新需要手动触发或使用外部服务',
                'force_refresh': False
            }), 200
        
        print(f"[refresh_stock_cache] 开始刷新股票列表缓存 - 时间: {current_time_str}")
        
        # 确保分析器已初始化
        init_analyzer()
        
        if analyzer is None or analyzer.fetcher is None:
            return jsonify({
                'success': False,
                'message': '分析器未初始化',
                'current_time': current_time_str
            }), 500
        
        # ✅ 在 Vercel 环境中，优先从 K 线文件生成缓存（USE_GITHUB_DATA_ONLY 模式）
        if is_vercel or analyzer.fetcher._use_github_data_only:
            print("[refresh_stock_cache] Vercel 环境检测到，优先从 K 线文件生成缓存...")
            
            # 先确保数据包已下载（在 Vercel 环境中，首次请求时可能还未下载）
            _ensure_stock_data_downloaded()
            
            # 检查 K 线文件目录是否存在（Vercel 下从 LOCAL_CACHE_DIR 读 /tmp/cache）
            cache_dir = os.environ.get('LOCAL_CACHE_DIR') or os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cache')
            weekly_dir = os.path.join(cache_dir, 'weekly_kline')
            daily_dir = os.path.join(cache_dir, 'daily_kline')
            
            weekly_exists = os.path.exists(weekly_dir) and os.listdir(weekly_dir) if os.path.exists(weekly_dir) else False
            daily_exists = os.path.exists(daily_dir) and os.listdir(daily_dir) if os.path.exists(daily_dir) else False
            
            if not weekly_exists and not daily_exists:
                # K 线目录不存在时，先尝试在本请求内拉取数据包（解决多实例 / 冷启动未拉取到的情况）
                if os.environ.get('STOCK_DATA_URL') and is_vercel:
                    print("[refresh_stock_cache] K 线缺失，先在本请求内拉取数据包...")
                    try:
                        from fetch_github_cache import fetch_github_cache
                        fetch_github_cache(skip_if_exists=False, root_dir='/tmp', timeout=120)
                    except Exception as fe:
                        print(f"[refresh_stock_cache] 拉取数据包异常: {fe}")
                    weekly_exists = os.path.exists(weekly_dir) and os.listdir(weekly_dir) if os.path.exists(weekly_dir) else False
                    daily_exists = os.path.exists(daily_dir) and os.listdir(daily_dir) if os.path.exists(daily_dir) else False
                if not weekly_exists and not daily_exists:
                    error_msg = '⚠️ **K 线数据尚未就绪**\n\n'
                    error_msg += '首次访问或冷启动时，数据包下载约需 1–2 分钟。\n\n'
                    error_msg += '**请先点击「打开预热页」，等待 1–2 分钟完成后关闭，再立即扫描；**\n'
                    error_msg += '或 2 分钟后再点击「手动刷新缓存」重试。\n\n'
                    error_msg += '若仍失败，请检查：\n'
                    error_msg += '1. Vercel 环境变量 `STOCK_DATA_URL` 已设置\n'
                    error_msg += '2. Vercel 部署日志中是否有「✅ 数据下载并解压成功」\n'
                    print(f"[refresh_stock_cache] ❌ K 线数据文件不存在: weekly_dir={weekly_dir}, daily_dir={daily_dir}")
                    return jsonify({
                        'success': False,
                        'message': error_msg,
                        'current_time': current_time_str,
                        'is_vercel': True,
                        'weekly_dir_exists': weekly_exists,
                        'daily_dir_exists': daily_exists,
                        'suggestion': '打开预热页或 2 分钟后再试刷新'
                    }), 200
            
            # K 线文件存在，尝试生成股票列表
            try:
                from generate_stock_list_from_files import generate_stock_list_from_kline_files
                print(f"[refresh_stock_cache] 开始从 K 线文件生成股票列表...")
                if generate_stock_list_from_kline_files():
                    # 验证缓存是否生成成功
                    cached_stocks = analyzer.fetcher._get_stock_list_from_cache(check_age=False)
                    if cached_stocks is not None and len(cached_stocks) > 0:
                        print(f"[refresh_stock_cache] ✅ 已从 K 线文件生成股票列表，股票数: {len(cached_stocks)} 只")
                        return jsonify({
                            'success': True,
                            'message': f'✅ 股票列表缓存已从 K 线文件生成，股票数: {len(cached_stocks)} 只\n\n现在可以正常扫描了！',
                            'stock_count': len(cached_stocks),
                            'current_time': current_time_str,
                            'method': 'from_kline_files',
                            'is_vercel': True
                        }), 200
                    else:
                        print("[refresh_stock_cache] ⚠️ 生成股票列表后，缓存仍为空")
                        error_msg = '⚠️ **生成股票列表失败**\n\n虽然 K 线文件存在，但缓存仍为空。请 2 分钟后再试刷新。'
                        return jsonify({
                            'success': False,
                            'message': error_msg,
                            'current_time': current_time_str,
                            'is_vercel': True,
                            'suggestion': '2 分钟后再试刷新'
                        }), 200
                else:
                    print("[refresh_stock_cache] ⚠️ 从 K 线文件生成股票列表失败（函数返回 False）")
                    error_msg = '⚠️ **生成股票列表失败**\n\n请 2 分钟后再试刷新。'
                    return jsonify({
                        'success': False,
                        'message': error_msg,
                        'current_time': current_time_str,
                        'is_vercel': True,
                        'suggestion': '2 分钟后再试刷新'
                    }), 200
            except Exception as gen_error:
                import traceback
                error_detail = traceback.format_exc()
                print(f"[refresh_stock_cache] ⚠️ 从 K 线文件生成股票列表时出错: {gen_error}")
                print(f"[refresh_stock_cache] 错误详情: {error_detail}")
                
                error_msg = f'⚠️ **生成股票列表时出错**\n\n{str(gen_error)}\n\n请 2 分钟后再试刷新。'
                return jsonify({
                    'success': False,
                    'message': error_msg,
                    'current_time': current_time_str,
                    'is_vercel': True,
                    'error': str(gen_error),
                    'error_type': type(gen_error).__name__,
                    'suggestion': '2 分钟后再试刷新'
                }), 200
        
        # 非 Vercel 环境：从 akshare API 获取股票列表（后台任务可以使用更长的超时）
        print("[refresh_stock_cache] 从 akshare API 获取股票列表...")
        # 注意：这是后台 Cron Job 任务，允许使用更长的超时时间
        # 直接调用 akshare API，不使用 get_all_stocks 的限制（因为它会自动限制 Vercel 环境的超时）
        # 添加重试机制，最多重试3次，处理网络连接错误（如 ConnectionResetError）
        import akshare as ak
        import threading
        import time as time_module
        import traceback
        
        max_retries = 3
        retry_delay = 2  # 重试间隔（秒）
        timeout = 30  # 单次尝试的超时时间（秒）
        stock_list = None
        
        for attempt in range(max_retries):
            try:
                result = [None]
                error = [None]
                start_time = time_module.time()
                
                def fetch_stocks():
                    try:
                        if attempt > 0:
                            print(f"[refresh_stock_cache] 重试第 {attempt + 1}/{max_retries} 次，调用 ak.stock_info_a_code_name()...")
                        else:
                            print("[refresh_stock_cache] 开始调用 ak.stock_info_a_code_name()...")
                        result[0] = ak.stock_info_a_code_name()
                        elapsed = time_module.time() - start_time
                        print(f"[refresh_stock_cache] ✅ ak.stock_info_a_code_name() 调用成功，耗时 {elapsed:.2f}秒")
                    except Exception as e:
                        error[0] = e
                        elapsed = time_module.time() - start_time
                        error_type = type(e).__name__
                        print(f"[refresh_stock_cache] ❌ 调用失败（耗时 {elapsed:.2f}秒，错误类型: {error_type}）: {e}")
                        if attempt < max_retries - 1:
                            print(f"[refresh_stock_cache] 错误详情: {traceback.format_exc()}")
                
                fetch_thread = threading.Thread(target=fetch_stocks)
                fetch_thread.daemon = True
                fetch_thread.start()
                fetch_thread.join(timeout=timeout)
                
                elapsed_total = time_module.time() - start_time
                
                if fetch_thread.is_alive():
                    print(f"[refresh_stock_cache] ⏱️ 获取超时（>{timeout}秒，实际耗时 {elapsed_total:.2f}秒）")
                    if attempt < max_retries - 1:
                        print(f"[refresh_stock_cache] 等待 {retry_delay} 秒后重试...")
                        time_module.sleep(retry_delay)
                        continue  # 重试
                    else:
                        return jsonify({
                            'success': False,
                            'message': f'获取股票列表超时（>{timeout}秒），已重试 {max_retries} 次，请稍后重试',
                            'current_time': current_time_str,
                            'retries': max_retries,
                            'error_type': 'timeout'
                        }), 500
                
                if error[0]:
                    error_type = type(error[0]).__name__
                    error_msg_str = str(error[0])
                    is_network_error = (
                        'Connection' in error_type or 
                        'Connection' in error_msg_str or
                        'reset' in error_msg_str.lower() or
                        'aborted' in error_msg_str.lower() or
                        'timeout' in error_msg_str.lower() or
                        '104' in error_msg_str  # Connection reset by peer (104)
                    )
                    
                    print(f"[refresh_stock_cache] ❌ 获取出错（耗时 {elapsed_total:.2f}秒，错误类型: {error_type}，网络错误: {is_network_error}）: {error[0]}")
                    
                    if is_network_error and attempt < max_retries - 1:
                        print(f"[refresh_stock_cache] 网络连接错误，等待 {retry_delay} 秒后重试（第 {attempt + 1}/{max_retries} 次）...")
                        time_module.sleep(retry_delay)
                        continue  # 重试
                    else:
                        # 最后一次尝试或非网络错误，返回错误
                        if is_network_error:
                            error_message = f'网络连接错误: {error_msg_str}\n\n已重试 {attempt + 1} 次，仍然失败。\n\n💡 **解决方案：**\n1. 稍后重试（可能是网络波动或 akshare 服务暂时不可用）\n2. 等待一段时间后再试（建议等待 1-2 分钟后重试）\n3. 如果问题持续，可能是 akshare 服务暂时不可用，请稍后再试'
                        else:
                            error_message = f'获取股票列表失败: {error_msg_str}'
                        
                        return jsonify({
                            'success': False,
                            'message': error_message,
                            'current_time': current_time_str,
                            'retries': attempt + 1,
                            'error_type': error_type,
                            'is_network_error': is_network_error
                        }), 500
                
                if result[0] is None or len(result[0]) == 0:
                    print(f"[refresh_stock_cache] ⚠️ 返回结果为空（耗时 {elapsed_total:.2f}秒）")
                    if attempt < max_retries - 1:
                        print(f"[refresh_stock_cache] 等待 {retry_delay} 秒后重试...")
                        time_module.sleep(retry_delay)
                        continue  # 重试
                    else:
                        return jsonify({
                            'success': False,
                            'message': f'获取股票列表失败: 返回结果为空（已重试 {max_retries} 次）',
                            'current_time': current_time_str,
                            'retries': max_retries,
                            'error_type': 'empty_result'
                        }), 500
                
                # 成功获取到数据，跳出重试循环
                stock_list = result[0]
                break
                
            except Exception as e:
                error_type = type(e).__name__
                error_detail = traceback.format_exc()
                print(f"[refresh_stock_cache] ❌ 外层异常（第 {attempt + 1}/{max_retries} 次）: {error_detail}")
                
                if attempt < max_retries - 1:
                    print(f"[refresh_stock_cache] 等待 {retry_delay} 秒后重试...")
                    time_module.sleep(retry_delay)
                    continue  # 重试
                else:
                    return jsonify({
                        'success': False,
                        'message': f'刷新股票列表缓存失败: {str(e)}（已重试 {max_retries} 次）',
                        'current_time': current_time_str,
                        'retries': max_retries,
                        'error_type': error_type,
                        'error_detail': error_detail
                    }), 500
        
        if stock_list is None:
            return jsonify({
                'success': False,
                'message': f'获取股票列表失败: 所有重试均失败（已重试 {max_retries} 次）',
                'current_time': current_time_str,
                'retries': max_retries,
                'error_type': 'all_retries_failed'
            }), 500
        
        # 成功获取到股票列表，开始保存到缓存
        try:
            # 将股票列表保存到缓存
            print(f"[refresh_stock_cache] 获取到 {len(stock_list)} 只股票，开始保存到缓存...")
            
            # 计算数据大小（用于调试）
            try:
                import json
                import pandas as pd
                stock_data = stock_list.to_dict('records')
                stock_json = json.dumps(stock_data, default=str, ensure_ascii=False)
                data_size_mb = len(stock_json.encode('utf-8')) / (1024 * 1024)
                print(f"[refresh_stock_cache] 数据大小: {data_size_mb:.2f} MB ({len(stock_json)} 字符)")
            except Exception as size_error:
                print(f"[refresh_stock_cache] ⚠️ 计算数据大小失败: {size_error}")
                data_size_mb = None
            
            cache_success = analyzer.fetcher._save_stock_list_to_cache(stock_list)
            if cache_success:
                print(f"[refresh_stock_cache] ✅ 股票列表已保存到缓存")
                # 更新分析器的股票列表
                analyzer.fetcher.stock_list = stock_list
                
                return jsonify({
                    'success': True,
                    'message': f'股票列表缓存已刷新（{len(stock_list)} 只股票）',
                    'stock_count': len(stock_list),
                    'current_time': current_time_str,
                    'cache_ttl': '24小时',
                    'data_size_mb': round(data_size_mb, 2) if data_size_mb else None
                }), 200
            else:
                print(f"[refresh_stock_cache] ❌ 保存到缓存失败，但已获取股票列表")
                # 即使保存失败，也更新分析器的股票列表（可以在当前请求中使用）
                analyzer.fetcher.stock_list = stock_list
                
                # 检查 Redis 和 Vercel KV 的可用性
                redis_available = bool(os.environ.get('UPSTASH_REDIS_REST_URL') and os.environ.get('UPSTASH_REDIS_REST_TOKEN'))
                vercel_kv_available = False
                try:
                    from vercel_kv import kv
                    vercel_kv_available = True
                except ImportError:
                    pass
                
                error_message = f'获取股票列表成功（{len(stock_list)} 只股票），但保存到缓存失败。'
                if data_size_mb and data_size_mb > 10:
                    error_message += f'\n\n⚠️ 数据较大（{data_size_mb:.2f} MB），可能超过存储限制。'
                if not redis_available and not vercel_kv_available:
                    error_message += '\n\n⚠️ Redis 和 Vercel KV 均不可用，请检查环境变量配置。'
                elif not redis_available:
                    error_message += '\n\n⚠️ Redis 不可用，已尝试使用 Vercel KV。'
                elif not vercel_kv_available:
                    error_message += '\n\n⚠️ Vercel KV 不可用，已尝试使用 Redis。'
                else:
                    error_message += '\n\n💡 可能的原因：\n1. 网络连接问题\n2. 数据过大\n3. 存储服务暂时不可用\n\n请稍后重试或检查 Vercel 日志。'
                
                return jsonify({
                    'success': False,
                    'message': error_message,
                    'stock_count': len(stock_list),
                    'current_time': current_time_str,
                    'cache_saved': False,
                    'error_type': 'cache_save_failed',
                    'data_size_mb': round(data_size_mb, 2) if data_size_mb else None,
                    'redis_available': redis_available,
                    'vercel_kv_available': vercel_kv_available
                }), 500
            
        except Exception as e:
            import traceback
            error_detail = traceback.format_exc()
            print(f"[refresh_stock_cache] ❌ 保存股票列表到缓存时异常: {error_detail}")
            return jsonify({
                'success': False,
                'message': f'保存股票列表到缓存时异常: {str(e)}',
                'error': error_detail,
                'current_time': current_time_str
            }), 500
            
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"[refresh_stock_cache] ❌ 错误: {error_detail}")
        from datetime import datetime, timezone, timedelta
        try:
            utc_now = datetime.now(timezone.utc)
            beijing_tz = timezone(timedelta(hours=8))
            beijing_now = utc_now.astimezone(beijing_tz)
            current_time_str = beijing_now.strftime('%Y-%m-%d %H:%M:%S')
        except:
            current_time_str = 'unknown'
        
        return jsonify({
            'success': False,
            'message': f'刷新股票列表缓存失败: {str(e)}',
            'error': error_detail,
            'current_time': current_time_str
        }), 500


@app.route('/api/get_weekly_kline_for_stock', methods=['POST'])
@require_login
def get_weekly_kline_for_stock():
    """获取指定股票的周K线数据（用于在反转个股结果中显示）"""
    init_analyzer()
    try:
        data = request.json
        stock_code = data.get('code', '').strip()
        
        if not stock_code:
            return jsonify({'error': '请输入股票代码'}), 400
        
        # 获取周K线数据
        weekly_df = analyzer.fetcher.get_weekly_kline(stock_code, period="2y")
        if weekly_df is None or len(weekly_df) == 0:
            return jsonify({'error': '无法获取周K线数据'}), 500
        
        # 计算技术指标（按需导入，减轻冷启动）
        from technical_analysis import TechnicalAnalysis
        ma5 = TechnicalAnalysis.calculate_ma(weekly_df, period=5) if len(weekly_df) >= 5 else None
        ma10 = TechnicalAnalysis.calculate_ma(weekly_df, period=10) if len(weekly_df) >= 10 else None
        ma20 = TechnicalAnalysis.calculate_ma(weekly_df, period=20) if len(weekly_df) >= 20 else None
        ma60 = TechnicalAnalysis.calculate_ma(weekly_df, period=60) if len(weekly_df) >= 60 else None
        
        # 准备数据
        dates = []
        kline_data = []
        volumes = []
        ma5_data = []
        ma10_data = []
        ma20_data = []
        ma60_data = []
        
        for i in range(len(weekly_df)):
            row = weekly_df.iloc[i]
            dates.append(str(row['日期']))
            kline_data.append([
                float(row['开盘']),
                float(row['收盘']),
                float(row['最低']),
                float(row['最高'])
            ])
            volumes.append(float(row.get('周成交量', row.get('成交量', 0))))
            
            # 均线数据
            ma5_data.append(float(ma5.iloc[i]) if ma5 is not None and i < len(ma5) and pd.notna(ma5.iloc[i]) else None)
            ma10_data.append(float(ma10.iloc[i]) if ma10 is not None and i < len(ma10) and pd.notna(ma10.iloc[i]) else None)
            ma20_data.append(float(ma20.iloc[i]) if ma20 is not None and i < len(ma20) and pd.notna(ma20.iloc[i]) else None)
            ma60_data.append(float(ma60.iloc[i]) if ma60 is not None and i < len(ma60) and pd.notna(ma60.iloc[i]) else None)
        
        # 获取股票名称
        stock_list = analyzer.fetcher.get_all_stocks()
        stock_name = stock_code
        if stock_list is not None:
            stock_row = stock_list[stock_list['code'] == stock_code]
            if len(stock_row) > 0:
                stock_name = stock_row.iloc[0]['name']
        
        return jsonify({
            'code': stock_code,
            'name': stock_name,
            'dates': dates,
            'kline': kline_data,
            'volumes': volumes,
            'ma5': ma5_data,
            'ma10': ma10_data,
            'ma20': ma20_data,
            'ma60': ma60_data
        })
    except Exception as e:
        import traceback
        return jsonify({'error': f'获取周K线数据失败: {str(e)}'}), 500


# ==================== KDJ模式扫描 ====================

def calculate_kdj(df, n=9, m1=3, m2=3):
    """
    计算KDJ指标
    :param df: K线数据，必须包含 '最高', '最低', '收盘' 列
    :param n: RSV周期，默认9
    :param m1: K值平滑周期，默认3
    :param m2: D值平滑周期，默认3
    :return: DataFrame添加 K, D, J 列
    """
    if df is None or len(df) < n:
        return None
    
    df = df.copy()
    
    # 计算N日内最高价和最低价
    df['HHV'] = df['最高'].rolling(window=n, min_periods=1).max()
    df['LLV'] = df['最低'].rolling(window=n, min_periods=1).min()
    
    # 计算RSV
    df['RSV'] = (df['收盘'] - df['LLV']) / (df['HHV'] - df['LLV'] + 0.0001) * 100
    
    # 计算K值（使用SMA平滑）
    # K = 2/3 * 前一日K + 1/3 * RSV
    k_values = []
    d_values = []
    k = 50  # 初始K值
    d = 50  # 初始D值
    
    for rsv in df['RSV']:
        k = (m1 - 1) / m1 * k + 1 / m1 * rsv
        d = (m2 - 1) / m2 * d + 1 / m2 * k
        k_values.append(k)
        d_values.append(d)
    
    df['K'] = k_values
    df['D'] = d_values
    df['J'] = 3 * df['K'] - 2 * df['D']
    
    # 清理临时列
    df = df.drop(columns=['HHV', 'LLV', 'RSV'], errors='ignore')
    
    return df


def get_latest_kdj(df, n=9, m1=3, m2=3):
    """
    获取最新的KDJ值
    :return: dict {'K': x, 'D': y, 'J': z} 或 None
    """
    df_with_kdj = calculate_kdj(df, n, m1, m2)
    if df_with_kdj is None or len(df_with_kdj) == 0:
        return None
    
    last_row = df_with_kdj.iloc[-1]
    return {
        'K': round(last_row['K'], 2),
        'D': round(last_row['D'], 2),
        'J': round(last_row['J'], 2)
    }


# KDJ扫描进度存储
kdj_scan_progress = {
    'status': 'idle',  # idle, running, completed, stopped
    'processed': 0,
    'total': 0,
    'found': 0,
    'percentage': 0,
    'current_stock': '',
    'message': '',
    'candidates': [],
    'threshold': 20,
    'limit': 50
}
kdj_scan_stop_flag = False


@app.route('/api/scan_kdj', methods=['POST'])
@require_login
def scan_kdj():
    """
    KDJ模式扫描API（启动扫描）
    筛选日KDJ、周KDJ、月KDJ的K、D、J值都在指定阈值以下的个股
    """
    global kdj_scan_progress, kdj_scan_stop_flag
    
    try:
        data = request.get_json(silent=True) or {}
        threshold = float(data.get('threshold', 20))  # KDJ阈值，默认20
        limit = int(data.get('limit', 50))  # 返回数量限制
        max_workers = int(data.get('max_workers', 10))  # 并发线程数，默认10（Render环境建议5-10）
        
        # Render环境自动调整线程数
        if is_render:
            max_workers = min(max_workers, 10)  # Render免费版限制
        
        # 重置进度和停止标志
        kdj_scan_stop_flag = False
        kdj_scan_progress = {
            'status': 'running',
            'processed': 0,
            'total': 0,
            'found': 0,
            'percentage': 0,
            'current_stock': '',
            'message': '正在初始化...',
            'candidates': [],
            'threshold': threshold,
            'limit': limit
        }
        
        print(f"\n🔍 KDJ模式扫描开始...")
        print(f"   阈值: K,D,J < {threshold}")
        print(f"   并发线程数: {max_workers}")
        
        # 启动后台线程执行扫描
        import threading
        scan_thread = threading.Thread(target=_kdj_scan_worker, args=(threshold, limit, max_workers))
        scan_thread.daemon = True
        scan_thread.start()
        
        return jsonify({
            'success': True,
            'message': 'KDJ扫描已启动'
        })
        
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"KDJ扫描启动错误: {error_detail}")
        return jsonify({
            'success': False,
            'message': f'扫描启动失败: {str(e)}'
        }), 500


def _load_daily_kline_from_cache(code, cache_dir):
    """从本地缓存加载日K线数据"""
    csv_path = os.path.join(cache_dir, 'daily_kline', f'{code}.csv')
    if os.path.exists(csv_path):
        try:
            df = pd.read_csv(csv_path)
            if '日期' in df.columns:
                df['日期'] = pd.to_datetime(df['日期'], errors='coerce')
                df = df.dropna(subset=['日期']).sort_values('日期').reset_index(drop=True)
            return df
        except Exception:
            return None
    return None


def _load_weekly_kline_from_cache(code, cache_dir):
    """从本地缓存加载周K线数据"""
    csv_path = os.path.join(cache_dir, 'weekly_kline', f'{code}.csv')
    json_path = os.path.join(cache_dir, 'weekly_kline', f'{code}.json')
    
    if os.path.exists(csv_path):
        try:
            df = pd.read_csv(csv_path)
            if '日期' in df.columns:
                df['日期'] = pd.to_datetime(df['日期'], errors='coerce')
                df = df.dropna(subset=['日期']).sort_values('日期').reset_index(drop=True)
            return df
        except Exception:
            pass
    
    if os.path.exists(json_path):
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            df = pd.DataFrame(data)
            if '日期' in df.columns:
                df['日期'] = pd.to_datetime(df['日期'], errors='coerce')
                df = df.dropna(subset=['日期']).sort_values('日期').reset_index(drop=True)
            return df
        except Exception:
            pass
    
    return None


def _generate_monthly_kline_from_daily(daily_df):
    """从日K线生成月K线数据"""
    if daily_df is None or len(daily_df) < 30:
        return None
    
    try:
        df = daily_df.copy()
        
        # 确保日期列是datetime类型
        if '日期' not in df.columns:
            return None
        df['日期'] = pd.to_datetime(df['日期'], errors='coerce')
        df = df.dropna(subset=['日期'])
        
        # 提取年月
        df['年月'] = df['日期'].dt.to_period('M')
        
        # 按月聚合
        monthly_data = []
        for period, group in df.groupby('年月'):
            monthly_data.append({
                '日期': period.to_timestamp(),
                '开盘': group['开盘'].iloc[0],
                '收盘': group['收盘'].iloc[-1],
                '最高': group['最高'].max(),
                '最低': group['最低'].min(),
                '成交量': group['成交量'].sum() if '成交量' in group.columns else 0
            })
        
        monthly_df = pd.DataFrame(monthly_data)
        monthly_df = monthly_df.sort_values('日期').reset_index(drop=True)
        return monthly_df
    except Exception:
        return None


def _kdj_scan_worker(threshold, limit, max_workers=10):
    """KDJ扫描工作线程 - 使用本地缓存数据，并行处理"""
    global kdj_scan_progress, kdj_scan_stop_flag
    
    try:
        from concurrent.futures import ThreadPoolExecutor, as_completed
        import threading
        
        # 获取股票列表（Vercel 下从 LOCAL_CACHE_DIR 读 /tmp/cache）
        cache_dir = os.environ.get('LOCAL_CACHE_DIR') or os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cache')
        stock_list_path = os.path.join(cache_dir, 'stock_list_all.json')
        
        if os.path.exists(stock_list_path):
            with open(stock_list_path, 'r', encoding='utf-8') as f:
                stock_list = json.load(f)
        else:
            kdj_scan_progress['status'] = 'completed'
            kdj_scan_progress['message'] = '无法获取股票列表，请先下载本地数据'
            return
        
        candidates = []
        candidates_lock = threading.Lock()  # 线程锁
        total = len(stock_list)
        kdj_scan_progress['total'] = total
        kdj_scan_progress['message'] = f'使用本地缓存数据并行扫描中... ({max_workers} 线程)'
        
        processed_count = 0
        processed_lock = threading.Lock()  # 进度更新锁
        
        def process_single_stock(stock_info):
            """处理单只股票"""
            nonlocal processed_count
            
            if kdj_scan_stop_flag:
                return None
            
            if isinstance(stock_info, dict):
                code = stock_info.get('code', stock_info.get('股票代码', ''))
                name = stock_info.get('name', stock_info.get('股票名称', ''))
            else:
                return None
            
            # 排除ST和北交所
            if 'ST' in name.upper() or code.startswith('8') or code.startswith('9'):
                with processed_lock:
                    processed_count += 1
                    kdj_scan_progress['processed'] = processed_count
                    kdj_scan_progress['percentage'] = round(processed_count / total * 100, 1)
                return None
            
            try:
                # 从本地缓存获取日K线数据
                daily_df = _load_daily_kline_from_cache(code, cache_dir)
                if daily_df is None or len(daily_df) < 30:
                    with processed_lock:
                        processed_count += 1
                        kdj_scan_progress['processed'] = processed_count
                        kdj_scan_progress['percentage'] = round(processed_count / total * 100, 1)
                    return None
                
                # 计算日KDJ
                daily_kdj = get_latest_kdj(daily_df, 9, 3, 3)
                if daily_kdj is None:
                    with processed_lock:
                        processed_count += 1
                        kdj_scan_progress['processed'] = processed_count
                        kdj_scan_progress['percentage'] = round(processed_count / total * 100, 1)
                    return None
                
                # 快速筛选：如果日KDJ不满足条件，跳过
                if daily_kdj['K'] >= threshold or daily_kdj['D'] >= threshold or daily_kdj['J'] >= threshold:
                    with processed_lock:
                        processed_count += 1
                        kdj_scan_progress['processed'] = processed_count
                        kdj_scan_progress['percentage'] = round(processed_count / total * 100, 1)
                    return None
                
                # 从本地缓存获取周K线数据
                weekly_df = _load_weekly_kline_from_cache(code, cache_dir)
                if weekly_df is None or len(weekly_df) < 20:
                    with processed_lock:
                        processed_count += 1
                        kdj_scan_progress['processed'] = processed_count
                        kdj_scan_progress['percentage'] = round(processed_count / total * 100, 1)
                    return None
                
                # 计算周KDJ
                weekly_kdj = get_latest_kdj(weekly_df, 9, 3, 3)
                if weekly_kdj is None:
                    with processed_lock:
                        processed_count += 1
                        kdj_scan_progress['processed'] = processed_count
                        kdj_scan_progress['percentage'] = round(processed_count / total * 100, 1)
                    return None
                
                # 检查周KDJ
                if weekly_kdj['K'] >= threshold or weekly_kdj['D'] >= threshold or weekly_kdj['J'] >= threshold:
                    with processed_lock:
                        processed_count += 1
                        kdj_scan_progress['processed'] = processed_count
                        kdj_scan_progress['percentage'] = round(processed_count / total * 100, 1)
                    return None
                
                # 从日K线生成月K线数据
                monthly_df = _generate_monthly_kline_from_daily(daily_df)
                if monthly_df is None or len(monthly_df) < 12:
                    with processed_lock:
                        processed_count += 1
                        kdj_scan_progress['processed'] = processed_count
                        kdj_scan_progress['percentage'] = round(processed_count / total * 100, 1)
                    return None
                
                # 计算月KDJ
                monthly_kdj = get_latest_kdj(monthly_df, 9, 3, 3)
                if monthly_kdj is None:
                    with processed_lock:
                        processed_count += 1
                        kdj_scan_progress['processed'] = processed_count
                        kdj_scan_progress['percentage'] = round(processed_count / total * 100, 1)
                    return None
                
                # 检查月KDJ
                if monthly_kdj['K'] >= threshold or monthly_kdj['D'] >= threshold or monthly_kdj['J'] >= threshold:
                    with processed_lock:
                        processed_count += 1
                        kdj_scan_progress['processed'] = processed_count
                        kdj_scan_progress['percentage'] = round(processed_count / total * 100, 1)
                    return None
                
                # 全部通过！创建候选对象
                current_price = float(daily_df.iloc[-1]['收盘'])
                
                candidate = {
                    '股票代码': code,
                    '股票名称': name,
                    '当前价格': round(current_price, 2),
                    '日K': daily_kdj['K'],
                    '日D': daily_kdj['D'],
                    '日J': daily_kdj['J'],
                    '周K': weekly_kdj['K'],
                    '周D': weekly_kdj['D'],
                    '周J': weekly_kdj['J'],
                    '月K': monthly_kdj['K'],
                    '月D': monthly_kdj['D'],
                    '月J': monthly_kdj['J'],
                    'KDJ平均': round((daily_kdj['K'] + daily_kdj['D'] + weekly_kdj['K'] + weekly_kdj['D'] + monthly_kdj['K'] + monthly_kdj['D']) / 6, 2)
                }
                
                # 更新进度
                with processed_lock:
                    processed_count += 1
                    kdj_scan_progress['processed'] = processed_count
                    kdj_scan_progress['percentage'] = round(processed_count / total * 100, 1)
                    kdj_scan_progress['current_stock'] = f"{code} {name}"
                
                print(f"   ✅ {code} {name}: 日KDJ({daily_kdj['K']:.1f},{daily_kdj['D']:.1f},{daily_kdj['J']:.1f}) "
                      f"周KDJ({weekly_kdj['K']:.1f},{weekly_kdj['D']:.1f},{weekly_kdj['J']:.1f}) "
                      f"月KDJ({monthly_kdj['K']:.1f},{monthly_kdj['D']:.1f},{monthly_kdj['J']:.1f})")
                
                return candidate
                
            except Exception as e:
                with processed_lock:
                    processed_count += 1
                    kdj_scan_progress['processed'] = processed_count
                    kdj_scan_progress['percentage'] = round(processed_count / total * 100, 1)
                return None
        
        # 使用线程池并行处理
        print(f"\n🚀 开始并行KDJ扫描 ({max_workers} 线程)...")
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(process_single_stock, stock_info): stock_info for stock_info in stock_list}
            
            for future in as_completed(futures):
                if kdj_scan_stop_flag:
                    executor.shutdown(wait=False, cancel_futures=True)
                    kdj_scan_progress['status'] = 'stopped'
                    kdj_scan_progress['message'] = '扫描已停止'
                    break
                
                candidate = future.result()
                if candidate:
                    with candidates_lock:
                        candidates.append(candidate)
                        kdj_scan_progress['found'] = len(candidates)
                        # 只保留最新的候选列表（避免内存过大）
                        if len(candidates) <= limit * 2:
                            kdj_scan_progress['candidates'] = candidates.copy()
        
        # 按KDJ平均值排序（越小越超卖）
        candidates.sort(key=lambda x: x['KDJ平均'])
        
        # 限制返回数量
        if limit > 0:
            candidates = candidates[:limit]
        
        # 更新最终结果
        if not kdj_scan_stop_flag:
            kdj_scan_progress['status'] = 'completed'
        kdj_scan_progress['candidates'] = candidates
        kdj_scan_progress['found'] = len(candidates)
        kdj_scan_progress['message'] = f'扫描完成，找到 {len(candidates)} 只符合条件的个股'
        
        print(f"\n✅ KDJ模式扫描完成: 共找到 {len(candidates)} 只符合条件的个股")
        
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"KDJ扫描工作线程错误: {error_detail}")
        kdj_scan_progress['status'] = 'completed'
        kdj_scan_progress['message'] = f'扫描出错: {str(e)}'


@app.route('/api/get_kdj_scan_progress', methods=['GET'])
@require_login
def get_kdj_scan_progress():
    """获取KDJ扫描进度"""
    global kdj_scan_progress
    return jsonify({
        'success': True,
        'status': kdj_scan_progress['status'],
        'processed': kdj_scan_progress['processed'],
        'total': kdj_scan_progress['total'],
        'found': kdj_scan_progress['found'],
        'percentage': kdj_scan_progress['percentage'],
        'current_stock': kdj_scan_progress['current_stock'],
        'message': kdj_scan_progress['message'],
        'threshold': kdj_scan_progress['threshold']
    })


@app.route('/api/get_kdj_scan_results', methods=['GET'])
@require_login
def get_kdj_scan_results():
    """获取KDJ扫描结果"""
    global kdj_scan_progress
    return jsonify({
        'success': True,
        'data': kdj_scan_progress['candidates'],
        'count': len(kdj_scan_progress['candidates']),
        'threshold': kdj_scan_progress['threshold'],
        'status': kdj_scan_progress['status'],
        'message': kdj_scan_progress['message']
    })


@app.route('/api/stop_kdj_scan', methods=['POST'])
@require_login
def stop_kdj_scan():
    """停止KDJ扫描"""
    global kdj_scan_stop_flag
    kdj_scan_stop_flag = True
    return jsonify({
        'success': True,
        'message': 'KDJ扫描停止请求已发送'
    })


# ✅ 数据包下载状态标记（模块级变量，确保只执行一次）
_data_download_checked = False
_data_download_lock = None

def _ensure_stock_data_downloaded():
    """确保股票数据包已下载（在 Vercel/Render 环境中）"""
    global _data_download_checked, _data_download_lock
    import os
    import threading
    
    # 只在首次调用时执行（使用模块级变量和锁确保线程安全）
    if _data_download_checked:
        return
    
    # 初始化锁（如果还没有）
    if _data_download_lock is None:
        _data_download_lock = threading.Lock()
    
    # 使用锁确保只执行一次
    with _data_download_lock:
        if _data_download_checked:
            return
        _data_download_checked = True
    
    # ✅ 在 Vercel 环境中，自动启用 GitHub 数据包模式（不连接实时 API）
    if is_vercel:
        os.environ['USE_GITHUB_DATA_ONLY'] = '1'
        print("=" * 80)
        print("✅ Vercel 环境检测到，已启用 USE_GITHUB_DATA_ONLY 模式")
        print("   系统将优先使用 GitHub 数据包，不连接实时股市 API")
        print("=" * 80)
    
    # ✅ 在 Render/Vercel 环境中，检查并下载股票数据（如果配置了 STOCK_DATA_URL）
    if is_render or is_vercel or os.environ.get('STOCK_DATA_URL'):
        try:
            # Vercel 仅 /tmp 可写，api/index 已解压到 /tmp 并设置 LOCAL_CACHE_DIR
            _base = os.environ.get('LOCAL_CACHE_DIR')
            if _base:
                cache_dir = _base
                stock_data_dir = os.path.join(os.path.dirname(_base), 'stock_data')
            else:
                cache_dir = 'cache'
                stock_data_dir = 'stock_data'
            
            # 检查数据是否存在
            cache_exists = os.path.exists(cache_dir) and os.listdir(cache_dir) if os.path.exists(cache_dir) else False
            stock_exists = os.path.exists(stock_data_dir) and os.listdir(stock_data_dir) if os.path.exists(stock_data_dir) else False
            
            if not cache_exists and not stock_exists:
                data_url = os.environ.get('STOCK_DATA_URL')
                if data_url:
                    env_name = "Vercel" if is_vercel else "Render"
                    print("=" * 80)
                    print(f"📥 检测到 {env_name} 环境，开始从 GitHub 下载股票数据...")
                    print(f"   数据包 URL: {data_url}")
                    print("=" * 80)
                    try:
                        # Vercel 仅 /tmp 可写，用 fetch_github_cache 解压到 /tmp；否则用 download_stock_data
                        if is_vercel and os.environ.get('LOCAL_CACHE_DIR'):
                            from fetch_github_cache import fetch_github_cache
                            fetch_github_cache(skip_if_exists=False, root_dir='/tmp')
                        else:
                            from download_stock_data import main as download_main
                            download_main()
                        
                        # ✅ 下载后自动生成股票列表（如果不存在）
                        stock_list_path = os.path.join(cache_dir, 'stock_list_all.json')
                        if not os.path.exists(stock_list_path):
                            print("\n📋 检测到股票列表不存在，正在从K线文件列表生成...")
                            try:
                                from generate_stock_list_from_files import generate_stock_list_from_kline_files
                                if generate_stock_list_from_kline_files():
                                    print("✅ 股票列表生成成功！")
                                else:
                                    print("⚠️  股票列表生成失败，但不影响使用（将从API获取）")
                            except Exception as e:
                                print(f"⚠️  生成股票列表时出错: {e}")
                                print("   不影响使用（将从API获取股票列表）")
                    except Exception as e:
                        print(f"⚠️  下载数据失败: {e}")
                        import traceback
                        traceback.print_exc()
                        if is_vercel:
                            print("   ⚠️  Vercel 环境：由于 USE_GITHUB_DATA_ONLY 模式，将无法从实时 API 获取数据")
                            print("   请确保 STOCK_DATA_URL 指向有效的 GitHub Releases 数据包")
                        else:
                            print("   将使用网络实时获取数据")
                else:
                    env_name = "Vercel" if is_vercel else "Render"
                    print(f"⚠️  未设置 STOCK_DATA_URL 环境变量（{env_name} 环境）")
                    if is_vercel:
                        print("   ⚠️  Vercel 环境：由于 USE_GITHUB_DATA_ONLY 模式，必须设置 STOCK_DATA_URL")
                        print("   请在 Vercel Dashboard 中设置 STOCK_DATA_URL 指向 GitHub Releases 数据包")
                    else:
                        print("   数据将从网络实时获取（较慢）")
            else:
                print("✅ 股票数据已存在，跳过下载")
        except Exception as e:
            print(f"⚠️  数据检查失败: {e}，继续启动应用")
            import traceback
            traceback.print_exc()

# ✅ 在 Vercel 环境中，在首次请求时触发数据包下载
# 使用 Flask 的 before_request，但只执行一次
@app.before_request
def ensure_data_downloaded():
    """在每次请求前检查并下载数据包（仅在 Vercel 环境中，且仅执行一次）"""
    global _data_download_checked
    # 避免在“页面初始化/轻量接口”上触发长耗时拉包，导致 504/超时
    # 仅在明确需要本地数据的接口上尝试拉包（扫描/预热/手动刷新）
    try:
        from flask import request as _req
        _path = _req.path or ""
    except Exception:
        _path = ""
    _download_allow_paths = {
        "/api/cache_debug",
        "/api/refresh_stock_cache",
        "/api/scan_all_stocks",
        "/api/continue_scan",
    }
    if _path and _path.startswith("/api/") and (_path not in _download_allow_paths):
        return

    if (is_vercel or is_render or os.environ.get('STOCK_DATA_URL')) and not _data_download_checked:
        try:
            _ensure_stock_data_downloaded()
        except Exception as e:
            # 静默失败，不影响请求处理
            print(f"[ensure_data_downloaded] ⚠️ 检查数据包时出错: {e}")
            import traceback
            traceback.print_exc()

if __name__ == '__main__':
    import os
    import time
    
    # ✅ 在 Vercel 环境中，自动启用 GitHub 数据包模式（不连接实时 API）
    if is_vercel:
        os.environ['USE_GITHUB_DATA_ONLY'] = '1'
        print("=" * 80)
        print("✅ Vercel 环境检测到，已启用 USE_GITHUB_DATA_ONLY 模式")
        print("   系统将优先使用 GitHub 数据包，不连接实时股市 API")
        print("=" * 80)
    
    # ✅ 在本地/Render 环境中，在启动时下载数据包
    # 注意：在 Vercel 环境中，这个块不会执行，数据包下载在 before_request 中处理
    if (is_render or os.environ.get('STOCK_DATA_URL')) and not is_vercel:
        _ensure_stock_data_downloaded()
    
    # 检测是否在Render或其他云平台环境
    # Render 通常会设置 PORT 环境变量，如果设置了 PORT，说明在云环境
    port_env = os.environ.get('PORT')
    is_port_set = port_env is not None
    
    is_render = (
        os.environ.get('RENDER') == 'true' or
        os.environ.get('RENDER_SERVICE_NAME') is not None or
        os.environ.get('RENDER_SERVICE_ID') is not None or
        os.environ.get('RENDER_EXTERNAL_URL') is not None or
        os.environ.get('RENDER_EXTERNAL_HOSTNAME') is not None
    )
    is_vercel = (
        os.environ.get('VERCEL') == '1' or 
        os.environ.get('VERCEL_ENV') is not None or
        os.environ.get('VERCEL_URL') is not None
    )
    # 如果 PORT 环境变量被设置（通常是云平台），或者检测到 Render/Vercel，认为是云环境
    is_cloud = is_render or is_vercel or is_port_set
    
    # 支持Render等平台：从环境变量获取端口，如果没有则使用默认端口5002
    port = int(os.environ.get('PORT', 5002))
    
    # 只在本地环境检查并释放端口（云平台不需要）
    if not is_cloud:
        import socket
        import subprocess
        
        # 检查并释放端口5002（只终止占用端口的进程，避免 pkill 误杀当前启动进程）
        port = 5002
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(('127.0.0.1', port))
        sock.close()
        
        if result == 0:
            # 端口被占用，强制释放
            print(f"⚠️  端口{port}被占用，正在强制释放...")
            try:
                # 方法1: 使用lsof查找并终止
                if os.name == 'posix':  # Unix/Linux/Mac
                    result = subprocess.run(['lsof', '-ti', f':{port}'], 
                                          capture_output=True, text=True, timeout=2)
                    if result.returncode == 0 and result.stdout.strip():
                        pids = result.stdout.strip().split('\n')
                        for pid in pids:
                            try:
                                os.kill(int(pid), 9)
                                print(f"   ✅ 已终止进程 {pid}")
                            except Exception as e:
                                print(f"   ⚠️  终止进程{pid}失败: {e}")
                        time.sleep(1)
                        
                        # 再次检查端口是否已释放
                        sock2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        sock2.settimeout(1)
                        result2 = sock2.connect_ex(('127.0.0.1', port))
                        sock2.close()
                        if result2 == 0:
                            print(f"   ❌ 端口{port}仍被占用，请手动检查")
                        else:
                            print(f"   ✅ 端口{port}已成功释放")
            except Exception as e:
                print(f"   ⚠️  释放端口失败: {e}")
    else:
        # 云环境：跳过端口检查
        print("⚠️  检测到云环境（Render/Vercel），跳过本地端口检查和释放。")
    
    print("=" * 80)
    print("大牛股分析器Web界面")
    print("=" * 80)
    
    print(f"访问地址: http://0.0.0.0:{port}")
    print("=" * 80)
    
    # 使用waitress服务器（避免macOS上的Werkzeug错误）
    try:
        from waitress import serve
        print("使用Waitress服务器启动...")
        serve(app, host='0.0.0.0', port=port, threads=4)
    except ImportError:
        # 如果waitress不可用，使用Flask开发服务器
        print("⚠️  Waitress不可用，使用Flask开发服务器...")
        # 增加请求超时时间，避免长时间扫描任务超时
        import werkzeug.serving
        werkzeug.serving.WSGIRequestHandler.timeout = 60  # 设置60秒超时
        # 监听所有网络接口，允许远程访问
        # 关闭debug模式，避免自动重启导致的问题
        app.run(host='0.0.0.0', port=port, debug=False, threaded=True, use_reloader=False)

