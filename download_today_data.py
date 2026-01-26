#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
下载今天（1月22日）的股票数据
包括日K线和周K线数据
"""
import os
import sys
import pandas as pd
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bull_stock_analyzer import BullStockAnalyzer

def download_stock_data(code, name, analyzer):
    """下载单只股票的数据"""
    try:
        updated = {'daily': False, 'weekly': False}
        
        # 1. 下载日K线数据（确保包含今天的数据）
        try:
            # 使用period="1y"获取最近1年数据，akshare会自动包含今天的数据
            daily_df = analyzer.fetcher.get_daily_kline(code, period="1y", use_cache=False, local_only=False)
            if daily_df is not None and len(daily_df) > 0:
                # 检查是否包含今天的数据
                if '日期' in daily_df.columns:
                    daily_df['日期'] = pd.to_datetime(daily_df['日期'], errors='coerce')
                    today_str = datetime.now().strftime('%Y-%m-%d')
                    today_data = daily_df[daily_df['日期'].dt.strftime('%Y-%m-%d') == today_str]
                    if len(today_data) > 0:
                        print(f"  ✅ {code} 日K线包含今天数据")
                
                daily_path = f'cache/daily_kline/{code}.csv'
                os.makedirs('cache/daily_kline', exist_ok=True)
                daily_df.to_csv(daily_path, index=False, encoding='utf-8')
                updated['daily'] = True
        except Exception as e:
            print(f"  ⚠️ {code} 日K线下载失败: {str(e)[:50]}")
        
        # 2. 下载周K线数据（确保包含本周的数据）
        try:
            # 使用period="2y"获取最近2年数据，akshare会自动包含本周的数据
            weekly_df = analyzer.fetcher.get_weekly_kline(code, period="2y", use_cache=False, local_only=False)
            if weekly_df is not None and len(weekly_df) > 0:
                # 检查是否包含本周的数据
                if '日期' in weekly_df.columns:
                    weekly_df['日期'] = pd.to_datetime(weekly_df['日期'], errors='coerce')
                    # 获取最新的周K线日期
                    latest_week = weekly_df['日期'].max()
                    today_dt = datetime.now()
                    # 如果最新周K线日期是本周或更晚，说明包含本周数据
                    if latest_week >= today_dt - pd.Timedelta(days=7):
                        print(f"  ✅ {code} 周K线包含本周数据")
                
                weekly_path = f'cache/weekly_kline/{code}.csv'
                os.makedirs('cache/weekly_kline', exist_ok=True)
                weekly_df.to_csv(weekly_path, index=False, encoding='utf-8')
                updated['weekly'] = True
        except Exception as e:
            print(f"  ⚠️ {code} 周K线下载失败: {str(e)[:50]}")
        
        return updated
    except Exception as e:
        return {'daily': False, 'weekly': False, 'error': str(e)}

def main():
    print("=" * 80)
    print("📥 下载今天（1月22日）的股票数据")
    print("=" * 80)
    print()
    
    # 创建分析器
    analyzer = BullStockAnalyzer(auto_load_default_stocks=False)
    
    # 获取股票列表
    stock_list = analyzer.fetcher.get_all_stocks()
    if stock_list is None or len(stock_list) == 0:
        print("❌ 无法获取股票列表")
        return
    
    # 过滤ST和北交所
    valid_stocks = []
    for _, row in stock_list.iterrows():
        code = str(row.iloc[0]) if len(row) > 0 else ''
        name = str(row.iloc[1]) if len(row) > 1 else ''
        if not code or not name:
            continue
        if 'ST' in name or '*ST' in name:
            continue
        if code.startswith('8') or code.startswith('4'):
            continue
        valid_stocks.append({'code': code, 'name': name})
    
    print(f"📊 有效股票数量: {len(valid_stocks)}")
    print(f"📅 目标日期: 2026-01-22（今天）")
    print()
    
    # 统计
    daily_updated = 0
    weekly_updated = 0
    failed = 0
    skipped = 0
    
    start_time = time.time()
    
    # 使用多线程下载（10线程）
    print(f"🚀 开始下载（10线程并发）...")
    print()
    
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {}
        for item in valid_stocks:
            code = item['code']
            name = item['name']
            future = executor.submit(download_stock_data, code, name, analyzer)
            futures[future] = (code, name)
        
        completed = 0
        for future in as_completed(futures):
            completed += 1
            code, name = futures[future]
            
            try:
                result = future.result()
                if result.get('daily'):
                    daily_updated += 1
                if result.get('weekly'):
                    weekly_updated += 1
                if result.get('error'):
                    failed += 1
                if not result.get('daily') and not result.get('weekly') and not result.get('error'):
                    skipped += 1
            except Exception as e:
                failed += 1
            
            # 显示进度
            if completed % 100 == 0 or completed == len(valid_stocks):
                elapsed = time.time() - start_time
                speed = completed / elapsed if elapsed > 0 else 0
                print(f"进度: {completed}/{len(valid_stocks)} ({completed/len(valid_stocks)*100:.1f}%) "
                      f"| 日K更新: {daily_updated} | 周K更新: {weekly_updated} "
                      f"| 跳过: {skipped} | 失败: {failed} "
                      f"| 速度: {speed:.1f} 只/秒")
    
    elapsed = time.time() - start_time
    print()
    print("=" * 80)
    print(f"✅ 下载完成！")
    print(f"  总耗时: {elapsed:.1f} 秒")
    print(f"  日K线更新: {daily_updated} 只")
    print(f"  周K线更新: {weekly_updated} 只")
    print(f"  跳过（已是最新）: {skipped} 只")
    print(f"  失败: {failed} 只")
    print("=" * 80)
    print()
    print("💡 提示：数据已保存到 cache/daily_kline/ 和 cache/weekly_kline/ 目录")
    print("   现在可以开始扫描了！")

if __name__ == '__main__':
    main()
