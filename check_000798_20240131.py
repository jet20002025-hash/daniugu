#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查中水渔业(000798)在2024-01-31的匹配度和均线方向
"""
import sys
import pandas as pd
from datetime import datetime

sys.path.insert(0, '.')
from bull_stock_analyzer import BullStockAnalyzer

code = '000798'
name = '中水渔业'
scan_date = '2024-01-31'

print("=" * 80)
print(f"检查 {name}({code}) 在 {scan_date} 的情况")
print("=" * 80)
print()

analyzer = BullStockAnalyzer(auto_load_default_stocks=False, auto_analyze_and_train=False)

# 加载模型
model_path = 'trained_model.json'
print(f"加载模型: {model_path}")
analyzer.load_model(model_path)
print(f"✅ 模型加载成功")
print()

# 获取日K线数据（直接从本地缓存读取）
print("获取日K线数据...")
import os
cache_path = f'cache/daily_kline/{code}.csv'
if not os.path.exists(cache_path):
    print(f"❌ 本地缓存不存在: {cache_path}")
    sys.exit(1)

daily_df = pd.read_csv(cache_path, encoding='utf-8-sig')
daily_df['日期'] = pd.to_datetime(daily_df['日期'], errors='coerce')
daily_df = daily_df.dropna(subset=['日期']).sort_values('日期').reset_index(drop=True)
print(f"✅ 读取本地数据: {len(daily_df)} 条，日期范围: {daily_df.iloc[0]['日期']} 至 {daily_df.iloc[-1]['日期']}")

# 找到扫描日期
scan_dt = pd.to_datetime(scan_date)
if scan_dt not in daily_df['日期'].values:
    print(f"❌ 未找到 {scan_date} 的数据")
    # 找最近的交易日
    before = daily_df[daily_df['日期'] <= scan_dt]
    if len(before) == 0:
        print("❌ 没有该日期之前的数据")
        sys.exit(1)
    scan_dt = before['日期'].iloc[-1]
    print(f"⚠️ 使用最近的交易日: {scan_dt.strftime('%Y-%m-%d')}")

scan_idx = daily_df[daily_df['日期'] == scan_dt].index[0]
print(f"✅ 找到数据，索引: {scan_idx}")
print()

# 计算120日和250日均线
print("计算均线...")
if scan_idx < 250:
    print("❌ 数据不足，无法计算250日均线")
    sys.exit(1)

# 计算均线值
ma120_current = daily_df['收盘'].iloc[scan_idx-119:scan_idx+1].mean()
ma250_current = daily_df['收盘'].iloc[scan_idx-249:scan_idx+1].mean()

# 计算均线方向（向前看20天，计算斜率）
if scan_idx >= 20:
    ma120_20d_ago = daily_df['收盘'].iloc[scan_idx-139:scan_idx-119].mean()
    ma250_20d_ago = daily_df['收盘'].iloc[scan_idx-269:scan_idx-249].mean()
    
    ma120_slope = (ma120_current - ma120_20d_ago) / ma120_20d_ago * 100
    ma250_slope = (ma250_current - ma250_20d_ago) / ma250_20d_ago * 100
    
    ma120_direction = "向下" if ma120_slope < 0 else "向上"
    ma250_direction = "向下" if ma250_slope < 0 else "向上"
else:
    ma120_slope = None
    ma250_slope = None
    ma120_direction = "数据不足"
    ma250_direction = "数据不足"

print(f"MA120: {ma120_current:.2f}, 方向: {ma120_direction} (斜率: {ma120_slope:.2f}%)")
print(f"MA250: {ma250_current:.2f}, 方向: {ma250_direction} (斜率: {ma250_slope:.2f}%)")
print()

# 计算匹配度
print("计算匹配度...")
try:
    # 找到最佳买点
    result = analyzer.scan_all_stocks(
        stock_codes=[code],
        min_match_score=0.0,
        scan_date=scan_date,
        strict_local_only=True
    )
    
    if result and 'candidates' in result and len(result['candidates']) > 0:
        candidate = result['candidates'][0]
        match_score = candidate.get('match_score', 0)
        buy_date = candidate.get('buy_date', '')
        buy_price = candidate.get('buy_price', 0)
        
        print(f"✅ 匹配度: {match_score:.4f}")
        print(f"最佳买点日期: {buy_date}")
        print(f"最佳买点价格: {buy_price:.2f}")
    else:
        print("❌ 未找到匹配的买点")
        match_score = 0
except Exception as e:
    print(f"❌ 计算匹配度失败: {e}")
    import traceback
    traceback.print_exc()
    match_score = 0

print()
print("=" * 80)
print("总结")
print("=" * 80)
print(f"股票: {name}({code})")
print(f"日期: {scan_date}")
print(f"MA120方向: {ma120_direction}")
print(f"MA250方向: {ma250_direction}")
print(f"匹配度: {match_score:.4f}")
if ma120_direction == "向下" and ma250_direction == "向下":
    print("⚠️ 警告: 120日均线和250日均线都向下，应该被排除！")
print()
