#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
用户认证模块
实现会员注册和登录功能
"""
import hashlib
import json
import os
from datetime import datetime, timedelta
from functools import wraps
from flask import session, request, jsonify

# 用户数据文件
USERS_FILE = 'users.json'
INVITE_CODES_FILE = 'invite_codes.json'

# 初始化用户数据文件
def init_data_files():
    """初始化数据文件"""
    if not os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'w', encoding='utf-8') as f:
            json.dump({}, f, ensure_ascii=False, indent=2)
    
    if not os.path.exists(INVITE_CODES_FILE):
        # 创建默认邀请码
        default_codes = {
            'ADMIN2024': {
                'code': 'ADMIN2024',
                'created_at': datetime.now().isoformat(),
                'used': False,
                'used_by': None,
                'used_at': None,
                'max_uses': 1
            },
            'VIP2024': {
                'code': 'VIP2024',
                'created_at': datetime.now().isoformat(),
                'used': False,
                'used_by': None,
                'used_at': None,
                'max_uses': 1
            }
        }
        with open(INVITE_CODES_FILE, 'w', encoding='utf-8') as f:
            json.dump(default_codes, f, ensure_ascii=False, indent=2)

# 初始化默认测试用户（永久保留，除非用户明确删除）
def init_default_test_users():
    """初始化默认测试用户（永久保留）"""
    users = load_users()
    updated = False
    
    # 默认测试用户配置（永久保留）
    default_test_users = [
        {
            'username': 'super',
            'email': 'super@test.com',
            'password': 'super123',
            'is_vip': True,
            'is_super': True,
            'is_test_user': True,  # 标记为测试用户
            'tier_name': '超级用户'
        },
        {
            'username': 'vip',
            'email': 'vip@test.com',
            'password': 'vip123',
            'is_vip': True,
            'is_super': False,
            'is_test_user': True,  # 标记为测试用户
            'tier_name': 'VIP用户'
        },
        {
            'username': 'free',
            'email': 'free@test.com',
            'password': 'free123',
            'is_vip': False,
            'is_super': False,
            'is_test_user': True,  # 标记为测试用户
            'tier_name': '免费用户'
        }
    ]
    
    for user_config in default_test_users:
        username = user_config['username']
        
        # 检查用户是否已存在
        if username in users:
            # 如果用户已存在，检查是否需要更新（保持测试用户标记）
            existing_user = users[username]
            if not existing_user.get('is_test_user', False):
                # 如果现有用户不是测试用户，更新为测试用户（但保留其他数据）
                existing_user['is_test_user'] = True
                updated = True
            # 确保密码和权限正确（用于测试）
            if existing_user.get('password') != hash_password(user_config['password']):
                existing_user['password'] = hash_password(user_config['password'])
                updated = True
            if existing_user.get('is_vip') != user_config['is_vip']:
                existing_user['is_vip'] = user_config['is_vip']
                updated = True
            if existing_user.get('is_super') != user_config['is_super']:
                existing_user['is_super'] = user_config['is_super']
                updated = True
        else:
            # 创建新测试用户
            user_data = {
                'username': username,
                'email': user_config['email'],
                'password': hash_password(user_config['password']),
                'created_at': datetime.now().isoformat(),
                'last_login': None,
                'invite_code': 'DEFAULT_TEST_USER',
                'is_active': True,
                'is_vip': user_config['is_vip'],
                'is_super': user_config['is_super'],
                'is_test_user': True  # 标记为测试用户（永久保留）
            }
            users[username] = user_data
            updated = True
            print(f"✅ 创建默认测试用户: {username} ({user_config['tier_name']})")
    
    # 如果有更新，保存用户数据
    if updated:
        save_users(users)
        print("✅ 默认测试用户已初始化")

# 初始化数据文件
init_data_files()

def hash_password(password):
    """加密密码"""
    return hashlib.sha256(password.encode('utf-8')).hexdigest()

def load_users():
    """加载用户数据"""
    try:
        with open(USERS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {}

def save_users(users):
    """保存用户数据"""
    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

def load_invite_codes():
    """加载邀请码数据"""
    try:
        with open(INVITE_CODES_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {}

def save_invite_codes(codes):
    """保存邀请码数据"""
    with open(INVITE_CODES_FILE, 'w', encoding='utf-8') as f:
        json.dump(codes, f, ensure_ascii=False, indent=2)

def register_user(username, email, password, invite_code=None):
    """注册用户（邮箱注册，无需邀请码）"""
    users = load_users()
    
    # 检查用户名是否已存在
    if username in users:
        return {'success': False, 'message': '用户名已存在'}
    
    # 检查邮箱是否已注册
    for user in users.values():
        if user.get('email') == email:
            return {'success': False, 'message': '邮箱已被注册'}
    
    # 创建用户（默认免费用户，只能查看，不能扫描）
    user_data = {
        'username': username,
        'email': email,
        'password': hash_password(password),
        'created_at': datetime.now().isoformat(),
        'last_login': None,
        'invite_code': invite_code or 'EMAIL_REGISTER',  # 记录注册方式
        'is_active': True,
        'is_vip': False,  # 默认免费用户
        'is_super': False  # 默认非超级用户
    }
    
    users[username] = user_data
    save_users(users)
    
    return {'success': True, 'message': '注册成功'}

def login_user(username, password):
    """用户登录"""
    users = load_users()
    
    if username not in users:
        return {'success': False, 'message': '用户名或密码错误'}
    
    user = users[username]
    
    # 检查账户是否激活
    if not user.get('is_active', True):
        return {'success': False, 'message': '账户已被禁用'}
    
    # 验证密码
    if user['password'] != hash_password(password):
        return {'success': False, 'message': '用户名或密码错误'}
    
    # 更新最后登录时间
    user['last_login'] = datetime.now().isoformat()
    save_users(users)
    
    return {
        'success': True,
        'message': '登录成功',
        'user': {
            'username': user['username'],
            'email': user['email'],
            'is_vip': user.get('is_vip', False)
        }
    }

def is_logged_in():
    """检查用户是否已登录"""
    return 'username' in session

def get_current_user():
    """获取当前登录用户"""
    if not is_logged_in():
        return None
    
    users = load_users()
    username = session.get('username')
    
    if username in users:
        user = users[username]
        return {
            'username': user['username'],
            'email': user['email'],
            'is_vip': user.get('is_vip', False)
        }
    
    return None

def require_login(f):
    """装饰器：要求登录"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_logged_in():
            return jsonify({
                'success': False,
                'message': '请先登录',
                'require_login': True
            }), 401
        return f(*args, **kwargs)
    return decorated_function

