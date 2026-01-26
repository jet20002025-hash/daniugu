#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自动监控回测任务，直到生成结果
"""
import time
import os
import subprocess
import re
import glob
from datetime import datetime

print("=" * 80)
print("🚀 自动监控回测任务，直到生成结果")
print("=" * 80)
print()

log_file = "backtest_2025_weekly_top5.log"
result_pattern = "backtest_2025_weekly_top5_*.csv"
check_interval = 30  # 每30秒检查一次
max_wait_time = 3600 * 24  # 最多等待24小时
start_time = time.time()

def check_process():
    """检查进程是否运行"""
    try:
        result = subprocess.run(
            ["pgrep", "-f", "backtest_2025_weekly_top5.py"],
            capture_output=True,
            text=True
        )
        return result.returncode == 0
    except:
        return False

def check_results():
    """检查结果文件是否生成"""
    try:
        files = glob.glob(result_pattern)
        if files:
            # 按修改时间排序，返回最新的
            files.sort(key=os.path.getmtime, reverse=True)
            return files[0]
    except:
        pass
    return None

def get_latest_progress():
    """获取最新进度"""
    try:
        if not os.path.exists(log_file):
            return "日志文件不存在"
        
        with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
        
        if not lines:
            return "日志为空"
        
        # 查找关键信息
        scan_dates = []
        for line in lines[-2000:]:
            match = re.search(r'\[(\d+)/53\] 扫描日期: (\d{4}-\d{2}-\d{2})', line)
            if match:
                scan_dates.append((int(match.group(1)), match.group(2)))
        
        if scan_dates:
            latest = max(scan_dates, key=lambda x: x[0])
            total = len(set(scan_dates))
            return f"第{latest[0]}/53周 ({latest[1]}) - 已完成{total}周"
        
        # 查找"找到候选"
        candidate_count = 0
        for line in lines[-500:]:
            if '找到候选:' in line:
                candidate_count += 1
        
        if candidate_count > 0:
            return f"正在扫描，已找到 {candidate_count} 只候选股票"
        
        # 查找完成标记
        for line in lines[-100:]:
            if '回测完成' in line:
                return "✅ 回测已完成"
            if 'CSV文件已保存' in line:
                return "✅ 结果文件已保存"
        
        return f"运行中... (日志行数: {len(lines)})"
    except Exception as e:
        return f"读取日志错误: {e}"

iteration = 0
last_progress = ""

print(f"开始监控... (检查间隔: {check_interval}秒)")
print()

while True:
    iteration += 1
    elapsed = time.time() - start_time
    elapsed_min = int(elapsed // 60)
    elapsed_sec = int(elapsed % 60)
    
    # 检查结果文件
    result_file = check_results()
    if result_file:
        print(f"\n{'='*80}")
        print(f"✅ 结果文件已生成！")
        print(f"{'='*80}")
        print(f"文件: {result_file}")
        file_size = os.path.getsize(result_file) / 1024  # KB
        print(f"文件大小: {file_size:.2f} KB")
        print(f"总耗时: {elapsed_min}分{elapsed_sec}秒")
        print(f"{'='*80}")
        break
    
    # 检查进程
    is_running = check_process()
    if not is_running:
        print(f"\n⚠️ 进程已停止")
        print(f"最后进度: {get_latest_progress()}")
        print(f"总耗时: {elapsed_min}分{elapsed_sec}秒")
        print(f"\n检查是否有结果文件...")
        result_file = check_results()
        if result_file:
            print(f"✅ 找到结果文件: {result_file}")
        else:
            print("❌ 未找到结果文件，可能任务异常退出")
        break
    
    # 获取进度
    progress = get_latest_progress()
    if progress != last_progress or iteration % 10 == 0:  # 每10次或进度变化时输出
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] [{elapsed_min:03d}:{elapsed_sec:02d}] {progress}")
        last_progress = progress
    
    # 检查超时
    if elapsed > max_wait_time:
        print(f"\n⏰ 达到最大等待时间 ({max_wait_time//3600}小时)")
        break
    
    time.sleep(check_interval)

print(f"\n监控结束")
