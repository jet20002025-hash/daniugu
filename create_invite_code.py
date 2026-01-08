#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""创建邀请码工具"""
from user_auth import create_invite_code, list_invite_codes
import sys

def main():
    if len(sys.argv) < 2:
        print("=" * 60)
        print("邀请码管理工具")
        print("=" * 60)
        print("\n用法:")
        print("  创建邀请码: python create_invite_code.py <邀请码> [使用次数]")
        print("  查看所有邀请码: python create_invite_code.py list")
        print("\n示例:")
        print("  python create_invite_code.py NEWCODE2024 1")
        print("  python create_invite_code.py MULTI2024 10")
        print("  python create_invite_code.py list")
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
        print(f"{'邀请码':<20} {'状态':<10} {'使用次数':<12} {'使用人':<15}")
        print("-" * 60)
        
        for code, info in codes.items():
            status = "已使用" if info.get('used', False) else "可用"
            use_count = f"{info.get('use_count', 0)}/{info.get('max_uses', 1)}"
            used_by = info.get('used_by', 'N/A')
            
            print(f"{code:<20} {status:<10} {use_count:<12} {used_by:<15}")
        
        print("=" * 60)
    else:
        # 创建邀请码
        code = sys.argv[1].upper()
        max_uses = int(sys.argv[2]) if len(sys.argv) > 2 else 1
        
        result = create_invite_code(code, max_uses)
        print(result['message'])

if __name__ == '__main__':
    main()

