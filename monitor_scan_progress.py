#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
扫描进度实时监控脚本
实时监控扫描进展，发现问题
"""
import time
import json
import requests
from datetime import datetime
from typing import Dict, Optional
import sys

class ScanMonitor:
    """扫描进度监控器"""
    
    def __init__(self, base_url: str = "http://localhost:5002", username: str = "test", password: str = "test", log_file: str = None):
        self.base_url = base_url.rstrip('/')
        self.username = username
        self.password = password
        self.session = requests.Session()
        self.session_id = None
        self.last_progress = None
        self.last_update_time = None
        self.stuck_count = 0
        self.max_stuck_time = 30  # 超过30秒未更新认为卡住
        self.log_file = log_file
        self.start_time = time.time()
        self.progress_history = []  # 记录进度历史，用于分析
        
    def login(self) -> bool:
        """登录获取session"""
        try:
            response = self.session.post(
                f"{self.base_url}/api/login",
                json={"username": self.username, "password": self.password},
                timeout=5
            )
            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    success_msg = f"✅ 登录成功: {self.username}"
                    print(success_msg)
                    if hasattr(self, 'log'):
                        self.log(success_msg, to_file=True)
                    return True
            error_msg = f"❌ 登录失败: {response.status_code} - {response.text}"
            print(error_msg)
            if hasattr(self, 'log'):
                self.log(error_msg, to_file=True)
            return False
        except Exception as e:
            print(f"❌ 登录异常: {e}")
            return False
    
    def get_progress(self) -> Optional[Dict]:
        """获取扫描进度"""
        try:
            response = self.session.get(
                f"{self.base_url}/api/get_progress",
                timeout=5
            )
            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    return result.get('progress')
            return None
        except Exception as e:
            print(f"❌ 获取进度异常: {e}")
            return None
    
    def get_scan_results(self) -> Optional[Dict]:
        """获取扫描结果"""
        try:
            response = self.session.get(
                f"{self.base_url}/api/get_scan_results",
                timeout=5
            )
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            print(f"❌ 获取结果异常: {e}")
            return None
    
    def log(self, message: str, to_file: bool = True):
        """记录日志"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_message = f"[{timestamp}] {message}"
        print(log_message)
        if to_file and self.log_file:
            try:
                with open(self.log_file, 'a', encoding='utf-8') as f:
                    f.write(log_message + '\n')
            except Exception as e:
                print(f"⚠️ 写入日志失败: {e}")
    
    def format_progress(self, progress: Dict) -> str:
        """格式化进度信息"""
        if not progress:
            return "无进度信息"
        
        status = progress.get('status', '未知')
        current = progress.get('current', 0)
        total = progress.get('total', 0)
        percentage = progress.get('percentage', 0)
        found = progress.get('found', 0)
        detail = progress.get('detail', '')
        
        # 计算速度
        speed_info = ""
        avg_speed_info = ""
        if self.last_progress and self.last_update_time:
            last_current = self.last_progress.get('current', 0)
            time_diff = time.time() - self.last_update_time
            if time_diff > 0:
                processed = current - last_current
                speed = processed / time_diff
                speed_info = f" | 速度: {speed:.2f} 只/秒"
                
                # 计算平均速度
                elapsed_time = time.time() - self.start_time
                if elapsed_time > 0 and current > 0:
                    avg_speed = current / elapsed_time
                    avg_speed_info = f" | 平均: {avg_speed:.2f} 只/秒"
        
        # 计算预计剩余时间
        eta_info = ""
        if status == '进行中' and total > 0 and current > 0:
            if self.last_progress and self.last_update_time:
                last_current = self.last_progress.get('current', 0)
                time_diff = time.time() - self.last_update_time
                if time_diff > 0:
                    speed = (current - last_current) / time_diff
                    if speed > 0:
                        remaining = total - current
                        eta_seconds = remaining / speed
                        if eta_seconds < 3600:
                            eta_info = f" | 预计剩余: {eta_seconds/60:.1f}分钟"
                        else:
                            eta_info = f" | 预计剩余: {eta_seconds/3600:.1f}小时"
        
        return f"状态: {status} | 进度: {current}/{total} ({percentage:.1f}%) | 已找到: {found} 只{speed_info}{avg_speed_info}{eta_info} | {detail}"
    
    def check_issues(self, progress: Dict) -> list:
        """检查问题"""
        issues = []
        
        if not progress:
            return ["⚠️ 无法获取进度信息"]
        
        status = progress.get('status', '')
        current = progress.get('current', 0)
        total = progress.get('total', 0)
        last_update = progress.get('last_update_time', 0)
        
        # 检查是否卡住
        if status == '进行中':
            if self.last_progress:
                last_current = self.last_progress.get('current', 0)
                if current == last_current and self.last_update_time:
                    stuck_time = time.time() - self.last_update_time
                    if stuck_time > self.max_stuck_time:
                        issues.append(f"⚠️ 可能卡住: {stuck_time:.0f}秒未更新进度 (当前: {current}/{total})")
                        self.stuck_count += 1
                    else:
                        self.stuck_count = 0
                else:
                    self.stuck_count = 0
            else:
                self.stuck_count = 0
        
        # 检查进度异常
        if total > 0 and current > total:
            issues.append(f"⚠️ 进度异常: 当前({current}) > 总数({total})")
        
        # 检查长时间未更新
        if last_update:
            time_since_update = time.time() - last_update
            if time_since_update > 60 and status == '进行中':
                issues.append(f"⚠️ 长时间未更新: {time_since_update:.0f}秒")
        
        # 检查警告信息
        if 'warning' in progress:
            issues.append(f"⚠️ {progress['warning']}")
        
        return issues
    
    def monitor(self, interval: float = 2.0):
        """开始监控"""
        header = "=" * 80 + "\n"
        header += "🔍 扫描进度实时监控\n"
        header += "=" * 80 + "\n"
        header += f"监控地址: {self.base_url}\n"
        header += f"更新间隔: {interval}秒\n"
        if self.log_file:
            header += f"日志文件: {self.log_file}\n"
        header += "=" * 80 + "\n"
        print(header)
        if self.log_file:
            self.log(header.strip(), to_file=True)
        
        if not self.login():
            error_msg = "❌ 登录失败，无法继续监控"
            print(error_msg)
            if self.log_file:
                self.log(error_msg, to_file=True)
            return
        
        start_msg = "开始监控... (按 Ctrl+C 停止)"
        print(start_msg)
        print()
        if self.log_file:
            self.log(start_msg, to_file=True)
        
        try:
            while True:
                progress = self.get_progress()
                current_time = datetime.now().strftime("%H:%M:%S")
                
                if progress:
                    status = progress.get('status', '未知')
                    
                    # 记录进度历史（最多保留100条）
                    self.progress_history.append({
                        'time': time.time(),
                        'progress': progress.copy()
                    })
                    if len(self.progress_history) > 100:
                        self.progress_history.pop(0)
                    
                    # 显示进度
                    progress_str = self.format_progress(progress)
                    self.log(progress_str, to_file=False)
                    
                    # 检查问题
                    issues = self.check_issues(progress)
                    if issues:
                        for issue in issues:
                            self.log(f"  {issue}", to_file=True)
                    
                    # 如果完成，显示结果
                    if status == '完成':
                        self.log("\n✅ 扫描完成！", to_file=True)
                        results = self.get_scan_results()
                        if results and results.get('success'):
                            candidates = results.get('candidates', [])
                            found_count = results.get('found_count', 0)
                            total_scanned = results.get('total_scanned', 0)
                            self.log(f"   共扫描: {total_scanned} 只股票", to_file=True)
                            self.log(f"   找到: {found_count} 只符合条件的股票", to_file=True)
                            if candidates:
                                self.log(f"\n   前5只股票:", to_file=True)
                                for i, candidate in enumerate(candidates[:5], 1):
                                    stock_code = candidate.get('股票代码', '')
                                    stock_name = candidate.get('股票名称', '')
                                    match_score = candidate.get('匹配度', 0)
                                    self.log(f"     {i}. {stock_code} {stock_name} (匹配度: {match_score:.3f})", to_file=True)
                        
                        # 输出统计信息
                        if len(self.progress_history) > 0:
                            total_time = time.time() - self.start_time
                            self.log(f"\n📊 监控统计:", to_file=True)
                            self.log(f"   总监控时间: {total_time/60:.1f}分钟", to_file=True)
                            self.log(f"   记录次数: {len(self.progress_history)}", to_file=True)
                        
                        self.log("\n监控结束", to_file=True)
                        break
                    
                    # 如果失败，显示错误
                    if status == '失败':
                        self.log(f"\n❌ 扫描失败", to_file=True)
                        detail = progress.get('detail', '')
                        if detail:
                            self.log(f"   错误: {detail}", to_file=True)
                        self.log("\n监控结束", to_file=True)
                        break
                    
                    # 如果空闲，等待扫描开始
                    if status == '空闲':
                        self.log("等待扫描开始...", to_file=False)
                    
                    # 更新最后状态
                    self.last_progress = progress.copy()
                    self.last_update_time = time.time()
                else:
                    self.log("⚠️ 无法获取进度信息", to_file=True)
                
                time.sleep(interval)
                
        except KeyboardInterrupt:
            stop_msg = "\n\n监控已停止"
            print(stop_msg)
            if self.log_file:
                self.log(stop_msg, to_file=True)
        except Exception as e:
            error_msg = f"\n❌ 监控异常: {e}"
            print(error_msg)
            if self.log_file:
                self.log(error_msg, to_file=True)
            import traceback
            traceback.print_exc()
            if self.log_file:
                self.log(traceback.format_exc(), to_file=True)


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='扫描进度实时监控')
    parser.add_argument('--url', default='http://localhost:5002', help='服务器地址 (默认: http://localhost:5002)')
    parser.add_argument('--username', default='test', help='用户名 (默认: test)')
    parser.add_argument('--password', default='test', help='密码 (默认: test)')
    parser.add_argument('--interval', type=float, default=2.0, help='更新间隔(秒) (默认: 2.0)')
    parser.add_argument('--log', default=None, help='日志文件路径 (默认: 不记录日志)')
    
    args = parser.parse_args()
    
    # 如果没有指定日志文件，使用默认名称
    log_file = args.log
    if log_file is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = f"monitor_{timestamp}.log"
    
    monitor = ScanMonitor(
        base_url=args.url,
        username=args.username,
        password=args.password,
        log_file=log_file
    )
    monitor.monitor(interval=args.interval)


if __name__ == '__main__':
    main()
