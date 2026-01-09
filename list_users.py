#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
列出所有注册用户
支持本地文件和 Redis 两种存储方式
"""
import os
import json

def load_users_from_file():
    """从本地文件读取用户"""
    if os.path.exists('users.json'):
        with open('users.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    return None

def load_users_from_redis():
    """从 Redis 读取用户"""
    redis_url = os.environ.get('UPSTASH_REDIS_REST_URL')
    redis_token = os.environ.get('UPSTASH_REDIS_REST_TOKEN')
    
    if not redis_url or not redis_token:
        return None
    
    try:
        import requests
        # Upstash Redis REST API
        response = requests.get(
            f'{redis_url}/get/users',
            headers={'Authorization': f'Bearer {redis_token}'},
            timeout=5
        )
        if response.status_code == 200:
            result = response.json()
            users_str = result.get('result')
            if users_str:
                # 如果返回的是字符串，需要解析 JSON
                if isinstance(users_str, str):
                    try:
                        return json.loads(users_str)
                    except:
                        # 如果解析失败，可能已经是对象了
                        return users_str
                # 如果已经是对象，直接返回
                return users_str
        else:
            print(f'Redis 请求失败: HTTP {response.status_code}')
            print(f'响应: {response.text[:200]}')
    except Exception as e:
        print(f'读取 Redis 失败: {e}')
        import traceback
        traceback.print_exc()
    
    return None

def main():
    print('=' * 60)
    print('📋 用户列表')
    print('=' * 60)
    
    # 先尝试从本地文件读取
    users = load_users_from_file()
    source = '本地文件 (users.json)'
    
    # 如果本地没有，尝试从 Redis 读取
    if not users:
        users = load_users_from_redis()
        source = 'Redis'
    
    if not users:
        print('❌ 未找到用户数据')
        print('\n可能的原因：')
        print('1. 还没有用户注册')
        print('2. 用户数据存储在其他位置')
        return
    
    print(f'\n📦 数据来源: {source}')
    print(f'👥 总用户数: {len(users)}\n')
    print('-' * 60)
    
    # 统计信息
    vip_count = sum(1 for u in users.values() if u.get('is_vip', False))
    free_count = len(users) - vip_count
    
    for idx, (username, user_data) in enumerate(users.items(), 1):
        is_vip = user_data.get('is_vip', False)
        email = user_data.get('email', '无邮箱')
        created_at = user_data.get('created_at', '未知')
        last_login = user_data.get('last_login', '从未登录')
        invite_code = user_data.get('invite_code', '未知')
        is_active = user_data.get('is_active', True)
        
        vip_badge = '💎 VIP' if is_vip else '🆓 免费版'
        status_badge = '✅ 激活' if is_active else '❌ 禁用'
        
        print(f'\n[{idx}] 用户名: {username}')
        print(f'    邮箱: {email}')
        print(f'    等级: {vip_badge}')
        print(f'    状态: {status_badge}')
        print(f'    邀请码: {invite_code}')
        print(f'    注册时间: {created_at}')
        print(f'    最后登录: {last_login}')
        print('-' * 60)
    
    print(f'\n📊 统计信息:')
    print(f'   💎 VIP 用户: {vip_count} 人')
    print(f'   🆓 免费用户: {free_count} 人')
    print(f'   👥 总用户数: {len(users)} 人')
    print('=' * 60)

if __name__ == '__main__':
    main()

