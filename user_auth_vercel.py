#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
用户认证模块 - Vercel 适配版
使用环境变量和内存存储（适合 serverless 环境）
"""
import hashlib
import json
import os
from datetime import datetime, timedelta
from functools import wraps
from flask import session, request, jsonify

# 在 Vercel 环境中，使用环境变量存储邀请码
# 用户数据使用 session（临时存储，适合演示）
# 生产环境建议使用 Vercel KV 或数据库

# 从环境变量获取邀请码（用逗号分隔）
def get_invite_codes_from_env():
    """从环境变量获取邀请码列表"""
    codes_str = os.environ.get('INVITE_CODES', 'ADMIN2024,VIP2024')
    codes = {}
    for code in codes_str.split(','):
        code = code.strip().upper()
        if code:
            codes[code] = {
                'code': code,
                'created_at': datetime.now().isoformat(),
                'used': False,
                'used_by': None,
                'used_at': None,
                'max_uses': 1,
                'use_count': 0
            }
    return codes

# 内存存储（仅用于演示，生产环境应使用数据库）
_users_storage = {}
_invite_codes_storage = get_invite_codes_from_env()

def hash_password(password):
    """加密密码"""
    return hashlib.sha256(password.encode('utf-8')).hexdigest()

def load_users():
    """加载用户数据（从内存）"""
    return _users_storage.copy()

def save_users(users):
    """保存用户数据（到内存）"""
    global _users_storage
    _users_storage = users.copy()

def load_invite_codes():
    """加载邀请码数据（从环境变量和内存）"""
    # 合并环境变量和内存中的邀请码
    env_codes = get_invite_codes_from_env()
    merged = {**env_codes, **_invite_codes_storage}
    return merged

def save_invite_codes(codes):
    """保存邀请码数据（到内存）"""
    global _invite_codes_storage
    _invite_codes_storage = codes.copy()

def register_user(username, email, password, invite_code):
    """注册用户（需要邀请码）"""
    users = load_users()
    invite_codes = load_invite_codes()
    
    # 检查用户名是否已存在
    if username in users:
        return {'success': False, 'message': '用户名已存在'}
    
    # 检查邮箱是否已注册
    for user in users.values():
        if user.get('email') == email:
            return {'success': False, 'message': '邮箱已被注册'}
    
    # 验证邀请码
    if invite_code not in invite_codes:
        return {'success': False, 'message': '邀请码无效'}
    
    code_info = invite_codes[invite_code]
    
    # 检查邀请码是否已使用
    if code_info.get('used', False):
        # 检查使用次数
        if code_info.get('max_uses', 1) <= code_info.get('use_count', 0):
            return {'success': False, 'message': '邀请码已使用'}
    
    # 创建用户
    user_data = {
        'username': username,
        'email': email,
        'password': hash_password(password),
        'created_at': datetime.now().isoformat(),
        'last_login': None,
        'invite_code': invite_code,
        'is_active': True,
        'is_vip': False
    }
    
    users[username] = user_data
    save_users(users)
    
    # 更新邀请码使用状态
    if not code_info.get('use_count'):
        code_info['use_count'] = 0
    code_info['use_count'] = code_info.get('use_count', 0) + 1
    code_info['used_by'] = username
    code_info['used_at'] = datetime.now().isoformat()
    if code_info.get('use_count', 0) >= code_info.get('max_uses', 1):
        code_info['used'] = True
    
    save_invite_codes(invite_codes)
    
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
    """创建邀请码（仅内存，不会持久化）"""
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
    return {'success': True, 'message': f'邀请码 {code} 创建成功（仅内存）'}

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

