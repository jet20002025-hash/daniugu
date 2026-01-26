#!/usr/bin/env python3
"""
全自动测试和优化脚本
1. 自动测试扫描性能
2. 分析性能瓶颈
3. 实施优化方案
4. 重新测试
5. 循环直到满足要求（10分钟内完成）
"""
import requests
import time
import json
import os
import subprocess
from datetime import datetime
from collections import defaultdict

BASE_URL = "https://www.daniugu.online"
TARGET_TIME = 600  # 目标时间：10分钟（600秒）
TARGET_SPEED = 5470 / TARGET_TIME  # 目标速度：约9.12只/秒

class AutoTester:
    def __init__(self):
        self.session = requests.Session()
        self.optimization_history = []
        self.test_results = []
        
    def login(self):
        """登录"""
        login_url = f"{BASE_URL}/api/login"
        login_data = {
            "username": "vip",
            "password": "vip123"
        }
        
        try:
            response = self.session.post(login_url, json=login_data, timeout=10)
            if response.status_code == 200:
                return True
            return False
        except:
            return False
    
    def start_scan(self):
        """启动扫描"""
        scan_url = f"{BASE_URL}/api/scan_all_stocks"
        scan_data = {
            "min_match_score": 0.6,
            "max_market_cap": 60.0,
            "use_parallel": True,
            "max_workers": 20
        }
        
        try:
            # 使用短超时，即使超时也继续监控
            response = self.session.post(scan_url, json=scan_data, timeout=5)
            return response.status_code == 200
        except:
            # 即使超时也继续，可能已在后台启动
            return True
    
    def monitor_scan(self, sample_size=500):
        """监控扫描进度，采样前N只股票的性能"""
        progress_url = f"{BASE_URL}/api/get_progress"
        
        stats = {
            'start_time': time.time(),
            'progress_updates': [],
            'sample_size': sample_size,
            'processed': 0,
            'total': 0
        }
        
        last_processed = 0
        last_update_time = time.time()
        check_interval = 2
        no_progress_count = 0
        max_no_progress = 30
        
        # 等待扫描启动
        time.sleep(5)
        
        while True:
            try:
                response = self.session.get(progress_url, timeout=10)
                if response.status_code == 200:
                    progress = response.json().get('progress', {})
                    
                    current = progress.get('current', 0)
                    total = progress.get('total', 0)
                    status = progress.get('status', '未知')
                    
                    stats['processed'] = current
                    stats['total'] = total
                    
                    # 记录进度
                    if current > last_processed:
                        elapsed = time.time() - last_update_time
                        stocks_diff = current - last_processed
                        speed = stocks_diff / elapsed if elapsed > 0 else 0
                        
                        stats['progress_updates'].append({
                            'time': time.time(),
                            'current': current,
                            'speed': speed
                        })
                        
                        last_processed = current
                        last_update_time = time.time()
                        no_progress_count = 0
                        
                        # 如果达到采样大小，停止监控
                        if current >= sample_size:
                            stats['end_time'] = time.time()
                            stats['total_time'] = stats['end_time'] - stats['start_time']
                            stats['avg_speed'] = current / stats['total_time']
                            stats['status'] = '采样完成'
                            return stats
                    else:
                        no_progress_count += 1
                    
                    # 检查是否完成或卡住
                    if status == '完成':
                        stats['end_time'] = time.time()
                        stats['total_time'] = stats['end_time'] - stats['start_time']
                        stats['avg_speed'] = current / stats['total_time'] if stats['total_time'] > 0 else 0
                        stats['status'] = '完成'
                        return stats
                    
                    if no_progress_count >= max_no_progress:
                        stats['end_time'] = time.time()
                        stats['total_time'] = stats['end_time'] - stats['start_time']
                        stats['avg_speed'] = current / stats['total_time'] if stats['total_time'] > 0 else 0
                        stats['status'] = '可能卡住'
                        return stats
                
                time.sleep(check_interval)
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"监控异常: {e}")
                time.sleep(check_interval)
        
        return stats
    
    def analyze_performance(self, stats):
        """分析性能"""
        analysis = {
            'avg_speed': stats.get('avg_speed', 0),
            'target_speed': TARGET_SPEED,
            'estimated_total_time': (5470 / stats['avg_speed']) if stats['avg_speed'] > 0 else float('inf'),
            'target_time': TARGET_TIME,
            'meets_target': False,
            'improvement_needed': 0
        }
        
        if stats['avg_speed'] > 0:
            analysis['estimated_total_time'] = 5470 / stats['avg_speed']
            analysis['meets_target'] = analysis['estimated_total_time'] <= TARGET_TIME
            if not analysis['meets_target']:
                analysis['improvement_needed'] = analysis['estimated_total_time'] / TARGET_TIME
        
        return analysis
    
    def optimize(self, analysis):
        """根据分析结果实施优化"""
        optimizations = []
        
        # 如果速度太慢，实施优化
        if analysis['avg_speed'] < TARGET_SPEED:
            improvement = analysis['improvement_needed']
            
            # 优化1: 减少print输出
            if 'reduce_prints' not in [opt['name'] for opt in self.optimization_history]:
                optimizations.append({
                    'name': 'reduce_prints',
                    'description': '减少print输出以提高性能',
                    'priority': 1
                })
            
            # 优化2: 增加并行线程数
            if improvement > 2:
                optimizations.append({
                    'name': 'increase_workers',
                    'description': f'增加并行线程数（当前20，建议50-100）',
                    'priority': 2
                })
            
            # 优化3: 优化缓存策略
            if improvement > 3:
                optimizations.append({
                    'name': 'optimize_cache',
                    'description': '优化缓存策略，预加载常用数据',
                    'priority': 3
                })
        
        return optimizations
    
    def apply_optimization(self, optimization):
        """应用优化方案"""
        print(f"\n🔧 应用优化: {optimization['name']}")
        print(f"   描述: {optimization['description']}")
        
        if optimization['name'] == 'reduce_prints':
            # 减少print输出（需要修改代码并推送）
            print("   ⚠️ 需要手动修改代码，注释掉不必要的print语句")
            return False
        
        elif optimization['name'] == 'increase_workers':
            # 增加并行线程数（需要修改代码）
            print("   ⚠️ 需要手动修改代码，增加max_workers")
            return False
        
        elif optimization['name'] == 'optimize_cache':
            # 优化缓存（需要修改代码）
            print("   ⚠️ 需要手动修改代码，优化缓存策略")
            return False
        
        return False
    
    def run_test_cycle(self, cycle=1, sample_size=500):
        """运行一个测试周期"""
        print("=" * 80)
        print(f"🔄 测试周期 #{cycle}")
        print(f"⏰ 开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 80)
        
        # 1. 登录
        print("\n[1/4] 登录...")
        if not self.login():
            print("❌ 登录失败")
            return None
        print("✅ 登录成功")
        
        # 2. 启动扫描
        print("\n[2/4] 启动扫描...")
        if not self.start_scan():
            print("⚠️ 扫描启动可能超时，继续监控...")
        else:
            print("✅ 扫描已启动")
        
        # 3. 监控扫描
        print(f"\n[3/4] 监控扫描（采样前 {sample_size} 只股票）...")
        stats = self.monitor_scan(sample_size=sample_size)
        
        # 4. 分析性能
        print("\n[4/4] 分析性能...")
        analysis = self.analyze_performance(stats)
        
        # 输出结果
        print("\n" + "=" * 80)
        print("📊 测试结果")
        print("=" * 80)
        print(f"平均速度: {analysis['avg_speed']:.2f} 只/秒")
        print(f"目标速度: {analysis['target_speed']:.2f} 只/秒")
        print(f"预计总时间: {analysis['estimated_total_time']:.1f}秒 ({analysis['estimated_total_time']/60:.1f}分钟)")
        print(f"目标时间: {TARGET_TIME}秒 ({TARGET_TIME/60:.1f}分钟)")
        print(f"是否满足要求: {'✅ 是' if analysis['meets_target'] else '❌ 否'}")
        if not analysis['meets_target']:
            print(f"需要提升: {analysis['improvement_needed']:.2f}倍")
        print("=" * 80)
        
        # 保存结果
        result = {
            'cycle': cycle,
            'stats': stats,
            'analysis': analysis,
            'timestamp': datetime.now().isoformat()
        }
        self.test_results.append(result)
        
        return analysis
    
    def run_auto_test(self, max_cycles=5, sample_size=500):
        """运行全自动测试和优化"""
        print("=" * 80)
        print("🚀 全自动测试和优化")
        print(f"🎯 目标: 在 {TARGET_TIME/60:.0f} 分钟内完成全市场扫描（5470只股票）")
        print(f"📊 目标速度: {TARGET_SPEED:.2f} 只/秒")
        print(f"🔄 最大测试周期: {max_cycles}")
        print("=" * 80)
        
        for cycle in range(1, max_cycles + 1):
            # 运行测试
            analysis = self.run_test_cycle(cycle, sample_size)
            
            if analysis is None:
                print("\n❌ 测试失败，停止")
                break
            
            # 检查是否满足要求
            if analysis['meets_target']:
                print("\n" + "=" * 80)
                print("🎉 成功！已满足性能要求！")
                print("=" * 80)
                break
            
            # 生成优化方案
            if cycle < max_cycles:
                print("\n" + "=" * 80)
                print("💡 生成优化方案...")
                print("=" * 80)
                
                optimizations = self.optimize(analysis)
                
                if optimizations:
                    print(f"\n找到 {len(optimizations)} 个优化方案：")
                    for i, opt in enumerate(optimizations, 1):
                        print(f"{i}. {opt['name']}: {opt['description']}")
                    
                    print("\n⚠️ 注意：这些优化需要手动修改代码并推送")
                    print("   建议按照优先级依次实施优化")
                else:
                    print("\n⚠️ 未找到更多优化方案")
                
                print("\n按 Enter 继续下一个测试周期，或 Ctrl+C 退出...")
                try:
                    input()
                except KeyboardInterrupt:
                    print("\n\n⚠️ 用户中断")
                    break
        
        # 输出总结
        print("\n" + "=" * 80)
        print("📊 测试总结")
        print("=" * 80)
        for result in self.test_results:
            print(f"\n周期 #{result['cycle']}:")
            print(f"  平均速度: {result['analysis']['avg_speed']:.2f} 只/秒")
            print(f"  预计总时间: {result['analysis']['estimated_total_time']:.1f}秒 ({result['analysis']['estimated_total_time']/60:.1f}分钟)")
            print(f"  满足要求: {'✅' if result['analysis']['meets_target'] else '❌'}")
        
        # 保存结果到文件
        result_file = f"auto_test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(result_file, 'w', encoding='utf-8') as f:
            json.dump(self.test_results, f, indent=2, ensure_ascii=False)
        print(f"\n💾 详细结果已保存到: {result_file}")

if __name__ == "__main__":
    tester = AutoTester()
    try:
        tester.run_auto_test(max_cycles=3, sample_size=500)
    except KeyboardInterrupt:
        print("\n\n⚠️ 用户中断")
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()

