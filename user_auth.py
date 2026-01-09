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

# 初始化
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


