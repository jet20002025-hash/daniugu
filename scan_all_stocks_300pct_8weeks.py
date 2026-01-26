#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
扫描所有A股，找出2024-2026年8周内涨幅达到300%的个股
"""
import sys
sys.path.insert(0, '.')
from bull_stock_analyzer import BullStockAnalyzer
import json
from datetime import datetime
import pandas as pd

def scan_all_stocks_for_300pct_8weeks():
    """扫描所有A股，找出8周内涨幅达到300%的个股"""
    print("=" * 80)
    print("🔍 扫描所有A股，找出2024-2026年8周内涨幅达到300%的个股")
    print("=" * 80)
    
    # 创建分析器
    analyzer = BullStockAnalyzer(
        auto_load_default_stocks=False,
        auto_analyze_and_train=False
    )
    
    # 获取所有A股列表
    print("\n📊 获取所有A股列表...")
    all_stocks = analyzer.fetcher.get_all_stocks(timeout=30, max_retries=3)
    if all_stocks is None or len(all_stocks) == 0:
        print("❌ 无法获取股票列表")
        return
    
    print(f"✅ 获取到 {len(all_stocks)} 只A股")
    
    # 结果列表
    all_results = []
    total_stocks = len(all_stocks)
    
    print("\n" + "=" * 80)
    print("🔍 开始扫描每只股票...")
    print("=" * 80)
    print(f"📊 将扫描 {total_stocks} 只股票，查找8周内涨幅达到300%的区间")
    print("💡 提示：这可能需要较长时间，请耐心等待...")
    
    for idx, (_, row) in enumerate(all_stocks.iterrows(), 1):
        stock_code = str(row.get('code', '')).zfill(6)
        stock_name = row.get('name', stock_code)
        
        # 每处理50只股票打印一次进度
        if idx % 50 == 0:
            progress = (idx / total_stocks) * 100
            found_count = len(all_results)
            print(f"  进度: {progress:.1f}% - 已扫描 {idx}/{total_stocks} 只股票，找到 {found_count} 只符合条件的股票...")
        
        try:
            # 获取2024-2026年的周K线数据（搜索3年数据以确保覆盖）
            weekly_df = analyzer.fetcher.get_weekly_kline(stock_code, period="3y")
            
            if weekly_df is None or len(weekly_df) < 8:
                continue
            
            # 过滤未来日期和2024年之前的数据
            from datetime import datetime
            today = datetime.now().date()
            start_date = datetime(2024, 1, 1).date()
            
            if '日期' in weekly_df.columns:
                weekly_df['日期'] = pd.to_datetime(weekly_df['日期'])
                weekly_df['日期_date'] = weekly_df['日期'].dt.date
                weekly_df = weekly_df[
                    (weekly_df['日期_date'] >= start_date) & 
                    (weekly_df['日期_date'] <= today)
                ].copy()
                weekly_df = weekly_df.drop(columns=['日期_date'])
                weekly_df = weekly_df.sort_values('日期').reset_index(drop=True)
            
            if len(weekly_df) < 8:
                continue
            
            # 查找8周内涨幅达到300%的区间
            max_weeks = 8
            min_gain = 300.0
            valid_intervals = []
            
            for start_idx in range(len(weekly_df) - max_weeks):
                max_end_idx = min(start_idx + max_weeks, len(weekly_df))
                
                for end_idx in range(start_idx + 1, max_end_idx + 1):
                    interval_df = weekly_df.iloc[start_idx:end_idx].copy()
                    
                    if len(interval_df) < 2:
                        continue
                    
                    start_price = float(interval_df.iloc[0]['收盘'])
                    max_price = float(interval_df['最高'].max())
                    gain = (max_price - start_price) / start_price * 100
                    
                    if gain >= min_gain:
                        start_date_obj = interval_df.iloc[0]['日期']
                        if isinstance(start_date_obj, pd.Timestamp):
                            start_date_str = start_date_obj.strftime('%Y-%m-%d')
                        else:
                            start_date_str = str(start_date_obj)
                        
                        max_price_pos = interval_df['最高'].values.argmax()
                        max_price_date = interval_df.iloc[max_price_pos]['日期']
                        if isinstance(max_price_date, pd.Timestamp):
                            max_price_date_str = max_price_date.strftime('%Y-%m-%d')
                        else:
                            max_price_date_str = str(max_price_date)
                        
                        valid_intervals.append({
                            '起点日期': start_date_str,
                            '起点价格': round(start_price, 2),
                            '最高价': round(max_price, 2),
                            '最高价日期': max_price_date_str,
                            '涨幅': round(gain, 2),
                            '周数': end_idx - start_idx
                        })
                        break  # 找到一个符合条件的区间就足够了
            
            # 如果找到符合条件的区间，记录结果
            if valid_intervals:
                # 按涨幅排序，取最高的
                valid_intervals.sort(key=lambda x: x['涨幅'], reverse=True)
                best_interval = valid_intervals[0]
                
                all_results.append({
                    '股票代码': stock_code,
                    '股票名称': stock_name,
                    '最佳买点日期': best_interval['起点日期'],
                    '最佳买点价格': best_interval['起点价格'],
                    '区间涨幅': best_interval['涨幅'],
                    '区间周数': best_interval['周数'],
                    '最高价': best_interval['最高价'],
                    '最高价日期': best_interval['最高价日期'],
                    '找到的区间数': len(valid_intervals)
                })
                
                if idx % 10 == 0 or len(all_results) <= 10:
                    print(f"  ✅ [{idx}/{total_stocks}] {stock_code} {stock_name}: 找到买点 {best_interval['起点日期']}, 涨幅 {best_interval['涨幅']:.2f}%")
        
        except Exception as e:
            # 单个股票出错，继续处理下一个
            if idx % 100 == 0:
                print(f"  ⚠️ [{idx}/{total_stocks}] {stock_code} 处理出错: {str(e)[:50]}")
            continue
    
    # 打印汇总
    print("\n" + "=" * 80)
    print("📊 扫描结果汇总")
    print("=" * 80)
    
    if len(all_results) == 0:
        print("❌ 未找到任何符合条件的股票")
        return
    
    # 按涨幅排序
    all_results.sort(key=lambda x: x['区间涨幅'], reverse=True)
    
    print(f"\n✅ 共找到 {len(all_results)} 只股票在2024-2026年有8周内涨幅达到300%的区间")
    
    print(f"\n{'序号':<4} {'股票代码':<8} {'股票名称':<12} {'最佳买点日期':<12} {'价格(元)':<10} {'区间涨幅':<10} {'区间周数':<8} {'最高价':<10} {'最高价日期':<12}")
    print("-" * 100)
    
    for idx, result in enumerate(all_results, 1):
        code = result['股票代码']
        name = result['股票名称']
        date = result['最佳买点日期']
        price = f"{result['最佳买点价格']:.2f}"
        gain = f"{result['区间涨幅']:.2f}%"
        weeks = f"{result['区间周数']}"
        max_price = f"{result['最高价']:.2f}"
        max_date = result['最高价日期']
        
        print(f"{idx:<4} {code:<8} {name:<12} {date:<12} {price:<10} {gain:<10} {weeks:<8} {max_price:<10} {max_date:<12}")
    
    # 保存结果
    output_file = f"all_stocks_300pct_8weeks_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ 结果已保存到: {output_file}")
    
    # 统计信息
    avg_gain = sum(r['区间涨幅'] for r in all_results) / len(all_results)
    max_gain = max(r['区间涨幅'] for r in all_results)
    min_gain = min(r['区间涨幅'] for r in all_results)
    
    print(f"\n📈 统计信息:")
    print(f"   - 找到符合条件的股票: {len(all_results)} 只")
    print(f"   - 平均涨幅: {avg_gain:.2f}%")
    print(f"   - 最高涨幅: {max_gain:.2f}%")
    print(f"   - 最低涨幅: {min_gain:.2f}%")
    
    print("\n" + "=" * 80)
    print("✅ 扫描完成")
    print("=" * 80)
    
    return all_results

if __name__ == '__main__':
    scan_all_stocks_for_300pct_8weeks()
