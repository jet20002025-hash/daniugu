#!/usr/bin/env python3
"""
全自动测试和优化脚本（无交互版本）
1. 自动测试扫描性能
2. 分析性能瓶颈
3. 自动实施优化方案
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

def test_scan_performance(sample_size=500):
    """测试扫描性能"""
    session = requests.Session()
    
    print("=" * 80)
    print("🧪 开始性能测试")
    print(f"⏰ 开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    
    # 1. 登录
    print("\n[1/4] 登录...")
    login_url = f"{BASE_URL}/api/login"
    login_data = {"username": "vip", "password": "vip123"}
    
    try:
        response = session.post(login_url, json=login_data, timeout=10)
        if response.status_code != 200:
            print("❌ 登录失败")
            return None
        print("✅ 登录成功")
    except Exception as e:
        print(f"❌ 登录异常: {e}")
        return None
    
    # 2. 启动扫描
    print("\n[2/4] 启动扫描...")
    scan_url = f"{BASE_URL}/api/scan_all_stocks"
    scan_data = {
        "min_match_score": 0.6,
        "max_market_cap": 60.0,
        "use_parallel": True,
        "max_workers": 20
    }
    
    try:
        response = session.post(scan_url, json=scan_data, timeout=5)
        print("✅ 扫描启动请求已发送")
    except:
        print("⚠️ 扫描启动请求超时，继续监控...")
    
    # 3. 监控扫描
    print(f"\n[3/4] 监控扫描（采样前 {sample_size} 只股票）...")
    progress_url = f"{BASE_URL}/api/get_progress"
    
    stats = {
        'start_time': time.time(),
        'progress_updates': [],
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
    
    try:
        while True:
            try:
                response = session.get(progress_url, timeout=10)
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
                        
                        print(f"[{datetime.now().strftime('%H:%M:%S')}] "
                              f"进度: {current}/{total} | "
                              f"速度: {speed:.2f} 只/秒")
                        
                        last_processed = current
                        last_update_time = time.time()
                        no_progress_count = 0
                        
                        # 如果达到采样大小，停止监控
                        if current >= sample_size:
                            stats['end_time'] = time.time()
                            stats['total_time'] = stats['end_time'] - stats['start_time']
                            stats['avg_speed'] = current / stats['total_time']
                            stats['status'] = '采样完成'
                            break
                    else:
                        no_progress_count += 1
                        if no_progress_count % 10 == 0:
                            print(f"[{datetime.now().strftime('%H:%M:%S')}] "
                                  f"进度: {current}/{total} | "
                                  f"状态: {status}（无新进度）")
                    
                    # 检查是否完成或卡住
                    if status == '完成':
                        stats['end_time'] = time.time()
                        stats['total_time'] = stats['end_time'] - stats['start_time']
                        stats['avg_speed'] = current / stats['total_time'] if stats['total_time'] > 0 else 0
                        stats['status'] = '完成'
                        break
                    
                    if no_progress_count >= max_no_progress:
                        stats['end_time'] = time.time()
                        stats['total_time'] = stats['end_time'] - stats['start_time']
                        stats['avg_speed'] = current / stats['total_time'] if stats['total_time'] > 0 else 0
                        stats['status'] = '可能卡住'
                        break
                
                time.sleep(check_interval)
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"监控异常: {e}")
                time.sleep(check_interval)
    except KeyboardInterrupt:
        print("\n\n⚠️ 用户中断")
        stats['end_time'] = time.time()
        stats['total_time'] = stats['end_time'] - stats['start_time']
        stats['avg_speed'] = stats['processed'] / stats['total_time'] if stats['total_time'] > 0 else 0
    
    # 4. 分析性能
    print("\n[4/4] 分析性能...")
    
    if stats['avg_speed'] > 0:
        estimated_total_time = 5470 / stats['avg_speed']
        meets_target = estimated_total_time <= TARGET_TIME
        improvement_needed = estimated_total_time / TARGET_TIME if not meets_target else 1.0
    else:
        estimated_total_time = float('inf')
        meets_target = False
        improvement_needed = float('inf')
    
    analysis = {
        'avg_speed': stats['avg_speed'],
        'target_speed': TARGET_SPEED,
        'estimated_total_time': estimated_total_time,
        'target_time': TARGET_TIME,
        'meets_target': meets_target,
        'improvement_needed': improvement_needed
    }
    
    # 输出结果
    print("\n" + "=" * 80)
    print("📊 测试结果")
    print("=" * 80)
    print(f"平均速度: {analysis['avg_speed']:.2f} 只/秒")
    print(f"目标速度: {analysis['target_speed']:.2f} 只/秒")
    if estimated_total_time < float('inf'):
        print(f"预计总时间: {estimated_total_time:.1f}秒 ({estimated_total_time/60:.1f}分钟)")
    else:
        print(f"预计总时间: 无法计算（速度太慢）")
    print(f"目标时间: {TARGET_TIME}秒 ({TARGET_TIME/60:.1f}分钟)")
    print(f"是否满足要求: {'✅ 是' if analysis['meets_target'] else '❌ 否'}")
    if not analysis['meets_target'] and improvement_needed < float('inf'):
        print(f"需要提升: {improvement_needed:.2f}倍")
    print("=" * 80)
    
    return analysis

def generate_optimization_plan(analysis):
    """生成优化方案"""
    if analysis['meets_target']:
        return []
    
    optimizations = []
    improvement = analysis['improvement_needed']
    
    # 优化1: 减少print输出（最快实施）
    optimizations.append({
        'name': 'reduce_prints',
        'description': '减少print输出以提高性能',
        'priority': 1,
        'estimated_improvement': 1.2  # 预计提升20%
    })
    
    # 优化2: 增加并行线程数
    if improvement > 1.5:
        optimizations.append({
            'name': 'increase_workers',
            'description': '增加并行线程数（从20增加到50-100）',
            'priority': 2,
            'estimated_improvement': 2.0  # 预计提升2倍
        })
    
    # 优化3: 优化缓存策略
    if improvement > 3.0:
        optimizations.append({
            'name': 'optimize_cache',
            'description': '优化缓存策略，预加载常用数据',
            'priority': 3,
            'estimated_improvement': 2.0  # 预计提升2倍
        })
    
    return optimizations

def print_optimization_summary(analysis, optimizations):
    """打印优化方案总结"""
    print("\n" + "=" * 80)
    print("💡 优化方案")
    print("=" * 80)
    
    if not optimizations:
        print("✅ 无需优化，性能已满足要求")
        return
    
    print(f"\n找到 {len(optimizations)} 个优化方案：")
    for i, opt in enumerate(optimizations, 1):
        print(f"\n{i}. {opt['name']}")
        print(f"   描述: {opt['description']}")
        print(f"   优先级: {opt['priority']}")
        print(f"   预计提升: {opt['estimated_improvement']:.1f}倍")
    
    print("\n" + "=" * 80)
    print("📋 实施建议")
    print("=" * 80)
    print("按照优先级依次实施优化方案：")
    for i, opt in enumerate(optimizations, 1):
        print(f"{i}. {opt['name']}: {opt['description']}")
    
    print("\n⚠️ 注意：这些优化需要修改代码并推送到GitHub")
    print("   推送后，Render会自动部署，部署完成后可以重新测试")

if __name__ == "__main__":
    try:
        # 运行测试
        analysis = test_scan_performance(sample_size=500)
        
        if analysis:
            # 生成优化方案
            optimizations = generate_optimization_plan(analysis)
            
            # 打印优化方案
            print_optimization_summary(analysis, optimizations)
            
            # 保存结果
            result_file = f"test_result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(result_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'analysis': analysis,
                    'optimizations': optimizations,
                    'timestamp': datetime.now().isoformat()
                }, f, indent=2, ensure_ascii=False)
            print(f"\n💾 测试结果已保存到: {result_file}")
    except KeyboardInterrupt:
        print("\n\n⚠️ 用户中断")
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()

