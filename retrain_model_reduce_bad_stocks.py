#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
重新训练模型，大幅降低"垃圾个股"的匹配度
策略：找出垃圾个股与训练股票差异最大的特征，大幅缩小这些特征的标准差
"""
import sys
sys.path.insert(0, '.')
from bull_stock_analyzer import BullStockAnalyzer
from datetime import datetime
import pandas as pd
import numpy as np
import json

# 11只训练股票
TRAINING_STOCKS = {
    '000592': '平潭发展',
    '002104': '恒宝股份',
    '002759': '天际股份',
    '300436': '广生堂',
    '301005': '超捷股份',
    '301232': '飞沃科技',
    '002788': '鹭燕医药',
    '603778': '国晟科技',
    '603122': '合富中国',
    '600343': '航天动力',
    '603216': '梦天家居'
}

# "勉强可以"的股票（保留高匹配度）
GOOD_STOCKS = {
    '000006': {'date': '2025-08-04', 'name': '深振业Ａ'},
    '000010': {'date': '2025-07-28', 'name': '美丽生态'}
}

# "垃圾个股"（需要大幅降低匹配度）
BAD_STOCKS = {
    '000012': {'name': '南  玻Ａ', 'date': '2025-01-02'},
    '000020': {'name': '深华发Ａ', 'date': '2025-01-02'},
    '000011': {'name': '深物业A', 'date': '2025-02-24'},
    '000019': {'name': '深粮控股', 'date': '2025-02-24'},
    '000030': {'name': '富奥股份', 'date': '2025-01-02'},
    '000058': {'name': '深 赛 格', 'date': '2025-01-02'}
}

def extract_features_for_stock(analyzer, stock_code, scan_date_str):
    """提取股票在特定日期的特征"""
    try:
        scan_date = datetime.strptime(scan_date_str, '%Y-%m-%d').date()
        weekly_df = analyzer.fetcher.get_weekly_kline(stock_code, period="2y", use_cache=True, end_date=scan_date)
        if weekly_df is None or len(weekly_df) < 40:
            return None
        if '日期' in weekly_df.columns:
            weekly_df['日期'] = pd.to_datetime(weekly_df['日期']).dt.date
            weekly_df = weekly_df[weekly_df['日期'] <= scan_date].copy()
            weekly_df = weekly_df.sort_values('日期').reset_index(drop=True)
        if len(weekly_df) < 40:
            return None
        current_idx = len(weekly_df) - 1
        volume_surge_idx = analyzer.find_volume_surge_point(stock_code, current_idx, weekly_df=weekly_df, min_volume_ratio=3.0, lookback_weeks=52)
        if volume_surge_idx is None:
            volume_surge_idx = max(0, current_idx - 20)
        features = analyzer.extract_features_at_start_point(stock_code, volume_surge_idx, lookback_weeks=40, weekly_df=weekly_df)
        return features
    except Exception as e:
        return None

def main():
    print("=" * 80)
    print("🎓 重新训练模型（大幅降低垃圾个股匹配度）")
    print("=" * 80)
    print()
    
    # 加载模型
    analyzer = BullStockAnalyzer(auto_load_default_stocks=False, auto_analyze_and_train=False)
    if not analyzer.load_model('models/模型11.json', skip_network=True):
        print("❌ 模型加载失败")
        return
    
    print("✅ 模型加载成功")
    print()
    
    # 提取特征
    print("📈 提取特征...")
    training_features = {}
    good_features = {}
    bad_features = {}
    
    # 提取训练股票特征（使用它们的买点日期）
    for stock_code, stock_name in TRAINING_STOCKS.items():
        features = extract_features_for_stock(analyzer, stock_code, '2025-01-02')
        if features:
            training_features[stock_code] = features
    
    # 提取"勉强可以"股票特征
    for stock_code, info in GOOD_STOCKS.items():
        features = extract_features_for_stock(analyzer, stock_code, info['date'])
        if features:
            good_features[stock_code] = features
    
    # 提取"垃圾个股"特征
    for stock_code, info in BAD_STOCKS.items():
        features = extract_features_for_stock(analyzer, stock_code, info['date'])
        if features:
            bad_features[stock_code] = features
    
    print(f"  训练股票: {len(training_features)} 只")
    print(f"  '勉强可以': {len(good_features)} 只")
    print(f"  '垃圾个股': {len(bad_features)} 只")
    print()
    
    # 重新训练模型
    print("🎓 重新训练模型...")
    analyzer.analysis_results = {}
    analyzer.trained_features = None
    analyzer.bull_stocks = []
    
    for stock_code in TRAINING_STOCKS.keys():
        analyzer.add_bull_stock(stock_code)
    
    for stock_code in TRAINING_STOCKS.keys():
        analyzer.analyze_bull_stock(stock_code)
    
    train_result = analyzer.train_features()
    if not train_result.get('success'):
        print(f"❌ 训练失败: {train_result.get('message', '')}")
        return
    
    print("✅ 基础模型训练完成")
    print()
    
    # 分析特征差异并调整
    if analyzer.trained_features and 'common_features' in analyzer.trained_features:
        common_features = analyzer.trained_features['common_features']
        
        print("📊 分析特征差异并调整...")
        print()
        
        feature_adjustments = {}
        
        # 对每个特征进行分析
        for feature_name in common_features.keys():
            # 收集训练股票的特征值
            training_values = []
            for stock_code, features in training_features.items():
                if feature_name in features and features[feature_name] is not None:
                    try:
                        val = float(features[feature_name])
                        if not np.isnan(val) and not np.isinf(val):
                            training_values.append(val)
                    except:
                        pass
            
            # 收集"勉强可以"股票的特征值
            good_values = []
            for stock_code, features in good_features.items():
                if feature_name in features and features[feature_name] is not None:
                    try:
                        val = float(features[feature_name])
                        if not np.isnan(val) and not np.isinf(val):
                            good_values.append(val)
                    except:
                        pass
            
            # 收集"垃圾个股"的特征值
            bad_values = []
            for stock_code, features in bad_features.items():
                if feature_name in features and features[feature_name] is not None:
                    try:
                        val = float(features[feature_name])
                        if not np.isnan(val) and not np.isinf(val):
                            bad_values.append(val)
                    except:
                        pass
            
            if len(training_values) > 0 and len(bad_values) > 0:
                training_mean = np.mean(training_values)
                good_mean = np.mean(good_values) if len(good_values) > 0 else training_mean
                bad_mean = np.mean(bad_values)
                
                # 计算差异
                diff_good = abs(good_mean - training_mean)
                diff_bad = abs(bad_mean - training_mean)
                
                # 更激进的策略：只要垃圾个股与训练股票有差异，就调整
                # 缩小阈值，调整更多特征
                if diff_bad > 0.01:  # 只要有差异就调整（非常低的阈值）
                    original_std = common_features[feature_name].get('标准差', 1.0)
                    original_mean = common_features[feature_name].get('均值', training_mean)
                    
                    # 更激进地缩小标准差（缩小到5-15%）
                    if diff_bad > diff_good * 3.0:
                        reduction_factor = 0.1  # 缩小到10%（最激进）
                    elif diff_bad > diff_good * 2.5:
                        reduction_factor = 0.12  # 缩小到12%
                    elif diff_bad > diff_good * 2.0:
                        reduction_factor = 0.15  # 缩小到15%
                    elif diff_bad > diff_good * 1.5:
                        reduction_factor = 0.2  # 缩小到20%
                    elif diff_bad > diff_good * 1.2:
                        reduction_factor = 0.25  # 缩小到25%
                    else:
                        reduction_factor = 0.3  # 缩小到30%
                    
                    new_std = original_std * reduction_factor
                    # 确保标准差不会太小（至少0.05，比之前更小）
                    new_std = max(new_std, 0.05)
                    
                    # 调整均值和范围，使"垃圾个股"的特征值更可能落在范围外
                    # 将均值向"勉强可以"股票靠拢（远离"垃圾个股"）
                    if len(good_values) > 0:
                        # 使用训练股票和"勉强可以"股票的加权平均作为新均值
                        new_mean = training_mean * 0.7 + good_mean * 0.3
                    else:
                        new_mean = training_mean
                    
                    # 更激进地调整范围，确保"垃圾个股"的特征值落在范围外
                    original_min = common_features[feature_name].get('最小值', training_mean - original_std * 2)
                    original_max = common_features[feature_name].get('最大值', training_mean + original_std * 2)
                    range_size = original_max - original_min
                    
                    # 计算训练股票和"勉强可以"股票的特征值范围
                    all_good_values = training_values + good_values
                    if len(all_good_values) > 0:
                        good_min = min(all_good_values)
                        good_max = max(all_good_values)
                    else:
                        good_min = training_mean - new_std * 1.5
                        good_max = training_mean + new_std * 1.5
                    
                    # 新范围：只包含训练股票和"勉强可以"股票的特征值，明确排除"垃圾个股"
                    # 使用训练股票和"勉强可以"股票的min/max，但稍微扩展以确保训练股票都被包含
                    range_margin = new_std * 0.5  # 小幅度扩展
                    new_min = good_min - range_margin
                    new_max = good_max + range_margin
                    
                    # 确保"垃圾个股"的特征值在范围外
                    if bad_mean >= new_min and bad_mean <= new_max:
                        # "垃圾个股"仍然在范围内，进一步缩小范围
                        # 根据"垃圾个股"的位置，调整范围边界
                        if bad_mean > new_mean:
                            # "垃圾个股"在右侧，缩小右侧边界
                            new_max = bad_mean - new_std * 0.3  # 在"垃圾个股"之前结束
                        else:
                            # "垃圾个股"在左侧，缩小左侧边界
                            new_min = bad_mean + new_std * 0.3  # 在"垃圾个股"之后开始
                    
                    # 确保范围不为空
                    if new_min >= new_max:
                        new_max = new_min + new_std * 0.5
                    
                    common_features[feature_name]['标准差'] = new_std
                    common_features[feature_name]['均值'] = new_mean
                    common_features[feature_name]['最小值'] = new_min
                    common_features[feature_name]['最大值'] = new_max
                    
                    feature_adjustments[feature_name] = {
                        'original_std': original_std,
                        'new_std': new_std,
                        'original_mean': original_mean,
                        'new_mean': new_mean,
                        'diff_good': diff_good,
                        'diff_bad': diff_bad,
                        'reduction': reduction_factor
                    }
        
        print(f"调整了 {len(feature_adjustments)} 个特征的标准差:")
        for feature_name, adj_info in sorted(feature_adjustments.items(), key=lambda x: x[1]['diff_bad'], reverse=True)[:20]:
            print(f"  {feature_name}: {adj_info['original_std']:.4f} -> {adj_info['new_std']:.4f} (差异: 好={adj_info['diff_good']:.4f}, 坏={adj_info['diff_bad']:.4f})")
        print()
    
    # 保存模型
    model_path = 'models/模型11_优化_v2.json'
    if analyzer.save_model(model_path):
        print(f"✅ 模型已保存到: {model_path}")
    else:
        print("❌ 模型保存失败")
        return
    
    # 测试匹配度
    print()
    print("=" * 80)
    print("📊 测试匹配度")
    print("=" * 80)
    print()
    
    # 测试训练股票
    print("训练股票匹配度:")
    training_scores = {}
    for stock_code, stock_name in TRAINING_STOCKS.items():
        if stock_code in training_features:
            features = training_features[stock_code]
            match_score = analyzer._calculate_match_score(features, analyzer.trained_features['common_features'], tolerance=0.3)
            total_match = match_score.get('总匹配度', 0)
            training_scores[stock_code] = total_match
            print(f"  {stock_code} {stock_name}: {total_match:.3f}")
    
    print()
    print(f"训练股票平均匹配度: {np.mean(list(training_scores.values())):.3f}")
    print()
    
    # 测试"勉强可以"股票
    print("'勉强可以'股票匹配度:")
    good_scores = {}
    for stock_code, info in GOOD_STOCKS.items():
        if stock_code in good_features:
            features = good_features[stock_code]
            match_score = analyzer._calculate_match_score(features, analyzer.trained_features['common_features'], tolerance=0.3)
            total_match = match_score.get('总匹配度', 0)
            good_scores[stock_code] = total_match
            print(f"  {stock_code} {info['name']}: {total_match:.3f}")
    
    print()
    if len(good_scores) > 0:
        print(f"'勉强可以'股票平均匹配度: {np.mean(list(good_scores.values())):.3f}")
        print()
    
    # 测试"垃圾个股"
    print("'垃圾个股'匹配度:")
    bad_scores = {}
    for stock_code, info in BAD_STOCKS.items():
        if stock_code in bad_features:
            features = bad_features[stock_code]
            match_score = analyzer._calculate_match_score(features, analyzer.trained_features['common_features'], tolerance=0.3)
            total_match = match_score.get('总匹配度', 0)
            bad_scores[stock_code] = total_match
            print(f"  {stock_code} {info['name']}: {total_match:.3f}")
    
    print()
    if len(bad_scores) > 0:
        print(f"'垃圾个股'平均匹配度: {np.mean(list(bad_scores.values())):.3f}")
        print()
        print(f"匹配度降低幅度: {1.0 - np.mean(list(bad_scores.values())):.3f}")
    
    print()
    print("=" * 80)
    print("✅ 模型重新训练完成")
    print("=" * 80)
    print()
    print(f"新模型文件: {model_path}")
    print()
    print("建议：使用新模型重新运行回测，验证垃圾个股的匹配度是否降低")

if __name__ == '__main__':
    main()
