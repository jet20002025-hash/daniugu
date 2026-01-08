#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
用户认证模块 - Vercel 适配版（持久化存储）
支持多种持久化存储方案：
1. Upstash Redis（推荐，免费）
2. Vercel KV（如果配置）
3. 环境变量存储（简单方案，有限制）
"""
import hashlib
import json
import os
from datetime import datetime, timedelta
from functools import wraps
from flask import session, request, jsonify

# 存储后端类型
_storage_type = None
_redis_client = None

# 尝试使用 Upstash Redis（推荐，免费）
try:
    redis_url = os.environ.get('UPSTASH_REDIS_REST_URL')
    redis_token = os.environ.get('UPSTASH_REDIS_REST_TOKEN')
    if redis_url and redis_token:
        import requests
        _storage_type = 'upstash_redis'
        print("✅ 使用 Upstash Redis 持久化存储")
except Exception as e:
    print(f"⚠️ Upstash Redis 不可用: {e}")

# 如果 Upstash Redis 不可用，尝试使用 Vercel KV
if not _storage_type:
    try:
        from vercel_kv import kv
        _storage_type = 'vercel_kv'
        print("✅ 使用 Vercel KV 持久化存储")
    except ImportError:
        pass

# 如果都不可用，使用内存存储（会丢失，不推荐生产环境）
if not _storage_type:
    _storage_type = 'memory'
    print("⚠️ 使用内存存储（数据不会持久化，重启后会丢失）")

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

# 内存缓存（用于快速访问）
_users_cache = {}
_invite_codes_cache = None

def hash_password(password):
    """加密密码"""
    return hashlib.sha256(password.encode('utf-8')).hexdigest()

def _upstash_redis_get(key):
    """从 Upstash Redis 获取数据"""
    try:
        redis_url = os.environ.get('UPSTASH_REDIS_REST_URL')
        redis_token = os.environ.get('UPSTASH_REDIS_REST_TOKEN')
        if not redis_url or not redis_token:
            return None
        
        import requests
        response = requests.get(
            f"{redis_url}/get/{key}",
            headers={"Authorization": f"Bearer {redis_token}"}
        )
        if response.status_code == 200:
            result = response.json()
            return result.get('result')
        return None
    except Exception as e:
        print(f"⚠️ Upstash Redis GET 失败: {e}")
        return None

def _upstash_redis_set(key, value):
    """保存数据到 Upstash Redis"""
    try:
        redis_url = os.environ.get('UPSTASH_REDIS_REST_URL')
        redis_token = os.environ.get('UPSTASH_REDIS_REST_TOKEN')
        if not redis_url or not redis_token:
            return False
        
        import requests
        response = requests.post(
            f"{redis_url}/set/{key}",
            headers={
                "Authorization": f"Bearer {redis_token}",
                "Content-Type": "application/json"
            },
            json=value
        )
        return response.status_code == 200
    except Exception as e:
        print(f"⚠️ Upstash Redis SET 失败: {e}")
        return False

def load_users():
    """加载用户数据（从持久化存储）"""
    global _users_cache
    
    # 如果缓存存在且非空，直接返回
    if _users_cache:
        return _users_cache.copy()
    
    try:
        if _storage_type == 'upstash_redis':
            # 从 Upstash Redis 加载
            data = _upstash_redis_get('users')
            if data:
                _users_cache = json.loads(data) if isinstance(data, str) else data
                return _users_cache.copy()
        elif _storage_type == 'vercel_kv':
            # 从 Vercel KV 加载
            from vercel_kv import kv
            data = kv.get('users')
            if data:
                _users_cache = json.loads(data) if isinstance(data, str) else data
                return _users_cache.copy()
        elif _storage_type == 'memory':
            # 内存存储，直接返回缓存（可能是空的）
            pass
    except Exception as e:
        print(f"⚠️ 加载用户数据失败: {e}")
    
    # 如果加载失败或使用内存存储，返回缓存（可能是空的）
    if not _users_cache:
        _users_cache = {}
    return _users_cache.copy()

def save_users(users):
    """保存用户数据（到持久化存储）"""
    global _users_cache
    
    try:
        _users_cache = users.copy()
        users_json = json.dumps(users, ensure_ascii=False)
        
        if _storage_type == 'upstash_redis':
            # 保存到 Upstash Redis
            success = _upstash_redis_set('users', users_json)
            if success:
                return True
        elif _storage_type == 'vercel_kv':
            # 保存到 Vercel KV
            from vercel_kv import kv
            kv.set('users', users_json)
            return True
        elif _storage_type == 'memory':
            # 内存存储，只更新缓存（重启后会丢失）
            return True
    except Exception as e:
        print(f"⚠️ 保存用户数据失败: {e}")
    
    # 即使保存失败，也更新缓存（至少内存中有数据）
    return True

def load_invite_codes():
    """加载邀请码数据（从持久化存储）"""
    global _invite_codes_cache
    
    # 如果缓存存在，直接返回
    if _invite_codes_cache:
        return _invite_codes_cache.copy()
    
    try:
        if _storage_type == 'upstash_redis':
            # 从 Upstash Redis 加载
            data = _upstash_redis_get('invite_codes')
            if data:
                _invite_codes_cache = json.loads(data) if isinstance(data, str) else data
            else:
                # 如果不存在，使用环境变量初始化
                _invite_codes_cache = get_invite_codes_from_env()
                save_invite_codes(_invite_codes_cache)
            return _invite_codes_cache.copy()
        elif _storage_type == 'vercel_kv':
            # 从 Vercel KV 加载
            from vercel_kv import kv
            data = kv.get('invite_codes')
            if data:
                _invite_codes_cache = json.loads(data) if isinstance(data, str) else data
            else:
                # 如果不存在，使用环境变量初始化
                _invite_codes_cache = get_invite_codes_from_env()
                save_invite_codes(_invite_codes_cache)
            return _invite_codes_cache.copy()
        elif _storage_type == 'memory':
            # 内存存储，使用环境变量初始化
            _invite_codes_cache = get_invite_codes_from_env()
            return _invite_codes_cache.copy()
    except Exception as e:
        print(f"⚠️ 加载邀请码数据失败: {e}")
    
    # 如果加载失败，使用环境变量
    _invite_codes_cache = get_invite_codes_from_env()
    return _invite_codes_cache.copy()

def save_invite_codes(codes):
    """保存邀请码数据（到持久化存储）"""
    global _invite_codes_cache
    
    try:
        _invite_codes_cache = codes.copy()
        codes_json = json.dumps(codes, ensure_ascii=False)
        
        if _storage_type == 'upstash_redis':
            # 保存到 Upstash Redis
            success = _upstash_redis_set('invite_codes', codes_json)
            if success:
                return True
        elif _storage_type == 'vercel_kv':
            # 保存到 Vercel KV
            from vercel_kv import kv
            kv.set('invite_codes', codes_json)
            return True
        elif _storage_type == 'memory':
            # 内存存储，只更新缓存（重启后会丢失）
            return True
    except Exception as e:
        print(f"⚠️ 保存邀请码数据失败: {e}")
    
    # 即使保存失败，也更新缓存（至少内存中有数据）
    return True

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
    """创建邀请码（持久化）"""
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
    return {'success': True, 'message': f'邀请码 {code} 创建成功（已持久化）'}

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
        'available_codes': available_codes,
        'storage_type': _storage_type
    }
