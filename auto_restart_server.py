#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自动重启服务器脚本
监控指定文件的变化，自动重启服务器
"""

import os
import sys
import time
import subprocess
import signal
from pathlib import Path

# 要监控的文件列表（修改这些文件后会自动重启服务器）
WATCH_FILES = [
    'bull_stock_web.py',
    'bull_stock_analyzer.py',
    'templates/bull_stock_web.html',
    'data_fetcher.py',
    'technical_analysis.py',
    'trained_model.json'  # 模型文件变化也需要重启
]

# 服务器启动命令
SERVER_CMD = ['python3', 'bull_stock_web.py']
LOG_FILE = 'bull_stock_web.log'
PID_FILE = 'web_service.pid'

class ServerManager:
    def __init__(self):
        self.server_process = None
        self.last_modified = {}
        self.project_root = Path(__file__).parent
        
    def get_file_mtime(self, filepath):
        """获取文件的修改时间"""
        full_path = self.project_root / filepath
        if full_path.exists():
            return full_path.stat().st_mtime
        return 0
    
    def check_files_changed(self):
        """检查文件是否有变化"""
        changed = False
        for filepath in WATCH_FILES:
            current_mtime = self.get_file_mtime(filepath)
            if filepath in self.last_modified:
                if current_mtime > self.last_modified[filepath]:
                    print(f"📝 检测到文件变化: {filepath}")
                    changed = True
            else:
                # 首次记录
                self.last_modified[filepath] = current_mtime
            self.last_modified[filepath] = current_mtime
        return changed
    
    def stop_server(self):
        """停止服务器"""
        if self.server_process:
            try:
                print("🛑 正在停止服务器...")
                self.server_process.terminate()
                self.server_process.wait(timeout=5)
                print("✅ 服务器已停止")
            except subprocess.TimeoutExpired:
                print("⚠️  服务器未响应，强制终止...")
                self.server_process.kill()
                self.server_process.wait()
            except Exception as e:
                print(f"❌ 停止服务器时出错: {e}")
            finally:
                self.server_process = None
        
        # 也尝试通过PID文件停止
        pid_file = self.project_root / PID_FILE
        if pid_file.exists():
            try:
                with open(pid_file, 'r') as f:
                    pid = int(f.read().strip())
                try:
                    os.kill(pid, signal.SIGTERM)
                    print(f"✅ 已通过PID文件停止进程 {pid}")
                except ProcessLookupError:
                    pass  # 进程已不存在
            except Exception as e:
                pass
        
        # 也尝试通过进程名停止
        try:
            subprocess.run(['pkill', '-f', 'python.*bull_stock_web'], 
                         timeout=3, stderr=subprocess.DEVNULL)
        except:
            pass
    
    def start_server(self):
        """启动服务器"""
        print("🚀 正在启动服务器...")
        log_path = self.project_root / LOG_FILE
        
        try:
            with open(log_path, 'a') as log_file:
                self.server_process = subprocess.Popen(
                    SERVER_CMD,
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                    cwd=str(self.project_root)
                )
            
            # 保存PID
            pid_file = self.project_root / PID_FILE
            with open(pid_file, 'w') as f:
                f.write(str(self.server_process.pid))
            
            print(f"✅ 服务器已启动，PID: {self.server_process.pid}")
            
            # 等待几秒，检查是否启动成功
            time.sleep(3)
            if self.server_process.poll() is not None:
                print("❌ 服务器启动失败，请检查日志")
                return False
            return True
        except Exception as e:
            print(f"❌ 启动服务器时出错: {e}")
            return False
    
    def restart_server(self):
        """重启服务器"""
        print("\n" + "=" * 60)
        print("🔄 检测到文件变化，正在重启服务器...")
        print("=" * 60)
        self.stop_server()
        time.sleep(2)  # 等待端口释放
        return self.start_server()
    
    def run(self):
        """运行监控循环"""
        print("=" * 60)
        print("🔍 文件监控已启动")
        print("=" * 60)
        print(f"监控文件: {', '.join(WATCH_FILES)}")
        print(f"检查间隔: 2秒")
        print("按 Ctrl+C 停止监控")
        print("=" * 60)
        
        # 初始化文件修改时间
        for filepath in WATCH_FILES:
            self.last_modified[filepath] = self.get_file_mtime(filepath)
        
        # 首次启动服务器
        if not self.start_server():
            print("❌ 初始启动失败，退出")
            return
        
        try:
            while True:
                time.sleep(2)  # 每2秒检查一次
                
                if self.check_files_changed():
                    if not self.restart_server():
                        print("⚠️  重启失败，继续监控...")
                
                # 检查服务器是否还在运行
                if self.server_process and self.server_process.poll() is not None:
                    print("⚠️  服务器意外退出，正在重启...")
                    if not self.start_server():
                        print("❌ 重启失败，继续监控...")
                        
        except KeyboardInterrupt:
            print("\n\n🛑 收到停止信号，正在关闭...")
            self.stop_server()
            print("✅ 监控已停止")

if __name__ == '__main__':
    manager = ServerManager()
    manager.run()
