#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
根据均线特征差异调整模型参数
"""

import json
import sys
sys.path.insert(0, '.')
from bull_stock_analyzer import BullStockAnalyzer
import pandas as pd
import numpy as np

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
print('提取所有股票的均线相关特征')
print('=' * 80)
print()

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
        common = analyzer._get_common_features()
        match_score = analyzer._calculate_match_score(features, common, tolerance=0.3)
        
        all_features_list.append({
            'code': code,
            'name': name,
            'is_good': (code, name) in stocks_good,
            'match_score': match_score['总匹配度'],
            'features': features
        })

# 分析均线相关特征
ma_related_features = [
    '均线多头排列',
    '均线粘合度',
    '价格相对MA20',
    '均线平滑度',
]

print('\n【均线相关特征值对比】')
print('-' * 80)

good_values = {feat: [] for feat in ma_related_features}
bad_values = {feat: [] for feat in ma_related_features}

for item in all_features_list:
    label = '✅' if item['is_good'] else '❌'
    print(f'\n{item["name"]} ({item["code"]}) {label} - 匹配度: {item["match_score"]:.4f}')
    
    for feat in ma_related_features:
        val = item['features'].get(feat)
        if val is not None:
            print(f'  {feat}: {val}')
            if item['is_good']:
                good_values[feat].append(val)
            else:
                bad_values[feat].append(val)

print('\n' + '=' * 80)
print('特征统计对比')
print('=' * 80)

for feat in ma_related_features:
    if good_values[feat] and bad_values[feat]:
        good_avg = np.mean(good_values[feat])
        bad_avg = np.mean(bad_values[feat])
        good_median = np.median(good_values[feat])
        bad_median = np.median(bad_values[feat])
        
        print(f'\n【{feat}】')
        print(f'  表现好: 平均值={good_avg:.2f}, 中位数={good_median:.2f}, 范围=[{min(good_values[feat]):.2f}, {max(good_values[feat]):.2f}]')
        print(f'  表现差: 平均值={bad_avg:.2f}, 中位数={bad_median:.2f}, 范围=[{min(bad_values[feat]):.2f}, {max(bad_values[feat]):.2f}]')
        print(f'  差异: 平均值差异={good_avg-bad_avg:.2f}, 中位数差异={good_median-bad_median:.2f}')

# 加载模型文件
with open('trained_model.json', 'r', encoding='utf-8') as f:
    model_data = json.load(f)

print('\n' + '=' * 80)
print('当前模型参数')
print('=' * 80)

common_features = model_data.get('buy_features', {}).get('common_features', {})

for feat in ma_related_features:
    if feat in common_features:
        stats = common_features[feat]
        print(f'\n【{feat}】')
        print(f'  中位数: {stats.get("中位数")}')
        print(f'  最小值: {stats.get("最小值")}')
        print(f'  最大值: {stats.get("最大值")}')
        print(f'  标准差: {stats.get("标准差")}')

print('\n' + '=' * 80)
print('调整建议')
print('=' * 80)

# 根据差异调整参数
adjustments = {}

for feat in ma_related_features:
    if good_values[feat] and bad_values[feat]:
        good_median = np.median(good_values[feat])
        bad_median = np.median(bad_values[feat])
        good_min = min(good_values[feat])
        good_max = max(good_values[feat])
        bad_min = min(bad_values[feat])
        bad_max = max(bad_values[feat])
        
        if feat in common_features:
            current_median = common_features[feat].get('中位数', 0)
            current_min = common_features[feat].get('最小值', 0)
            current_max = common_features[feat].get('最大值', 0)
            
            # 调整策略：让表现好的股票得分更高
            # 如果表现好的中位数 > 表现差的中位数，提高中位数和最小值
            # 如果表现好的中位数 < 表现差的中位数，降低中位数和最大值
            
            if good_median > bad_median:
                # 表现好的值更大，应该提高中位数和最小值，让大值得分更高
                new_median = max(good_median, current_median * 1.1)
                new_min = max(good_min * 0.9, current_min)
                new_max = max(good_max * 1.1, current_max)
            else:
                # 表现好的值更小，应该降低中位数和最大值，让小值得分更高
                new_median = min(good_median, current_median * 0.9)
                new_min = min(good_min * 0.9, current_min)
                new_max = min(bad_max * 1.1, current_max)
            
            adjustments[feat] = {
                'current': {
                    '中位数': current_median,
                    '最小值': current_min,
                    '最大值': current_max,
                },
                'new': {
                    '中位数': round(new_median, 2),
                    '最小值': round(new_min, 2),
                    '最大值': round(new_max, 2),
                },
                'good_median': good_median,
                'bad_median': bad_median,
            }

for feat, adj in adjustments.items():
    print(f'\n【{feat}】')
    print(f'  表现好中位数: {adj["good_median"]:.2f}, 表现差中位数: {adj["bad_median"]:.2f}')
    print(f'  当前: 中位数={adj["current"]["中位数"]}, 最小值={adj["current"]["最小值"]}, 最大值={adj["current"]["最大值"]}')
    print(f'  建议: 中位数={adj["new"]["中位数"]}, 最小值={adj["new"]["最小值"]}, 最大值={adj["new"]["最大值"]}')

# 保存调整建议
with open('ma_adjustment_suggestions.json', 'w', encoding='utf-8') as f:
    json.dump(adjustments, f, ensure_ascii=False, indent=2)

print('\n✅ 调整建议已保存到 ma_adjustment_suggestions.json')
