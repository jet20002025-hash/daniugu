#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
深度分析志特新材和雄塑科技的特征差异，并微调模型
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

# 获取共同特征（目标特征）
common_features = analyzer._get_common_features()

# 两只股票代码
stock1_code = '300599'  # 雄塑科技
stock2_code = '300986'  # 志特新材
scan_date = '2026-01-04'

print('=' * 80)
print('深度分析志特新材和雄塑科技的特征差异')
print('=' * 80)
print()

# 获取周K线数据
weekly_df1 = analyzer.fetcher.get_weekly_kline(stock1_code, period='2y', use_cache=True, local_only=True)
weekly_df2 = analyzer.fetcher.get_weekly_kline(stock2_code, period='2y', use_cache=True, local_only=True)

if weekly_df1 is None or len(weekly_df1) < 40:
    print(f'❌ {stock1_code} 数据不足')
    sys.exit(1)
if weekly_df2 is None or len(weekly_df2) < 40:
    print(f'❌ {stock2_code} 数据不足')
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

# 计算匹配度
match1 = analyzer._calculate_match_score(features1, common_features, tolerance=0.3)
match2 = analyzer._calculate_match_score(features2, common_features, tolerance=0.3)

print(f'雄塑科技匹配度: {match1["总匹配度"]:.4f}')
print(f'志特新材匹配度: {match2["总匹配度"]:.4f}')
print(f'差距: {(match1["总匹配度"] - match2["总匹配度"])*100:.2f}%')
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

# 详细分析每个核心特征的匹配度贡献
core_analysis = []
for feature_name in core_features:
    if feature_name not in common_features or feature_name not in features1 or feature_name not in features2:
        continue
    
    val1 = features1.get(feature_name, 0)
    val2 = features2.get(feature_name, 0)
    stats = common_features[feature_name]
    
    median = stats.get('中位数', stats.get('median', 0)) if isinstance(stats, dict) else stats
    mean = stats.get('均值', stats.get('mean', 0)) if isinstance(stats, dict) else 0
    std = stats.get('标准差', stats.get('std', 0)) if isinstance(stats, dict) else 0
    min_val = stats.get('最小值', stats.get('min', 0)) if isinstance(stats, dict) else 0
    max_val = stats.get('最大值', stats.get('max', 0)) if isinstance(stats, dict) else 0
    
    # 计算匹配度（使用与_calculate_match_score相同的逻辑）
    def calc_feature_score(val, median, mean, std, min_val, max_val):
        if std > 0:
            z_score = abs((val - median) / std)
            score = math.exp(-0.25 * z_score * z_score)
        else:
            score = 1.0 if abs(val - median) < 0.01 else 0.0
        
        # 范围内加分
        if min_val <= val <= max_val:
            score = max(score, 0.6)
        
        return score
    
    score1 = calc_feature_score(val1, median, mean, std, min_val, max_val)
    score2 = calc_feature_score(val2, median, mean, std, min_val, max_val)
    
    # 获取实际匹配度
    match1_detail = match1.get('核心特征匹配', {}).get(feature_name, 0)
    match2_detail = match2.get('核心特征匹配', {}).get(feature_name, 0)
    
    core_analysis.append({
        'feature': feature_name,
        'target_median': median,
        'target_mean': mean,
        'target_std': std,
        'stock1_val': val1,
        'stock2_val': val2,
        'stock1_score': score1,
        'stock2_score': score2,
        'stock1_match': match1_detail,
        'stock2_match': match2_detail,
        'gap': match1_detail - match2_detail,
        'stock1_z': abs((val1 - median) / std) if std > 0 else 0,
        'stock2_z': abs((val2 - median) / std) if std > 0 else 0,
    })

# 按差距排序
core_analysis.sort(key=lambda x: abs(x['gap']), reverse=True)

print(f"{'特征名称':<25} {'目标中位':>10} {'雄塑值':>10} {'志特值':>10} {'雄匹配':>8} {'志匹配':>8} {'差距':>8} {'雄Z值':>8} {'志Z值':>8}")
print('-' * 110)

for d in core_analysis:
    print(f"{d['feature']:<25} {d['target_median']:>10.2f} {d['stock1_val']:>10.2f} {d['stock2_val']:>10.2f} {d['stock1_match']:>8.3f} {d['stock2_match']:>8.3f} {d['gap']:>8.3f} {d['stock1_z']:>8.2f} {d['stock2_z']:>8.2f}")

print()
print('=' * 80)
print('微调建议：调整目标特征值（向志特新材靠拢）')
print('=' * 80)
print()

# 找出志特新材明显低于雄塑科技的核心特征
adjustments = []
for d in core_analysis:
    if d['gap'] > 0.05:  # 匹配度差距大于0.05
        # 如果志特新材的Z值较大（离目标较远），但它是大牛股，说明目标值可能需要调整
        if d['stock2_z'] > 1.5 and d['stock2_match'] < 0.8:
            # 微调：向志特新材的值靠拢（30%调整）
            new_median = d['target_median'] * 0.7 + d['stock2_val'] * 0.3
            adjustments.append({
                'feature': d['feature'],
                'old_median': d['target_median'],
                'new_median': new_median,
                'stock2_val': d['stock2_val'],
                'stock1_val': d['stock1_val'],
                'gap': d['gap'],
                'reason': f'志特新材Z值{d["stock2_z"]:.2f}较大，但为大牛股，调整目标值'
            })

