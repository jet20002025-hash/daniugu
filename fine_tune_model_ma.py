#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
根据均线特征差异微调模型参数
"""

import json
import sys
sys.path.insert(0, '.')
from bull_stock_analyzer import BullStockAnalyzer
import pandas as pd
import numpy as np

# 加载模型
with open('trained_model.json', 'r', encoding='utf-8') as f:
    model_data = json.load(f)

common_features = model_data.get('buy_features', {}).get('common_features', {})

# 股票列表
stocks_good = [
    ('300986', '志特新材'),
    ('002254', '泰和新材'),
    ('300599', '雄塑科技'),
    ('300063', '天龙集团'),
]

stocks_bad = [
    ('300205', '*ST天喻'),
    ('300778', '新城市'),
    ('002599', '盛通股份'),
]

scan_date = '2026-01-04'
scan_ts = pd.to_datetime(scan_date)

analyzer = BullStockAnalyzer(auto_load_default_stocks=False, auto_analyze_and_train=False)
analyzer.load_model('trained_model.json')

print('=' * 80)
print('调整模型参数')
print('=' * 80)
print()

# 提取所有股票的特征
all_features_list = []

for code, name in stocks_good + stocks_bad:
    weekly_df = analyzer.fetcher.get_weekly_kline(code, period='2y', use_cache=True, local_only=True)
    weekly_df['日期'] = pd.to_datetime(weekly_df['日期'], errors='coerce')
    weekly_df = weekly_df[weekly_df['日期'] <= scan_ts].sort_values('日期').reset_index(drop=True)
    
    if len(weekly_df) < 40:
        continue
    
    start_idx = len(weekly_df) - 1
    features = analyzer.extract_features_at_start_point(code, start_idx, lookback_weeks=40, weekly_df=weekly_df)
    
    if features:
        all_features_list.append({
            'code': code,
            'name': name,
            'is_good': (code, name) in stocks_good,
            'features': features
        })

# 分析关键特征
key_features = ['价格相对MA20', '均线粘合度', '均线平滑度']

print('【调整前匹配度】')
print('-' * 60)
common = analyzer._get_common_features()
for item in all_features_list:
    match_score = analyzer._calculate_match_score(item['features'], common, tolerance=0.3)
    label = '✅' if item['is_good'] else '❌'
    print(f'{item["name"]} ({item["code"]}) {label}: {match_score["总匹配度"]:.4f}')

# 调整参数
print('\n【参数调整】')
print('-' * 60)

# 1. 价格相对MA20：表现好的中位数-1.56，表现差的中位数1.76
# 调整策略：降低中位数和最大值，让负值或接近0的值得分更高
if '价格相对MA20' in common_features:
    current_median = common_features['价格相对MA20'].get('中位数', 4.29)
    current_min = common_features['价格相对MA20'].get('最小值', -6.9)
    current_max = common_features['价格相对MA20'].get('最大值', 54.25)
    
    # 表现好的中位数是-1.56，表现差的是1.76
    # 调整中位数为表现好的中位数附近，最大值设为表现差的中位数附近
    new_median = -1.0  # 略高于表现好的中位数，让接近0的值得分高
    new_min = current_min  # 保持最小值
    new_max = 2.0  # 略高于表现差的中位数，让大于此值的受惩罚
    
    common_features['价格相对MA20']['中位数'] = new_median
    common_features['价格相对MA20']['最大值'] = new_max
    
    print(f'价格相对MA20: 中位数 {current_median} -> {new_median}, 最大值 {current_max} -> {new_max}')

# 2. 均线粘合度：表现好的中位数5.26，表现差的中位数4.67，差异不大
# 但表现好的范围更广（4.74-10.62），表现差的更集中（4.17-10.39）
# 微调：让中等粘合度（5-6）得分更高
if '均线粘合度' in common_features:
    current_median = common_features['均线粘合度'].get('中位数', 7.56)
    current_min = common_features['均线粘合度'].get('最小值', 2.34)
    current_max = common_features['均线粘合度'].get('最大值', 25.8)
    
    # 表现好的中位数5.26，调整中位数接近这个值
    new_median = 5.5  # 略高于表现好的中位数
    new_min = current_min  # 保持最小值
    new_max = current_max  # 保持最大值
    
    common_features['均线粘合度']['中位数'] = new_median
    
    print(f'均线粘合度: 中位数 {current_median} -> {new_median}')

# 3. 均线平滑度：表现好的中位数16.00，表现差的中位数16.00，差异不大
# 但表现好的范围更广（5-17），表现差的更集中（14-17）
# 微调：让中等平滑度（15-17）得分更高
if '均线平滑度' in common_features:
    current_median = common_features['均线平滑度'].get('中位数', 18.0)
    current_min = common_features['均线平滑度'].get('最小值', 10.0)
    current_max = common_features['均线平滑度'].get('最大值', 25.0)
    
    # 表现好的中位数16.00，调整中位数接近这个值
    new_median = 16.0
    new_min = 5.0  # 表现好的最小值是5，降低最小值让5-10的也能得分
    new_max = current_max  # 保持最大值
    
    common_features['均线平滑度']['中位数'] = new_median
    common_features['均线平滑度']['最小值'] = new_min
    
    print(f'均线平滑度: 中位数 {current_median} -> {new_median}, 最小值 {current_min} -> {new_min}')

# 保存调整后的模型
output_file = 'trained_model.json'
with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(model_data, f, ensure_ascii=False, indent=2)

print(f'\n✅ 模型已保存到 {output_file}')

# 重新加载模型并验证
analyzer.load_model(output_file)
common = analyzer._get_common_features()

print('\n【调整后匹配度】')
print('-' * 60)

for item in all_features_list:
    match_score = analyzer._calculate_match_score(item['features'], common, tolerance=0.3)
    label = '✅' if item['is_good'] else '❌'
    print(f'{item["name"]} ({item["code"]}) {label}: {match_score["总匹配度"]:.4f}')

# 计算表现好的平均匹配度和表现差的平均匹配度
good_scores = [analyzer._calculate_match_score(item['features'], common, tolerance=0.3)['总匹配度'] 
               for item in all_features_list if item['is_good']]
bad_scores = [analyzer._calculate_match_score(item['features'], common, tolerance=0.3)['总匹配度'] 
              for item in all_features_list if not item['is_good']]

print(f'\n表现好的平均匹配度: {np.mean(good_scores):.4f}')
print(f'表现差的平均匹配度: {np.mean(bad_scores):.4f}')
print(f'差异: {np.mean(good_scores) - np.mean(bad_scores):.4f}')

if np.mean(good_scores) > np.mean(bad_scores):
    print('\n✅ 调整成功：表现好的股票匹配度已高于表现差的股票')
else:
    print('\n⚠️  需要进一步调整')
