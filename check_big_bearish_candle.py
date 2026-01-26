#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查指定日期股票是否为大阴线
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bull_stock_analyzer import BullStockAnalyzer
from data_fetcher import DataFetcher
from datetime import datetime
import pandas as pd

def check_big_bearish_candle(stock_code, stock_name, date_str):
    """检查指定日期是否为大阴线"""
    print("=" * 80)
    print(f"🔍 检查 {stock_code} {stock_name} 在 {date_str} 是否为大阴线")
    print("=" * 80)
    print()
    
    # 初始化分析器
    analyzer = BullStockAnalyzer(auto_load_default_stocks=False, auto_analyze_and_train=False)
    fetcher = DataFetcher()
    
    # 获取该日期的OHLC数据
    print(f"📊 获取 {date_str} 的日K线数据...")
    daily_df = fetcher.get_daily_kline(stock_code, period="2y")
    
    if daily_df is None or len(daily_df) == 0:
        print("❌ 无法获取日K线数据")
        return
    
    # 标准化列名
    daily_df['日期'] = pd.to_datetime(daily_df['日期'], errors='coerce')
    daily_df = daily_df.dropna(subset=['日期'])
    daily_df['日期_date'] = daily_df['日期'].dt.date
    daily_df = daily_df.sort_values('日期').reset_index(drop=True)
    
    # 找到指定日期
    target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    day_data = daily_df[daily_df['日期_date'] == target_date]
    
    if len(day_data) == 0:
        print(f"⚠️ 未找到 {date_str} 的交易数据")
        print(f"   最近的交易日:")
        nearby = daily_df[
            (daily_df['日期_date'] >= target_date - pd.Timedelta(days=5)) &
            (daily_df['日期_date'] <= target_date + pd.Timedelta(days=5))
        ]
        if len(nearby) > 0:
            for _, row in nearby.iterrows():
                print(f"   {row['日期_date']}: 开盘={row.get('开盘', 'N/A')}, 收盘={row.get('收盘', 'N/A')}")
        return
    
    row = day_data.iloc[0]
    open_price = float(row.get('开盘', row.get('open', 0)))
    close_price = float(row.get('收盘', row.get('close', 0)))
    high_price = float(row.get('最高', row.get('high', 0)))
    low_price = float(row.get('最低', row.get('low', 0)))
    volume = row.get('成交量', row.get('volume', 0))
    
    print(f"✅ 找到 {date_str} 的数据:")
    print(f"   开盘价: {open_price:.2f}")
    print(f"   收盘价: {close_price:.2f}")
    print(f"   最高价: {high_price:.2f}")
    print(f"   最低价: {low_price:.2f}")
    print(f"   成交量: {volume}")
    print()
    
    # 判断是否为大阴线
    if open_price <= 0:
        print("❌ 开盘价无效，无法判断")
        return
    
    is_bearish = close_price < open_price  # 阴线：收盘 < 开盘
    drop_pct = (open_price - close_price) / open_price * 100 if is_bearish else 0
    
    print("=" * 80)
    print("📈 分析结果:")
    print("=" * 80)
    print(f"   是否阴线: {'是' if is_bearish else '否'} (收盘 {'<' if is_bearish else '>='} 开盘)")
    print(f"   跌幅: {drop_pct:.2f}%")
    print()
    
    # 使用分析器的判断方法（默认阈值3%）
    is_big_bearish = analyzer._is_big_bearish_candle_on_date(stock_code, date_str, min_drop_pct=3.0)
    
    print(f"   是否为大阴线 (跌幅>=3%): {'✅ 是' if is_big_bearish else '❌ 否'}")
    print()
    
    if is_big_bearish:
        print("⚠️ 该日期为大阴线，在扫描时会被排除")
    else:
        print("✅ 该日期不是大阴线（或跌幅<3%），不会被排除")
    print()

if __name__ == '__main__':
    # 检查2022年1月5日的峨眉山A
    check_big_bearish_candle('000888', '峨眉山A', '2022-01-05')
