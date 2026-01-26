#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
对比志特新材和畅联股份的特征差异，微调模型
目标：提高志特新材匹配度，降低畅联股份匹配度
采用更激进的调整策略
"""
import sys
sys.path.insert(0, '.')
from bull_stock_analyzer import BullStockAnalyzer
import pandas as pd
import json
import math

# 加载模型
analyzer = BullStockAnalyzer(auto_load_default_stocks=False, auto_analyze_and_train=False)
analyzer.load_model('trained_model.json')

# 获取共同特征
common_features = analyzer._get_common_features()

# 两只股票代码
stock1_code = '300986'  # 志特新材（大牛股）
stock2_code = '603648'  # 畅联股份（一般）
scan_date = '2026-01-04'

print('=' * 80)
print('对比志特新材（大牛股）和畅联股份（一般）的特征差异')
print('=' * 80)
print()

# 获取周K线数据
weekly_df1 = analyzer.fetcher.get_weekly_kline(stock1_code, period='2y', use_cache=True, local_only=True)
weekly_df2 = analyzer.fetcher.get_weekly_kline(stock2_code, period='2y', use_cache=True, local_only=True)

if weekly_df1 is None or len(weekly_df1) < 40:
    print(f'❌ {stock1_code} 志特新材数据不足')
    sys.exit(1)
if weekly_df2 is None or len(weekly_df2) < 40:
    print(f'❌ {stock2_code} 畅联股份数据不足')
    sys.exit(1)

# 找到扫描日期对应的索引
scan_ts = pd.to_datetime(scan_date)
weekly_df1['日期'] = pd.to_datetime(weekly_df1['日期'], errors='coerce')
weekly_df2['日期'] = pd.to_datetime(weekly_df2['日期'], errors='coerce')

weekly_df1 = weekly_df1[weekly_df1['日期'] <= scan_ts].sort_values('日期').reset_index(drop=True)
weekly_df2 = weekly_df2[weekly_df2['日期'] <= scan_ts].sort_values('日期').reset_index(drop=True)

if len(weekly_df1) < 40 or len(weekly_df2) < 40:
    print(f'❌ 数据不足（需要至少40周）')
    sys.exit(1)

idx1 = len(weekly_df1) - 1
idx2 = len(weekly_df2) - 1

# 提取特征
features1 = analyzer.extract_features_at_start_point(stock1_code, idx1, lookback_weeks=40, weekly_df=weekly_df1)
features2 = analyzer.extract_features_at_start_point(stock2_code, idx2, lookback_weeks=40, weekly_df=weekly_df2)

if features1 is None or features2 is None:
    print('❌ 特征提取失败')
    sys.exit(1)

# 计算原始匹配度
match1_original = analyzer._calculate_match_score(features1, common_features, tolerance=0.3)
match2_original = analyzer._calculate_match_score(features2, common_features, tolerance=0.3)

print(f'志特新材原始匹配度: {match1_original["总匹配度"]:.4f}')
print(f'畅联股份原始匹配度: {match2_original["总匹配度"]:.4f}')
print(f'差距: {(match1_original["总匹配度"] - match2_original["总匹配度"])*100:.2f}%')
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
print('核心特征详细对比')
print('=' * 80)
print()

# 详细分析每个核心特征
core_analysis = []
for feature_name in core_features:
    if feature_name not in common_features or feature_name not in features1 or feature_name not in features2:
        continue
    
    val1 = features1.get(feature_name, 0)
    val2 = features2.get(feature_name, 0)
    stats = common_features[feature_name]
    
    median = stats.get('中位数', stats.get('median', 0))
    std = stats.get('标准差', stats.get('std', 0))
    
    # 获取匹配度
    match1_detail = match1_original.get('核心特征匹配', {}).get(feature_name, 0)
    match2_detail = match2_original.get('核心特征匹配', {}).get(feature_name, 0)
    
    # 计算Z值
    z1 = abs((val1 - median) / std) if std > 0 else 0
    z2 = abs((val2 - median) / std) if std > 0 else 0
    
    # 计算如果目标中位数调整为志特新材的值，新匹配度会是多少
    new_median1 = val1
    new_z1 = 0
    new_score1 = math.exp(-0.4 * new_z1 * new_z1)
    if stats.get('最小值', 0) <= val1 <= stats.get('最大值', 0):
        new_score1 = max(new_score1, 0.6)
    
    # 计算如果目标中位数调整为志特新材的值，畅联股份的新匹配度
    new_z2 = abs((val2 - new_median1) / std) if std > 0 else 0
    new_score2 = math.exp(-0.4 * new_z2 * new_z2)
    if stats.get('最小值', 0) <= val2 <= stats.get('最大值', 0):
        new_score2 = max(new_score2, 0.6)
    
    core_analysis.append({
        'feature': feature_name,
        'target_median': median,
        'target_std': std,
        'stock1_val': val1,  # 志特新材
        'stock2_val': val2,  # 畅联股份
        'stock1_match': match1_detail,
        'stock2_match': match2_detail,
        'stock1_z': z1,
        'stock2_z': z2,
        'match_gap': match1_detail - match2_detail,
        'new_median': new_median1,
        'new_stock1_match': new_score1,
        'new_stock2_match': new_score2,
        'stock1_improvement': new_score1 - match1_detail,
        'stock2_change': new_score2 - match2_detail,
    })

# 按匹配度提升潜力排序
core_analysis.sort(key=lambda x: x['stock1_improvement'] - x['stock2_change'], reverse=True)

print(f"{'特征名称':<25} {'目标中位':>10} {'志特值':>10} {'畅联值':>10} {'志匹配':>8} {'畅匹配':>8} {'新志匹配':>8} {'新畅匹配':>8} {'提升潜力':>8}")
print('-' * 110)

for d in core_analysis:
    improvement = d['stock1_improvement'] - d['stock2_change']
    print(f"{d['feature']:<25} {d['target_median']:>10.2f} {d['stock1_val']:>10.2f} {d['stock2_val']:>10.2f} {d['stock1_match']:>8.3f} {d['stock2_match']:>8.3f} {d['new_stock1_match']:>8.3f} {d['new_stock2_match']:>8.3f} {improvement:>8.3f}")

print()
print('=' * 80)
print('微调策略：选择提升潜力最大的特征')
print('=' * 80)
print()

# 选择提升潜力最大的特征进行调整
# 提升潜力 = 志特新材匹配度提升 - 畅联股份匹配度变化（我们希望这个值越大越好）
top_features = sorted(core_analysis, key=lambda x: x['stock1_improvement'] - x['stock2_change'], reverse=True)[:5]

print('选择调整的特征（提升潜力最大）：')
adjustments = []
for d in top_features:
    if d['stock1_improvement'] > 0.01:  # 至少能提升0.01
        old_median = d['target_median']
        # 80%向志特新材靠拢（更激进）
        new_median = old_median * 0.2 + d['stock1_val'] * 0.8
        
        adjustments.append({
            'feature': d['feature'],
            'old_median': old_median,
            'new_median': new_median,
            'stock1_val': d['stock1_val'],
            'stock2_val': d['stock2_val'],
            'stock1_improvement': d['stock1_improvement'],
            'stock2_change': d['stock2_change'],
            'net_improvement': d['stock1_improvement'] - d['stock2_change'],
        })
        
        print(f"  {d['feature']}: {old_median:.2f} -> {new_median:.2f}")
        print(f"    志特值: {d['stock1_val']:.2f}, 畅联值: {d['stock2_val']:.2f}")
        print(f"    志特提升: {d['stock1_improvement']:.3f}, 畅联变化: {d['stock2_change']:.3f}")
        print(f"    净提升: {d['stock1_improvement'] - d['stock2_change']:.3f}")
        print()

if adjustments:
    # 读取原模型
    with open('trained_model.json', 'r', encoding='utf-8') as f:
        model_data = json.load(f)
    
    # 应用调整
    adjusted_count = 0
    for adj in adjustments:
        feature_name = adj['feature']
        if feature_name in model_data.get('buy_features', {}).get('common_features', {}):
            model_data['buy_features']['common_features'][feature_name]['median'] = round(adj['new_median'], 2)
            adjusted_count += 1
    
    # 保存微调后的模型（文件名包含"志特"）
    output_file = 'trained_model_志特.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(model_data, f, ensure_ascii=False, indent=2)
    
    print(f'✅ 已保存微调后的模型到: {output_file}')
    print(f'   共调整了 {adjusted_count} 个特征')
    
    # 验证微调后的匹配度
    print()
    print('=' * 80)
    print('验证微调后的匹配度')
    print('=' * 80)
    
    analyzer.load_model(output_file)
    common_features_adjusted = analyzer._get_common_features()
    match1_adjusted = analyzer._calculate_match_score(features1, common_features_adjusted, tolerance=0.3)
    match2_adjusted = analyzer._calculate_match_score(features2, common_features_adjusted, tolerance=0.3)
    
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
        feature_name = adj['feature']
        old_match = match1_original.get('核心特征匹配', {}).get(feature_name, 0)
        new_match = match1_adjusted.get('核心特征匹配', {}).get(feature_name, 0)
        change = new_match - old_match
        if abs(change) > 0.001:
            print(f"  {feature_name}: {old_match:.3f} -> {new_match:.3f} ({change:+.3f})")
    
    print()
    print('核心特征匹配度变化（畅联股份）：')
    for adj in adjustments:
        feature_name = adj['feature']
        old_match = match2_original.get('核心特征匹配', {}).get(feature_name, 0)
        new_match = match2_adjusted.get('核心特征匹配', {}).get(feature_name, 0)
        change = new_match - old_match
        if abs(change) > 0.001:
            print(f"  {feature_name}: {old_match:.3f} -> {new_match:.3f} ({change:+.3f})")
else:
    print('未找到需要调整的特征')
