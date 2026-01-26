#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
分析300342天银机电的买点选择：为什么选择11月14日而不是11月21日
"""
from bull_stock_analyzer import BullStockAnalyzer
import pandas as pd

def analyze_300342():
    """分析300342的买点选择"""
    print("=" * 80)
    print("🔍 分析300342天银机电的买点选择")
    print("=" * 80)
    
    stock_code = '300342'
    stock_name = '天银机电'
    
    # 创建分析器
    analyzer = BullStockAnalyzer(auto_load_default_stocks=False, auto_analyze_and_train=False)
    analyzer.load_model('trained_model.json', skip_network=True)
    
    # 获取周K线数据
    print(f"\n📈 获取 {stock_code} {stock_name} 的周K线数据...")
    weekly_df = analyzer.fetcher.get_weekly_kline(stock_code, period="2y")
    if weekly_df is None or len(weekly_df) == 0:
        print(f"❌ 无法获取周K线数据")
        return
    
    print(f"总周数: {len(weekly_df)}")
    print(f"数据日期范围: {weekly_df.iloc[0]['日期']} 至 {weekly_df.iloc[-1]['日期']}")
    
    # 查找11月14日和11月21日的位置
    print(f"\n📅 查找关键日期...")
    idx_1114 = None
    idx_1121 = None
    
    for i in range(len(weekly_df)):
        date = str(weekly_df.iloc[i]['日期'])
        if '2025-11-14' in date or '11-14' in date:
            idx_1114 = i
        if '2025-11-21' in date or '11-21' in date:
            idx_1121 = i
    
    print(f"11月14日索引: {idx_1114}")
    print(f"11月21日索引: {idx_1121}")
    
    # 显示这两个日期前后的详细数据
    if idx_1114 is not None:
        print(f"\n📊 11月14日前后各5周的数据:")
        print("-" * 100)
        start_range = max(0, idx_1114 - 5)
        end_range = min(len(weekly_df), idx_1114 + 6)
        for i in range(start_range, end_range):
            row = weekly_df.iloc[i]
            date = row['日期']
            close = row['收盘']
            high = row.get('最高', close)
            low = row.get('最低', close)
            volume = row.get('周成交量', row.get('成交量', 0))
            change_pct = row.get('涨跌幅', 0)
            marker = " ⭐ 11月14日" if i == idx_1114 else ""
            print(f"   [{i:3d}] {date} | 收盘: {close:.2f} | 最高: {high:.2f} | 最低: {low:.2f} | 成交量: {volume:,.0f} | 涨跌幅: {change_pct:+.2f}%{marker}")
    
    if idx_1121 is not None:
        print(f"\n📊 11月21日前后各5周的数据:")
        print("-" * 100)
        start_range = max(0, idx_1121 - 5)
        end_range = min(len(weekly_df), idx_1121 + 6)
        for i in range(start_range, end_range):
            row = weekly_df.iloc[i]
            date = row['日期']
            close = row['收盘']
            high = row.get('最高', close)
            low = row.get('最低', close)
            volume = row.get('周成交量', row.get('成交量', 0))
            change_pct = row.get('涨跌幅', 0)
            marker = " ⭐ 11月21日" if i == idx_1121 else ""
            print(f"   [{i:3d}] {date} | 收盘: {close:.2f} | 最高: {high:.2f} | 最低: {low:.2f} | 成交量: {volume:,.0f} | 涨跌幅: {change_pct:+.2f}%{marker}")
    
    # 查看当前分析结果
    if stock_code in analyzer.analysis_results:
        result = analyzer.analysis_results[stock_code]
        interval = result.get('interval', {})
        current_start_idx = interval.get('起点索引')
        current_start_date = interval.get('起点日期')
        current_start_price = interval.get('起点价格')
        current_end_date = interval.get('终点日期')
        current_end_price = interval.get('终点价格')
        current_gain = interval.get('涨幅', 0)
        
        print(f"\n📊 当前分析结果:")
        print(f"   起点日期: {current_start_date}")
        print(f"   起点索引: {current_start_idx}")
        print(f"   起点价格: {current_start_price} 元")
        print(f"   终点日期: {current_end_date}")
        print(f"   终点价格: {current_end_price} 元")
        print(f"   涨幅: {current_gain:.2f}%")
    
    # 比较11月14日和11月21日作为起点的涨幅
    print(f"\n🔍 比较不同起点日期的涨幅（在10周内查找最高点）:")
    print("-" * 80)
    
    search_weeks = 10
    
    if idx_1114 is not None:
        start_price_1114 = float(weekly_df.iloc[idx_1114]['收盘'])
        end_idx_1114 = min(idx_1114 + search_weeks, len(weekly_df))
        window_df_1114 = weekly_df.iloc[idx_1114:end_idx_1114]
        max_price_1114 = float(window_df_1114['最高'].max())
        max_price_idx_1114 = window_df_1114['最高'].idxmax()
        max_price_date_1114 = weekly_df.loc[max_price_idx_1114, '日期']
        gain_1114 = (max_price_1114 - start_price_1114) / start_price_1114 * 100
        
        print(f"\n以11月14日为起点:")
        print(f"   起点价格: {start_price_1114:.2f} 元")
        print(f"   10周内最高价: {max_price_1114:.2f} 元 (日期: {max_price_date_1114})")
        print(f"   涨幅: {gain_1114:.2f}%")
    
    if idx_1121 is not None:
        start_price_1121 = float(weekly_df.iloc[idx_1121]['收盘'])
        end_idx_1121 = min(idx_1121 + search_weeks, len(weekly_df))
        window_df_1121 = weekly_df.iloc[idx_1121:end_idx_1121]
        max_price_1121 = float(window_df_1121['最高'].max())
        max_price_idx_1121 = window_df_1121['最高'].idxmax()
        max_price_date_1121 = weekly_df.loc[max_price_idx_1121, '日期']
        gain_1121 = (max_price_1121 - start_price_1121) / start_price_1121 * 100
        
        print(f"\n以11月21日为起点:")
        print(f"   起点价格: {start_price_1121:.2f} 元")
        print(f"   10周内最高价: {max_price_1121:.2f} 元 (日期: {max_price_date_1121})")
        print(f"   涨幅: {gain_1121:.2f}%")
    
    # 分析为什么选择11月14日
    print(f"\n" + "=" * 80)
    print("💡 分析选择11月14日的原因")
    print("=" * 80)
    
    if idx_1114 is not None and idx_1121 is not None:
        if gain_1114 > gain_1121:
            print(f"✅ 选择11月14日的原因：")
            print(f"   - 11月14日起点的涨幅 ({gain_1114:.2f}%) 大于11月21日起点的涨幅 ({gain_1121:.2f}%)")
            print(f"   - 算法目标是找到10周内涨幅最大的区间")
            print(f"   - 因此选择了涨幅更大的11月14日")
        else:
            print(f"⚠️ 发现：11月21日起点的涨幅 ({gain_1121:.2f}%) 大于11月14日起点的涨幅 ({gain_1114:.2f}%)")
            print(f"   但当前分析选择了11月14日，可能存在以下原因：")
            print(f"   1. 算法遍历所有可能的起点，选择全局最大涨幅")
            print(f"   2. 可能存在其他起点（非11月14日或11月21日）产生了更大的涨幅")
            print(f"   3. 需要查看完整的分析过程")
    
    # 重新分析，查看所有可能的起点
    print(f"\n" + "=" * 80)
    print("🔍 重新分析，查看所有可能的起点（10周窗口）")
    print("=" * 80)
    
    max_gain = 0
    best_start_idx = None
    best_end_idx = None
    best_start_date = None
    best_end_date = None
    
    for start_idx in range(len(weekly_df) - search_weeks + 1):
        start_price = float(weekly_df.iloc[start_idx]['收盘'])
        start_date = weekly_df.iloc[start_idx]['日期']
        
        end_idx = min(start_idx + search_weeks, len(weekly_df))
        window_df = weekly_df.iloc[start_idx:end_idx]
        max_price = float(window_df['最高'].max())
        max_price_idx = window_df['最高'].idxmax()
        
        gain = (max_price - start_price) / start_price * 100
        
        if gain > max_gain:
            max_gain = gain
            best_start_idx = start_idx
            best_end_idx = weekly_df.index.get_loc(max_price_idx)
            best_start_date = start_date
            best_end_date = weekly_df.loc[max_price_idx, '日期']
    
    print(f"\n✅ 全局最大涨幅区间:")
    print(f"   起点日期: {best_start_date}")
    print(f"   起点索引: {best_start_idx}")
    print(f"   起点价格: {float(weekly_df.iloc[best_start_idx]['收盘']):.2f} 元")
    print(f"   终点日期: {best_end_date}")
    print(f"   终点价格: {float(weekly_df.loc[best_end_idx, '最高']):.2f} 元")
    print(f"   涨幅: {max_gain:.2f}%")
    
    # 检查11月14日和11月21日附近的涨幅
    print(f"\n📊 11月14日和11月21日附近的涨幅对比:")
    if idx_1114 is not None:
        print(f"   11月14日 (索引{idx_1114}): 涨幅 = {gain_1114:.2f}%")
    if idx_1121 is not None:
        print(f"   11月21日 (索引{idx_1121}): 涨幅 = {gain_1121:.2f}%")
    
    if best_start_idx == idx_1114:
        print(f"\n✅ 结论：算法选择了11月14日，因为它是全局最大涨幅的起点")
    elif best_start_idx == idx_1121:
        print(f"\n⚠️ 结论：算法应该选择11月21日，但当前分析选择了11月14日，可能存在bug")
    else:
        print(f"\n💡 结论：算法选择了索引{best_start_idx} ({best_start_date})，而不是11月14日或11月21日")
        print(f"   这说明在10周窗口内，存在其他起点产生了更大的涨幅")

if __name__ == '__main__':
    analyze_300342()
