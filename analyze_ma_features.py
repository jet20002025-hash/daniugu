#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
分析多只股票的均线特征差异
"""

import sys
sys.path.insert(0, '.')
from bull_stock_analyzer import BullStockAnalyzer
import pandas as pd
import numpy as np

# 股票列表
stocks_good = [
    ('300986', '志特新材', '表现最好'),
    ('002254', '泰和新材', '表现相当好'),
    ('300599', '雄塑科技', '表现相当好'),
    ('300063', '天龙集团', '表现相当好'),
]

stocks_bad = [
    ('300205', '*ST天喻', '表现一般'),
    ('300778', '新城市', '表现一般'),
    ('002599', '盛通股份', '表现一般'),
]

scan_date = '2026-01-04'
scan_ts = pd.to_datetime(scan_date)

analyzer = BullStockAnalyzer(auto_load_default_stocks=False, auto_analyze_and_train=False)
analyzer.load_model('trained_model.json')

print('=' * 80)
print('均线特征分析（2026-01-04）')
print('=' * 80)
print()

all_features = []

for code, name, label in stocks_good + stocks_bad:
    print(f'\n【{name} ({code}) - {label}】')
    print('-' * 60)
    
    # 获取周K线数据
    weekly_df = analyzer.fetcher.get_weekly_kline(code, period='2y', use_cache=True, local_only=True)
    weekly_df['日期'] = pd.to_datetime(weekly_df['日期'], errors='coerce')
    weekly_df = weekly_df[weekly_df['日期'] <= scan_ts].sort_values('日期').reset_index(drop=True)
    
    if len(weekly_df) < 40:
        print(f'  数据不足')
        continue
    
    start_idx = len(weekly_df) - 1
    
    # 提取特征
    features = analyzer.extract_features_at_start_point(code, start_idx, lookback_weeks=40, weekly_df=weekly_df)
    if not features:
        print(f'  特征提取失败')
        continue
    
    # 获取日K线数据，计算均线
    end_dt = weekly_df.iloc[start_idx]['日期']
    end_ts = pd.to_datetime(end_dt)
    end_ymd = end_ts.strftime('%Y%m%d')
    
    daily_df = analyzer.fetcher.get_daily_kline_range(
        code, start_date='20240101', end_date=end_ymd,
        use_cache=True, local_only=True
    )
    
    ma_features = {}
    
    if daily_df is not None and len(daily_df) >= 60:
        daily_df = daily_df.copy()
        daily_df['日期'] = pd.to_datetime(daily_df['日期'], errors='coerce')
        daily_df = daily_df.dropna(subset=['日期']).sort_values('日期').reset_index(drop=True)
        daily_df = daily_df[daily_df['日期'] <= end_ts].reset_index(drop=True)
        
        close = daily_df['收盘'].astype(float)
        
        # 计算均线
        ma5 = close.rolling(5).mean()
        ma10 = close.rolling(10).mean()
        ma20 = close.rolling(20).mean()
        ma60 = close.rolling(60).mean()
        
        # 获取最后有效值
        last_idx = len(daily_df) - 1
        ma5_val = ma5.iloc[last_idx] if not pd.isna(ma5.iloc[last_idx]) else None
        ma10_val = ma10.iloc[last_idx] if not pd.isna(ma10.iloc[last_idx]) else None
        ma20_val = ma20.iloc[last_idx] if not pd.isna(ma20.iloc[last_idx]) else None
        ma60_val = ma60.iloc[last_idx] if not pd.isna(ma60.iloc[last_idx]) else None
        price = close.iloc[last_idx]
        
        # 均线排列关系
        if all(x is not None for x in [ma5_val, ma10_val, ma20_val, ma60_val]):
            # 多头排列：MA5 > MA10 > MA20 > MA60
            ma_bullish = (ma5_val > ma10_val > ma20_val > ma60_val)
            # 空头排列：MA5 < MA10 < MA20 < MA60
            ma_bearish = (ma5_val < ma10_val < ma20_val < ma60_val)
            
            # 均线间距（相对价格）
            ma5_10_gap = abs(ma5_val - ma10_val) / price * 100 if price > 0 else 0
            ma10_20_gap = abs(ma10_val - ma20_val) / price * 100 if price > 0 else 0
            ma20_60_gap = abs(ma20_val - ma60_val) / price * 100 if price > 0 else 0
            
            # 均线斜率（最近20日）
            if len(daily_df) >= 20:
                ma5_slope = (ma5.iloc[last_idx] - ma5.iloc[max(0, last_idx-20)]) / ma5.iloc[max(0, last_idx-20)] * 100 if ma5.iloc[max(0, last_idx-20)] > 0 else 0
                ma10_slope = (ma10.iloc[last_idx] - ma10.iloc[max(0, last_idx-20)]) / ma10.iloc[max(0, last_idx-20)] * 100 if ma10.iloc[max(0, last_idx-20)] > 0 else 0
                ma20_slope = (ma20.iloc[last_idx] - ma20.iloc[max(0, last_idx-20)]) / ma20.iloc[max(0, last_idx-20)] * 100 if ma20.iloc[max(0, last_idx-20)] > 0 else 0
                ma60_slope = (ma60.iloc[last_idx] - ma60.iloc[max(0, last_idx-60)]) / ma60.iloc[max(0, last_idx-60)] * 100 if ma60.iloc[max(0, last_idx-60)] > 0 else 0
            else:
                ma5_slope = ma10_slope = ma20_slope = ma60_slope = 0
            
            # 均线粘合度（标准差）
            ma_values = [ma5_val, ma10_val, ma20_val, ma60_val]
            ma_std = np.std(ma_values) / price * 100 if price > 0 else 0
            
            # 价格相对均线位置
            price_vs_ma5 = (price - ma5_val) / ma5_val * 100 if ma5_val > 0 else 0
            price_vs_ma10 = (price - ma10_val) / ma10_val * 100 if ma10_val > 0 else 0
            price_vs_ma20 = (price - ma20_val) / ma20_val * 100 if ma20_val > 0 else 0
            price_vs_ma60 = (price - ma60_val) / ma60_val * 100 if ma60_val > 0 else 0
            
            ma_features = {
                'MA5': round(ma5_val, 2),
                'MA10': round(ma10_val, 2),
                'MA20': round(ma20_val, 2),
                'MA60': round(ma60_val, 2),
                '价格': round(price, 2),
                '多头排列': 1 if ma_bullish else 0,
                '空头排列': 1 if ma_bearish else 0,
                'MA5-MA10间距%': round(ma5_10_gap, 2),
                'MA10-MA20间距%': round(ma10_20_gap, 2),
                'MA20-MA60间距%': round(ma20_60_gap, 2),
                'MA5斜率%': round(ma5_slope, 2),
                'MA10斜率%': round(ma10_slope, 2),
                'MA20斜率%': round(ma20_slope, 2),
                'MA60斜率%': round(ma60_slope, 2),
                '均线粘合度': round(ma_std, 2),
                '价格相对MA5%': round(price_vs_ma5, 2),
                '价格相对MA10%': round(price_vs_ma10, 2),
                '价格相对MA20%': round(price_vs_ma20, 2),
                '价格相对MA60%': round(price_vs_ma60, 2),
            }
            
            print(f'  价格: {price:.2f}')
            print(f'  MA5: {ma5_val:.2f}, MA10: {ma10_val:.2f}, MA20: {ma20_val:.2f}, MA60: {ma60_val:.2f}')
            print(f'  多头排列: {"是" if ma_bullish else "否"}')
            print(f'  均线间距: MA5-MA10={ma5_10_gap:.2f}%, MA10-MA20={ma10_20_gap:.2f}%, MA20-MA60={ma20_60_gap:.2f}%')
            print(f'  均线斜率(20日): MA5={ma5_slope:.2f}%, MA10={ma10_slope:.2f}%, MA20={ma20_slope:.2f}%')
            print(f'  均线斜率(60日): MA60={ma60_slope:.2f}%')
            print(f'  均线粘合度: {ma_std:.2f}%')
            print(f'  价格相对均线: MA5={price_vs_ma5:.2f}%, MA10={price_vs_ma10:.2f}%, MA20={price_vs_ma20:.2f}%, MA60={price_vs_ma60:.2f}%')
    
    # 计算匹配度
    common = analyzer._get_common_features()
    match_score = analyzer._calculate_match_score(features, common, tolerance=0.3)
    
    print(f'  当前匹配度: {match_score["总匹配度"]:.4f}')
    
    # 保存特征
    all_features.append({
        'code': code,
        'name': name,
        'label': label,
        'match_score': match_score['总匹配度'],
        'ma_features': ma_features,
        'features': features
    })

print('\n' + '=' * 80)
print('特征对比分析')
print('=' * 80)

# 计算平均值
good_ma = {}
bad_ma = {}

for item in all_features:
    ma = item['ma_features']
    if not ma:
        continue
    
    if item['label'] in ['表现最好', '表现相当好']:
        for key, val in ma.items():
            if isinstance(val, (int, float)):
                if key not in good_ma:
                    good_ma[key] = []
                good_ma[key].append(val)
    else:
        for key, val in ma.items():
            if isinstance(val, (int, float)):
                if key not in bad_ma:
                    bad_ma[key] = []
                bad_ma[key].append(val)

print('\n【表现好的股票平均值】')
for key in sorted(good_ma.keys()):
    if key in ['MA5', 'MA10', 'MA20', 'MA60', '价格']:
        continue
    avg = np.mean(good_ma[key])
    print(f'  {key}: {avg:.2f}')

print('\n【表现差的股票平均值】')
for key in sorted(bad_ma.keys()):
    if key in ['MA5', 'MA10', 'MA20', 'MA60', '价格']:
        continue
    avg = np.mean(bad_ma[key])
    print(f'  {key}: {avg:.2f}')

print('\n【差异分析】')
for key in sorted(good_ma.keys()):
    if key in ['MA5', 'MA10', 'MA20', 'MA60', '价格']:
        continue
    if key in bad_ma:
        good_avg = np.mean(good_ma[key])
        bad_avg = np.mean(bad_ma[key])
        diff = good_avg - bad_avg
        print(f'  {key}: 好={good_avg:.2f}, 差={bad_avg:.2f}, 差异={diff:.2f}')
