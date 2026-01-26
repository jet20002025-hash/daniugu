#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基于 model有效模型0124.json 的回测脚本
在2026、2025、2024、2023四年内，每年随机选1天，找出排名前5的个股
以第二天开盘价买入，计算1周、1个月、2个月的收益
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bull_stock_analyzer import BullStockAnalyzer
from data_fetcher import DataFetcher
from datetime import datetime, date, timedelta
import pandas as pd
import random
import json

def get_random_trading_day(year, fetcher):
    """获取指定年份的一个随机交易日"""
    # 尝试从本地缓存获取日K线数据（用000001作为参考）
    try:
        cache_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cache', 'daily_kline')
        csv_path = os.path.join(cache_dir, '000001.csv')
        
        if os.path.exists(csv_path):
            daily_df = pd.read_csv(csv_path)
        else:
            # 如果本地缓存不存在，使用简单方法：选择年中某一天
            mid_date = date(year, 6, 15)
            return mid_date.strftime('%Y-%m-%d')
    except:
        # 如果读取失败，使用简单方法
        mid_date = date(year, 6, 15)
        return mid_date.strftime('%Y-%m-%d')
    
    if daily_df is None or len(daily_df) == 0:
        # 如果获取失败，使用简单方法：选择年中某一天
        mid_date = date(year, 6, 15)
        return mid_date.strftime('%Y-%m-%d')
    
    daily_df['日期'] = pd.to_datetime(daily_df['日期'], errors='coerce')
    daily_df = daily_df.dropna(subset=['日期'])
    daily_df['日期_date'] = daily_df['日期'].dt.date
    
    # 筛选指定年份的交易日
    year_start = date(year, 1, 1)
    year_end = date(year, 12, 31)
    trading_days = daily_df[
        (daily_df['日期_date'] >= year_start) & 
        (daily_df['日期_date'] <= year_end)
    ]['日期_date'].unique().tolist()
    
    if len(trading_days) == 0:
        # 如果没有交易日，返回年中某一天
        mid_date = date(year, 6, 15)
        return mid_date.strftime('%Y-%m-%d')
    
    # 随机选择一个交易日
    selected = random.choice(trading_days)
    return selected.strftime('%Y-%m-%d') if isinstance(selected, date) else str(selected)[:10]

def get_next_day_open_price(stock_code, scan_date_str, fetcher):
    """获取扫描日期后第一个交易日的开盘价"""
    try:
        scan_date = datetime.strptime(scan_date_str, '%Y-%m-%d').date()
        
        # 获取日K线数据（获取足够的历史数据）
        daily_df = fetcher.get_daily_kline(stock_code, period="2y")
        if daily_df is None or len(daily_df) == 0:
            return None
        
        daily_df['日期'] = pd.to_datetime(daily_df['日期'], errors='coerce')
        daily_df = daily_df.dropna(subset=['日期'])
        daily_df['日期_date'] = daily_df['日期'].dt.date
        daily_df = daily_df.sort_values('日期').reset_index(drop=True)
        
        # 找到扫描日期后的第一个交易日
        next_days = daily_df[daily_df['日期_date'] > scan_date]
        if len(next_days) == 0:
            return None
        
        next_day = next_days.iloc[0]
        open_price = float(next_day.get('开盘', next_day.get('open', 0)))
        
        if open_price > 0:
            return {
                'buy_date': next_day['日期_date'].strftime('%Y-%m-%d') if isinstance(next_day['日期_date'], date) else str(next_day['日期_date'])[:10],
                'buy_price': open_price
            }
        
        return None
    except Exception as e:
        print(f"  ⚠️ 获取 {stock_code} 第二天开盘价失败: {e}")
        return None

