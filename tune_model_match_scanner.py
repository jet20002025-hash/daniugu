#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
调整模型参数，使用与扫描器相同的特征提取逻辑（从成交量突增点提取特征）
"""
import sys
sys.path.insert(0, '.')
from bull_stock_analyzer import BullStockAnalyzer
import json
import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')

# 目标股票及其匹配度（从图片中）
TARGET_STOCKS = {
    '300141': ('和顺电气', 0.970),
    '002928': ('华夏航空', 0.964),
    '002811': ('郑中设计', 0.962),
    '001217': ('华尔泰', 0.961),
    '002197': ('证通电子', 0.954),
    '002810': ('山东赫达', 0.951),
    '603008': ('喜临门', 0.947),
    '603212': ('赛伍技术', 0.947),
    '002636': ('金安国纪', 0.942),
    '000532': ('华金资本', 0.939),
    '002538': ('司尔特', 0.937),
    '002957': ('科瑞技术', 0.937),
    '300414': ('中光防雷', 0.936),
    '605155': ('西大门', 0.935),
    '002253': ('*ST智胜', 0.933),
    '301027': ('华蓝集团', 0.930),
}

# 与扫描器相同的核心特征定义
SUPER_CORE_FEATURES = ['盈利筹码比例', '价格相对位置']
CORE_FEATURES = [
    '盈利筹码比例', '价格相对位置', '90%成本集中度', '起点当周量比', '成交量萎缩程度', '价格相对MA20',
    '起点前20周波动率', '是否跌破最大量最低价', '起点前40周最大量', '相对高点跌幅'
]

def calculate_match_score_scanner(features, template):
    """使用与BullStockAnalyzer._calculate_match_score完全相同的计算逻辑"""
    if not features or not template:
        return 0.0
    
    super_core_scores = []
    core_scores = []
    normal_scores = []
    
    for feature_name, feature_value in features.items():
        if feature_name in ['股票代码', '股票名称', '起点日期', '终点日期']:
            continue
        
        if not isinstance(feature_value, (int, float)) or pd.isna(feature_value):
            continue
        
        if feature_name not in template:
            continue
        
        stats = template[feature_name]
        mean = stats.get('均值', 0)
        std = stats.get('标准差', 0)
        min_val = stats.get('最小值', 0)
        max_val = stats.get('最大值', 0)
        
        is_super_core = feature_name in SUPER_CORE_FEATURES
        
        if std > 0:
            z_score = abs((feature_value - mean) / std)
            decay_factor = 0.3 if is_super_core else 0.5
            match_score = 1.0 / (1.0 + z_score * decay_factor)
        else:
            match_score = 1.0 if abs(feature_value - mean) < 0.01 else 0.0
        
        if min_val <= feature_value <= max_val:
            match_score = min(1.0, match_score + 0.1)
        
        if is_super_core and std > 0:
            z_score = abs((feature_value - mean) / std)
            if z_score > 2.0:
                match_score = match_score * 0.5
            elif z_score > 1.5:
                match_score = match_score * 0.7
        
        if feature_name in SUPER_CORE_FEATURES:
            super_core_scores.append(match_score)
        elif feature_name in CORE_FEATURES:
            core_scores.append(match_score)
        else:
            normal_scores.append(match_score)
    
    super_core_weight = 6.0
    core_weight = 4.0
    normal_weight = 1.0
    
    super_core_avg = np.mean(super_core_scores) if super_core_scores else 0.0
    core_avg = np.mean(core_scores) if core_scores else 0.0
    normal_avg = np.mean(normal_scores) if normal_scores else 0.0
    
    total_weight = (len(super_core_scores) * super_core_weight + 
                    len(core_scores) * core_weight + 
                    len(normal_scores) * normal_weight)
    
    if total_weight > 0:
        total_match = (
            super_core_avg * len(super_core_scores) * super_core_weight +
            core_avg * len(core_scores) * core_weight +
            normal_avg * len(normal_scores) * normal_weight
        ) / total_weight
    else:
        total_match = 0.0
    
    return round(float(total_match), 3)

def extract_features_like_scanner(analyzer, code, scan_date='2025-12-31'):
    """
    使用与扫描器相同的逻辑提取特征：
    1. 获取周线数据
    2. 找成交量突增点
    3. 从突增点提取特征
    """
    kline = analyzer.fetcher.get_weekly_kline(code, period='2y')
    if kline is None or len(kline) == 0:
        return None, None
    
    kline['日期'] = pd.to_datetime(kline['日期'])
    scan_dt = pd.to_datetime(scan_date)
    mask = kline['日期'] <= scan_dt
    filtered = kline[mask].copy()
    
    if len(filtered) < 40:
        return None, None
    
    buy_point_idx = len(filtered) - 1
    
    # 找成交量突增点（与扫描器逻辑一致）
    volume_surge_idx = analyzer.find_volume_surge_point(code, buy_point_idx, filtered, 
                                                         min_volume_ratio=3.0, lookback_weeks=52)
    
    # 确定特征起点（与扫描器逻辑一致）
    if volume_surge_idx is not None and volume_surge_idx >= 40:
        feature_idx = volume_surge_idx
    else:
        feature_idx = buy_point_idx
    
    # 提取特征
    features = analyzer.extract_features_at_start_point(code, feature_idx, lookback_weeks=40, weekly_df=filtered)
    
    return features, feature_idx

def main():
    print("=" * 80)
    print("调整模型参数（使用与扫描器相同的特征提取逻辑）")
    print("目标: 和顺电气 0.970 排第一")
    print("=" * 80)
    print()
    
    analyzer = BullStockAnalyzer(auto_load_default_stocks=False, auto_analyze_and_train=False)
    
    print("📊 使用扫描器逻辑提取目标股票特征...")
    all_features = {}
    
    for code, (name, target_score) in TARGET_STOCKS.items():
        features, feature_idx = extract_features_like_scanner(analyzer, code)
        if features:
            all_features[code] = {
                'name': name,
                'target_score': target_score,
                'features': features,
                'feature_idx': feature_idx
            }
            print(f"  ✅ {code} {name}: 特征起点索引={feature_idx}, 特征数={len(features)}")
        else:
            print(f"  ⚠️ {code} {name}: 特征提取失败")
    
    print(f"\n成功提取 {len(all_features)} 只股票的特征")
    
    if len(all_features) == 0:
        print("❌ 没有提取到特征")
        return
    
    # 收集特征统计信息
    heshun = all_features.get('300141')
    if not heshun:
        print("❌ 未找到和顺电气")
        return
    
    heshun_features = heshun['features']
    
    print("\n🔧 开始优化模板参数...")
    
    # 收集所有特征的统计信息
    feature_stats = {}
    for feature_name in heshun_features.keys():
        if not isinstance(heshun_features[feature_name], (int, float)):
            continue
        
        values = [all_features[code]['features'].get(feature_name) 
                  for code in all_features 
                  if code in all_features and 
                  isinstance(all_features[code]['features'].get(feature_name), (int, float))]
        
        if len(values) > 0:
            feature_stats[feature_name] = {
                'values': values,
                'mean': np.mean(values),
                'std': np.std(values) if len(values) > 1 else 0.1,
                'min': min(values),
                'max': max(values),
                'heshun': heshun_features[feature_name]
            }
    
    best_template = None
    best_error = float('inf')
    
    for iteration in range(500):
        template = {}
        
        mean_shift = (iteration % 50) / 100.0
        std_scale = 1.0 + (iteration % 30) * 0.1
        range_expand = 0.2 + (iteration % 20) * 0.05
        
        for feature_name, stats in feature_stats.items():
            heshun_val = stats['heshun']
            mean_val = stats['mean']
            std_val = stats['std']
            
            adjusted_mean = heshun_val * (1 - mean_shift) + mean_val * mean_shift
            adjusted_std = max(std_val * std_scale, abs(heshun_val - mean_val) * 0.5, 0.01)
            
            range_size = max(abs(stats['max'] - stats['min']), 0.1)
            adjusted_min = stats['min'] - range_size * range_expand
            adjusted_max = stats['max'] + range_size * range_expand
            
            template[feature_name] = {
                "均值": adjusted_mean,
                "中位数": heshun_val,
                "最小值": adjusted_min,
                "最大值": adjusted_max,
                "标准差": adjusted_std,
                "样本数": len(stats['values'])
            }
        
        calculated_scores = {}
        for code, info in all_features.items():
            score = calculate_match_score_scanner(info['features'], template)
            calculated_scores[code] = score
        
        total_error = 0
        sorted_scores = sorted(calculated_scores.items(), key=lambda x: x[1], reverse=True)
        
        if sorted_scores[0][0] != '300141':
            total_error += 5.0
        
        for code, info in all_features.items():
            target = info['target_score']
            actual = calculated_scores[code]
            total_error += (target - actual) ** 2
        
        if total_error < best_error:
            best_error = total_error
            best_template = {k: v.copy() for k, v in template.items()}
            
            if iteration % 100 == 0 or total_error < 0.1:
                print(f"  迭代 {iteration}: 误差={total_error:.4f}")
                for i, (code, score) in enumerate(sorted_scores[:3]):
                    name = all_features[code]['name']
                    target = all_features[code]['target_score']
                    print(f"    {i+1}. {code} {name}: {score:.3f} (目标: {target:.3f})")
    
    # 精细调整
    print("\n🔬 精细调整...")
    for iteration in range(1000):
        new_template = {k: v.copy() for k, v in best_template.items()}
        
        feature_name = np.random.choice(list(new_template.keys()))
        params = new_template[feature_name]
        
        adjustment = np.random.choice(['mean', 'std', 'range'])
        if adjustment == 'mean':
            params['均值'] *= (0.98 + np.random.random() * 0.04)
        elif adjustment == 'std':
            params['标准差'] *= (0.9 + np.random.random() * 0.2)
        else:
            params['最小值'] *= (0.95 + np.random.random() * 0.1)
            params['最大值'] *= (0.95 + np.random.random() * 0.1)
        
        calculated_scores = {}
        for code, info in all_features.items():
            score = calculate_match_score_scanner(info['features'], new_template)
            calculated_scores[code] = score
        
        total_error = 0
        sorted_scores = sorted(calculated_scores.items(), key=lambda x: x[1], reverse=True)
        
        if sorted_scores[0][0] != '300141':
            total_error += 10.0
        
        for code, info in all_features.items():
            target = info['target_score']
            actual = calculated_scores[code]
            total_error += (target - actual) ** 2
        
        if total_error < best_error:
            best_error = total_error
            best_template = {k: v.copy() for k, v in new_template.items()}
    
    # 最终验证
    print("\n📊 最终验证:")
    calculated_scores = {}
    for code, info in all_features.items():
        score = calculate_match_score_scanner(info['features'], best_template)
        calculated_scores[code] = score
    
    sorted_scores = sorted(calculated_scores.items(), key=lambda x: x[1], reverse=True)
    
    print(f"\n{'排名':<4} {'股票代码':<10} {'股票名称':<12} {'目标匹配度':<12} {'实际匹配度':<12} {'差异':<8}")
    print("-" * 70)
    
    for i, (code, score) in enumerate(sorted_scores, 1):
        if code in all_features:
            name = all_features[code]['name']
            target = all_features[code]['target_score']
            diff = score - target
            print(f"{i:<4} {code:<10} {name:<12} {target:.3f}        {score:.3f}        {diff:+.3f}")
    
    # 保存模型
    model = {
        "trained_at": pd.Timestamp.now().isoformat(),
        "buy_features": {
            "common_features": best_template,
            "sample_count": len(all_features),
            "trained_at": pd.Timestamp.now().isoformat(),
            "sample_stocks": list(all_features.keys()),
            "training_stocks": list(all_features.keys()),
            "match_scores": {
                code: {
                    "股票名称": info['name'],
                    "匹配度": calculated_scores[code]
                }
                for code, info in all_features.items()
            }
        },
        "sell_features": None,
        "bull_stocks": [
            {
                "代码": code,
                "名称": info['name'],
                "添加时间": pd.Timestamp.now().isoformat(),
                "数据条数": 0
            }
            for code, info in all_features.items()
        ]
    }
    
    model_path = 'models/目标模型_完全匹配扫描器.json'
    with open(model_path, 'w', encoding='utf-8') as f:
        json.dump(model, f, ensure_ascii=False, indent=2, default=str)
    
    print(f"\n✅ 模型已保存到: {model_path}")
    return model_path

if __name__ == '__main__':
    main()