def create_invite_code(code, max_uses=1):
    """创建邀请码"""
    invite_codes = load_invite_codes()
    
    invite_codes[code] = {
        'code': code,
        'created_at': datetime.now().isoformat(),
        'used': False,
        'used_by': None,
        'used_at': None,
        'max_uses': max_uses,
        'use_count': 0
    }
    
    save_invite_codes(invite_codes)
    return {'success': True, 'message': f'邀请码 {code} 创建成功'}

def list_invite_codes():
    """列出所有邀请码"""
    invite_codes = load_invite_codes()
    return invite_codes

def get_user_stats():
    """获取用户统计"""
    users = load_users()
    invite_codes = load_invite_codes()
    
    total_users = len(users)
    active_users = sum(1 for u in users.values() if u.get('is_active', True))
    vip_users = sum(1 for u in users.values() if u.get('is_vip', False))
    
    total_codes = len(invite_codes)
    used_codes = sum(1 for c in invite_codes.values() if c.get('used', False))
    available_codes = total_codes - used_codes
    
    return {
        'total_users': total_users,
        'active_users': active_users,
        'vip_users': vip_users,
        'total_invite_codes': total_codes,
        'used_codes': used_codes,
        'available_codes': available_codes
    }

# 在所有函数定义完成后，初始化默认测试用户（永久保留，直到用户明确删除）
# 注意：这个调用必须在所有函数定义之后，因为 init_default_test_users 依赖于 load_users, save_users, hash_password 等函数
try:
    init_default_test_users()
except Exception as e:
    print(f"⚠️ 初始化默认测试用户失败: {e}")
    import traceback
    traceback.print_exc()


