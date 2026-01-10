#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
创建测试用户脚本
创建3个测试账户：超级用户、VIP用户、免费用户
"""
import os
import sys
from datetime import datetime

# 检测环境
is_vercel = (
    os.environ.get('VERCEL') == '1' or 
    os.environ.get('VERCEL_ENV') is not None or
    os.environ.get('VERCEL_URL') is not None
)

# 根据环境导入对应的用户认证模块
if is_vercel:
    print("🌐 检测到 Vercel 环境，使用 Vercel 存储...")
    try:
        from user_auth_vercel import (
            load_users, save_users, hash_password, register_user
        )
        print("✅ 使用 user_auth_vercel 模块")
    except ImportError as e:
        print(f"❌ 无法导入 user_auth_vercel: {e}")
        sys.exit(1)
else:
    print("💻 检测到本地环境，使用文件存储...")
    try:
        from user_auth import (
            load_users, save_users, hash_password, register_user
        )
        print("✅ 使用 user_auth 模块")
    except ImportError as e:
        print(f"❌ 无法导入 user_auth: {e}")
        sys.exit(1)


def create_test_users():
    """创建测试用户"""
    print("\n" + "=" * 60)
    print("🔧 开始创建测试用户...")
    print("=" * 60)
    
    users = load_users()
    
    # 测试用户配置
    test_users = [
        {
            'username': 'super',
            'email': 'super@test.com',
            'password': 'super123',
            'is_vip': True,
            'is_super': True,
            'tier_name': '超级用户'
        },
        {
            'username': 'vip',
            'email': 'vip@test.com',
            'password': 'vip123',
            'is_vip': True,
            'is_super': False,
            'tier_name': 'VIP用户'
        },
        {
            'username': 'free',
            'email': 'free@test.com',
            'password': 'free123',
            'is_vip': False,
            'is_super': False,
            'tier_name': '免费用户'
        }
    ]
    
    created_users = []
    updated_users = []
    
    for user_config in test_users:
        username = user_config['username']
        email = user_config['email']
        password = user_config['password']
        is_vip = user_config['is_vip']
        is_super = user_config['is_super']
        tier_name = user_config['tier_name']
        
        # 检查用户是否已存在
        if username in users:
            print(f"\n⚠️  用户 '{username}' 已存在，更新用户信息...")
            # 更新现有用户
            users[username]['email'] = email
            users[username]['password'] = hash_password(password)
            users[username]['is_vip'] = is_vip
            users[username]['is_super'] = is_super
            users[username]['is_active'] = True
            users[username]['last_login'] = None
            updated_users.append(user_config)
        else:
            # 创建新用户
            user_data = {
                'username': username,
                'email': email,
                'password': hash_password(password),
                'created_at': datetime.now().isoformat(),
                'last_login': None,
                'invite_code': 'TEST_USER',
                'is_active': True,
                'is_vip': is_vip,
                'is_super': is_super
            }
            users[username] = user_data
            created_users.append(user_config)
    
    # 保存用户数据
    try:
        save_users(users)
        print("\n" + "=" * 60)
        print("✅ 测试用户创建/更新成功！")
        print("=" * 60)
        
        # 显示创建的用户
        if created_users:
            print("\n📝 新创建的用户：")
            for user_config in created_users:
                print(f"  - {user_config['tier_name']}: {user_config['username']} / {user_config['password']}")
        
        if updated_users:
            print("\n🔄 已更新的用户：")
            for user_config in updated_users:
                print(f"  - {user_config['tier_name']}: {user_config['username']} / {user_config['password']}")
        
        # 显示所有测试账户信息
        print("\n" + "=" * 60)
        print("📋 测试账户信息汇总")
        print("=" * 60)
        for user_config in test_users:
            print(f"\n{user_config['tier_name']}:")
            print(f"  用户名: {user_config['username']}")
            print(f"  密码: {user_config['password']}")
            print(f"  邮箱: {user_config['email']}")
            print(f"  VIP状态: {'是' if user_config['is_vip'] else '否'}")
            print(f"  超级用户: {'是' if user_config['is_super'] else '否'}")
        
        print("\n" + "=" * 60)
        print("💡 使用说明")
        print("=" * 60)
        print("1. 使用上述账号密码登录")
        print("2. 超级用户：拥有所有功能权限")
        print("3. VIP用户：拥有VIP功能权限（深度分析、关注列表、价格预警等）")
        print("4. 免费用户：只能查看系统自动扫描结果")
        print("=" * 60)
        
        return True
        
    except Exception as e:
        print(f"\n❌ 保存用户数据失败: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    try:
        success = create_test_users()
        if success:
            print("\n✅ 测试用户创建完成！")
            sys.exit(0)
        else:
            print("\n❌ 测试用户创建失败！")
            sys.exit(1)
    except Exception as e:
        print(f"\n❌ 创建测试用户时出错: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

