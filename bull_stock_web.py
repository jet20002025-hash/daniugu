#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
大牛股分析器Web界面
提供添加大牛股的功能
"""
from flask import Flask, render_template, jsonify, request, session, redirect, url_for, send_file
from bull_stock_analyzer import BullStockAnalyzer
from technical_analysis import TechnicalAnalysis
from datetime import datetime
# 根据环境选择使用哪个认证模块
import os

# 检测 Vercel 环境（更可靠的方式）
is_vercel = (
    os.environ.get('VERCEL') == '1' or 
    os.environ.get('VERCEL_ENV') is not None or
    os.environ.get('VERCEL_URL') is not None
)

try:
    if is_vercel:
        # Vercel 环境：使用内存存储版本
        from user_auth_vercel import (
            register_user, login_user, is_logged_in, get_current_user,
            require_login, create_invite_code, list_invite_codes, get_user_stats
        )
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

app = Flask(__name__)
app.config['SECRET_KEY'] = 'bull-stock-analyzer-secret-key-change-in-production'

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

# 创建全局分析器实例（延迟初始化，先启动Flask服务）
# 使用延迟初始化，避免阻塞Flask启动
analyzer = None

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
    """根据用户等级返回扫描配置"""
    tier = get_user_tier()
    
    if tier == 'super':
        # 超级用户：最快扫描，无限制
        return {
            'batch_size': 50,      # 50只/批
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
            'batch_size': 50,      # 50只/批
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
            'batch_size': 20,      # 20只/批（更慢）
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
    """延迟初始化分析器"""
    global analyzer
    if analyzer is None:
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
                    os.path.join(project_root, 'trained_model.json'),  # 项目根目录（最可能）
                    'trained_model.json',  # 当前工作目录
                    '../trained_model.json',  # 父目录
                    os.path.join(current_file_dir, 'trained_model.json'),  # 当前文件所在目录
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
                # 本地环境：正常初始化
                print("正在初始化分析器...")
                analyzer = BullStockAnalyzer(
                    auto_load_default_stocks=True, 
                    auto_analyze_and_train=False  # 即使是本地也禁用自动训练，避免阻塞
                )
                
                # 尝试加载已保存的模型（本地环境也跳过网络请求，仅加载模型文件）
                print("尝试加载已保存的模型...")
                if analyzer.load_model('trained_model.json', skip_network=True):
                    print("✅ 模型加载成功")
                    # 检查模型完整性
                    if analyzer.trained_features:
                        feature_count = len(analyzer.trained_features.get('common_features', {}))
                        print(f"   - 买点特征数: {feature_count}")
                    if analyzer.trained_sell_features:
                        sell_feature_count = len(analyzer.trained_sell_features.get('common_features', {}))
                        print(f"   - 卖点特征数: {sell_feature_count}")
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
    try:
        # 检查是否已登录
        if not is_logged_in():
            return redirect(url_for('login_page'))
        # 确保分析器已初始化（不阻塞，如果失败也继续）
        try:
            init_analyzer()
        except Exception as e:
            print(f"分析器初始化警告: {e}")
        return render_template('bull_stock_web.html')
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"主页错误: {error_detail}")
        return f"<h1>服务器错误</h1><pre>{error_detail}</pre>", 500

@app.route('/favicon.ico')
def favicon():
    """处理favicon请求，返回204 No Content"""
    return '', 204

@app.route('/login')
def login_page():
    """登录页面"""
    if is_logged_in():
        return redirect(url_for('index'))
    return render_template('login.html')

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

# ==================== 认证相关 API ====================

@app.route('/api/register', methods=['POST'])
def api_register():
    """用户注册API（邮箱注册，无需邀请码）"""
    try:
        data = request.get_json() or {}
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
    try:
        data = request.get_json() or {}
        username = data.get('username', '').strip()
        password = data.get('password', '')
        
        if not username or not password:
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
        
        if result['success']:
            session['username'] = username
            return jsonify(result)
        else:
            return jsonify(result), 401
            
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"登录错误: {error_detail}")
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


@app.route('/api/check_cache_status', methods=['GET'])
@require_login
def check_cache_status():
    """检查股票列表缓存状态API"""
    try:
        init_analyzer()
        
        if analyzer is None or analyzer.fetcher is None:
            return jsonify({
                'success': False,
                'message': '分析器未初始化',
                'cache_exists': False,
                'cached_stock_count': 0
            }), 500
        
        # 检测缓存是否存在
        cache_exists = False
        cached_stock_count = 0
        try:
            cached_stocks = analyzer.fetcher._get_stock_list_from_cache()
            if cached_stocks is not None and len(cached_stocks) > 0:
                cache_exists = True
                cached_stock_count = len(cached_stocks)
                print(f"[check_cache_status] ✅ 缓存存在，股票数: {cached_stock_count} 只")
            else:
                print(f"[check_cache_status] ⚠️ 缓存不存在或为空")
        except Exception as e:
            print(f"[check_cache_status] ⚠️ 检测缓存时出错: {e}")
        
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
        data = request.get_json()
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
    """获取当前用户信息（包括等级）"""
    try:
        user = get_current_user()
        if not user:
            return jsonify({
                'success': False,
                'message': '未登录'
            }), 401
        
        is_premium = user.get('is_vip', False) or user.get('is_premium', False)
        tier = get_user_tier()  # 使用统一的函数获取等级
        scan_config = get_scan_config()
        
        # 获取扫描限制信息
        from scan_limit_helper import get_beijing_time, check_scan_time_limit, check_result_view_time, check_daily_scan_limit
        beijing_now = get_beijing_time()
        
        # 检查当前是否可以扫描
        can_scan, scan_time_error = check_scan_time_limit(tier, scan_config)
        
        # 检查当前是否可以查看结果
        can_view, view_time_error = check_result_view_time(tier, scan_config)
        
        # 检查今日扫描次数
        username = user.get('username', 'anonymous')
        can_scan_daily, daily_error, today_count = check_daily_scan_limit(username, tier, scan_config, is_vercel)
        
        return jsonify({
            'success': True,
            'user': {
                'username': user.get('username'),
                'email': user.get('email'),
                'tier': tier,
                'is_premium': is_premium,
                'is_super': is_super_user(),
                'scan_config': scan_config,
                'scan_restrictions': {
                    'can_scan_now': can_scan,
                    'scan_time_error': scan_time_error,
                    'can_view_now': can_view,
                    'view_time_error': view_time_error,
                    'can_scan_daily': can_scan_daily,
                    'daily_error': daily_error,
                    'today_scan_count': today_count,
                    'current_time': beijing_now.strftime('%Y-%m-%d %H:%M:%S')
                }
            }
        })
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"获取用户信息错误: {error_detail}")
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
        
        data = request.get_json() or {}
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
        
        data = request.get_json() or {}
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
        
        data = request.get_json() or {}
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
        data = request.get_json()
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
        data = request.get_json()
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
        
        data = request.get_json() or {}
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
    
    # 在 Vercel serverless 环境中，从 Redis 读取进度
    if is_vercel:
        scan_id = request.args.get('scan_id')
        if scan_id:
            try:
                # 获取当前用户信息，用于验证权限
                current_user = get_current_user()
                username = current_user.get('username', 'anonymous') if current_user else 'anonymous'
                
                import scan_progress_store
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
                print(f"[get_progress] 从 Redis 读取进度失败: {e}")
        
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
        init_analyzer()  # 确保分析器已初始化
        
        # 检查 analyzer 是否已初始化
        if analyzer is None:
            print("[get_progress] analyzer 未初始化，返回默认值")
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
        
        # 获取进度信息
        try:
            progress = analyzer.get_progress()
            # 确保 progress 是字典类型且可以被序列化
            if not isinstance(progress, dict):
                print(f"[get_progress] progress 不是字典类型: {type(progress)}")
                progress = {
                    'type': None,
                    'current': 0,
                    'total': 0,
                    'status': '空闲',
                    'detail': '',
                    'percentage': 0,
                    'found': 0
                }
            
            # 移除任何不能序列化的对象
            import json
            try:
                # 测试是否可以序列化
                json.dumps(progress, default=str)
            except (TypeError, ValueError) as e:
                print(f"[get_progress] 序列化测试失败: {e}")
                # 如果序列化失败，返回默认值
                progress = {
                    'type': None,
                    'current': 0,
                    'total': 0,
                    'status': '空闲',
                    'detail': '',
                    'percentage': 0,
                    'found': 0
                }
            
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
        data = request.get_json()
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


@app.route('/api/scan_all_stocks', methods=['POST'])
@require_login
def scan_all_stocks():
    """扫描所有A股API"""
    init_analyzer()  # 确保分析器已初始化
    try:
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
        
        data = request.get_json() or {}
        min_match_score = float(data.get('min_match_score', 0.97))
        max_market_cap = float(data.get('max_market_cap', 100.0))
        limit = data.get('limit')
        if limit:
            limit = int(limit)
        
        # VIP用户自定义参数（第二阶段功能）
        exclude_st = data.get('exclude_st', True)  # 默认排除ST股票
        exclude_suspended = data.get('exclude_suspended', True)  # 默认排除停牌股票（暂不支持，预留）
        industry_filter = data.get('industry_filter', '').strip()  # 行业筛选（暂不支持，预留）
        custom_stock_pool = data.get('custom_stock_pool', '').strip()  # 自定义股票池（暂不支持，预留）
        
        # 在 Vercel 环境中，使用分批处理方案
        if is_vercel:
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
            
            # 每次扫描前先检测缓存是否存在（建议每次使用前都检测）
            print("[scan_all_stocks] 🔍 检测缓存是否存在...")
            cache_exists = False
            cached_stock_count = 0
            cache_status = "未知"
            try:
                cached_stocks = analyzer.fetcher._get_stock_list_from_cache()
                if cached_stocks is not None and len(cached_stocks) > 0:
                    cache_exists = True
                    cached_stock_count = len(cached_stocks)
                    cache_status = f"缓存存在（{cached_stock_count} 只股票）"
                    print(f"[scan_all_stocks] ✅ 缓存存在，股票数: {cached_stock_count} 只，可以直接使用")
                else:
                    cache_status = "缓存不存在"
                    print(f"[scan_all_stocks] ⚠️ 缓存不存在或为空")
            except Exception as e:
                cache_status = f"检测缓存时出错: {e}"
                print(f"[scan_all_stocks] ⚠️ {cache_status}")
            
            # 如果缓存不存在，只在交易时间段内且是 Vercel 环境时提前返回错误（避免超时和数据不一致）
            # 非交易时间段，允许从 API 获取数据（虽然可能慢，但应该允许用户扫描）
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
                    # 非交易时间段，允许从 API 获取数据
                    if is_in_trading_time:
                        error_msg = '⚠️ **缓存未生成（股票列表缓存不存在）**\n\n'
                        error_msg += f'当前时间: {current_time_str}（交易时间段内）\n\n'
                        error_msg += '💡 **解决方案：**\n'
                        error_msg += '当前在交易时间段内，数据变化频繁，建议等待缓存生成。\n'
                        error_msg += '**方案1（推荐）：** 等待几分钟，系统会在下次扫描时自动刷新缓存\n'
                        error_msg += '**方案2（手动）：** 手动触发缓存刷新：访问 https://www.daniugu.online/api/refresh_stock_cache?force=true\n'
                        error_msg += '   - 手动刷新可能需要30秒，请耐心等待\n'
                        error_msg += '   - 刷新成功后，再尝试扫描\n'
                        error_msg += '\n📌 **说明：**\n'
                        error_msg += '- 交易时间段内（9:30-11:30, 13:00-15:00）数据变化频繁\n'
                        error_msg += '- 建议等待缓存生成后再扫描，避免数据不一致和超时\n'
                        
                        print(f"[scan_all_stocks] ❌ 交易时间段内缓存不存在，提前返回错误（避免超时和数据不一致）")
                        return jsonify({
                            'success': False,
                            'message': error_msg,
                            'cache_exists': False,
                            'current_time': current_time_str,
                            'is_in_trading_time': True
                        }), 400
                    else:
                        # 非交易时间段，允许从 API 获取数据（虽然可能慢，但应该允许用户扫描）
                        print(f"[scan_all_stocks] ⚠️ 非交易时间段缓存不存在，将从 API 获取数据（可能需要较长时间，但允许扫描）")
                except Exception as e:
                    print(f"[scan_all_stocks] ⚠️ 检查交易时间时出错: {e}，继续执行（从 API 获取数据）")
            
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
                # Vercel 中：超时5秒，只尝试1次；本地：超时15秒，最多重试3次
                # 交易时间段内，如果缓存超过5分钟，会自动从API获取最新数据
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
                return jsonify({
                    'success': False,
                    'message': f'获取股票列表失败: {str(e)}\n\n可能的原因：\n1. 网络连接问题（Vercel 环境网络限制）\n2. akshare 服务暂时不可用\n3. 超时（Vercel 函数执行时间限制为 10 秒）\n\n建议：\n- 请稍后重试\n- 如果问题持续，可能是 akshare 服务暂时不可用\n- 可以尝试在非高峰时段重试'
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
        # 在后台线程中执行扫描（避免阻塞）
        import threading
        
        def run_scan():
            try:
                import time as time_module
                start_time = time_module.time()
                max_scan_time = 3600 * 2  # 最大扫描时间：2小时
                
                print(f"\n🔄 开始扫描，匹配度阈值: {min_match_score:.3f}")
                
                # 只执行一次扫描，不再自动调整阈值
                result = analyzer.scan_all_stocks(
                    min_match_score=min_match_score,
                    max_market_cap=max_market_cap,
                    limit=limit
                )
                
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
            'message': '扫描已开始，请通过进度API查看进度'
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
        data = request.get_json() or {}
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
        min_match_score = progress.get('min_match_score', 0.97)
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
            data = request.get_json() or {}
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
        data = request.get_json()
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
        
        if scan_results is None:
            return jsonify({
                'success': False,
                'message': '尚未开始扫描或扫描未完成',
                'results': None
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


@app.route('/api/scan_reversal_stocks', methods=['POST'])
@require_login
def scan_reversal_stocks():
    """搜索上周阴线+本周阳线的反转个股API"""
    init_analyzer()  # 确保分析器已初始化
    try:
        # 获取请求参数
        data = request.get_json() or {}
        market_cap_max = float(data.get('market_cap_max', 100.0))  # 默认100亿
        
        # 在后台线程中执行扫描（避免阻塞）
        import threading
        
        def run_reversal_scan():
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
        
        data = request.get_json() or {}
        
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
        
        data = request.get_json() or {}
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
        
        data = request.get_json() or {}
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
        
        data = request.get_json() or {}
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
        
        data = request.get_json() or {}
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
        data = request.get_json()
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
        force_refresh = request.args.get('force', '').lower() == 'true' or request.get_json(silent=True) and request.get_json().get('force', False)
        
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
        
        # 从 akshare API 获取股票列表（后台任务可以使用更长的超时）
        print("[refresh_stock_cache] 从 akshare API 获取股票列表...")
        # 注意：这是后台 Cron Job 任务，允许使用更长的超时时间
        # 直接调用 akshare API，不使用 get_all_stocks 的限制（因为它会自动限制 Vercel 环境的超时）
        try:
            import akshare as ak
            import threading
            import time as time_module
            
            result = [None]
            error = [None]
            start_time = time_module.time()
            
            def fetch_stocks():
                try:
                    print("[refresh_stock_cache] 开始调用 ak.stock_info_a_code_name()...")
                    result[0] = ak.stock_info_a_code_name()
                    elapsed = time_module.time() - start_time
                    print(f"[refresh_stock_cache] ✅ ak.stock_info_a_code_name() 调用成功，耗时 {elapsed:.2f}秒")
                except Exception as e:
                    error[0] = e
                    elapsed = time_module.time() - start_time
                    print(f"[refresh_stock_cache] ❌ 调用失败（耗时 {elapsed:.2f}秒）: {e}")
                    import traceback
                    print(f"[refresh_stock_cache] 错误详情: {traceback.format_exc()}")
            
            fetch_thread = threading.Thread(target=fetch_stocks)
            fetch_thread.daemon = True
            fetch_thread.start()
            fetch_thread.join(timeout=30)  # Cron Job 任务允许30秒超时
            
            elapsed_total = time_module.time() - start_time
            
            if fetch_thread.is_alive():
                print(f"[refresh_stock_cache] ⏱️ 获取超时（>{30}秒，实际耗时 {elapsed_total:.2f}秒）")
                return jsonify({
                    'success': False,
                    'message': f'获取股票列表超时（>{30}秒），请稍后重试',
                    'current_time': current_time_str
                }), 500
            
            if error[0]:
                print(f"[refresh_stock_cache] ❌ 获取出错（耗时 {elapsed_total:.2f}秒）: {error[0]}")
                return jsonify({
                    'success': False,
                    'message': f'获取股票列表失败: {str(error[0])}',
                    'current_time': current_time_str
                }), 500
            
            if result[0] is None or len(result[0]) == 0:
                print(f"[refresh_stock_cache] ⚠️ 返回结果为空（耗时 {elapsed_total:.2f}秒）")
                return jsonify({
                    'success': False,
                    'message': '获取股票列表返回空数据',
                    'current_time': current_time_str
                }), 500
            
            stock_list = result[0]
            
            # 将股票列表保存到缓存
            print(f"[refresh_stock_cache] 获取到 {len(stock_list)} 只股票，开始保存到缓存...")
            cache_success = analyzer.fetcher._save_stock_list_to_cache(stock_list)
            if cache_success:
                print(f"[refresh_stock_cache] ✅ 股票列表已保存到缓存（耗时 {elapsed_total:.2f}秒）")
            else:
                print(f"[refresh_stock_cache] ⚠️ 保存到缓存失败，但已获取股票列表（耗时 {elapsed_total:.2f}秒）")
            
            # 更新分析器的股票列表
            analyzer.fetcher.stock_list = stock_list
            
            # 保存到缓存（已经在上面保存了，这里只是确认）
            print(f"[refresh_stock_cache] ✅ 成功刷新股票列表缓存，股票数: {len(stock_list)}")
            
            return jsonify({
                'success': True,
                'message': f'股票列表缓存已刷新（{len(stock_list)} 只股票）',
                'stock_count': len(stock_list),
                'current_time': current_time_str,
                'cache_ttl': '24小时'
            }), 200
            
        except Exception as e:
            import traceback
            error_detail = traceback.format_exc()
            print(f"[refresh_stock_cache] ❌ 获取股票列表异常: {error_detail}")
            return jsonify({
                'success': False,
                'message': f'获取股票列表异常: {str(e)}',
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
        
        # 计算技术指标
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


if __name__ == '__main__':
    import socket
    import subprocess
    import os
    import time
    
    # 检查并释放端口5002（更强制的方式）
    port = 5002
    
    # 先尝试用pkill停止所有相关进程
    try:
        subprocess.run(['pkill', '-9', '-f', 'bull_stock_web'], 
                      capture_output=True, timeout=2)
        time.sleep(0.5)
    except:
        pass
    
    # 再检查端口并释放
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
    
    print("=" * 80)
    print("大牛股分析器Web界面")
    print("=" * 80)
    print("访问地址: http://localhost:5002")
    print("=" * 80)
    # 增加请求超时时间，避免长时间扫描任务超时
    import werkzeug.serving
    werkzeug.serving.WSGIRequestHandler.timeout = 60  # 设置60秒超时
    # 监听所有网络接口，允许远程访问
    # 关闭debug模式，避免自动重启导致的问题
    app.run(host='0.0.0.0', port=5002, debug=False, threaded=True, use_reloader=False)

