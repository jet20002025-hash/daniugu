#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
大牛股分析器Web界面
提供添加大牛股的功能
"""
from flask import Flask, render_template, jsonify, request, session, redirect, url_for
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

def get_user_tier():
    """获取用户等级：'free' 或 'premium'"""
    if is_premium_user():
        return 'premium'
    return 'free'

def get_scan_config():
    """根据用户等级返回扫描配置"""
    is_premium = is_premium_user()
    
    if is_premium:
        # 收费版（VIP）：快速扫描
        return {
            'batch_size': 50,      # 50只/批
            'batch_delay': 1,      # 延迟1秒
            'stock_timeout': 10,   # 单股票10秒
            'retry_delay': 2,      # 重试延迟2秒
            'daily_limit': None,   # 无限制
            'scan_interval': 0     # 无间隔
        }
    else:
        # 免费版：慢速扫描
        return {
            'batch_size': 20,      # 20只/批（更慢）
            'batch_delay': 3,      # 延迟3秒（更慢）
            'stock_timeout': 8,    # 单股票8秒
            'retry_delay': 5,      # 重试延迟5秒
            'daily_limit': 2000,   # 每日2000只
            'scan_interval': 180   # 间隔3分钟
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
    """用户注册API（需要邀请码）"""
    try:
        data = request.get_json() or {}
        username = data.get('username', '').strip()
        email = data.get('email', '').strip()
        password = data.get('password', '')
        invite_code = data.get('invite_code', '').strip().upper()
        
        if not username or not email or not password or not invite_code:
            return jsonify({
                'success': False,
                'message': '请填写所有字段'
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
        import traceback
        error_detail = traceback.format_exc()
        print(f"检查登录状态错误: {error_detail}")
        return jsonify({
            'success': False,
            'logged_in': False,
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


@app.route('/api/add_stock', methods=['POST'])
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
        tier = 'premium' if is_premium else 'free'
        scan_config = get_scan_config()
        
        return jsonify({
            'success': True,
            'user': {
                'username': user.get('username'),
                'email': user.get('email'),
                'tier': tier,
                'is_premium': is_premium,
                'scan_config': scan_config
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

@app.route('/admin')
@require_login
def admin_page():
    """管理员页面"""
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

@app.route('/api/get_stocks', methods=['GET'])
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


@app.route('/api/get_analysis/<stock_code>', methods=['GET'])
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
                import scan_progress_store
                progress = scan_progress_store.get_scan_progress(scan_id)
                if progress:
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
def scan_all_stocks():
    """扫描所有A股API"""
    init_analyzer()  # 确保分析器已初始化
    try:
        data = request.get_json() or {}
        min_match_score = float(data.get('min_match_score', 0.97))
        max_market_cap = float(data.get('max_market_cap', 100.0))
        limit = data.get('limit')
        if limit:
            limit = int(limit)
        
        # 在 Vercel 环境中，使用分批处理方案
        if is_vercel:
            import uuid
            import scan_progress_store
            
            # 生成扫描任务ID
            scan_id = str(uuid.uuid4())
            
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
            
            try:
                stock_list = analyzer.fetcher.get_all_stocks()
            except Exception as e:
                import traceback
                error_detail = traceback.format_exc()
                print(f"获取股票列表失败: {error_detail}")
                return jsonify({
                    'success': False,
                    'message': f'获取股票列表失败: {str(e)}'
                }), 500
            
            if stock_list is None or len(stock_list) == 0:
                return jsonify({
                    'success': False,
                    'message': '无法获取股票列表'
                }), 500
            
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
def continue_scan():
    """继续扫描下一批次（Vercel 环境）"""
    if not is_vercel:
        return jsonify({
            'success': False,
            'message': '此API仅在 Vercel 环境中可用'
        }), 400
    
    try:
        data = request.get_json() or {}
        scan_id = data.get('scan_id')
        if not scan_id:
            return jsonify({
                'success': False,
                'message': '缺少 scan_id 参数'
            }), 400
        
        import scan_progress_store
        from vercel_scan_helper import process_scan_batch_vercel
        
        # 获取当前进度
        progress = scan_progress_store.get_scan_progress(scan_id)
        if not progress:
            # 提供更详细的错误信息
            import traceback
            error_detail = traceback.format_exc()
            print(f"⚠️ 找不到扫描任务 scan_id={scan_id}")
            print(f"   可能原因：1) Redis 数据过期（TTL 24小时） 2) scan_id 错误 3) Redis 连接问题")
            return jsonify({
                'success': False,
                'message': f'找不到扫描任务（scan_id: {scan_id}）。可能原因：数据已过期（超过24小时）或任务已删除。',
                'error_code': 'SCAN_NOT_FOUND',
                'scan_id': scan_id
            }), 404
        
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
        
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"继续扫描错误: {error_detail}")
        return jsonify({
            'success': False,
            'message': f'服务器错误: {str(e)}'
        }), 500


@app.route('/api/stop_scan', methods=['POST'])
def stop_scan():
    """停止扫描API"""
    try:
        # 在 Vercel 环境中，更新 Redis 中的进度状态
        if is_vercel:
            data = request.get_json() or {}
            scan_id = data.get('scan_id')
            if scan_id:
                import scan_progress_store
                progress = scan_progress_store.get_scan_progress(scan_id)
                if progress:
                    progress['status'] = '已停止'
                    progress['detail'] = '扫描已停止（用户请求）'
                    scan_progress_store.save_scan_progress(scan_id, progress)
                    return jsonify({
                        'success': True,
                        'message': '停止扫描请求已发送'
                    })
        
        # 本地环境
        init_analyzer()  # 确保分析器已初始化
        analyzer.stop_scanning()
        return jsonify({
            'success': True,
            'message': '停止扫描请求已发送'
        })
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"停止扫描错误: {error_detail}")
        return jsonify({
            'success': False,
            'message': f'服务器错误: {str(e)}'
        }), 500


@app.route('/api/find_buy_points', methods=['POST'])
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
def get_scan_results():
    """获取扫描结果API"""
    try:
        # 在 Vercel 环境中，从 Redis 读取结果
        if is_vercel:
            scan_id = request.args.get('scan_id') or request.args.get('scanId')
            if scan_id:
                import scan_progress_store
                results = scan_progress_store.get_scan_results(scan_id)
                if results:
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
                    if progress and progress.get('candidates'):
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


@app.route('/api/scan_reversal_stocks', methods=['POST'])
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

@app.route('/api/get_weekly_kline_for_stock', methods=['POST'])
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

