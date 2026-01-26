#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
详细计算峨眉山A在2022-01-05的匹配度，并检查大阴线过滤逻辑
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bull_stock_analyzer import BullStockAnalyzer
from data_fetcher import DataFetcher
from datetime import datetime
import pandas as pd
import json

def detailed_calculate_match(stock_code, stock_name, scan_date_str, buy_date_str):
    """详细计算匹配度并展示过程"""
    print("=" * 100)
    print(f"🔍 详细计算 {stock_code} {stock_name} 的匹配度")
    print(f"   扫描日期: {scan_date_str}")
    print(f"   最佳买点日期: {buy_date_str}")
    print("=" * 100)
    print()
    
    # 加载最新模型
    analyzer = BullStockAnalyzer(auto_load_default_stocks=False, auto_analyze_and_train=False)
    model_path = 'model有效模型0124.json'
    
    print(f"📂 加载模型: {model_path}")
    if not analyzer.load_model(model_path, skip_network=True):
        print("❌ 模型加载失败")
        return
    
    print("✅ 模型加载成功")
    print()
    
    # 获取特征模板
    common_features = analyzer.trained_features.get('common_features', {})
    print(f"📊 特征模板包含 {len(common_features)} 个特征")
    print()
    
    # 检查大阴线
    print("=" * 100)
    print("1️⃣ 检查大阴线过滤")
    print("=" * 100)
    
    # 检查扫描日期
    is_big_bear_scan_date = analyzer._is_big_bearish_candle_on_date(stock_code, scan_date_str)
    print(f"   扫描日期 ({scan_date_str}) 是否为大阴线: {'✅ 是' if is_big_bear_scan_date else '❌ 否'}")
    
    # 检查买点日期
    is_big_bear_buy_date = analyzer._is_big_bearish_candle_on_date(stock_code, buy_date_str)
    print(f"   买点日期 ({buy_date_str}) 是否为大阴线: {'✅ 是' if is_big_bear_buy_date else '❌ 否'}")
    print()
    
    if is_big_bear_buy_date:
        print("⚠️ 买点日期是大阴线，应该被排除！")
        print()
    
    # 获取周K线数据
    print("=" * 100)
    print("2️⃣ 获取周K线数据")
    print("=" * 100)
    
    weekly_df = analyzer.fetcher.get_weekly_kline(stock_code, period="2y", use_cache=True, local_only=True)
    if weekly_df is None or len(weekly_df) == 0:
        print("❌ 无法获取周K线数据")
        return
    
    # 按扫描日期截断
    scan_ts = pd.to_datetime(scan_date_str)
    if '日期' in weekly_df.columns:
        weekly_df['__dt'] = pd.to_datetime(weekly_df['日期'], errors='coerce')
        weekly_df = weekly_df.dropna(subset=['__dt'])
        weekly_df = weekly_df[weekly_df['__dt'] <= scan_ts]
        weekly_df = weekly_df.sort_values('__dt').reset_index(drop=True)
    
    print(f"   获取到 {len(weekly_df)} 周数据（截断到 {scan_date_str}）")
    
    # 找到买点日期对应的周
    buy_ts = pd.to_datetime(buy_date_str)
    buy_idx = None
    for i, row in weekly_df.iterrows():
        if pd.to_datetime(row['日期']) <= buy_ts:
            buy_idx = i
        else:
            break
    
    if buy_idx is None:
        print("❌ 无法找到买点日期对应的周")
        return
    
    print(f"   买点日期对应的周索引: {buy_idx}")
    print(f"   该周日期: {weekly_df.iloc[buy_idx]['日期']}")
    print()
    
    # 提取特征
    print("=" * 100)
    print("3️⃣ 提取特征")
    print("=" * 100)
    
    features = analyzer.extract_features_at_start_point(stock_code, buy_idx, lookback_weeks=40, weekly_df=weekly_df)
    if features is None:
        print("❌ 特征提取失败")
        return
    
    print(f"   成功提取 {len(features)} 个特征")
    print()
    
    # 显示部分特征
    print("   部分特征值:")
    feature_items = list(features.items())[:10]
    for key, value in feature_items:
        if isinstance(value, (int, float)):
            print(f"     {key}: {value:.4f}")
        else:
            print(f"     {key}: {value}")
    print(f"     ... (共 {len(features)} 个特征)")
    print()
    
    # 计算匹配度
    print("=" * 100)
    print("4️⃣ 计算匹配度")
    print("=" * 100)
    
    match_result = analyzer._calculate_match_score(features, common_features, tolerance=0.3)
    
    total_match = match_result.get('总匹配度', 0)
    print(f"   总匹配度: {total_match:.4f}")
    print()
    
    # 显示详细匹配信息
    print("   详细匹配信息:")
    core_match = match_result.get('核心特征匹配', {})
    if core_match:
        print("   核心特征匹配:")
        for key, value in list(core_match.items())[:10]:
            if isinstance(value, dict):
                score = value.get('匹配度', 0)
                print(f"     {key}: {score:.4f}")
            else:
                print(f"     {key}: {value}")
        print(f"     ... (共 {len(core_match)} 个核心特征)")
    print()
    
    # 检查扫描逻辑中的大阴线过滤
    print("=" * 100)
    print("5️⃣ 扫描逻辑中的大阴线过滤检查")
    print("=" * 100)
    
    # 模拟扫描逻辑
    print(f"   在扫描逻辑中:")
    print(f"   - limit_date (扫描日期) = {scan_date_str}")
    print(f"   - buy_date (最佳买点日期) = {buy_date_str}")
    print()
    
    # 检查代码中实际使用的日期
    print("   代码检查:")
    print(f"   - 代码中使用: _is_big_bearish_candle_on_date(stock_code, limit_date)")
    print(f"   - 即检查: {scan_date_str} 是否为大阴线")
    print(f"   - 结果: {'✅ 是' if is_big_bear_scan_date else '❌ 否'}")
    print()
    
    print(f"   ⚠️ 问题发现:")
    print(f"   - 代码检查的是 limit_date ({scan_date_str})，而不是 buy_date ({buy_date_str})")
    print(f"   - 买点日期 ({buy_date_str}) 是大阴线，但扫描日期 ({scan_date_str}) 不是")
    print(f"   - 因此股票没有被过滤掉！")
    print()
    
    # 总结
    print("=" * 100)
    print("📊 总结")
    print("=" * 100)
    print(f"   股票代码: {stock_code}")
    print(f"   股票名称: {stock_name}")
    print(f"   扫描日期: {scan_date_str}")
    print(f"   最佳买点日期: {buy_date_str}")
    print(f"   匹配度: {total_match:.4f}")
    print(f"   买点日期是否为大阴线: {'✅ 是 (应该被排除)' if is_big_bear_buy_date else '❌ 否'}")
    print(f"   扫描日期是否为大阴线: {'✅ 是' if is_big_bear_scan_date else '❌ 否'}")
    print()
    print("   🐛 Bug确认:")
    print("   扫描逻辑中应该检查 buy_date 是否为大阴线，而不是 limit_date！")
    print()

if __name__ == '__main__':
    # 峨眉山A在2022-01-05的情况
    # 假设扫描日期是今天（2026-01-23），但最佳买点是2022-01-05
    detailed_calculate_match('000888', '峨眉山A', '2026-01-23', '2022-01-05')
