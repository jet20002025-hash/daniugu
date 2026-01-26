#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
调试300342的起点选择逻辑
"""
from bull_stock_analyzer import BullStockAnalyzer
import pandas as pd

def debug_selection():
    """调试选择逻辑"""
    print("=" * 80)
    print("🔍 调试300342的起点选择逻辑")
    print("=" * 80)
    
    stock_code = '300342'
    
    analyzer = BullStockAnalyzer(auto_load_default_stocks=False, auto_analyze_and_train=False)
    weekly_df = analyzer.fetcher.get_weekly_kline(stock_code, period="2y")
    
    # 过滤未来日期
    from datetime import datetime, timedelta
    today = datetime.now().date() + timedelta(days=1)
    if '日期' in weekly_df.columns:
        weekly_df['日期'] = pd.to_datetime(weekly_df['日期'])
        weekly_df['日期_date'] = weekly_df['日期'].dt.date
        weekly_df = weekly_df[weekly_df['日期_date'] <= today].copy()
        weekly_df = weekly_df.drop(columns=['日期_date'])
        weekly_df = weekly_df.sort_values('日期').reset_index(drop=True)
    
    search_weeks = 10
    max_gain = 0
    best_start_idx = None
    best_end_idx = None
    best_start_date = None
    best_end_date = None
    
    # 记录所有起点的涨幅
    all_gains = []
    
    print(f"\n遍历所有可能的起点（共 {len(weekly_df) - search_weeks + 1} 个）...")
    
    for start_idx in range(len(weekly_df) - search_weeks + 1):
        start_price = float(weekly_df.iloc[start_idx]['收盘'])
        start_date = weekly_df.iloc[start_idx]['日期']
        
        end_idx = min(start_idx + search_weeks, len(weekly_df))
        window_df = weekly_df.iloc[start_idx:end_idx]
        
        max_price_idx = window_df['最高'].idxmax()
        max_price = float(window_df.loc[max_price_idx, '最高'])
        max_price_date = window_df.loc[max_price_idx, '日期']
        
        gain = (max_price - start_price) / start_price * 100
        
        all_gains.append({
            'start_idx': start_idx,
            'start_date': start_date,
            'start_price': start_price,
            'max_price': max_price,
            'max_price_date': max_price_date,
            'gain': gain
        })
        
        if gain > max_gain:
            max_gain = gain
            best_start_idx = start_idx
            best_end_idx = weekly_df.index.get_loc(max_price_idx)
            best_start_date = start_date
            best_end_date = max_price_date
    
    # 找出涨幅最大的前10个起点
    all_gains.sort(key=lambda x: x['gain'], reverse=True)
    
    print(f"\n📊 涨幅最大的前10个起点:")
    print("-" * 100)
    for i, item in enumerate(all_gains[:10], 1):
        marker = " ⭐ 当前选择" if item['start_idx'] == best_start_idx else ""
        print(f"{i:2d}. 索引{item['start_idx']:3d} | 日期: {item['start_date']} | 起点价格: {item['start_price']:.2f} | 最高价: {item['max_price']:.2f} | 涨幅: {item['gain']:.2f}%{marker}")
    
    # 特别关注11月14日和11月21日
    print(f"\n📅 11月14日和11月21日的详细对比:")
    print("-" * 100)
    
    idx_1114 = None
    idx_1121 = None
    for i in range(len(weekly_df)):
        date = str(weekly_df.iloc[i]['日期'])
        if '2025-11-14' in date or '11-14' in date:
            idx_1114 = i
        if '2025-11-21' in date or '11-21' in date:
            idx_1121 = i
    
    if idx_1114 is not None:
        gain_1114 = next((x for x in all_gains if x['start_idx'] == idx_1114), None)
        if gain_1114:
            print(f"\n11月14日 (索引{idx_1114}):")
            print(f"   起点价格: {gain_1114['start_price']:.2f} 元")
            print(f"   10周内最高价: {gain_1114['max_price']:.2f} 元 (日期: {gain_1114['max_price_date']})")
            print(f"   涨幅: {gain_1114['gain']:.2f}%")
            print(f"   排名: {all_gains.index(gain_1114) + 1}")
    
    if idx_1121 is not None:
        gain_1121 = next((x for x in all_gains if x['start_idx'] == idx_1121), None)
        if gain_1121:
            print(f"\n11月21日 (索引{idx_1121}):")
            print(f"   起点价格: {gain_1121['start_price']:.2f} 元")
            print(f"   10周内最高价: {gain_1121['max_price']:.2f} 元 (日期: {gain_1121['max_price_date']})")
            print(f"   涨幅: {gain_1121['gain']:.2f}%")
            print(f"   排名: {all_gains.index(gain_1121) + 1}")
    
    print(f"\n" + "=" * 80)
    print("💡 结论")
    print("=" * 80)
    
    if idx_1114 is not None and idx_1121 is not None:
        gain_1114 = next((x for x in all_gains if x['start_idx'] == idx_1114), None)
        gain_1121 = next((x for x in all_gains if x['start_idx'] == idx_1121), None)
        
        if gain_1114 and gain_1121:
            if gain_1121['gain'] > gain_1114['gain']:
                print(f"⚠️ 问题发现：")
                print(f"   - 11月21日起点的涨幅 ({gain_1121['gain']:.2f}%) 明显大于11月14日起点的涨幅 ({gain_1114['gain']:.2f}%)")
                print(f"   - 但算法选择了11月14日，这可能是一个bug")
                print(f"   - 建议：应该选择11月21日作为起点，因为它的涨幅更大")
                print(f"\n📊 数据对比：")
                print(f"   11月14日: 起点价格 {gain_1114['start_price']:.2f} 元 → 最高价 {gain_1114['max_price']:.2f} 元 = 涨幅 {gain_1114['gain']:.2f}%")
                print(f"   11月21日: 起点价格 {gain_1121['start_price']:.2f} 元 → 最高价 {gain_1121['max_price']:.2f} 元 = 涨幅 {gain_1121['gain']:.2f}%")
                print(f"\n✅ 建议：将起点改为11月21日，涨幅提升 {gain_1121['gain'] - gain_1114['gain']:.2f} 个百分点")
            else:
                print(f"✅ 算法选择正确：11月14日起点的涨幅更大")

if __name__ == '__main__':
    debug_selection()
