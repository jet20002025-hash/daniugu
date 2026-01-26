#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
分析大牛股买点时的均线粘合度
计算5、10、20、30日均线的最大差值占买点股价的百分比
"""
import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bull_stock_analyzer import BullStockAnalyzer

def calculate_ma_convergence(stock_code, buy_date, buy_price):
    """
    计算买点时的均线粘合度
    :param stock_code: 股票代码
    :param buy_date: 买点日期（YYYY-MM-DD）
    :param buy_price: 买点价格
    :return: 均线粘合度信息
    """
    analyzer = BullStockAnalyzer(auto_load_default_stocks=False, auto_analyze_and_train=False)
    
    try:
        # 获取日K线数据（需要足够的历史数据来计算30日均线）
        daily_df = analyzer.fetcher.get_daily_kline(stock_code, period="1y")
        
        if daily_df is None or len(daily_df) == 0:
            return None
        
        # 确保日期列是datetime类型
        if '日期' in daily_df.columns:
            daily_df['日期'] = pd.to_datetime(daily_df['日期'], errors='coerce')
            daily_df = daily_df.dropna(subset=['日期'])
            daily_df = daily_df.sort_values('日期').reset_index(drop=True)
        
        # 过滤到买点日期及之前的数据
        buy_dt = pd.to_datetime(buy_date, errors='coerce')
        if pd.isna(buy_dt):
            return None
        
        daily_df = daily_df[daily_df['日期'] <= buy_dt].copy()
        
        if len(daily_df) < 30:
            return None
        
        # 计算均线（使用收盘价）
        close_prices = daily_df['收盘'].values
        
        # 计算5、10、20、30日均线（使用买点当天的收盘价）
        ma5 = np.mean(close_prices[-5:]) if len(close_prices) >= 5 else None
        ma10 = np.mean(close_prices[-10:]) if len(close_prices) >= 10 else None
        ma20 = np.mean(close_prices[-20:]) if len(close_prices) >= 20 else None
        ma30 = np.mean(close_prices[-30:]) if len(close_prices) >= 30 else None
        
        if ma5 is None or ma10 is None or ma20 is None or ma30 is None:
            return None
        
        # 计算最大差值
        ma_values = [ma5, ma10, ma20, ma30]
        max_ma = max(ma_values)
        min_ma = min(ma_values)
        max_diff = max_ma - min_ma
        
        # 计算百分比（最大差值占买点股价的百分比）
        if buy_price > 0:
            diff_percent = (max_diff / buy_price) * 100
        else:
            diff_percent = None
        
        return {
            '股票代码': stock_code,
            '买点日期': buy_date,
            '买点价格': buy_price,
            'MA5': round(ma5, 2),
            'MA10': round(ma10, 2),
            'MA20': round(ma20, 2),
            'MA30': round(ma30, 2),
            '最大均线': round(max_ma, 2),
            '最小均线': round(min_ma, 2),
            '最大差值': round(max_diff, 2),
            '差值百分比': round(diff_percent, 2) if diff_percent is not None else None
        }
    except Exception as e:
        print(f"  ⚠️ 计算 {stock_code} 均线粘合度失败: {e}")
        return None

def analyze_all_bull_stocks():
    """分析所有大牛股的均线粘合度"""
    analyzer = BullStockAnalyzer(auto_load_default_stocks=True, auto_analyze_and_train=False)
    
    # 获取大牛股列表
    bull_stocks = analyzer.bull_stocks
    
    if not bull_stocks:
        print("❌ 无法获取大牛股列表")
        return
    
    print("="*80)
    print("分析大牛股买点时的均线粘合度")
    print("="*80)
    print(f"\n共 {len(bull_stocks)} 只大牛股\n")
    
    results = []
    
    for idx, stock in enumerate(bull_stocks, 1):
        stock_code = stock.get('代码', '')
        stock_name = stock.get('名称', '')
        
        if not stock_code:
            continue
        
        print(f"[{idx}/{len(bull_stocks)}] 分析 {stock_code} {stock_name}...")
        
        # 分析股票，找到买点
        try:
            analysis_result = analyzer.analyze_bull_stock(stock_code)
            
            if analysis_result is None:
                print(f"  ❌ 无法分析 {stock_code}")
                continue
            
            # 获取买点信息（从interval字段中获取）
            interval = analysis_result.get('interval')
            if interval is None:
                print(f"  ❌ 无法找到涨幅区间")
                continue
            
            buy_date = interval.get('起点日期', '')
            buy_price = interval.get('起点价格', 0)
            
            if not buy_date or buy_price <= 0:
                print(f"  ❌ 买点信息不完整 (日期: {buy_date}, 价格: {buy_price})")
                continue
            
            # 计算均线粘合度
            ma_info = calculate_ma_convergence(stock_code, buy_date, buy_price)
            
            if ma_info:
                ma_info['股票名称'] = stock_name
                results.append(ma_info)
                print(f"  ✅ MA5={ma_info['MA5']:.2f}, MA10={ma_info['MA10']:.2f}, MA20={ma_info['MA20']:.2f}, MA30={ma_info['MA30']:.2f}")
                print(f"     最大差值={ma_info['最大差值']:.2f}, 差值百分比={ma_info['差值百分比']:.2f}%")
            else:
                print(f"  ❌ 无法计算均线粘合度")
        except Exception as e:
            print(f"  ❌ 分析失败: {e}")
            import traceback
            traceback.print_exc()
            continue
    
    # 输出结果表格
    print("\n" + "="*80)
    print("结果汇总")
    print("="*80)
    
    if not results:
        print("❌ 没有成功分析的结果")
        return
    
    # 创建DataFrame并输出
    df = pd.DataFrame(results)
    
    # 按差值百分比排序
    df = df.sort_values('差值百分比', ascending=True)
    
    print("\n均线粘合度分析结果（按差值百分比从小到大排序）：")
    print("-"*120)
    print(f"{'股票代码':<10} {'股票名称':<15} {'买点日期':<12} {'买点价格':<10} {'MA5':<10} {'MA10':<10} {'MA20':<10} {'MA30':<10} {'最大差值':<10} {'差值百分比':<12}")
    print("-"*120)
    
    for _, row in df.iterrows():
        print(f"{row['股票代码']:<10} {row['股票名称']:<15} {row['买点日期']:<12} {row['买点价格']:<10.2f} "
              f"{row['MA5']:<10.2f} {row['MA10']:<10.2f} {row['MA20']:<10.2f} {row['MA30']:<10.2f} "
              f"{row['最大差值']:<10.2f} {row['差值百分比']:<12.2f}%")
    
    print("-"*120)
    
    # 统计信息
    avg_diff_percent = df['差值百分比'].mean()
    min_diff_percent = df['差值百分比'].min()
    max_diff_percent = df['差值百分比'].max()
    
    print(f"\n统计信息：")
    print(f"  平均差值百分比: {avg_diff_percent:.2f}%")
    print(f"  最小差值百分比: {min_diff_percent:.2f}%")
    print(f"  最大差值百分比: {max_diff_percent:.2f}%")
    
    # 保存结果到CSV
    output_file = f'bull_stocks_ma_convergence_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
    df.to_csv(output_file, index=False, encoding='utf-8-sig')
    print(f"\n✅ 结果已保存到: {output_file}")

if __name__ == '__main__':
    try:
        analyze_all_bull_stocks()
    except KeyboardInterrupt:
        print("\n⚠️ 用户中断")
    except Exception as e:
        print(f"\n❌ 执行失败: {e}")
        import traceback
        traceback.print_exc()
