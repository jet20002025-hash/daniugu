#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查直接运行的扫描测试状态
"""
import os
import time
from datetime import datetime

def check_scan_status():
    log_file = 'auto_scan_output.log'
    
    if not os.path.exists(log_file):
        print("⚠️  日志文件不存在: auto_scan_output.log")
        print("   扫描可能还未开始或已结束")
        return
    
    # 读取日志文件
    with open(log_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    if not lines:
        print("⚠️  日志文件为空")
        return
    
    print("=" * 80)
    print("🔍 直接扫描测试状态检查")
    print("=" * 80)
    print()
    
    # 检查进程是否还在运行
    import subprocess
    result = subprocess.run(['pgrep', '-f', 'auto_scan_test.py'], 
                          capture_output=True, text=True)
    if result.returncode == 0:
        pids = result.stdout.strip().split('\n')
        print(f"✅ 扫描进程正在运行 (PID: {', '.join(pids)})")
    else:
        print("⚠️  扫描进程未运行（可能已完成或已停止）")
    
    print()
    
    # 分析日志
    print("📊 扫描进度分析:")
    print()
    
    # 查找关键信息
    total_stocks = None
    current_stock = None
    found_count = 0
    batch_info = None
    
    for line in lines[-100:]:  # 只看最后100行
        if '总扫描股票数' in line or 'total_scanned' in line:
            try:
                # 尝试提取数字
                import re
                match = re.search(r'(\d+)', line)
                if match:
                    total_stocks = match.group(1)
            except:
                pass
        
        if '找到符合条件的股票' in line or 'found_count' in line:
            try:
                import re
                match = re.search(r'(\d+)', line)
                if match:
                    found_count = int(match.group(1))
            except:
                pass
        
        if '开始处理' in line or '开始获取周K线' in line:
            # 提取股票代码
            import re
            match = re.search(r'\[(\d+)/(\d+)\]', line)
            if match:
                current_idx = match.group(1)
                total = match.group(2)
                current_stock = f"{current_idx}/{total}"
            
            # 提取股票代码和名称
            match = re.search(r'(\d{6})\s+([^\s]+)', line)
            if match:
                stock_code = match.group(1)
                stock_name = match.group(2)
                current_stock = f"{stock_code} {stock_name}"
        
        if '第' in line and '批扫描' in line:
            batch_info = line.strip()
    
    # 显示进度
    if batch_info:
        print(f"   当前批次: {batch_info}")
    
    if current_stock:
        print(f"   当前处理: {current_stock}")
    
    if total_stocks:
        print(f"   总股票数: {total_stocks}")
    
    if found_count > 0:
        print(f"   ✅ 已找到: {found_count} 只符合条件的股票")
    
    print()
    
    # 显示最后几行日志
    print("📝 最新日志（最后10行）:")
    print("-" * 80)
    for line in lines[-10:]:
        print(line.rstrip())
    print("-" * 80)
    
    # 检查是否完成
    if '扫描完成' in ''.join(lines[-20:]):
        print()
        print("✅ 扫描已完成！")
        print()
        print("📋 查看完整结果:")
        print("   cat auto_scan_output.log | grep -A 5 '找到的个股'")
    elif '扫描失败' in ''.join(lines[-20:]) or '出错' in ''.join(lines[-20:]):
        print()
        print("❌ 扫描可能失败，请查看完整日志")
    
    print()
    print("=" * 80)
    print("💡 查看实时日志:")
    print("   tail -f auto_scan_output.log")
    print("=" * 80)

if __name__ == '__main__':
    check_scan_status()