def calculate_returns(stock_code, buy_date_str, buy_price, fetcher, periods_days=[5, 20, 40]):
    """
    计算买入后N天的收益
    :param stock_code: 股票代码
    :param buy_date_str: 买入日期（YYYY-MM-DD）
    :param buy_price: 买入价格
    :param fetcher: DataFetcher实例
    :param periods_days: 收益周期（天数列表，默认[5, 20, 40]对应1周、1月、2月）
    :return: 字典，包含各周期的收益
    """
    try:
        buy_date = datetime.strptime(buy_date_str, '%Y-%m-%d').date()
        
        # 获取日K线数据
        daily_df = fetcher.get_daily_kline(stock_code, period="2y")
        if daily_df is None or len(daily_df) == 0:
            return {f'{d}天收益': None for d in periods_days}
        
        daily_df['日期'] = pd.to_datetime(daily_df['日期'], errors='coerce')
        daily_df = daily_df.dropna(subset=['日期'])
        daily_df['日期_date'] = daily_df['日期'].dt.date
        daily_df = daily_df.sort_values('日期').reset_index(drop=True)
        
        # 找到买入日期
        buy_data = daily_df[daily_df['日期_date'] == buy_date]
        if len(buy_data) == 0:
            # 如果买入日期没有数据，找最近的一个交易日
            buy_data = daily_df[daily_df['日期_date'] <= buy_date]
            if len(buy_data) == 0:
                return {f'{d}天收益': None for d in periods_days}
            buy_date = buy_data.iloc[-1]['日期_date']
            buy_data = daily_df[daily_df['日期_date'] == buy_date]
        
        if len(buy_data) == 0:
            return {f'{d}天收益': None for d in periods_days}
        
        buy_idx = buy_data.index[0]
        results = {}
        
        # 计算各周期收益
        for days in periods_days:
            target_date = buy_date + timedelta(days=days)
            end_data = daily_df[
                (daily_df['日期_date'] > buy_date) & 
                (daily_df['日期_date'] <= target_date)
            ]
            
            if len(end_data) == 0:
                # 如果N天内没有数据，使用最后一个交易日
                end_data = daily_df[daily_df['日期_date'] > buy_date]
                if len(end_data) == 0:
                    results[f'{days}天收益'] = None
                    continue
            
            end_price = float(end_data.iloc[-1]['收盘'])
            if end_price > 0:
                gain = (end_price - buy_price) / buy_price * 100
                results[f'{days}天收益'] = round(gain, 2)
            else:
                results[f'{days}天收益'] = None
        
        return results
    except Exception as e:
        print(f"  ⚠️ 计算 {stock_code} 收益失败: {e}")
        return {f'{d}天收益': None for d in periods_days}

