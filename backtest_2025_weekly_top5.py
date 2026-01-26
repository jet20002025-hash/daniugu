#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
2025年每周回测脚本
基于训练好的模型，每周扫描所有个股，找出匹配度排名前5的个股
"""
from bull_stock_analyzer import BullStockAnalyzer
from data_fetcher import DataFetcher
from datetime import datetime, date, timedelta
import pandas as pd
import json
import os
import time


def main():
    print("=" * 80)
    print("🚀 2025年每周回测 - 匹配度排名前5")
    print("=" * 80)
    print()
    
    # 初始化分析器（自动加载模型）
    print("📊 初始化分析器并加载模型...")
    analyzer = BullStockAnalyzer(
        auto_load_default_stocks=True,
        auto_analyze_and_train=False  # 不自动训练，直接使用已保存的模型
    )
    
    # 确保模型已加载
    if not analyzer.trained_features or not analyzer.trained_features.get('common_features'):
        print("⚠️ 模型未加载，尝试从文件加载...")
        if analyzer.load_model('trained_model.json', skip_network=True):
            print("✅ 模型已从文件加载")
        else:
            print("❌ 模型加载失败，请先运行 train_and_save_model.py 训练模型")
            return
    else:
        print("✅ 模型已加载")
    print()
    
    # 设置回测参数
    start_date = date(2025, 1, 1)
    end_date = date(2025, 12, 31)
    min_match_score = 0.6  # 最小匹配度阈值（可以调整）
    max_market_cap = 100.0  # 最大市值（亿元）
    max_stocks_per_week = 5  # 每周选择前5只
    
    print("📋 回测参数:")
    print(f"   时间范围: {start_date} 至 {end_date}")
    print(f"   扫描模式: 每周")
    print(f"   匹配度阈值: {min_match_score:.3f}")
    print(f"   市值上限: {max_market_cap} 亿元")
    print(f"   每周选择: 匹配度排名前 {max_stocks_per_week} 只")
    print(f"   ⚠️ 注意: 不计算收益，仅筛选和排序")
    print()
    
    # 获取交易日列表（用于确定每周的扫描日期）
    print("🔄 获取交易日列表...")
    fetcher = DataFetcher()
    daily_df = fetcher.get_daily_kline('000001', period="1y")
    if daily_df is None or len(daily_df) == 0:
        print("⚠️ 无法获取交易日历，使用所有工作日")
        all_trading_days = []
        current = start_date
        while current <= end_date:
            if current.weekday() < 5:  # 0-4 是周一到周五
                all_trading_days.append(current)
            current += timedelta(days=1)
    else:
        if '日期' in daily_df.columns:
            daily_df['日期'] = pd.to_datetime(daily_df['日期'])
            daily_df['日期_date'] = daily_df['日期'].dt.date
            all_trading_days = []
            for date_val in daily_df['日期_date'].unique():
                if isinstance(date_val, str):
                    date_val = datetime.strptime(date_val, '%Y-%m-%d').date()
                elif hasattr(date_val, 'date') and not isinstance(date_val, date):
                    date_val = date_val.date()
                if isinstance(date_val, date) and start_date <= date_val <= end_date:
                    all_trading_days.append(date_val)
            all_trading_days.sort()
    
    # 每周选择第一个交易日
    scan_dates = []
    current_week = None
    for day in all_trading_days:
        week_num = day.isocalendar()[1]  # 周数
        year = day.year
        week_key = (year, week_num)
        if week_key != current_week:
            scan_dates.append(day)
            current_week = week_key
    
    print(f"✅ 找到 {len(all_trading_days)} 个交易日，需要扫描 {len(scan_dates)} 周")
    print()
    
    # 开始回测
    print("🔄 开始回测（仅筛选，不计算收益）...")
    print()
    
    results = []
    start_time = time.time()
    
    # 遍历每个扫描日期
    for idx, scan_date in enumerate(scan_dates, 1):
        print(f"[{idx}/{len(scan_dates)}] 扫描日期: {scan_date}")
        print("-" * 80)
        
        try:
            # 使用指定日期进行扫描
            # 注意：先不设置市值限制，扫描完成后再过滤（提升速度）
            scan_result = analyzer.scan_all_stocks(
                min_match_score=min_match_score,
                max_market_cap=0,  # 先不设置市值限制，扫描完成后再过滤
                limit=None,  # 扫描所有股票
                use_parallel=True,
                max_workers=10,  # 增加并行度，从5增加到10
                scan_date=scan_date.strftime('%Y-%m-%d'),
                force_refresh=False  # 使用本地缓存，确保数据从本地获取
            )
            
            if not scan_result.get('success'):
                print(f"   ⚠️ 扫描失败: {scan_result.get('message', '未知错误')}")
                results.append({
                    'date': scan_date.strftime('%Y-%m-%d'),
                    'stocks': [],
                    'error': scan_result.get('message', '扫描失败')
                })
                continue
            
            candidates = scan_result.get('candidates', [])
            
            if len(candidates) == 0:
                print(f"   ⚠️ 未找到符合条件的股票")
                results.append({
                    'date': scan_date.strftime('%Y-%m-%d'),
                    'stocks': [],
                    'error': '未找到符合条件的股票'
                })
                continue
            
            # 按匹配度排序
            candidates_sorted = sorted(candidates, key=lambda x: x.get('匹配度', 0), reverse=True)
            
            # 如果需要市值过滤，在这里进行（只过滤前5只，而不是全部5190只）
            # 使用流通股本和当前股价计算流通市值
            if max_market_cap > 0:
                filtered_candidates = []
                for candidate in candidates_sorted:
                    market_cap = candidate.get('市值')
                    # 如果市值不存在，使用流通股本和当前股价计算
                    if market_cap is None or market_cap == 0:
                        current_price = candidate.get('当前价格') or candidate.get('最佳买点价格')
                        if current_price:
                            market_cap = analyzer.fetcher.calculate_circulating_market_cap(
                                candidate.get('股票代码'),
                                current_price,
                                timeout=2
                            )
                            if market_cap:
                                candidate['市值'] = round(market_cap, 2)
                    
                    if market_cap is None or market_cap == 0 or market_cap <= max_market_cap:
                        filtered_candidates.append(candidate)
                        if len(filtered_candidates) >= max_stocks_per_week:
                            break
                selected_stocks = filtered_candidates
            else:
                selected_stocks = candidates_sorted[:max_stocks_per_week]
            
            print(f"   ✅ 找到 {len(candidates)} 只候选股票，选择匹配度最高的 {len(selected_stocks)} 只")
            
            # 只保存基本信息，不计算收益
            week_results = []
            for stock in selected_stocks:
                stock_code = stock.get('股票代码')
                stock_name = stock.get('股票名称')
                match_score = stock.get('匹配度', 0)
                
                print(f"      📊 {stock_code} {stock_name} (匹配度: {match_score:.4f})")
                
                week_results.append({
                    'stock_code': stock_code,
                    'stock_name': stock_name,
                    'match_score': match_score
                })
            
            results.append({
                'date': scan_date.strftime('%Y-%m-%d'),
                'stocks': week_results
            })
            
        except Exception as e:
            print(f"   ❌ 处理失败: {e}")
            import traceback
            traceback.print_exc()
            results.append({
                'date': scan_date.strftime('%Y-%m-%d'),
                'stocks': [],
                'error': str(e)
            })
        
        print()
    
    # 计算总耗时
    elapsed_time = time.time() - start_time
    elapsed_min = int(elapsed_time // 60)
    elapsed_sec = int(elapsed_time % 60)
    
    print("=" * 80)
    print(f"✅ 回测完成，总耗时: {elapsed_min}分{elapsed_sec}秒")
    print("=" * 80)
    
    # 构建结果字典
    result = {
        'start_date': start_date.strftime('%Y-%m-%d'),
        'end_date': end_date.strftime('%Y-%m-%d'),
        'scan_mode': 'weekly',
        'scan_dates_count': len(scan_dates),
        'total_trading_days': len(all_trading_days),
        'min_match_score': min_match_score,
        'max_market_cap': max_market_cap,
        'max_stocks_per_week': max_stocks_per_week,
        'results': results,
        'elapsed_time_seconds': elapsed_time
    }
    
    # 保存结果到CSV
    print()
    print("=" * 80)
    print("💾 保存回测结果...")
    print("=" * 80)
    
    # 生成时间戳
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # 准备CSV数据（简化版，不包含收益信息）
    csv_rows = []
    for week_result in result['results']:
        week_date = week_result['date']
        
        if 'error' in week_result:
            # 如果该周扫描失败，记录错误
            csv_rows.append({
                '周日期': week_date,
                '股票代码': '',
                '股票名称': '',
                '匹配度': '',
                '错误': week_result['error']
            })
        else:
            stocks = week_result.get('stocks', [])
            if len(stocks) == 0:
                # 该周未找到符合条件的股票
                csv_rows.append({
                    '周日期': week_date,
                    '股票代码': '',
                    '股票名称': '',
                    '匹配度': '',
                    '错误': '未找到符合条件的股票'
                })
            else:
                # 记录该周找到的每只股票
                for stock in stocks:
                    csv_rows.append({
                        '周日期': week_date,
                        '股票代码': stock.get('stock_code', ''),
                        '股票名称': stock.get('stock_name', ''),
                        '匹配度': f"{stock.get('match_score', 0):.4f}",
                        '错误': ''
                    })
    
    # 保存CSV
    df = pd.DataFrame(csv_rows)
    csv_filename = f"backtest_2025_weekly_top5_{timestamp}.csv"
    df.to_csv(csv_filename, index=False, encoding='utf-8-sig')
    print(f"✅ CSV文件已保存: {csv_filename}")
    
    # 保存详细JSON结果
    json_filename = f"backtest_2025_weekly_top5_{timestamp}.json"
    with open(json_filename, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2, default=str)
    print(f"✅ JSON文件已保存: {json_filename}")
    
    # 统计信息
    print()
    print("=" * 80)
    print("📊 回测统计")
    print("=" * 80)
    total_weeks = len(result['results'])
    weeks_with_stocks = sum(1 for r in result['results'] if r.get('stocks') and len(r['stocks']) > 0)
    weeks_with_errors = sum(1 for r in result['results'] if 'error' in r)
    total_stocks = sum(len(r.get('stocks', [])) for r in result['results'])
    
    print(f"总周数: {total_weeks}")
    print(f"找到股票的周数: {weeks_with_stocks}")
    print(f"扫描失败的周数: {weeks_with_errors}")
    print(f"总股票数: {total_stocks}")
    print(f"平均每周股票数: {total_stocks / max(weeks_with_stocks, 1):.2f}")
    print()
    
    # 显示前10周的示例结果
    print("=" * 80)
    print("📋 前10周结果示例")
    print("=" * 80)
    for i, week_result in enumerate(result['results'][:10], 1):
        week_date = week_result['date']
        if 'error' in week_result:
            print(f"{i}. {week_date}: ❌ {week_result['error']}")
        else:
            stocks = week_result.get('stocks', [])
            if len(stocks) == 0:
                print(f"{i}. {week_date}: ⚠️ 未找到符合条件的股票")
            else:
                print(f"{i}. {week_date}: ✅ 找到 {len(stocks)} 只股票")
                for j, stock in enumerate(stocks[:3], 1):  # 只显示前3只
                    match_score = stock.get('match_score', 0)
                    stock_code = stock.get('stock_code', '')
                    stock_name = stock.get('stock_name', '')
                    print(f"   {j}. {stock_code} {stock_name} (匹配度: {match_score:.4f})")
    print()
    
    print("=" * 80)
    print("✅ 回测完成！")
    print("=" * 80)


if __name__ == '__main__':
    main()
