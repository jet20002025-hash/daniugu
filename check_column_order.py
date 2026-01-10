#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查akshare返回的列顺序
"""
import akshare as ak
import pandas as pd
from datetime import datetime, timedelta

print("=" * 90)
print("检查akshare返回的列顺序（根据2025-12-31的正确数据）")
print("=" * 90)
print("正确数据：开盘=4.66, 收盘=4.65, 最高=4.68, 最低=4.62")
print("=" * 90)

try:
    end_date = datetime.now().strftime('%Y%m%d')
    start_date = (datetime.now() - timedelta(days=30)).strftime('%Y%m%d')
    
    df = ak.stock_zh_a_hist(symbol='000002', period="daily", 
                            start_date=start_date, end_date=end_date, adjust="qfq")
    
    if df is None or df.empty:
        print("❌ 无法获取数据")
    else:
        print(f"✅ 获取到 {len(df)} 条数据")
        print(f"\n列名: {list(df.columns)}")
        
        # 获取2025-12-31的数据
        date_col = df.columns[0]
        df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
        target_date = pd.to_datetime('2025-12-31')
        row = df[df[date_col] == target_date]
        
        if len(row) > 0:
            row = row.iloc[0]
            print(f"\n2025-12-31的原始数据（按列位置）：")
            for i in range(min(6, len(row))):
                print(f"列{i} ({df.columns[i] if i < len(df.columns) else 'N/A'}): {row.iloc[i]}")
            
            # 查找每个值的位置
            values = [float(row.iloc[i]) for i in range(1, min(6, len(row)))]
            print(f"\n列1-5的数值: {values}")
            
            # 查找正确值的位置
            correct_values = {
                '开盘': 4.66,
                '收盘': 4.65,
                '最高': 4.68,
                '最低': 4.62
            }
            
            print(f"\n值的位置映射：")
            for name, target_val in correct_values.items():
                # 查找最接近的值（允许0.01的误差）
                matches = [(i+1, v) for i, v in enumerate(values) if abs(v - target_val) < 0.01]
                if matches:
                    for idx, val in matches:
                        print(f"{name} ({target_val}) -> 列{idx} (值={val})")
                else:
                    print(f"{name} ({target_val}) -> 未找到匹配")
            
            # 推断列顺序
            print(f"\n推断的列顺序：")
            # 根据值匹配推断
            col_mapping = {}
            for name, target_val in correct_values.items():
                for i, v in enumerate(values):
                    if abs(v - target_val) < 0.01:
                        col_mapping[name] = i + 1  # +1因为列0是日期
                        break
            
            print(f"列映射: {col_mapping}")
            
        else:
            print("未找到2025-12-31的数据，显示最近的数据：")
            df = df.sort_values(date_col, ascending=False)
            print(df.head(3))
        
except Exception as e:
    print(f"❌ 错误: {e}")
    import traceback
    traceback.print_exc()








