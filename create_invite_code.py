#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""创建邀请码工具"""
from user_auth import create_invite_code, list_invite_codes
import sys
import secrets
import string

def generate_random_code(length=16):
    """
    生成安全的随机邀请码
    :param length: 邀请码长度（默认16位）
    :return: 随机邀请码字符串
    """
    # 使用安全的字符集（避免容易混淆的字符：0/O, 1/I/l）
    # 大写字母（排除 I, O）
    uppercase = 'ABCDEFGHJKLMNPQRSTUVWXYZ'
    # 小写字母（排除 i, l, o）
    lowercase = 'abcdefghjkmnpqrstuvwxyz'
    # 数字（排除 0, 1）
    digits = '23456789'
    
    # 组合字符集
    alphabet = uppercase + lowercase + digits
    
    # 使用 secrets 模块生成安全的随机字符串
    code = ''.join(secrets.choice(alphabet) for _ in range(length))
    
    return code

def main():
    if len(sys.argv) < 2:
        print("=" * 60)
        print("邀请码管理工具")
        print("=" * 60)
        print("\n用法:")
        print("  生成随机邀请码: python create_invite_code.py generate [数量] [使用次数] [长度]")
        print("  创建指定邀请码: python create_invite_code.py <邀请码> [使用次数]")
        print("  查看所有邀请码: python create_invite_code.py list")
        print("\n示例:")
        print("  python create_invite_code.py generate 10 1 16  # 生成10个16位随机邀请码，每个使用1次")
        print("  python create_invite_code.py generate 5 10 20  # 生成5个20位随机邀请码，每个使用10次")
        print("  python create_invite_code.py CUSTOM2024 1     # 创建指定邀请码")
        print("  python create_invite_code.py list              # 查看所有邀请码")
        sys.exit(1)
    
    if sys.argv[1] == 'list':
        # 列出所有邀请码
        codes = list_invite_codes()
        if not codes:
            print("暂无邀请码")
            return
        
        print("\n" + "=" * 60)
        print("邀请码列表")
        print("=" * 60)
        print(f"{'邀请码':<25} {'状态':<10} {'使用次数':<12} {'使用人':<15}")
        print("-" * 60)
        
        for code, info in codes.items():
            status = "已使用" if info.get('used', False) else "可用"
            use_count = f"{info.get('use_count', 0)}/{info.get('max_uses', 1)}"
            used_by = info.get('used_by') or 'N/A'
            
            print(f"{code:<25} {status:<10} {use_count:<12} {used_by:<15}")
        
        print("=" * 60)
    elif sys.argv[1] == 'generate':
        # 生成随机邀请码
        count = int(sys.argv[2]) if len(sys.argv) > 2 else 1
        max_uses = int(sys.argv[3]) if len(sys.argv) > 3 else 1
        length = int(sys.argv[4]) if len(sys.argv) > 4 else 16
        
        print("=" * 60)
        print(f"生成 {count} 个随机邀请码（长度: {length}，每个使用 {max_uses} 次）")
        print("=" * 60)
        print()
        
        generated_codes = []
        for i in range(count):
            # 生成随机邀请码，确保不重复
            attempts = 0
            while attempts < 100:  # 最多尝试100次
                code = generate_random_code(length)
                existing_codes = list_invite_codes()
                if code not in existing_codes:
                    break
                attempts += 1
            
            if attempts >= 100:
                print(f"❌ 生成第 {i+1} 个邀请码失败：无法生成唯一邀请码")
                continue
            
            # 创建邀请码
            result = create_invite_code(code, max_uses)
            if result.get('success'):
                generated_codes.append(code)
                print(f"✅ [{i+1}/{count}] {code}")
            else:
                print(f"❌ [{i+1}/{count}] 创建失败: {result.get('message', '')}")
        
        print()
        print("=" * 60)
        print(f"✅ 成功生成 {len(generated_codes)} 个邀请码")
        print("=" * 60)
        if generated_codes:
            print("\n生成的邀请码列表：")
            for code in generated_codes:
                print(f"  - {code}")
    else:
        # 创建指定邀请码
        code = sys.argv[1].upper()
        max_uses = int(sys.argv[2]) if len(sys.argv) > 2 else 1
        
        result = create_invite_code(code, max_uses)
        print(result['message'])

if __name__ == '__main__':
    main()

