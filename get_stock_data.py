#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
获取指定股票的K线数据
"""
from data_fetcher import DataFetcher
import pandas as pd

def get_recent_kline(stock_code, days=5):
    """获取最近N天的K线数据"""
    fetcher = DataFetcher()
    
    print(f"正在获取 {stock_code} 的最近 {days} 天K线数据...")
    
    # 获取日K线数据
    df = fetcher.get_daily_kline(stock_code, period="1y")
    
    if df is None or df.empty:
        print(f"无法获取 {stock_code} 的K线数据")
        return None
    
    # 输出原始列名和数据示例用于调试
    print(f"\n原始列名: {list(df.columns)}")
    print(f"数据条数: {len(df)}")
    if len(df) > 0:
        print(f"\n前3条原始数据:")
        print(df.head(3))
    
    # 确保日期列是datetime类型
    if '日期' in df.columns:
        df['日期'] = pd.to_datetime(df['日期'])
        df = df.sort_values('日期', ascending=False)  # 按日期降序排列，最新的在前
    else:
        print("警告: 未找到'日期'列")
        print(f"可用列: {list(df.columns)}")
        return None
    
    # 获取最近N天
    recent_df = df.head(days)
    
    # 按日期升序排列显示
    recent_df = recent_df.sort_values('日期', ascending=True)
    
    print(f"\n{stock_code} 最近 {days} 天K线数据：")
    print("=" * 80)
    print(f"{'日期':<12} {'开盘价':<10} {'收盘价':<10} {'最高价':<10} {'最低价':<10}")
    print("-" * 80)
    
    for idx, row in recent_df.iterrows():
        date = row['日期'].strftime('%Y-%m-%d') if pd.notna(row['日期']) else 'N/A'
        
        # 确保数据是数字类型，如果不是则转换
        try:
            open_val = float(row['开盘']) if pd.notna(row['开盘']) else None
            close_val = float(row['收盘']) if pd.notna(row['收盘']) else None
            high_val = float(row['最高']) if pd.notna(row['最高']) else None
            low_val = float(row['最低']) if pd.notna(row['最低']) else None
            
            open_price = f"{open_val:.2f}" if open_val is not None else 'N/A'
            close_price = f"{close_val:.2f}" if close_val is not None else 'N/A'
            high_price = f"{high_val:.2f}" if high_val is not None else 'N/A'
            low_price = f"{low_val:.2f}" if low_val is not None else 'N/A'
        except (ValueError, TypeError) as e:
            # 如果转换失败，直接使用原始值
            open_price = str(row['开盘']) if pd.notna(row['开盘']) else 'N/A'
            close_price = str(row['收盘']) if pd.notna(row['收盘']) else 'N/A'
            high_price = str(row['最高']) if pd.notna(row['最高']) else 'N/A'
            low_price = str(row['最低']) if pd.notna(row['最低']) else 'N/A'
        
        print(f"{date:<12} {open_price:<10} {close_price:<10} {high_price:<10} {low_price:<10}")
    
    print("=" * 80)
    
    return recent_df

if __name__ == '__main__':
    import sys
    try:
        # 获取000002最近5天的K线数据
        stock_code = '000002'
        get_recent_kline(stock_code, days=5)
    except Exception as e:
        import traceback
        print(f"错误: {e}")
        print(traceback.format_exc())
        sys.exit(1)

