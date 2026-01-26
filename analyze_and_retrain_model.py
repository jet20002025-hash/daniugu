#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
分析"垃圾个股"和模型股的特征差异，重新训练模型
"""
import sys
sys.path.insert(0, '.')
from bull_stock_analyzer import BullStockAnalyzer
from datetime import datetime
import pandas as pd
import numpy as np
import json

# 11只训练股票（模型股）
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

# "垃圾个股"（需要降低匹配度）
BAD_STOCKS = {
    '000012': {'name': '南  玻Ａ'},
    '000020': {'name': '深华发Ａ'},
    '000011': {'name': '深物业A'},
    '000019': {'name': '深粮控股'},
    '000030': {'name': '富奥股份'},
    '000058': {'name': '深 赛 格'}
}

def extract_features_for_stock(analyzer, stock_code, scan_date_str):
    """提取股票在特定日期的特征"""
    try:
        scan_date = datetime.strptime(scan_date_str, '%Y-%m-%d').date()
        
        # 获取周K线数据
        weekly_df = analyzer.fetcher.get_weekly_kline(
            stock_code, 
            period="2y", 
            use_cache=True,
            end_date=scan_date
        )
        
        if weekly_df is None or len(weekly_df) < 40:
            return None
        
        # 确保只使用到扫描日期的数据
        if '日期' in weekly_df.columns:
            weekly_df['日期'] = pd.to_datetime(weekly_df['日期']).dt.date
            weekly_df = weekly_df[weekly_df['日期'] <= scan_date].copy()
            weekly_df = weekly_df.sort_values('日期').reset_index(drop=True)
        
        if len(weekly_df) < 40:
            return None
        
        # 使用最后一周作为潜在的买点
        current_idx = len(weekly_df) - 1
        
        # 找到成交量突增点
        volume_surge_idx = analyzer.find_volume_surge_point(
            stock_code, 
            current_idx, 
            weekly_df=weekly_df, 
            min_volume_ratio=3.0, 
            lookback_weeks=52
        )
        if volume_surge_idx is None:
            volume_surge_idx = max(0, current_idx - 20)
        
        # 提取特征
        features = analyzer.extract_features_at_start_point(
            stock_code, 
            volume_surge_idx, 
            lookback_weeks=40, 
            weekly_df=weekly_df
        )
        
        return features
    except Exception as e:
        print(f"  提取特征失败: {e}")
        return None

def analyze_feature_differences():
    """分析特征差异"""
    print("=" * 80)
    print("📊 分析特征差异")
    print("=" * 80)
    print()
    
    # 加载模型
    analyzer = BullStockAnalyzer(auto_load_default_stocks=False, auto_analyze_and_train=False)
    if not analyzer.load_model('models/模型11.json', skip_network=True):
        print("❌ 模型加载失败")
        return None
    
    print("✅ 模型加载成功")
    print()
    
    # 提取训练股票的特征（使用它们的实际买点日期）
    print("📈 提取训练股票的特征...")
    training_features = {}
    
    # 从回测结果中找到训练股票被选中的日期，或者使用它们的买点日期
    # 这里我们使用一个代表性的日期来提取特征
    test_date = '2025-01-02'
    
    for stock_code, stock_name in TRAINING_STOCKS.items():
        print(f"  提取 {stock_code} {stock_name}...")
        features = extract_features_for_stock(analyzer, stock_code, test_date)
        if features:
            training_features[stock_code] = features
            print(f"    ✅ 成功")
        else:
            print(f"    ❌ 失败")
    
    print()
    
    # 提取"勉强可以"股票的特征
    print("📈 提取'勉强可以'股票的特征...")
    good_features = {}
    
    for stock_code, info in GOOD_STOCKS.items():
        print(f"  提取 {stock_code} {info['name']} 在 {info['date']}...")
        features = extract_features_for_stock(analyzer, stock_code, info['date'])
        if features:
            good_features[stock_code] = features
            print(f"    ✅ 成功")
        else:
            print(f"    ❌ 失败")
    
    print()
    
    # 提取"垃圾个股"的特征（使用回测中被选中的日期）
    print("📈 提取'垃圾个股'的特征...")
    bad_features = {}
    
    # 从回测结果中找到这些股票被选中的日期
    with open('backtest_model11_local_20260118_131753.json', 'r', encoding='utf-8') as f:
        backtest_data = json.load(f)
    
    bad_stock_dates = {}
    if 'detailed_results' in backtest_data:
        for day_result in backtest_data['detailed_results']:
            scan_date = day_result.get('date', '')
            if 'stocks' in day_result:
                for stock in day_result['stocks']:
                    stock_code = stock.get('stock_code', '')
                    if stock_code in BAD_STOCKS and stock_code not in bad_stock_dates:
                        bad_stock_dates[stock_code] = scan_date
    
    for stock_code, info in BAD_STOCKS.items():
        scan_date = bad_stock_dates.get(stock_code, '2025-01-02')
        print(f"  提取 {stock_code} {info['name']} 在 {scan_date}...")
        features = extract_features_for_stock(analyzer, stock_code, scan_date)
        if features:
            bad_features[stock_code] = features
            print(f"    ✅ 成功")
        else:
            print(f"    ❌ 失败")
    
    print()
    
    # 分析特征差异
    if not analyzer.trained_features or 'common_features' not in analyzer.trained_features:
        print("❌ 模型特征未加载")
        return None
    
    common_features = analyzer.trained_features['common_features']
    
    print("=" * 80)
    print("📊 特征差异分析")
    print("=" * 80)
    print()
    
    feature_differences = {}
    
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
            training_std = np.std(training_values)
            good_mean = np.mean(good_values) if len(good_values) > 0 else training_mean
            bad_mean = np.mean(bad_values)
            bad_std = np.std(bad_values)
            
            # 计算差异
            diff_good = abs(good_mean - training_mean)
            diff_bad = abs(bad_mean - training_mean)
            
            feature_differences[feature_name] = {
                'training_mean': training_mean,
                'training_std': training_std,
                'good_mean': good_mean,
                'bad_mean': bad_mean,
                'bad_std': bad_std,
                'diff_good': diff_good,
                'diff_bad': diff_bad,
                'ratio': diff_bad / diff_good if diff_good > 0 else 0
            }
    
    # 找出差异最大的特征（垃圾个股与训练股票差异大，但与"勉强可以"股票差异小）
    print("关键特征差异（垃圾个股 vs 训练股票）：")
    print()
    
    sorted_features = sorted(feature_differences.items(), key=lambda x: x[1]['diff_bad'], reverse=True)
    
    for feature_name, diff_info in sorted_features[:15]:
        print(f"{feature_name}:")
        print(f"  训练股票均值: {diff_info['training_mean']:.4f}")
        print(f"  '勉强可以'均值: {diff_info['good_mean']:.4f} (差异: {diff_info['diff_good']:.4f})")
        print(f"  '垃圾个股'均值: {diff_info['bad_mean']:.4f} (差异: {diff_info['diff_bad']:.4f})")
        print()
    
    return feature_differences, training_features, good_features, bad_features

def retrain_model_with_adjustments(feature_differences, training_features, good_features, bad_features):
    """根据特征差异重新训练模型"""
    print("=" * 80)
    print("🎓 重新训练模型（降低垃圾个股匹配度）")
    print("=" * 80)
    print()
    
    # 加载分析器
    analyzer = BullStockAnalyzer(auto_load_default_stocks=False, auto_analyze_and_train=False)
    
    # 添加训练股票
    for stock_code in TRAINING_STOCKS.keys():
        analyzer.add_bull_stock(stock_code)
    
    # 分析所有训练股票
    print("分析训练股票...")
    for stock_code in TRAINING_STOCKS.keys():
        analyzer.analyze_bull_stock(stock_code)
    
    # 训练特征
    print("训练特征模型...")
    train_result = analyzer.train_features()
    
    if not train_result.get('success'):
        print(f"❌ 训练失败: {train_result.get('message', '')}")
        return False
    
    # 调整特征模板，缩小标准差，使得垃圾个股的匹配度降低
    if analyzer.trained_features and 'common_features' in analyzer.trained_features:
        common_features = analyzer.trained_features['common_features']
        
        print("调整特征模板...")
        
        for feature_name, stats in common_features.items():
            if feature_name in feature_differences:
                diff_info = feature_differences[feature_name]
                
                # 如果垃圾个股与训练股票差异大，缩小标准差，使得偏离训练股票均值的特征值匹配度降低
                if diff_info['diff_bad'] > diff_info['diff_good'] * 1.5:
                    # 缩小标准差，使得垃圾个股的特征值（偏离训练股票均值）的z-score更大，匹配度更低
                    original_std = stats.get('标准差', 1.0)
                    # 将标准差缩小到原来的70%，使得偏离均值的特征值匹配度降低
                    new_std = original_std * 0.7
                    stats['标准差'] = new_std
                    print(f"  {feature_name}: 标准差 {original_std:.4f} -> {new_std:.4f}")
        
        print()
    
    # 保存模型
    model_path = 'models/模型11_优化.json'
    if analyzer.save_model(model_path):
        print(f"✅ 模型已保存到: {model_path}")
    else:
        print("❌ 模型保存失败")
        return False
    
    # 测试匹配度
    print()
    print("=" * 80)
    print("📊 测试匹配度")
    print("=" * 80)
    print()
    
    # 测试训练股票
    print("训练股票匹配度:")
    for stock_code, stock_name in TRAINING_STOCKS.items():
        if stock_code in training_features:
            features = training_features[stock_code]
            match_score = analyzer._calculate_match_score(
                features, 
                analyzer.trained_features['common_features'], 
                tolerance=0.3
            )
            total_match = match_score.get('总匹配度', 0)
            print(f"  {stock_code} {stock_name}: {total_match:.3f}")
    
    print()
    
    # 测试"勉强可以"股票
    print("'勉强可以'股票匹配度:")
    for stock_code, info in GOOD_STOCKS.items():
        if stock_code in good_features:
            features = good_features[stock_code]
            match_score = analyzer._calculate_match_score(
                features, 
                analyzer.trained_features['common_features'], 
                tolerance=0.3
            )
            total_match = match_score.get('总匹配度', 0)
            print(f"  {stock_code} {info['name']}: {total_match:.3f}")
    
    print()
    
    # 测试"垃圾个股"
    print("'垃圾个股'匹配度:")
    for stock_code, info in BAD_STOCKS.items():
        if stock_code in bad_features:
            features = bad_features[stock_code]
            match_score = analyzer._calculate_match_score(
                features, 
                analyzer.trained_features['common_features'], 
                tolerance=0.3
            )
            total_match = match_score.get('总匹配度', 0)
            print(f"  {stock_code} {info['name']}: {total_match:.3f}")
    
    return True

def main():
    # 分析特征差异
    result = analyze_feature_differences()
    if result is None:
        return
    
    feature_differences, training_features, good_features, bad_features = result
    
    # 重新训练模型
    success = retrain_model_with_adjustments(feature_differences, training_features, good_features, bad_features)
    
    if success:
        print()
        print("=" * 80)
        print("✅ 模型重新训练完成")
        print("=" * 80)
        print()
        print("新模型文件: models/模型11_优化.json")
        print()
        print("建议：使用新模型重新运行回测，验证垃圾个股的匹配度是否降低")

if __name__ == '__main__':
    main()
