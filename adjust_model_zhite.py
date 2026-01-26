#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
微调模型：提高志特新材匹配度，降低畅联股份匹配度
采用更激进的调整策略（50%向志特靠拢）
"""
import sys
sys.path.insert(0, '.')
from bull_stock_analyzer import BullStockAnalyzer
import pandas as pd
import json

analyzer = BullStockAnalyzer(auto_load_default_stocks=False, auto_analyze_and_train=False)
analyzer.load_model('trained_model.json')
common_features = analyzer._get_common_features()

stock1_code = '300986'  # 志特新材（大牛股）
stock2_code = '603648'  # 畅联股份（一般）
scan_date = '2026-01-04'

# 获取数据
weekly_df1 = analyzer.fetcher.get_weekly_kline(stock1_code, period='2y', use_cache=True, local_only=True)
weekly_df2 = analyzer.fetcher.get_weekly_kline(stock2_code, period='2y', use_cache=True, local_only=True)
if weekly_df1 is None or len(weekly_df1) < 40 or weekly_df2 is None or len(weekly_df2) < 40:
    print('数据不足')
    sys.exit(1)

scan_ts = pd.to_datetime(scan_date)
weekly_df1['日期'] = pd.to_datetime(weekly_df1['日期'], errors='coerce')
weekly_df2['日期'] = pd.to_datetime(weekly_df2['日期'], errors='coerce')
weekly_df1 = weekly_df1[weekly_df1['日期'] <= scan_ts].sort_values('日期').reset_index(drop=True)
weekly_df2 = weekly_df2[weekly_df2['日期'] <= scan_ts].sort_values('日期').reset_index(drop=True)
idx1, idx2 = len(weekly_df1) - 1, len(weekly_df2) - 1

features1 = analyzer.extract_features_at_start_point(stock1_code, idx1, lookback_weeks=40, weekly_df=weekly_df1)
features2 = analyzer.extract_features_at_start_point(stock2_code, idx2, lookback_weeks=40, weekly_df=weekly_df2)
if features1 is None or features2 is None:
    print('特征提取失败')
    sys.exit(1)

match1_original = analyzer._calculate_match_score(features1, common_features, tolerance=0.3)
match2_original = analyzer._calculate_match_score(features2, common_features, tolerance=0.3)

print('=' * 80)
print('微调模型：提高志特新材匹配度，降低畅联股份匹配度')
print('=' * 80)
print()
print(f'志特新材原始匹配度: {match1_original["总匹配度"]:.4f}')
print(f'畅联股份原始匹配度: {match2_original["总匹配度"]:.4f}')
print(f'差距: {(match1_original["总匹配度"] - match2_original["总匹配度"])*100:.2f}%')
print()

# 读取原模型
with open('trained_model.json', 'r', encoding='utf-8') as f:
    model_data = json.load(f)

print('=' * 80)
print('微调策略：针对关键特征做更激进调整（50%向志特新材靠拢）')
print('=' * 80)
print()

# 微调策略：针对畅联优于志特的特征，将目标中位数向志特靠拢（50%）
adjustments = []

# 核心特征：价格相对位置、OBV趋势、RSI、价格相对MA20
key_core_features = [
    ('价格相对位置', 0.5),
    ('OBV趋势', 0.5),
    ('RSI', 0.5),
    ('价格相对MA20', 0.5),
]

for feature_name, adjust_ratio in key_core_features:
    if feature_name not in common_features or feature_name not in features1:
        continue
    
    val1 = features1.get(feature_name, 0)
    stats = common_features[feature_name]
    old_median = stats.get('中位数', stats.get('均值', 0))
    
    # 50%向志特新材靠拢
    new_median = old_median * (1 - adjust_ratio) + val1 * adjust_ratio
    
    if feature_name in model_data.get('buy_features', {}).get('common_features', {}):
        adjustments.append({
            'feature': feature_name,
            'old_median': old_median,
            'new_median': new_median,
            'stock1_val': val1,
            'adjust_ratio': adjust_ratio,
            'type': '核心特征'
        })

# 非核心特征：KDJ系列、价格相对MA40、MACD（30%调整）
key_noncore_features = [
    ('KDJ超卖', 0.3),
    ('KDJ_K', 0.3),
    ('KDJ_D', 0.3),
    ('KDJ_J', 0.3),
    ('价格相对MA40', 0.3),
    ('MACD_DEA', 0.3),
    ('MACD_DIF', 0.3),
]

for feature_name, adjust_ratio in key_noncore_features:
    if feature_name not in common_features or feature_name not in features1:
        continue
    
    val1 = features1.get(feature_name, 0)
    stats = common_features[feature_name]
    old_median = stats.get('中位数', stats.get('均值', 0))
    
    # 30%向志特新材靠拢
    new_median = old_median * (1 - adjust_ratio) + val1 * adjust_ratio
    
    if feature_name in model_data.get('buy_features', {}).get('common_features', {}):
        adjustments.append({
            'feature': feature_name,
            'old_median': old_median,
            'new_median': new_median,
            'stock1_val': val1,
            'adjust_ratio': adjust_ratio,
            'type': '非核心特征'
        })

if adjustments:
    print('调整的特征：')
    for adj in adjustments:
        print(f"  {adj['feature']} ({adj['type']}):")
        print(f"    {adj['old_median']:.2f} -> {adj['new_median']:.2f} (志特值: {adj['stock1_val']:.2f}, 调整比例: {adj['adjust_ratio']*100:.0f}%)")
    print()
    
    # 应用调整
    adjusted_count = 0
    for adj in adjustments:
        feature_name = adj['feature']
        if feature_name in model_data.get('buy_features', {}).get('common_features', {}):
            model_data['buy_features']['common_features'][feature_name]['中位数'] = round(adj['new_median'], 2)
            adjusted_count += 1
    
    # 保存微调后的模型（文件名包含"志特"）
    output_file = 'trained_model_志特.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(model_data, f, ensure_ascii=False, indent=2)
    
    print(f'✅ 已保存微调后的模型到: {output_file}')
    print(f'   共调整了 {adjusted_count} 个特征')
    
    # 验证微调后的匹配度（重新加载模型）
    print()
    print('=' * 80)
    print('验证微调后的匹配度')
    print('=' * 80)
    
    # 重新创建analyzer实例以确保加载新模型
    analyzer_new = BullStockAnalyzer(auto_load_default_stocks=False, auto_analyze_and_train=False)
    analyzer_new.load_model(output_file)
    common_features_adjusted = analyzer_new._get_common_features()
    
    match1_adjusted = analyzer_new._calculate_match_score(features1, common_features_adjusted, tolerance=0.3)
    match2_adjusted = analyzer_new._calculate_match_score(features2, common_features_adjusted, tolerance=0.3)
    
    print(f'志特新材原匹配度: {match1_original["总匹配度"]:.4f}')
    print(f'志特新材微调后匹配度: {match1_adjusted["总匹配度"]:.4f}')
    print(f'志特新材提升: {(match1_adjusted["总匹配度"] - match1_original["总匹配度"])*100:.2f}%')
    print()
    print(f'畅联股份原匹配度: {match2_original["总匹配度"]:.4f}')
    print(f'畅联股份微调后匹配度: {match2_adjusted["总匹配度"]:.4f}')
    print(f'畅联股份变化: {(match2_adjusted["总匹配度"] - match2_original["总匹配度"])*100:.2f}%')
    print()
    print(f'匹配度差距变化:')
    print(f'  原差距: {(match1_original["总匹配度"] - match2_original["总匹配度"])*100:.2f}%')
    print(f'  新差距: {(match1_adjusted["总匹配度"] - match2_adjusted["总匹配度"])*100:.2f}%')
    print(f'  差距扩大: {((match1_adjusted["总匹配度"] - match2_adjusted["总匹配度"]) - (match1_original["总匹配度"] - match2_original["总匹配度"]))*100:.2f}%')
    
    # 显示核心特征匹配度的变化
    print()
    print('核心特征匹配度变化（志特新材）：')
    for adj in adjustments:
        if adj['type'] == '核心特征':
            feature_name = adj['feature']
            old_match = match1_original.get('核心特征匹配', {}).get(feature_name, 0)
            new_match = match1_adjusted.get('核心特征匹配', {}).get(feature_name, 0)
            change = new_match - old_match
            if abs(change) > 0.001:
                print(f"  {feature_name}: {old_match:.3f} -> {new_match:.3f} ({change:+.3f})")
    
    print()
    print('核心特征匹配度变化（畅联股份）：')
    for adj in adjustments:
        if adj['type'] == '核心特征':
            feature_name = adj['feature']
            old_match = match2_original.get('核心特征匹配', {}).get(feature_name, 0)
            new_match = match2_adjusted.get('核心特征匹配', {}).get(feature_name, 0)
            change = new_match - old_match
            if abs(change) > 0.001:
                print(f"  {feature_name}: {old_match:.3f} -> {new_match:.3f} ({change:+.3f})")
else:
    print('未找到需要调整的特征')
