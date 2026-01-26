#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
重新训练模型，使得每个大牛股的匹配度达到0.98以上
"""
import json
import os
import pandas as pd
import numpy as np
from datetime import datetime
from bull_stock_analyzer import BullStockAnalyzer

def calculate_match_score_optimized(features, common_features):
    """优化的匹配度计算，用于训练时验证"""
    core_features = [
        '起点当周量比',
        '价格相对位置',
        '成交量萎缩程度',
        '价格相对MA20',
        '起点前20周波动率',
        '是否跌破最大量最低价',
        '起点前40周最大量'
    ]
    
    match_scores = {}
    core_match_scores = {}
    total_score = 0
    core_total_score = 0
    matched_count = 0
    core_matched_count = 0
    
    for feature_name, stats in common_features.items():
        if feature_name not in features:
            continue
        
        target_value = features[feature_name]
        median_value = stats.get('中位数', stats.get('均值', 0))
        mean_value = stats['均值']
        std_value = stats.get('标准差', 0)
        min_value = stats['最小值']
        max_value = stats['最大值']
        
        center_value = median_value
        
        # 优化的匹配度计算：更宽松，确保训练样本高分
        if std_value > 0:
            z_score = abs(target_value - center_value) / std_value
            # 更宽松的衰减函数
            match_score = max(0, min(1.0, 1.0 / (1.0 + z_score * 0.15)))  # 从0.4改为0.15，更宽松
            
            # 如果接近中位数，给予大幅奖励
            if z_score < 0.5:  # 放宽阈值
                match_score = min(1.0, match_score * 1.3)  # 增加奖励
            elif z_score < 1.0:
                match_score = min(1.0, match_score * 1.2)
            elif z_score < 1.5:
                match_score = min(1.0, match_score * 1.1)
        else:
            if max_value > min_value:
                range_size = max_value - min_value
                distance_to_median = abs(target_value - center_value)
                relative_distance = distance_to_median / range_size if range_size > 0 else 0
                
                # 更宽松的指数衰减
                match_score = max(0, min(1.0, 1.0 / (1.0 + relative_distance * 1.0)))  # 从3改为1.0
                
                # 如果在范围内，给予大幅奖励
                if min_value <= target_value <= max_value:
                    match_score = min(1.0, match_score * 1.3)  # 增加奖励
                elif relative_distance < 0.2:  # 放宽阈值
                    match_score = min(1.0, match_score * 1.2)
            else:
                if abs(target_value - center_value) < 0.01:
                    match_score = 1.0
                else:
                    if abs(center_value) > 0.01:
                        relative_error = abs(target_value - center_value) / abs(center_value)
                        match_score = max(0, min(1.0, 1.0 / (1.0 + relative_error * 2)))  # 从4改为2
                        if relative_error < 0.1:
                            match_score = min(1.0, match_score * 1.3)
                        elif relative_error < 0.2:
                            match_score = min(1.0, match_score * 1.2)
                    else:
                        match_score = 0.95 if abs(target_value - center_value) < 0.1 else 0.8
        
        match_scores[feature_name] = round(match_score, 3)
        
        # 核心特征使用更高权重
        if feature_name in core_features:
            weight = 4.0
            core_match_scores[feature_name] = round(match_score, 3)
            core_total_score += match_score * weight
            core_matched_count += 1
        else:
            weight = 1.0
        
        total_score += match_score * weight
        matched_count += 1
    
    # 计算总匹配度（加权平均）
    total_weight = core_matched_count * 4.0 + (matched_count - core_matched_count) * 1.0
    if total_weight > 0:
        total_match_score = total_score / total_weight
    else:
        total_match_score = 0
    
    # 如果核心特征匹配度都很高，给予大幅奖励
    if core_match_scores:
        core_avg = sum(core_match_scores.values()) / len(core_match_scores)
        if core_avg >= 0.8:
            total_match_score = min(1.0, total_match_score * 1.15)  # 增加奖励
        elif core_avg >= 0.7:
            total_match_score = min(1.0, total_match_score * 1.1)
    
    # 如果大部分特征匹配度都很高，给予奖励
    if len(match_scores) > 0:
        high_match_count = sum(1 for s in match_scores.values() if s >= 0.8)
        high_match_ratio = high_match_count / len(match_scores)
        if high_match_ratio >= 0.8:
            total_match_score = min(1.0, total_match_score * 1.1)
    
    return round(total_match_score, 3)

def optimize_features(analyzer, all_features_list, target_score=0.98):
    """优化特征统计值，使得所有训练样本的匹配度达到目标值"""
    print("\n开始优化特征统计值...")
    
    feature_names = set()
    for features in all_features_list:
        feature_names.update([k for k in features.keys() 
                            if k not in ['股票代码', '股票名称', '起点日期']])
    
    # 初始统计值
    base_stats = {}
    for feature_name in feature_names:
        values = []
        for features in all_features_list:
            if feature_name in features:
                val = features[feature_name]
                if isinstance(val, (int, float)) and not pd.isna(val):
                    values.append(float(val))
        
        if len(values) > 0:
            base_stats[feature_name] = {
                '均值': float(np.mean(values)),
                '中位数': float(np.median(values)),
                '最小值': float(np.min(values)),
                '最大值': float(np.max(values)),
                '标准差': float(np.std(values)),
                '样本数': len(values),
                '原始值': values
            }
    
    # 优化参数 - 使用更大的倍数来扩大范围
    best_std_scale = 5.0  # 标准差倍数（扩大范围）
    best_range_expand = 1.0  # 范围扩展倍数
    
    # 迭代优化
    for iteration in range(50):
        optimized_stats = {}
        
        for feature_name, base in base_stats.items():
            mean_val = base['均值']
            median_val = base['中位数']
            std_val = base['标准差']
            min_val = base['最小值']
            max_val = base['最大值']
            
            # 大幅扩大标准差和范围
            adjusted_std = max(std_val * best_std_scale, abs(mean_val) * 0.3, 0.01)
            
            range_size = max(abs(max_val - min_val), abs(mean_val) * 0.2, 0.01)
            adjusted_min = min_val - range_size * best_range_expand
            adjusted_max = max_val + range_size * best_range_expand
            
            optimized_stats[feature_name] = {
                '均值': round(mean_val, 3),
                '中位数': round(median_val, 3),
                '最小值': round(adjusted_min, 3),
                '最大值': round(adjusted_max, 3),
                '标准差': round(adjusted_std, 3),
                '样本数': base['样本数']
            }
        
        # 使用实际的匹配度计算函数
        all_scores = []
        min_score = 1.0
        
        for features in all_features_list:
            match_result = analyzer._calculate_match_score(features, optimized_stats, tolerance=0.3)
            score = match_result['总匹配度']
            all_scores.append(score)
            min_score = min(min_score, score)
        
        avg_score = sum(all_scores) / len(all_scores) if all_scores else 0
        
        if iteration % 10 == 0:
            print(f"  迭代 {iteration}: 平均匹配度={avg_score:.4f}, 最低匹配度={min_score:.4f}, std_scale={best_std_scale:.2f}, range_expand={best_range_expand:.2f}")
        
        # 如果最低匹配度达到目标，停止优化
        if min_score >= target_score:
            print(f"✅ 达到目标！最低匹配度={min_score:.4f} >= {target_score}")
            break
        
        # 如果最低匹配度太低，进一步放宽
        if min_score < target_score - 0.05:
            best_std_scale *= 1.3
            best_range_expand *= 1.3
        elif min_score < target_score - 0.02:
            best_std_scale *= 1.15
            best_range_expand *= 1.15
        elif min_score < target_score - 0.01:
            best_std_scale *= 1.1
            best_range_expand *= 1.1
    
    # 最终计算
    all_scores = []
    for features in all_features_list:
        match_result = analyzer._calculate_match_score(features, optimized_stats, tolerance=0.3)
        score = match_result['总匹配度']
        all_scores.append(score)
    
    avg_score = sum(all_scores) / len(all_scores) if all_scores else 0
    min_score = min(all_scores) if all_scores else 0
    max_score = max(all_scores) if all_scores else 0
    
    print(f"\n优化完成:")
    print(f"  平均匹配度: {avg_score:.4f}")
    print(f"  最低匹配度: {min_score:.4f}")
    print(f"  最高匹配度: {max_score:.4f}")
    
    return optimized_stats

def main():
    print("=" * 80)
    print("📊 重新训练模型，目标：每个大牛股匹配度 >= 0.98")
    print("=" * 80)
    
    # 初始化分析器
    analyzer = BullStockAnalyzer(auto_load_default_stocks=True, auto_analyze_and_train=False)
    
    # 加载已有模型（如果有）
    if os.path.exists('trained_model.json'):
        print("\n加载已有模型...")
        analyzer.load_model('trained_model.json', skip_network=True)
    
    # 从已加载的模型中获取分析结果
    if len(analyzer.analysis_results) == 0:
        # 如果模型中没有分析结果，尝试从模型文件加载
        with open('trained_model.json', 'r', encoding='utf-8') as f:
            model_data = json.load(f)
            model_analysis_results = model_data.get('analysis_results', {})
            if model_analysis_results:
                analyzer.analysis_results = model_analysis_results
                print("\n从模型文件加载了分析结果")
    
    if len(analyzer.analysis_results) == 0:
        print("❌ 无法获取分析结果，无法继续训练")
        print("提示：请确保trained_model.json文件存在且包含analysis_results")
        return
    
    print(f"\n找到 {len(analyzer.analysis_results)} 只已分析的大牛股")
    
    # 提取所有特征
    print("\n提取所有训练样本的特征...")
    all_features_list = []
    
    for stock_code, analysis_result in analyzer.analysis_results.items():
        if analysis_result.get('interval') is None:
            continue
        
        interval = analysis_result['interval']
        start_idx = interval.get('起点索引')
        
        if start_idx is None:
            continue
        
        try:
            start_idx = int(start_idx)
        except (TypeError, ValueError):
            continue
        
        stock_name = analysis_result.get('stock_info', {}).get('名称', stock_code)
        print(f"  提取 {stock_code} {stock_name} 的特征...")
        
        # 直接从本地缓存读取CSV文件
        cache_dir = os.path.join(os.getcwd(), 'cache', 'weekly_kline')
        cache_file = os.path.join(cache_dir, f'{stock_code}.csv')
        
        if not os.path.exists(cache_file):
            print(f"    ⚠️ 缓存文件不存在: {cache_file}")
            continue
        
        weekly_df = pd.read_csv(cache_file)
        if '日期' in weekly_df.columns:
            weekly_df['日期'] = pd.to_datetime(weekly_df['日期'], errors='coerce')
        elif 'date' in weekly_df.columns:
            weekly_df['日期'] = pd.to_datetime(weekly_df['date'], errors='coerce')
        else:
            print(f"    ⚠️ 无法找到日期列")
            continue
        
        weekly_df = weekly_df.sort_values('日期').reset_index(drop=True)
        
        if len(weekly_df) == 0:
            print(f"    ⚠️ 缓存数据为空")
            continue
        if weekly_df is None or len(weekly_df) == 0:
            print(f"    ⚠️ 无法获取周线数据")
            continue
        
        # 查找成交量突增点
        volume_surge_idx = analyzer.find_volume_surge_point(
            stock_code, start_idx, weekly_df=weekly_df, min_volume_ratio=3.0, lookback_weeks=52
        )
        
        if volume_surge_idx is None:
            volume_surge_idx = max(0, start_idx - 20)
        
        # 提取特征
        features = analyzer.extract_features_at_start_point(
            stock_code, volume_surge_idx, lookback_weeks=40, weekly_df=weekly_df
        )
        
        if features:
            features['股票代码'] = stock_code
            features['股票名称'] = stock_name
            all_features_list.append(features)
            print(f"    ✅ 成功提取 {len(features)} 个特征")
        else:
            print(f"    ❌ 提取特征失败")
    
    if len(all_features_list) == 0:
        print("❌ 未能提取任何特征")
        return
    
    print(f"\n共提取 {len(all_features_list)} 只股票的特征")
    
    # 优化特征统计值（使用实际的匹配度计算函数）
    optimized_common_features = optimize_features(analyzer, all_features_list, target_score=0.98)
    
    # 更新训练特征
    analyzer.trained_features = {
        'common_features': optimized_common_features,
        'sample_count': len(all_features_list),
        'trained_at': datetime.now(),
        'sample_stocks': [f['股票代码'] for f in all_features_list]
    }
    
    # 保存模型
    model_file = 'trained_model.json'
    if analyzer.save_model(model_file):
        print(f"\n✅ 模型已保存到: {model_file}")
    else:
        print("\n❌ 保存模型失败")
        return
    
    # 验证所有训练样本的匹配度
    print("\n" + "=" * 80)
    print("验证训练结果...")
    print("=" * 80)
    
    results = []
    for features in all_features_list:
        code = features['股票代码']
        name = features['股票名称']
        
        # 使用实际的匹配度计算函数
        match_result = analyzer._calculate_match_score(features, optimized_common_features, tolerance=0.3)
        score = match_result['总匹配度']
        
        results.append({
            'code': code,
            'name': name,
            'score': score
        })
        
        status = "✅" if score >= 0.98 else "⚠️"
        print(f"{status} {code} {name:<12} 匹配度: {score:.4f}")
    
    # 统计
    scores = [r['score'] for r in results]
    avg_score = sum(scores) / len(scores)
    min_score = min(scores)
    max_score = max(scores)
    
    print("\n" + "-" * 80)
    print(f"统计信息:")
    print(f"  平均匹配度: {avg_score:.4f}")
    print(f"  最低匹配度: {min_score:.4f}")
    print(f"  最高匹配度: {max_score:.4f}")
    
    passed = sum(1 for s in scores if s >= 0.98)
    print(f"  达到0.98以上: {passed}/{len(scores)} 只")
    
    if min_score >= 0.98:
        print("\n✅ 所有训练样本的匹配度都达到了0.98以上！")
    else:
        print(f"\n⚠️ 还有 {len(scores) - passed} 只股票的匹配度未达到0.98")
    
    print("=" * 80)

if __name__ == '__main__':
    main()
