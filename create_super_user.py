#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
创建/更新超级用户脚本
用于在 Render 环境中创建或更新超级用户账户

使用方法：
1. 通过 Render Shell 执行：
   python create_super_user.py

2. 或者通过 API 调用（需要先设置环境变量 SUPER_USER_SECRET）：
   curl -X POST https://daniugu.onrender.com/api/admin/create_super_user \
     -H "Content-Type: application/json" \
     -d '{"secret": "your-secret-key"}'
"""
import os
import sys
import hashlib
import json
from datetime import datetime

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 导入用户认证模块
try:
    from user_auth_vercel import load_users, save_users, hash_password
    print("✅ 使用 user_auth_vercel（Redis 存储）")
except ImportError:
    try:
        from user_auth import load_users, save_users, hash_password
        print("✅ 使用 user_auth（文件存储）")
    except ImportError:
        print("❌ 无法导入用户认证模块")
        sys.exit(1)

def create_or_update_super_user(username='super', password='superzwj', email='super@admin.com'):
    """
    创建或更新超级用户
    
    参数：
    - username: 用户名（默认 'super'）
    - password: 密码（默认 'superzwj'）
    - email: 邮箱（默认 'super@admin.com'）
    """
    print(f"\n{'='*60}")
    print(f"🚀 创建/更新超级用户")
    print(f"{'='*60}\n")
    
    # 加载现有用户
    users = load_users()
    print(f"📊 当前用户数: {len(users)}")
    
    # 检查用户是否已存在
    if username in users:
        print(f"⚠️  用户 '{username}' 已存在，将更新密码和权限...")
        existing_user = users[username]
        
        # 更新密码
        existing_user['password'] = hash_password(password)
        print(f"✅ 密码已更新")
        
        # 更新权限
        existing_user['is_vip'] = True
        existing_user['is_super'] = True
        existing_user['is_active'] = True
        print(f"✅ 权限已更新：is_vip=True, is_super=True")
        
        # 更新邮箱（如果不同）
        if existing_user.get('email') != email:
            existing_user['email'] = email
            print(f"✅ 邮箱已更新：{email}")
        
        # 更新最后修改时间
        existing_user['updated_at'] = datetime.now().isoformat()
        
        users[username] = existing_user
    else:
        print(f"📝 创建新用户 '{username}'...")
        
        # 创建新用户
        user_data = {
            'username': username,
            'email': email,
            'password': hash_password(password),
            'created_at': datetime.now().isoformat(),
            'last_login': None,
            'invite_code': 'ADMIN_CREATED',
            'is_active': True,
            'is_vip': True,
            'is_super': True,
            'is_test_user': False  # 不是测试用户，是真正的管理员
        }
        
        users[username] = user_data
        print(f"✅ 用户已创建")
    
    # 保存用户数据
    print(f"\n💾 保存用户数据到存储...")
    success = save_users(users)
    
    if success:
        print(f"✅ 用户数据已保存成功！")
        print(f"\n{'='*60}")
        print(f"✅ 超级用户创建/更新完成！")
        print(f"{'='*60}\n")
        print(f"📋 用户信息：")
        print(f"   用户名: {username}")
        print(f"   密码: {password}")
        print(f"   邮箱: {email}")
        print(f"   权限: VIP + 超级用户")
        print(f"   状态: 激活")
        print(f"\n🔗 登录地址: https://daniugu.onrender.com")
        print(f"\n💡 提示：你现在可以使用这个账户登录系统，拥有所有功能权限！")
        return True
    else:
        print(f"❌ 保存用户数据失败！")
        return False

if __name__ == '__main__':
    # 从命令行参数获取用户名和密码（可选）
    username = sys.argv[1] if len(sys.argv) > 1 else 'super'
    password = sys.argv[2] if len(sys.argv) > 2 else 'superzwj'
    email = sys.argv[3] if len(sys.argv) > 3 else 'super@admin.com'
    
    # 创建/更新超级用户
    success = create_or_update_super_user(username, password, email)
    
    if success:
        sys.exit(0)
    else:
        sys.exit(1)
