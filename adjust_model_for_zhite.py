#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
微调模型以提高志特新材的匹配度
"""
import sys
sys.path.insert(0, '.')
from bull_stock_analyzer import BullStockAnalyzer
import pandas as pd
import json

# 加载模型
analyzer = BullStockAnalyzer(auto_load_default_stocks=False, auto_analyze_and_train=False)
analyzer.load_model('trained_model.json')

# 获取共同特征
common_features = analyzer._get_common_features()

# 志特新材代码
stock_code = '300986'
scan_date = '2026-01-04'

print('=' * 80)
print('微调模型以提高志特新材的匹配度')
print('=' * 80)
print()

# 获取周K线数据
weekly_df = analyzer.fetcher.get_weekly_kline(stock_code, period='2y', use_cache=True, local_only=True)

if weekly_df is None or len(weekly_df) < 40:
    print(f'❌ {stock_code} 数据不足')
    sys.exit(1)

# 找到扫描日期对应的索引
scan_ts = pd.to_datetime(scan_date)
weekly_df['日期'] = pd.to_datetime(weekly_df['日期'], errors='coerce')
weekly_df = weekly_df[weekly_df['日期'] <= scan_ts].sort_values('日期').reset_index(drop=True)

if len(weekly_df) < 40:
    print(f'❌ 数据不足（需要至少40周）')
    sys.exit(1)

idx = len(weekly_df) - 1

# 提取特征
features = analyzer.extract_features_at_start_point(stock_code, idx, lookback_weeks=40, weekly_df=weekly_df)

if features is None:
    print('❌ 特征提取失败')
    sys.exit(1)

# 计算原始匹配度
match_original = analyzer._calculate_match_score(features, common_features, tolerance=0.3)
print(f'志特新材原始匹配度: {match_original["总匹配度"]:.4f}')
print()

# 核心特征列表
core_features = [
    '起点当周量比',
    '价格相对位置',
    '成交量萎缩程度',
    '价格相对MA20',
    '起点前20周波动率',
    '是否跌破最大量最低价',
    '均线多头排列',
    'MACD零轴上方',
    'RSI',
    '均线粘合度',
    '布林带宽度',
    'OBV趋势',
    '买点前两月内曾涨停',
]

print('=' * 80)
print('分析志特新材的核心特征值')
print('=' * 80)
print()

# 找出志特新材与目标差距最大的核心特征
gaps = []
for feature_name in core_features:
    if feature_name not in common_features or feature_name not in features:
        continue
    
    val = features.get(feature_name, 0)
    stats = common_features[feature_name]
    median = stats.get('中位数', stats.get('median', 0))
    mean = stats.get('均值', stats.get('mean', 0))
    std = stats.get('标准差', stats.get('std', 0))
    
    # 计算Z值
    z_score = abs((val - median) / std) if std > 0 else 0
    
    # 获取匹配度
    match_detail = match_original.get('核心特征匹配', {}).get(feature_name, 0)
    
    gaps.append({
        'feature': feature_name,
        'value': val,
        'target_median': median,
        'z_score': z_score,
        'match_score': match_detail,
    })

# 按Z值排序
gaps.sort(key=lambda x: x['z_score'], reverse=True)

print(f"{'特征名称':<25} {'志特值':>12} {'目标中位':>12} {'Z值':>8} {'匹配度':>8}")
print('-' * 70)
for d in gaps:
    print(f"{d['feature']:<25} {d['value']:>12.2f} {d['target_median']:>12.2f} {d['z_score']:>8.2f} {d['match_score']:>8.3f}")

print()
print('=' * 80)
print('微调策略：向志特新材的值靠拢（50%调整）')
print('=' * 80)
print()

# 读取原模型
with open('trained_model.json', 'r', encoding='utf-8') as f:
    model_data = json.load(f)

# 对Z值大于0.5的核心特征进行调整
adjustments = []
for d in gaps:
    if d['z_score'] > 0.5 and d['match_score'] < 0.95:
        old_median = d['target_median']
        # 50%向志特新材靠拢
        new_median = old_median * 0.5 + d['value'] * 0.5
        
        feature_name = d['feature']
        if feature_name in model_data.get('buy_features', {}).get('common_features', {}):
            adjustments.append({
                'feature': feature_name,
                'old_median': old_median,
                'new_median': new_median,
                'value': d['value'],
                'z_score': d['z_score'],
            })
            print(f"  {feature_name}: {old_median:.2f} -> {new_median:.2f} (志特值: {d['value']:.2f}, Z值: {d['z_score']:.2f})")

if adjustments:
    # 应用调整
    adjusted_count = 0
    for adj in adjustments:
        feature_name = adj['feature']
        if feature_name in model_data.get('buy_features', {}).get('common_features', {}):
            model_data['buy_features']['common_features'][feature_name]['median'] = round(adj['new_median'], 2)
            adjusted_count += 1
    
    # 保存微调后的模型
    output_file = 'trained_model_zhite_adjusted.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(model_data, f, ensure_ascii=False, indent=2)
    
    print()
    print(f'✅ 已保存微调后的模型到: {output_file}')
    print(f'   共调整了 {adjusted_count} 个特征')
    
    # 验证微调后的匹配度
    print()
    print('=' * 80)
    print('验证微调后的匹配度')
    print('=' * 80)
    
    analyzer.load_model(output_file)
    common_features_adjusted = analyzer._get_common_features()
    match_adjusted = analyzer._calculate_match_score(features, common_features_adjusted, tolerance=0.3)
    
    print(f'志特新材原匹配度: {match_original["总匹配度"]:.4f}')
    print(f'志特新材微调后匹配度: {match_adjusted["总匹配度"]:.4f}')
    print(f'提升: {(match_adjusted["总匹配度"] - match_original["总匹配度"])*100:.2f}%')
    
    # 显示核心特征匹配度的变化
    print()
    print('核心特征匹配度变化：')
    for adj in adjustments:
        feature_name = adj['feature']
        old_match = match_original.get('核心特征匹配', {}).get(feature_name, 0)
        new_match = match_adjusted.get('核心特征匹配', {}).get(feature_name, 0)
        change = new_match - old_match
        print(f"  {feature_name}: {old_match:.3f} -> {new_match:.3f} ({change:+.3f})")
else:
    print('未找到需要调整的特征')
