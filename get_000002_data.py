#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
直接获取000002的K线数据，检查数据格式
"""
import akshare as ak
import pandas as pd
from datetime import datetime, timedelta

print("=" * 90)
print("获取000002最近5天K线数据")
print("=" * 90)

try:
    end_date = datetime.now().strftime('%Y%m%d')
    start_date = (datetime.now() - timedelta(days=30)).strftime('%Y%m%d')
    
    print(f"请求日期范围: {start_date} 到 {end_date}")
    print("正在获取数据...")
    
    df = ak.stock_zh_a_hist(symbol='000002', period="daily", 
                            start_date=start_date, end_date=end_date, adjust="qfq")
    
    if df is None or df.empty:
        print("❌ 无法获取数据")
    else:
        print(f"✅ 获取到 {len(df)} 条数据")
        print(f"\n列名: {list(df.columns)}")
        print(f"\n前5条原始数据:")
        print(df.head(5))
        
        # 按日期排序，获取最近5天
        date_col = df.columns[0]
        df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
        df = df.dropna(subset=[date_col])
        df = df.sort_values(date_col, ascending=False)
        recent = df.head(5).sort_values(date_col, ascending=True)
        
        print("\n" + "=" * 90)
        print("000002 最近5天K线数据：")
        print("=" * 90)
        print(f"{'日期':<12} {'开盘价':<12} {'收盘价':<12} {'最高价':<12} {'最低价':<12}")
        print("-" * 90)
        
        # 检查akshare返回的实际列顺序
        # 从错误数据看，可能是：日期、开盘、收盘、最低、最高（而不是最高、最低）
        # 或者需要检查列名来确定
        print(f"\n检查列名和列顺序...")
        print(f"列名: {list(df.columns)}")
        print(f"第1列（索引1）名称: {df.columns[1] if len(df.columns) > 1 else 'N/A'}")
        print(f"第2列（索引2）名称: {df.columns[2] if len(df.columns) > 2 else 'N/A'}")
        print(f"第3列（索引3）名称: {df.columns[3] if len(df.columns) > 3 else 'N/A'}")
        print(f"第4列（索引4）名称: {df.columns[4] if len(df.columns) > 4 else 'N/A'}")
        
        # akshare标准格式：日期、开盘、收盘、最高、最低、成交量...
        # 但实际可能是：日期、开盘、收盘、最低、最高、成交量...
        # 根据列名判断，或者根据数据逻辑判断
        for idx, row in recent.iterrows():
            date = row.iloc[0].strftime('%Y-%m-%d')
            
            # 使用位置索引获取数据
            # 从错误数据看，akshare返回的顺序是：日期、开盘、收盘、最低、最高（而不是最高、最低）
            open_val = row.iloc[1]  # 第2列：开盘
            close_val = row.iloc[2]  # 第3列：收盘
            low_val = row.iloc[3]  # 第4列：最低（akshare返回的是最低在前）
            high_val = row.iloc[4]  # 第5列：最高（akshare返回的是最高在后）
            
            # 转换为数字并格式化
            try:
                open_price = f"{float(open_val):.2f}"
                close_price = f"{float(close_val):.2f}"
                high_price = f"{float(high_val):.2f}"
                low_price = f"{float(low_val):.2f}"
            except (ValueError, TypeError):
                open_price = str(open_val)
                close_price = str(close_val)
                high_price = str(high_val)
                low_price = str(low_val)
            
            print(f"{date:<12} {open_price:<12} {close_price:<12} {high_price:<12} {low_price:<12}")
        
        print("=" * 90)
        
except Exception as e:
    print(f"❌ 错误: {e}")
    import traceback
    traceback.print_exc()

