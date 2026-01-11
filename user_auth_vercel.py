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

# 初始化标志（避免重复初始化）
_test_users_initialized = False

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
    
    # 如果缓存存在且非空，且是字典类型，直接返回
    if _users_cache and isinstance(_users_cache, dict):
        return _users_cache.copy()
    
    try:
        if _storage_type == 'upstash_redis':
            # 从 Upstash Redis 加载
            data = _upstash_redis_get('users')
            if data:
                if isinstance(data, str):
                    try:
                        _users_cache = json.loads(data)
                    except (json.JSONDecodeError, TypeError):
                        print(f"⚠️ 解析用户数据失败（不是有效的 JSON），使用空字典: {data[:100] if len(data) > 100 else data}")
                        _users_cache = {}
                elif isinstance(data, dict):
                    _users_cache = data
                else:
                    print(f"⚠️ 用户数据格式不正确（类型：{type(data)}），使用空字典")
                    _users_cache = {}
                # 确保 _users_cache 是字典类型
                if isinstance(_users_cache, dict):
                    return _users_cache.copy()
        elif _storage_type == 'vercel_kv':
            # 从 Vercel KV 加载
            from vercel_kv import kv
            data = kv.get('users')
            if data:
                if isinstance(data, str):
                    try:
                        _users_cache = json.loads(data)
                    except (json.JSONDecodeError, TypeError):
                        print(f"⚠️ 解析用户数据失败（不是有效的 JSON），使用空字典: {data[:100] if len(data) > 100 else data}")
                        _users_cache = {}
                elif isinstance(data, dict):
                    _users_cache = data
                else:
                    print(f"⚠️ 用户数据格式不正确（类型：{type(data)}），使用空字典")
                    _users_cache = {}
                # 确保 _users_cache 是字典类型
                if isinstance(_users_cache, dict):
                    return _users_cache.copy()
        elif _storage_type == 'memory':
            # 内存存储，直接返回缓存（可能是空的）
            pass
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"⚠️ 加载用户数据失败: {e}")
        print(f"⚠️ 错误详情: {error_detail}")
    
    # 如果加载失败或使用内存存储，返回缓存（确保是字典类型）
    if not isinstance(_users_cache, dict):
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

# 初始化默认测试用户（永久保留，除非用户明确删除）
def init_default_test_users():
    """初始化默认测试用户（永久保留）"""
    global _test_users_initialized
    if _test_users_initialized:
        return  # 避免重复初始化
    
    _test_users_initialized = True
    users = load_users()
    updated = False
    
    # 默认测试用户配置（永久保留，直到用户明确删除）
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
            # 如果用户已存在，检查是否需要更新（保持测试用户标记和权限）
            existing_user = users[username]
            needs_update = False
            
            if not existing_user.get('is_test_user', False):
                existing_user['is_test_user'] = True
                needs_update = True
            
            # 确保密码正确（用于测试）
            if existing_user.get('password') != hash_password(user_config['password']):
                existing_user['password'] = hash_password(user_config['password'])
                needs_update = True
            
            # 确保权限正确（用于测试）
            if existing_user.get('is_vip') != user_config['is_vip']:
                existing_user['is_vip'] = user_config['is_vip']
                needs_update = True
            if existing_user.get('is_super') != user_config['is_super']:
                existing_user['is_super'] = user_config['is_super']
                needs_update = True
            
            if needs_update:
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
                'is_test_user': True  # 标记为测试用户（永久保留，直到用户明确删除）
            }
            users[username] = user_data
            updated = True
            print(f"✅ 创建默认测试用户: {username} ({user_config['tier_name']})")
    
    # 如果有更新，保存用户数据
    if updated:
        save_users(users)
        if _storage_type != 'memory':  # 内存存储时不打印
            print("✅ 默认测试用户已初始化（永久保留）")


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
        try:
            if not is_logged_in():
                from flask import jsonify
                return jsonify({
                    'success': False,
                    'message': '请先登录',
                    'require_login': True
                }), 401
            return f(*args, **kwargs)
        except Exception as e:
            import traceback
            error_detail = traceback.format_exc()
            print(f"[require_login] ❌ 装饰器内部错误: {error_detail}")
            from flask import jsonify, request, has_request_context
            if has_request_context() and request.path.startswith('/api/'):
                return jsonify({
                    'success': False,
                    'message': f'服务器错误: {str(e)}',
                    'error_type': type(e).__name__,
                    'path': request.path if has_request_context() else 'unknown',
                    'method': request.method if has_request_context() else 'unknown'
                }), 500
            raise  # 非 API 路径或无法获取请求上下文，重新抛出异常
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

# 模块加载时自动初始化默认测试用户（永久保留，直到用户明确删除）
# 延迟初始化，避免在导入时就触发（在第一次使用时初始化）
try:
    # 在模块导入完成后，在后台线程中初始化（避免阻塞）
    import threading
    def _init_test_users_background():
        """在后台线程中初始化测试用户"""
        try:
            import time
            time.sleep(0.5)  # 稍微延迟，确保存储系统已初始化
            init_default_test_users()
        except Exception as e:
            print(f"⚠️ 初始化默认测试用户失败: {e}")
    
    # 延迟0.5秒后在后台线程初始化（避免在导入时阻塞）
    init_thread = threading.Thread(target=_init_test_users_background, daemon=True)
    init_thread.start()
except Exception as e:
    print(f"⚠️ 无法启动测试用户初始化线程: {e}")
    # 如果线程启动失败，直接初始化
    try:
        init_default_test_users()
    except Exception as e2:
        print(f"⚠️ 直接初始化默认测试用户也失败: {e2}")
