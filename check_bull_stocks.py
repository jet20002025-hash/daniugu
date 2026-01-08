#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查股票是否符合大牛股要求（一个月内涨幅超过100%）
"""
from data_fetcher import DataFetcher
import pandas as pd
from datetime import datetime, timedelta

def check_bull_stock(stock_code):
    """
    检查股票是否符合大牛股要求
    大牛股定义：在一个月内（约20个交易日，或4-5周）涨幅超过100%
    """
    fetcher = DataFetcher()
    
    print(f"\n{'='*80}")
    print(f"检查股票: {stock_code}")
    print(f"{'='*80}")
    
    # 获取周K线数据（至少需要2年数据）
    weekly_df = fetcher.get_weekly_kline(stock_code, period="2y")
    
    if weekly_df is None or len(weekly_df) == 0:
        print(f"❌ 无法获取 {stock_code} 的周线数据")
        return False
    
    if len(weekly_df) < 10:
        print(f"❌ {stock_code} 数据不足（少于10周）")
        return False
    
    print(f"✅ 获取到 {len(weekly_df)} 周数据")
    
    # 查找涨幅最大的区间（在10周内查找最高点）
    max_gain = 0
    max_gain_start_idx = None
    max_gain_end_idx = None
    max_gain_start_price = None
    max_gain_end_price = None
    max_gain_start_date = None
    max_gain_end_date = None
    
    search_weeks = 10  # 在起点后10周内查找最高点
    
    # 遍历所有可能的起点
    for start_idx in range(len(weekly_df) - search_weeks + 1):
        start_price = float(weekly_df.iloc[start_idx]['收盘'])
        start_date = weekly_df.iloc[start_idx]['日期']
        
        # 在起点后的search_weeks周内，找到最高价格
        end_idx = min(start_idx + search_weeks, len(weekly_df))
        window_df = weekly_df.iloc[start_idx:end_idx]
        
        # 找到窗口内的最高价格和对应日期
        max_price_idx = window_df['最高'].idxmax()
        max_price = float(window_df.loc[max_price_idx, '最高'])
        max_price_date = window_df.loc[max_price_idx, '日期']
        
        # 计算涨幅（使用最高价）
        gain = (max_price - start_price) / start_price * 100
        
        if gain > max_gain:
            max_gain = gain
            max_gain_start_idx = start_idx
            max_gain_end_idx = weekly_df.index.get_loc(max_price_idx)
            max_gain_start_price = start_price
            max_gain_end_price = max_price
            max_gain_start_date = start_date
            max_gain_end_date = max_price_date
    
    # 计算实际周数
    if max_gain_start_idx is not None and max_gain_end_idx is not None:
        trading_weeks = int(max_gain_end_idx - max_gain_start_idx + 1)
        
        # 格式化日期
        if isinstance(max_gain_start_date, pd.Timestamp):
            start_date_str = max_gain_start_date.strftime('%Y-%m-%d')
        else:
            start_date_str = str(max_gain_start_date)
        
        if isinstance(max_gain_end_date, pd.Timestamp):
            end_date_str = max_gain_end_date.strftime('%Y-%m-%d')
        else:
            end_date_str = str(max_gain_end_date)
        
        print(f"\n📊 涨幅最大区间:")
        print(f"   起点日期: {start_date_str}")
        print(f"   起点价格: {max_gain_start_price:.2f} 元")
        print(f"   终点日期: {end_date_str}")
        print(f"   终点价格: {max_gain_end_price:.2f} 元")
        print(f"   涨幅: {max_gain:.2f}% (翻{max_gain/100:.2f}倍)")
        print(f"   实际周数: {trading_weeks} 周")
        
        # 判断是否符合大牛股要求（涨幅超过100%）
        if max_gain >= 100.0:
            print(f"\n✅ {stock_code} 符合大牛股要求！")
            print(f"   在 {trading_weeks} 周内涨幅达到 {max_gain:.2f}%，超过100%的要求")
            return True
        else:
            print(f"\n❌ {stock_code} 不符合大牛股要求")
            print(f"   最大涨幅仅为 {max_gain:.2f}%，未达到100%的要求")
            return False
    else:
        print(f"\n❌ {stock_code} 未找到有效的涨幅区间")
        return False


if __name__ == '__main__':
    # 用户提供的大牛股代码
    stock_codes = ['000592', '002104', '002759', '002969', '300436']
    
    print("="*80)
    print("检查大牛股是否符合要求（一个月内涨幅超过100%）")
    print("="*80)
    
    results = {}
    for code in stock_codes:
        try:
            is_bull = check_bull_stock(code)
            results[code] = is_bull
        except Exception as e:
            import traceback
            print(f"\n❌ 检查 {code} 时出错: {str(e)}")
            print(f"错误详情: {traceback.format_exc()}")
            results[code] = False
    
    # 汇总结果
    print("\n" + "="*80)
    print("检查结果汇总:")
    print("="*80)
    
    valid_bull_stocks = []
    invalid_bull_stocks = []
    
    for code, is_bull in results.items():
        if is_bull:
            valid_bull_stocks.append(code)
            print(f"✅ {code}: 符合大牛股要求")
        else:
            invalid_bull_stocks.append(code)
            print(f"❌ {code}: 不符合大牛股要求")
    
    print(f"\n符合要求的股票: {len(valid_bull_stocks)} 只")
    print(f"不符合要求的股票: {len(invalid_bull_stocks)} 只")
    
    if invalid_bull_stocks:
        print(f"\n⚠️ 以下股票不符合大牛股要求: {', '.join(invalid_bull_stocks)}")
        print("   大牛股定义：在一个月内（约4-5周）涨幅必须超过100%（翻倍）")






