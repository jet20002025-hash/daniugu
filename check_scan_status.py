#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查扫描状态和定位问题
"""
import os
import time
import json

def check_scan_status():
    """检查扫描状态"""
    print("=" * 80)
    print("🔍 扫描状态检查工具")
    print("=" * 80)
    
    # 1. 检查进度API
    print("\n📊 1. 检查当前扫描进度...")
    try:
        import requests
        response = requests.get('http://localhost:5002/api/get_scan_progress', timeout=5)
        if response.status_code == 200:
            progress = response.json()
            print(f"   状态: {progress.get('status', '未知')}")
            print(f"   进度: {progress.get('percentage', 0):.1f}%")
            print(f"   当前: {progress.get('current', 0)}/{progress.get('total', 0)}")
            print(f"   当前股票: {progress.get('current_stock', '未知')} {progress.get('current_stock_name', '')}")
            print(f"   已找到: {progress.get('found', 0)} 只")
            
            if 'time_since_last_update' in progress:
                time_since = progress['time_since_last_update']
                print(f"   距离最后更新: {time_since:.1f} 秒")
                if time_since > 30:
                    print(f"   ⚠️ 警告: 已超过30秒未更新，可能卡住了！")
                    print(f"   ⚠️ 当前卡住的股票: {progress.get('current_stock', '未知')}")
            
            if 'warning' in progress:
                print(f"   ⚠️ {progress['warning']}")
        else:
            print(f"   ❌ API请求失败: HTTP {response.status_code}")
    except Exception as e:
        print(f"   ❌ 无法连接API: {e}")
    
    # 2. 检查调试日志
    print("\n📝 2. 检查调试日志（最后20行）...")
    log_file = 'scan_debug.log'
    if os.path.exists(log_file):
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                print(f"   日志总行数: {len(lines)}")
                print(f"   最后20行:")
                print("   " + "-" * 70)
                for line in lines[-20:]:
                    print(f"   {line.rstrip()}")
                print("   " + "-" * 70)
                
                # 检查是否有错误或超时
                error_count = sum(1 for line in lines if 'ERROR' in line or '超时' in line or 'timeout' in line.lower())
                if error_count > 0:
                    print(f"\n   ⚠️ 发现 {error_count} 条错误/超时记录")
        except Exception as e:
            print(f"   ❌ 读取日志失败: {e}")
    else:
        print(f"   ⚠️ 日志文件不存在: {log_file}")
    
    # 3. 检查服务状态
    print("\n🌐 3. 检查Web服务状态...")
    try:
        import requests
        response = requests.get('http://localhost:5002/api/get_stocks', timeout=5)
        if response.status_code == 200:
            print("   ✅ Web服务正常运行")
        else:
            print(f"   ⚠️ Web服务响应异常: HTTP {response.status_code}")
    except Exception as e:
        print(f"   ❌ Web服务无法连接: {e}")
    
    # 4. 提供建议
    print("\n💡 4. 问题定位建议:")
    print("   - 如果进度长时间未更新，查看日志文件最后几行")
    print("   - 检查当前卡住的股票代码，可能是该股票数据获取超时")
    print("   - 查看日志中的ERROR和超时记录，了解具体问题")
    print("   - 如果某个股票反复超时，可能是数据源问题")
    print("\n📋 查看完整日志命令:")
    print(f"   tail -f {log_file}")
    print(f"   或: tail -100 {log_file}")
    
    print("\n" + "=" * 80)

if __name__ == '__main__':
    check_scan_status()







