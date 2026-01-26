#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
登录时间后台监视程序
实时监控前端登录并显示登录时间
"""
import json
import os
import time
from datetime import datetime
from collections import deque

LOGIN_LOG_FILE = 'login_monitor.log'

class LoginMonitor:
    def __init__(self, log_file=LOGIN_LOG_FILE):
        self.log_file = log_file
        self.last_position = 0
        self.login_records = deque(maxlen=100)  # 保存最近100条记录
        self.stats = {
            'total_attempts': 0,
            'successful_logins': 0,
            'failed_logins': 0,
            'total_duration_ms': 0,
            'min_duration_ms': None,
            'max_duration_ms': None,
        }
        
    def clear_log(self):
        """清空日志文件（可选）"""
        if os.path.exists(self.log_file):
            with open(self.log_file, 'w', encoding='utf-8') as f:
                f.write('')
        self.last_position = 0
        print("✅ 日志文件已清空")
    
    def read_new_logs(self):
        """读取新的日志条目"""
        if not os.path.exists(self.log_file):
            return []
        
        new_logs = []
        try:
            with open(self.log_file, 'r', encoding='utf-8') as f:
                # 移动到上次读取的位置
                f.seek(self.last_position)
                
                # 读取新内容
                new_content = f.read()
                if new_content:
                    for line in new_content.strip().split('\n'):
                        if line.strip():
                            try:
                                log_entry = json.loads(line)
                                new_logs.append(log_entry)
                            except json.JSONDecodeError:
                                continue
                    
                    # 更新位置
                    self.last_position = f.tell()
        except Exception as e:
            print(f"⚠️ 读取日志失败: {e}")
        
        return new_logs
    
    def update_stats(self, log_entry):
        """更新统计信息"""
        self.stats['total_attempts'] += 1
        
        if log_entry.get('success'):
            self.stats['successful_logins'] += 1
        else:
            self.stats['failed_logins'] += 1
        
        duration = log_entry.get('duration_ms', 0)
        if duration > 0:
            self.stats['total_duration_ms'] += duration
            
            if self.stats['min_duration_ms'] is None or duration < self.stats['min_duration_ms']:
                self.stats['min_duration_ms'] = duration
            
            if self.stats['max_duration_ms'] is None or duration > self.stats['max_duration_ms']:
                self.stats['max_duration_ms'] = duration
    
    def format_log_entry(self, log_entry):
        """格式化日志条目用于显示"""
        timestamp = log_entry.get('timestamp', '')
        try:
            dt = datetime.fromisoformat(timestamp)
            time_str = dt.strftime('%H:%M:%S')
        except:
            time_str = timestamp
        
        username = log_entry.get('username', 'unknown')
        success = log_entry.get('success', False)
        duration = log_entry.get('duration_ms', 0)
        message = log_entry.get('message', '')
        
        status_icon = "✅" if success else "❌"
        status_text = "成功" if success else "失败"
        
        return f"[{time_str}] {status_icon} {username:10s} | {status_text:4s} | {duration:7.3f}ms | {message}"
    
    def print_stats(self):
        """打印统计信息"""
        stats = self.stats
        if stats['total_attempts'] == 0:
            return
        
        success_rate = (stats['successful_logins'] / stats['total_attempts'] * 100) if stats['total_attempts'] > 0 else 0
        avg_duration = (stats['total_duration_ms'] / stats['successful_logins']) if stats['successful_logins'] > 0 else 0
        
        print("\n" + "="*80)
        print("📊 统计信息")
        print("="*80)
        print(f"总登录尝试: {stats['total_attempts']}")
        print(f"成功登录: {stats['successful_logins']}")
        print(f"失败登录: {stats['failed_logins']}")
        print(f"成功率: {success_rate:.1f}%")
        if stats['successful_logins'] > 0:
            print(f"平均响应时间: {avg_duration:.3f}ms")
            print(f"最快响应: {stats['min_duration_ms']:.3f}ms")
            print(f"最慢响应: {stats['max_duration_ms']:.3f}ms")
        print("="*80 + "\n")
    
    def monitor(self, clear_on_start=False):
        """开始监视"""
        print("="*80)
        print("🔍 登录时间监视程序")
        print("="*80)
        print(f"监视日志文件: {self.log_file}")
        print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*80)
        print("\n等待登录请求...")
        print("（在前端进行登录操作，这里会实时显示登录时间）")
        print("-"*80)
        
        if clear_on_start:
            self.clear_log()
        
        # 初始化：读取现有日志的末尾位置
        if os.path.exists(self.log_file):
            with open(self.log_file, 'r', encoding='utf-8') as f:
                f.seek(0, 2)  # 移动到文件末尾
                self.last_position = f.tell()
        
        try:
            while True:
                # 读取新日志
                new_logs = self.read_new_logs()
                
                # 处理新日志
                for log_entry in new_logs:
                    self.login_records.append(log_entry)
                    self.update_stats(log_entry)
                    
                    # 显示日志条目
                    print(self.format_log_entry(log_entry))
                    
                    # 每10条记录显示一次统计
                    if self.stats['total_attempts'] % 10 == 0:
                        self.print_stats()
                
                # 短暂休眠，避免CPU占用过高
                time.sleep(0.1)
                
        except KeyboardInterrupt:
            print("\n\n" + "="*80)
            print("⚠️ 监视已停止")
            print("="*80)
            self.print_stats()
            print("\n最近10条登录记录:")
            print("-"*80)
            for record in list(self.login_records)[-10:]:
                print(self.format_log_entry(record))
            print("="*80)

if __name__ == "__main__":
    import sys
    
    monitor = LoginMonitor()
    
    # 检查命令行参数
    clear_log = False
    if len(sys.argv) > 1 and sys.argv[1] == '--clear':
        clear_log = True
    
    try:
        monitor.monitor(clear_on_start=clear_log)
    except Exception as e:
        print(f"\n❌ 监视程序出错: {e}")
        import traceback
        traceback.print_exc()
