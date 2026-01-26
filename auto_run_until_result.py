#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
全自动运行回测任务，直到生成测试结果
"""
import time
import os
import subprocess
import re
import glob
from datetime import datetime

print("=" * 80)
print("🚀 全自动运行 - 等待测试结果生成")
print("=" * 80)
print()

log_file = "backtest_2025_weekly_top5.log"
result_pattern = "backtest_2025_weekly_top5_*.csv"
check_interval = 30  # 每30秒检查一次
max_wait_time = 3600 * 24  # 最多等待24小时
start_time = time.time()

def check_process():
    """检查回测进程是否运行"""
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
            files.sort(key=os.path.getmtime, reverse=True)
            return files[0]
    except:
        pass
    return None

def get_progress():
    """获取最新进度"""
    try:
        if not os.path.exists(log_file):
            return "初始化中..."
        
        with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
        
        if not lines:
            return "日志为空"
        
        # 查找扫描进度
        scan_dates = []
        for line in lines[-5000:]:
            match = re.search(r'\[(\d+)/53\] 扫描日期: (\d{4}-\d{2}-\d{2})', line)
            if match:
                scan_dates.append((int(match.group(1)), match.group(2)))
        
        if scan_dates:
            latest = max(scan_dates, key=lambda x: x[0])
            total = len(set(scan_dates))
            return f"第{latest[0]}/53周 ({latest[1]}) - 已完成{total}周"
        
        # 查找完成标记
        for line in lines[-200:]:
            if '回测完成' in line or 'CSV文件已保存' in line:
                return "✅ 已完成"
        
        # 查找候选股票数量
        count = sum(1 for line in lines[-2000:] if '找到候选:' in line)
        if count > 0:
            return f"扫描中，已找到 {count} 只候选股票"
        
        return f"运行中... (日志: {len(lines)} 行)"
    except Exception as e:
        return f"错误: {e}"

def restart_task_if_needed():
    """如果任务停止，尝试重启"""
    if not check_process():
        print("\n⚠️  回测任务已停止，尝试重启...")
        try:
            # 停止旧进程
            subprocess.run(["pkill", "-9", "-f", "backtest_2025_weekly_top5.py"], 
                         capture_output=True)
            time.sleep(2)
            
            # 启动新任务
            subprocess.Popen(
                ["nohup", "python3", "backtest_2025_weekly_top5.py", 
                 ">", "backtest_2025_weekly_top5.log", "2>&1", "&"],
                shell=True
            )
            time.sleep(3)
            if check_process():
                print("✅ 任务已重启")
                return True
            else:
                print("❌ 重启失败")
                return False
        except Exception as e:
            print(f"❌ 重启出错: {e}")
            return False
    return True

iteration = 0
last_progress = ""
no_progress_count = 0
max_no_progress = 20  # 如果20次检查（10分钟）没有进度，报告

print(f"开始监控... (检查间隔: {check_interval}秒)")
print(f"结果文件格式: {result_pattern}")
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
        print(f"✅ 测试结果已生成！")
        print(f"{'='*80}")
        print(f"📁 结果文件: {result_file}")
        file_size = os.path.getsize(result_file) / 1024
        print(f"📊 文件大小: {file_size:.2f} KB")
        print(f"⏱️  总耗时: {elapsed_min}分{elapsed_sec}秒")
        
        # 检查JSON文件
        json_file = result_file.replace('.csv', '.json')
        if os.path.exists(json_file):
            json_size = os.path.getsize(json_file) / 1024
            print(f"📁 JSON文件: {json_file} ({json_size:.2f} KB)")
        
        print(f"{'='*80}")
        print("\n✅ 任务完成！")
        break
    
    # 检查进程
    is_running = check_process()
    if not is_running:
        print(f"\n⚠️  回测任务已停止")
        progress = get_progress()
        print(f"最后进度: {progress}")
        print(f"总耗时: {elapsed_min}分{elapsed_sec}秒")
        
        # 检查是否有结果文件
        result_file = check_results()
        if result_file:
            print(f"\n✅ 找到结果文件: {result_file}")
            break
        else:
            print("\n❌ 未找到结果文件")
            # 尝试重启
            if restart_task_if_needed():
                continue
            else:
                print("无法重启任务，退出监控")
                break
    
    # 显示进度
    progress = get_progress()
    if progress != last_progress:
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] [{elapsed_min:03d}:{elapsed_sec:02d}] {progress}")
        last_progress = progress
        no_progress_count = 0
    else:
        no_progress_count += 1
        if no_progress_count >= max_no_progress and iteration % max_no_progress == 0:
            timestamp = datetime.now().strftime("%H:%M:%S")
            print(f"[{timestamp}] [{elapsed_min:03d}:{elapsed_sec:02d}] {progress} (等待中...)")
    
    # 检查超时
    if elapsed > max_wait_time:
        print(f"\n⏰ 达到最大等待时间 ({max_wait_time//3600}小时)")
        break
    
    time.sleep(check_interval)

print(f"\n监控结束")