def main():
    print("=" * 100)
    print("🚀 基于 model有效模型0124.json 的回测")
    print("=" * 100)
    print()
    
    # 设置随机种子（可选，用于可重复性）
    random.seed(42)
    
    # 加载模型
    model_path = 'model有效模型0124.json'
    print(f"📂 加载模型: {model_path}")
    
    analyzer = BullStockAnalyzer(auto_load_default_stocks=False, auto_analyze_and_train=False)
    if not analyzer.load_model(model_path, skip_network=True):
        print("❌ 模型加载失败")
        return
    
    print("✅ 模型加载成功")
    print()
    
    # 初始化数据获取器
    fetcher = DataFetcher()
    
    # 随机选择4个日期（每年1个）
    years = [2026, 2025, 2024, 2023]
    scan_dates = []
    
    print("📅 随机选择扫描日期...")
    for year in years:
        scan_date = get_random_trading_day(year, fetcher)
        scan_dates.append((year, scan_date))
        print(f"  {year}年: {scan_date}")
    print()
    
    # 存储所有结果
    all_results = []
    
    # 对每个日期进行扫描和回测
    for year, scan_date_str in scan_dates:
        print("=" * 100)
        print(f"📊 {year}年 - 扫描日期: {scan_date_str}")
        print("=" * 100)
        print()
        
        # 扫描全市场
        min_match = float(os.environ.get('BACKTEST_MIN_MATCH_SCORE', '0.85'))
        print(f"🔍 开始扫描全市场 (min_match_score={min_match})...")
        result = analyzer.scan_all_stocks(
            min_match_score=min_match,
            max_market_cap=200.0,  # 放宽市值限制
            scan_date=scan_date_str,
            use_parallel=True,
            max_workers=50,
            strict_local_only=True  # 只使用本地数据
        )
        
        if not result.get('success'):
            print(f"❌ 扫描失败: {result.get('message', '')}")
            continue
        
        candidates = result.get('candidates', [])
        print(f"✅ 扫描完成，找到 {len(candidates)} 只候选股票")
        print()
        
        if len(candidates) == 0:
            print("⚠️ 未找到任何候选股票")
            continue
        
        # 按匹配度排序，取前5只
        candidates_sorted = sorted(candidates, key=lambda x: x.get('匹配度', 0), reverse=True)
        top_5 = candidates_sorted[:5]
        
        print(f"📈 排名前5的个股:")
        print("-" * 100)
        print(f"{'排名':<4} {'代码':<8} {'名称':<12} {'匹配度':<8} {'当前价格':<10}")
        print("-" * 100)
        
        for i, stock in enumerate(top_5, 1):
            code = stock.get('股票代码', 'N/A')
            name = stock.get('股票名称', 'N/A')
            match_score = stock.get('匹配度', 0)
            price = stock.get('当前价格', stock.get('最佳买点价格', 0))
            print(f"{i:<4} {code:<8} {name:<12} {match_score:.3f}    {price:.2f}")
        
        print()
        
        # 获取第二天开盘价并计算收益
        print("💰 计算收益（以第二天开盘价买入）...")
        print()
        
        for i, stock in enumerate(top_5, 1):
            stock_code = stock.get('股票代码')
            stock_name = stock.get('股票名称')
            
            print(f"  [{i}/5] {stock_code} {stock_name}...", end='', flush=True)
            
            # 获取第二天开盘价
            buy_info = get_next_day_open_price(stock_code, scan_date_str, fetcher)
            if buy_info is None:
                print(" ❌ 无法获取买入价")
                continue
            
            buy_date = buy_info['buy_date']
            buy_price = buy_info['buy_price']
            
            # 计算收益（1周=5天，1月=20天，2月=40天）
            returns = calculate_returns(stock_code, buy_date, buy_price, fetcher, periods_days=[5, 20, 40])
            
            # 保存结果
            result_row = {
                '年份': year,
                '扫描日期': scan_date_str,
                '排名': i,
                '股票代码': stock_code,
                '股票名称': stock_name,
                '匹配度': round(stock.get('匹配度', 0), 3),
                '买入日期': buy_date,
                '买入价': round(buy_price, 2),
                '1周收益(%)': returns.get('5天收益'),
                '1月收益(%)': returns.get('20天收益'),
                '2月收益(%)': returns.get('40天收益'),
            }
            
            all_results.append(result_row)
            
            ret_1w = returns.get('5天收益', 'N/A')
            ret_1m = returns.get('20天收益', 'N/A')
            ret_2m = returns.get('40天收益', 'N/A')
            
            ret_1w_str = f"{ret_1w}%" if ret_1w is not None else 'N/A'
            ret_1m_str = f"{ret_1m}%" if ret_1m is not None else 'N/A'
            ret_2m_str = f"{ret_2m}%" if ret_2m is not None else 'N/A'
            
            print(f" ✅ 买入:{buy_date} 价格:{buy_price:.2f} | 1周:{ret_1w_str} 1月:{ret_1m_str} 2月:{ret_2m_str}")
        
        print()
    
    # 输出汇总表格
    print("\n" + "=" * 100)
    print("📊 回测结果汇总表")
    print("=" * 100)
    print()
    
    if len(all_results) == 0:
        print("⚠️ 没有有效的回测结果")
        return
    
    # 创建DataFrame
    df = pd.DataFrame(all_results)
    
    # 打印表格
    print(f"{'年份':<6} {'扫描日期':<12} {'排名':<4} {'代码':<8} {'名称':<12} {'匹配度':<8} {'买入日期':<12} {'买入价':<8} {'1周收益':<10} {'1月收益':<10} {'2月收益':<10}")
    print("-" * 120)
    
    for _, row in df.iterrows():
        ret_1w = row['1周收益(%)']
        ret_1m = row['1月收益(%)']
        ret_2m = row['2月收益(%)']
        
        ret_1w_str = f"{ret_1w:.2f}%" if pd.notna(ret_1w) else "N/A"
        ret_1m_str = f"{ret_1m:.2f}%" if pd.notna(ret_1m) else "N/A"
        ret_2m_str = f"{ret_2m:.2f}%" if pd.notna(ret_2m) else "N/A"
        
        print(f"{row['年份']:<6} {row['扫描日期']:<12} {row['排名']:<4} {row['股票代码']:<8} {row['股票名称']:<12} "
              f"{row['匹配度']:<8.3f} {row['买入日期']:<12} {row['买入价']:<8.2f} "
              f"{ret_1w_str:<10} {ret_1m_str:<10} {ret_2m_str:<10}")
    
    print()
    
    # 统计信息
    print("=" * 100)
    print("📈 收益统计")
    print("=" * 100)
    print()
    
    for period_name, col_name in [('1周', '1周收益(%)'), ('1月', '1月收益(%)'), ('2月', '2月收益(%)')]:
        valid_returns = df[col_name].dropna()
        if len(valid_returns) > 0:
            avg_ret = valid_returns.mean()
            win_rate = (valid_returns > 0).sum() / len(valid_returns) * 100
            max_ret = valid_returns.max()
            min_ret = valid_returns.min()
            print(f"{period_name}: 平均收益 {avg_ret:.2f}% | 胜率 {win_rate:.1f}% | 最大 {max_ret:.2f}% | 最小 {min_ret:.2f}% | 有效样本 {len(valid_returns)}/20")
        else:
            print(f"{period_name}: 无有效数据")
    
    print()
    
    # 保存到CSV
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    csv_filename = f'backtest_model有效模型0124_{timestamp}.csv'
    df.to_csv(csv_filename, index=False, encoding='utf-8-sig')
    print(f"✅ 结果已保存到: {csv_filename}")
    
    # 保存到JSON
    json_filename = f'backtest_model有效模型0124_{timestamp}.json'
    with open(json_filename, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2, default=str)
    print(f"✅ 详细结果已保存到: {json_filename}")
    print()

if __name__ == '__main__':
    main()
