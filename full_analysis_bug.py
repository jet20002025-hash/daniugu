#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
完整分析峨眉山A在2022-01-05的匹配度计算和大阴线过滤问题
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bull_stock_analyzer import BullStockAnalyzer
from data_fetcher import DataFetcher
from datetime import datetime
import pandas as pd

def full_analysis():
    print("=" * 100)
    print("🔍 完整分析：峨眉山A (000888) 在2022-01-05的匹配度和大阴线过滤问题")
    print("=" * 100)
    print()
    
    stock_code = '000888'
    stock_name = '峨眉山A'
    scan_date = '2026-01-23'  # 假设扫描日期是今天
    buy_date = '2022-01-05'   # 最佳买点日期
    
    # 加载模型
    analyzer = BullStockAnalyzer(auto_load_default_stocks=False, auto_analyze_and_train=False)
    analyzer.load_model('model有效模型0124.json', skip_network=True)
    
    print("=" * 100)
    print("1️⃣ 大阴线检查（使用系统方法）")
    print("=" * 100)
    
    # 检查买点日期
    result_buy_date = analyzer._is_big_bearish_candle_on_date(stock_code, buy_date)
    print(f"   _is_big_bearish_candle_on_date('{stock_code}', '{buy_date}'): {result_buy_date}")
    
    # 检查扫描日期
    result_scan_date = analyzer._is_big_bearish_candle_on_date(stock_code, scan_date)
    print(f"   _is_big_bearish_candle_on_date('{stock_code}', '{scan_date}'): {result_scan_date}")
    print()
    
    # 检查_get_ohlc_on_date
    ohlc_buy = analyzer._get_ohlc_on_date(stock_code, buy_date)
    ohlc_scan = analyzer._get_ohlc_on_date(stock_code, scan_date)
    print(f"   _get_ohlc_on_date('{stock_code}', '{buy_date}'): {ohlc_buy}")
    print(f"   _get_ohlc_on_date('{stock_code}', '{scan_date}'): {ohlc_scan}")
    print()
    
    print("=" * 100)
    print("2️⃣ 从本地缓存直接读取2022-01-05的数据")
    print("=" * 100)
    
    # 从本地缓存读取
    cache_file = f'cache/daily_kline/{stock_code}.csv'
    if os.path.exists(cache_file):
        df = pd.read_csv(cache_file, encoding='utf-8-sig')
        df['日期'] = pd.to_datetime(df['日期'], errors='coerce')
        df = df.sort_values('日期').reset_index(drop=True)
        
        target = datetime(2022, 1, 5).date()
        df['日期_date'] = df['日期'].dt.date
        day_data = df[df['日期_date'] == target]
        
        if len(day_data) > 0:
            row = day_data.iloc[0]
            o = float(row['开盘'])
            c = float(row['收盘'])
            h = float(row['最高'])
            l = float(row['最低'])
            drop_pct = (o - c) / o * 100 if c < o else 0
            
            print(f"   ✅ 找到数据:")
            print(f"      开盘: {o:.2f}")
            print(f"      收盘: {c:.2f}")
            print(f"      最高: {h:.2f}")
            print(f"      最低: {l:.2f}")
            print(f"      跌幅: {drop_pct:.2f}%")
            print(f"      是否阴线: {'是' if c < o else '否'}")
            print(f"      是否大阴线 (跌幅>=3%): {'✅ 是' if (c < o and drop_pct >= 3.0) else '❌ 否'}")
        else:
            print("   ❌ 本地缓存中未找到该日期")
    else:
        print(f"   ❌ 本地缓存文件不存在: {cache_file}")
    print()
    
    print("=" * 100)
    print("3️⃣ 计算匹配度")
    print("=" * 100)
    
    # 获取周K线
    weekly_df = analyzer.fetcher.get_weekly_kline(stock_code, period="2y", use_cache=True, local_only=True)
    if weekly_df is None or len(weekly_df) == 0:
        print("   ❌ 无法获取周K线数据")
        return
    
    # 截断到扫描日期
    scan_ts = pd.to_datetime(scan_date)
    if '日期' in weekly_df.columns:
        weekly_df['__dt'] = pd.to_datetime(weekly_df['日期'], errors='coerce')
        weekly_df = weekly_df.dropna(subset=['__dt'])
        weekly_df = weekly_df[weekly_df['__dt'] <= scan_ts]
        weekly_df = weekly_df.sort_values('__dt').reset_index(drop=True)
    
    # 找到买点对应的周
    buy_ts = pd.to_datetime(buy_date)
    buy_idx = None
    for i, row in weekly_df.iterrows():
        if pd.to_datetime(row['日期']) <= buy_ts:
            buy_idx = i
        else:
            break
    
    if buy_idx is None:
        print("   ❌ 无法找到买点对应的周")
        return
    
    # 提取特征
    features = analyzer.extract_features_at_start_point(stock_code, buy_idx, lookback_weeks=40, weekly_df=weekly_df)
    if features is None:
        print("   ❌ 特征提取失败")
        return
    
    # 计算匹配度
    common_features = analyzer.trained_features.get('common_features', {})
    match_result = analyzer._calculate_match_score(features, common_features, tolerance=0.3)
    total_match = match_result.get('总匹配度', 0)
    
    print(f"   匹配度: {total_match:.4f}")
    print()
    
    print("=" * 100)
    print("4️⃣ 问题分析")
    print("=" * 100)
    print()
    print("   🐛 Bug #1: _get_ohlc_on_date 不从本地缓存读取")
    print("      - _get_ohlc_on_date 使用 get_daily_kline_range，该方法只从网络获取")
    print("      - 当网络请求失败时，返回 None")
    print("      - _is_big_bearish_candle_on_date 收到 None 后返回 False")
    print("      - 导致大阴线检查失效")
    print()
    print("   🐛 Bug #2: 大阴线检查使用了错误的日期")
    print("      - 代码中: buy_date = limit_date (扫描日期)")
    print("      - 检查: _is_big_bearish_candle_on_date(stock_code, limit_date)")
    print("      - 实际应该检查: _is_big_bearish_candle_on_date(stock_code, buy_date)")
    print("      - 但 buy_date 被设置为 limit_date，所以检查的是扫描日期，不是最佳买点日期")
    print()
    print("   实际情况:")
    print(f"      - 扫描日期: {scan_date}")
    print(f"      - 最佳买点日期: {buy_date}")
    print(f"      - 代码检查的是: {scan_date} (错误！)")
    print(f"      - 应该检查的是: {buy_date} (正确)")
    print(f"      - {buy_date} 是大阴线，但代码检查的是 {scan_date}，所以没有被过滤")
    print()
    
    print("=" * 100)
    print("5️⃣ 总结")
    print("=" * 100)
    print()
    print(f"   股票: {stock_code} {stock_name}")
    print(f"   匹配度: {total_match:.4f}")
    print(f"   最佳买点日期: {buy_date}")
    print(f"   {buy_date} 实际是大阴线 (跌幅5.47%)")
    print(f"   但系统检查的是扫描日期 ({scan_date})，不是买点日期")
    print(f"   因此股票没有被过滤掉")
    print()
    print("   修复建议:")
    print("   1. 修改 _get_ohlc_on_date，优先从本地缓存读取")
    print("   2. 修改扫描逻辑，检查实际的最佳买点日期，而不是扫描日期")
    print()

if __name__ == '__main__':
    full_analysis()