if adjustments:
    print('建议调整的核心特征：')
    for adj in adjustments:
        print(f"  {adj['feature']}:")
        print(f"    目标中位数: {adj['old_median']:.2f} -> {adj['new_median']:.2f}")
        print(f"    雄塑科技值: {adj['stock1_val']:.2f}")
        print(f"    志特新材值: {adj['stock2_val']:.2f}")
        print(f"    匹配度差距: {adj['gap']:.3f}")
        print(f"    原因: {adj['reason']}")
        print()
else:
    print('未找到需要调整的特征（所有特征差距都在可接受范围内）')
    print()
    print('分析：志特新材的主要劣势特征：')
    for d in core_analysis[:5]:
        if d['gap'] > 0:
            print(f"  {d['feature']}: 志特={d['stock2_val']:.2f}, 雄塑={d['stock1_val']:.2f}, 目标={d['target_median']:.2f}, 差距={d['gap']:.3f}")

# 如果找到需要调整的特征，保存微调后的模型
if adjustments:
    print('=' * 80)
    print('保存微调后的模型')
    print('=' * 80)
    
    # 读取原模型
    with open('trained_model.json', 'r', encoding='utf-8') as f:
        model_data = json.load(f)
    
    # 微调目标特征值
    adjusted_count = 0
    for adj in adjustments:
        feature_name = adj['feature']
        if feature_name in model_data.get('buy_features', {}).get('common_features', {}):
            old_median = model_data['buy_features']['common_features'][feature_name].get('median', 0)
            new_median = adj['new_median']
            
            # 微调：保持其他统计值不变，只调整中位数
            model_data['buy_features']['common_features'][feature_name]['median'] = round(new_median, 2)
            adjusted_count += 1
            
            print(f"✅ 调整 {feature_name}: {old_median:.2f} -> {new_median:.2f}")
    
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
    match2_adjusted = analyzer._calculate_match_score(features2, common_features_adjusted, tolerance=0.3)
    
    print(f'志特新材原匹配度: {match2["总匹配度"]:.4f}')
    print(f'志特新材微调后匹配度: {match2_adjusted["总匹配度"]:.4f}')
    print(f'提升: {(match2_adjusted["总匹配度"] - match2["总匹配度"])*100:.2f}%')
else:
    print()
    print('=' * 80)
    print('由于未找到需要调整的特征，将采用更激进的微调策略')
    print('=' * 80)
    print()
    
    # 找出志特新材与目标差距最大的3个核心特征，进行微调
    top_gaps = sorted(core_analysis, key=lambda x: abs(x['stock2_z']), reverse=True)[:3]
    
    print('对以下特征进行微调（向志特新材靠拢）：')
    adjustments = []
    for d in top_gaps:
        if d['stock2_z'] > 0.5:  # Z值大于0.5
            new_median = d['target_median'] * 0.8 + d['stock2_val'] * 0.2  # 20%调整
            adjustments.append({
                'feature': d['feature'],
                'old_median': d['target_median'],
                'new_median': new_median,
                'stock2_val': d['stock2_val'],
            })
            print(f"  {d['feature']}: {d['target_median']:.2f} -> {new_median:.2f} (志特值: {d['stock2_val']:.2f}, Z值: {d['stock2_z']:.2f})")
    
    if adjustments:
        # 读取原模型
        with open('trained_model.json', 'r', encoding='utf-8') as f:
            model_data = json.load(f)
        
        # 微调目标特征值
        adjusted_count = 0
        for adj in adjustments:
            feature_name = adj['feature']
            if feature_name in model_data.get('buy_features', {}).get('common_features', {}):
                old_median = model_data['buy_features']['common_features'][feature_name].get('median', 0)
                new_median = adj['new_median']
                model_data['buy_features']['common_features'][feature_name]['median'] = round(new_median, 2)
                adjusted_count += 1
        
        # 保存微调后的模型
        output_file = 'trained_model_zhite_adjusted.json'
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(model_data, f, ensure_ascii=False, indent=2)
        
        print()
        print(f'✅ 已保存微调后的模型到: {output_file}')
        print(f'   共调整了 {adjusted_count} 个特征')
        
        # 验证微调后的匹配度
        analyzer.load_model(output_file)
        common_features_adjusted = analyzer._get_common_features()
        match2_adjusted = analyzer._calculate_match_score(features2, common_features_adjusted, tolerance=0.3)
        
        print()
        print(f'志特新材原匹配度: {match2["总匹配度"]:.4f}')
        print(f'志特新材微调后匹配度: {match2_adjusted["总匹配度"]:.4f}')
        print(f'提升: {(match2_adjusted["总匹配度"] - match2["总匹配度"])*100:.2f}%')
