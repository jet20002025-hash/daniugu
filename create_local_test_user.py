#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
创建本地测试账号脚本
用于快速创建测试用户，方便本地开发
"""
import json
import hashlib
import os
from datetime import datetime

def hash_password(password):
    """加密密码"""
    return hashlib.sha256(password.encode('utf-8')).hexdigest()

def create_test_user():
    """创建测试用户"""
    users_file = 'users.json'
    
    # 加载现有用户
    if os.path.exists(users_file):
        with open(users_file, 'r', encoding='utf-8') as f:
            users = json.load(f)
    else:
        users = {}
    
    # 测试账号信息
    test_username = 'test'
    test_password = 'test123'
    test_email = 'test@local.com'
    
    # 检查用户是否已存在
    if test_username in users:
        print(f"⚠️  用户 '{test_username}' 已存在，将更新密码...")
    
    # 创建/更新用户
    users[test_username] = {
        'username': test_username,
        'email': test_email,
        'password': hash_password(test_password),
        'created_at': datetime.now().isoformat(),
        'last_login': None,
        'invite_code': 'LOCAL_TEST',
        'is_active': True,
        'is_vip': True,  # 设置为VIP，方便测试
        'is_super': False  # 不是超级用户
    }
    
    # 保存用户
    with open(users_file, 'w', encoding='utf-8') as f:
        json.dump(users, f, ensure_ascii=False, indent=2)
    
    print("=" * 50)
    print("✅ 本地测试账号创建成功！")
    print("=" * 50)
    print(f"用户名: {test_username}")
    print(f"密码: {test_password}")
    print(f"邮箱: {test_email}")
    print(f"VIP状态: 是")
    print("=" * 50)
    print("\n💡 提示：")
    print("   1. 使用上述账号密码登录")
    print("   2. 该账号为VIP用户，可以随时扫描")
    print("   3. 此账号仅用于本地开发测试")
    print("=" * 50)

if __name__ == '__main__':
    create_test_user()

