#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
快速查找通达信数据目录的工具
"""

import os
import sys

def find_tdx_directories():
    """查找通达信数据目录"""
    possible_paths = [
        # Mac 常见路径
        os.path.expanduser('~/通达信/vipdoc/sh/lday'),
        os.path.expanduser('~/通达信/vipdoc/sz/lday'),
        '/Applications/通达信/vipdoc/sh/lday',
        '/Applications/通达信/vipdoc/sz/lday',
        # Windows 常见路径（如果在Mac上通过Wine运行）
        os.path.expanduser('~/wine/drive_c/new_tdx/vipdoc/sh/lday'),
        os.path.expanduser('~/wine/drive_c/new_tdx/vipdoc/sz/lday'),
    ]
    
    found_dirs = []
    for path in possible_paths:
        if os.path.exists(path):
            # 检查是否有 .day 文件
            day_files = [f for f in os.listdir(path) if f.endswith('.day')]
            if day_files:
                found_dirs.append({
                    'path': path,
                    'count': len(day_files),
                    'market': '上海' if 'sh' in path else '深圳'
                })
    
    return found_dirs

def main():
    print("=" * 60)
    print("🔍 查找通达信数据目录")
    print("=" * 60)
    print()
    
    found_dirs = find_tdx_directories()
    
    if found_dirs:
        print("✅ 找到以下通达信数据目录：")
        print()
        for i, dir_info in enumerate(found_dirs, 1):
            print(f"{i}. {dir_info['market']}股票数据")
            print(f"   路径: {dir_info['path']}")
            print(f"   文件数: {dir_info['count']} 个 .day 文件")
            print()
        
        print("=" * 60)
        print("📝 使用以下命令导入数据：")
        print("=" * 60)
        for dir_info in found_dirs:
            print(f"python3 import_tdx_data.py \"{dir_info['path']}\"")
        print()
    else:
        print("⚠️ 未找到通达信数据目录")
        print()
        print("请手动查找通达信安装目录，通常在：")
        print("  - ~/通达信/vipdoc/sh/lday (上海)")
        print("  - ~/通达信/vipdoc/sz/lday (深圳)")
        print()
        print("或者运行以下命令搜索：")
        print("  find ~ -name 'lday' -type d 2>/dev/null")
        print()

if __name__ == '__main__':
    main()
