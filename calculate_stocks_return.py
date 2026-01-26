#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
计算指定股票的收益
用法: python3 calculate_stocks_return.py
然后在脚本中修改 stocks 列表
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data_fetcher import DataFetcher
from datetime import datetime, date, timedelta
import pandas as pd

def get_next_day_open_price(stock_code, scan_date_str, fetcher):
    """获取扫描日期后第一个交易日的开盘价"""
    try:
        scan_date = datetime.strptime(scan_date_str, '%Y-%m-%d').date()
        
        # 获取日K线数据
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
    print("💰 计算股票收益")
    print("=" * 100)
    print()
    
    # ========== 在这里修改你要计算的股票 ==========
    # 格式: (股票代码, 股票名称, 扫描日期)
    # 扫描日期：用于确定买入日期（第二天开盘价买入）
    stocks = [
        # 示例：
        # ('000001', '平安银行', '2026-01-19'),
        # ('000002', '万科A', '2026-01-19'),
        # 请在这里添加你的5只股票
    ]
    # ============================================
    
    if len(stocks) == 0:
        print("⚠️ 请在脚本中修改 stocks 列表，添加要计算的股票")
        print("\n格式示例:")
        print("stocks = [")
        print("    ('000001', '平安银行', '2026-01-19'),")
        print("    ('000002', '万科A', '2026-01-19'),")
        print("    # ... 添加更多股票")
        print("]")
        return
    
    print(f"📊 准备计算 {len(stocks)} 只股票的收益")
    print()
    
    # 初始化数据获取器
    fetcher = DataFetcher()
    
    # 存储结果
    results = []
    
    # 计算每只股票
    for i, (stock_code, stock_name, scan_date_str) in enumerate(stocks, 1):
        print(f"[{i}/{len(stocks)}] {stock_code} {stock_name} (扫描日期: {scan_date_str})...", end='', flush=True)
        
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
            '股票代码': stock_code,
            '股票名称': stock_name,
            '扫描日期': scan_date_str,
            '买入日期': buy_date,
            '买入价': round(buy_price, 2),
            '1周收益(%)': returns.get('5天收益'),
            '1月收益(%)': returns.get('20天收益'),
            '2月收益(%)': returns.get('40天收益'),
        }
        
        results.append(result_row)
        
        ret_1w = returns.get('5天收益', 'N/A')
        ret_1m = returns.get('20天收益', 'N/A')
        ret_2m = returns.get('40天收益', 'N/A')
        
        ret_1w_str = f"{ret_1w}%" if ret_1w is not None else 'N/A'
        ret_1m_str = f"{ret_1m}%" if ret_1m is not None else 'N/A'
        ret_2m_str = f"{ret_2m}%" if ret_2m is not None else 'N/A'
        
        print(f" ✅ 买入:{buy_date} 价格:{buy_price:.2f} | 1周:{ret_1w_str} 1月:{ret_1m_str} 2月:{ret_2m_str}")
    
    print()
    
    # 输出汇总表格
    if len(results) == 0:
        print("⚠️ 没有有效的计算结果")
        return
    
    print("=" * 100)
    print("📊 收益汇总表")
    print("=" * 100)
    print()
    
    # 打印表头
    print(f"{'股票代码':<10} {'股票名称':<12} {'扫描日期':<12} {'买入日期':<12} {'买入价':<8} {'1周收益':<10} {'1月收益':<10} {'2月收益':<10}")
    print("-" * 100)
    
    # 打印数据
    for row in results:
        ret_1w = row['1周收益(%)']
        ret_1m = row['1月收益(%)']
        ret_2m = row['2月收益(%)']
        
        ret_1w_str = f"{ret_1w:.2f}%" if ret_1w is not None else "N/A"
        ret_1m_str = f"{ret_1m:.2f}%" if ret_1m is not None else "N/A"
        ret_2m_str = f"{ret_2m:.2f}%" if ret_2m is not None else "N/A"
        
        print(f"{row['股票代码']:<10} {row['股票名称']:<12} {row['扫描日期']:<12} {row['买入日期']:<12} "
              f"{row['买入价']:<8.2f} {ret_1w_str:<10} {ret_1m_str:<10} {ret_2m_str:<10}")
    
    print()
    
    # 统计信息
    print("=" * 100)
    print("📈 收益统计")
    print("=" * 100)
    print()
    
    df = pd.DataFrame(results)
    
    for period_name, col_name in [('1周', '1周收益(%)'), ('1月', '1月收益(%)'), ('2月', '2月收益(%)')]:
        valid_returns = df[col_name].dropna()
        if len(valid_returns) > 0:
            avg_ret = valid_returns.mean()
            win_rate = (valid_returns > 0).sum() / len(valid_returns) * 100
            max_ret = valid_returns.max()
            min_ret = valid_returns.min()
            print(f"{period_name}: 平均收益 {avg_ret:.2f}% | 胜率 {win_rate:.1f}% | 最大 {max_ret:.2f}% | 最小 {min_ret:.2f}% | 有效样本 {len(valid_returns)}/{len(results)}")
        else:
            print(f"{period_name}: 无有效数据")
    
    print()
    
    # 保存到CSV
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    csv_filename = f'stocks_return_{timestamp}.csv'
    df.to_csv(csv_filename, index=False, encoding='utf-8-sig')
    print(f"✅ 结果已保存到: {csv_filename}")
    print()

if __name__ == '__main__':
    main()
