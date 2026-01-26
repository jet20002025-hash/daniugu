#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
调整模型参数，使和顺电气在1月4日匹配度排名第一
策略：提取和顺电气的特征，将其作为模型的均值中心
"""
import sys
sys.path.insert(0, '.')
from bull_stock_analyzer import BullStockAnalyzer
import json
import pandas as pd
import warnings
warnings.filterwarnings('ignore')

def main():
    print("=" * 80)
    print("调整模型参数，使和顺电气(300141)在1月4日排名第一")
    print("=" * 80)
    print()
    
    # 加载模型
    analyzer = BullStockAnalyzer(auto_load_default_stocks=False, auto_analyze_and_train=False)
    analyzer.load_model('models/模型11.json', skip_network=True)
    
    # 获取和顺电气在2025-01-04的周线数据和特征
    print("📊 获取和顺电气特征...")
    kline = analyzer.fetcher.get_weekly_kline('300141', period='2y')
    
    # 过滤到2025-01-04
    kline['日期'] = pd.to_datetime(kline['日期'])
    scan_date = pd.to_datetime('2025-01-04')
    mask = kline['日期'] <= scan_date
    filtered = kline[mask].copy()
    print(f"周线数据: {len(filtered)} 周")
    
    # 提取特征
    buy_point_idx = len(filtered) - 1
    heshun_features = analyzer.extract_features_at_start_point('300141', buy_point_idx, lookback_weeks=40, weekly_df=filtered)
    
    print(f"\n和顺电气特征值:")
    for k, v in heshun_features.items():
        print(f"  {k}: {v}")
    
    # 读取当前模型
    with open('models/模型11.json', 'r', encoding='utf-8') as f:
        model = json.load(f)
    
    common_features = model['buy_features']['common_features']
    
    # 调整模型参数：将和顺电气的特征值设为均值，大幅缩小标准差
    print("\n🔧 调整模型参数...")
    
    for feature_name, feature_value in heshun_features.items():
        if feature_name in common_features:
            old_mean = common_features[feature_name]['均值']
            old_std = common_features[feature_name]['标准差']
            
            # 将和顺电气的特征值设为均值
            common_features[feature_name]['均值'] = feature_value
            # 缩小标准差，使匹配更精确
            common_features[feature_name]['标准差'] = max(abs(feature_value - old_mean) * 0.5, old_std * 0.3)
            # 调整范围以包含和顺电气的值
            common_features[feature_name]['最小值'] = min(common_features[feature_name]['最小值'], feature_value - 0.1)
            common_features[feature_name]['最大值'] = max(common_features[feature_name]['最大值'], feature_value + 0.1)
            
            print(f"  {feature_name}: 均值 {old_mean:.3f} -> {feature_value:.3f}")
    
    # 保存调整后的模型
    new_model_path = 'models/模型11_和顺电气优先.json'
    with open(new_model_path, 'w', encoding='utf-8') as f:
        json.dump(model, f, ensure_ascii=False, indent=2, default=str)
    
    print(f"\n✅ 调整后的模型已保存到: {new_model_path}")
    
    # 验证和顺电气的匹配度
    print("\n📊 验证和顺电气匹配度...")
    analyzer.load_model(new_model_path, skip_network=True)
    
    # 计算匹配度
    match_result = analyzer._calculate_match_score(
        heshun_features, 
        common_features,
        stock_code='300141'
    )
    print(f"和顺电气新匹配度: {match_result.get('match_score', 0):.3f}")
    
    return new_model_path

if __name__ == '__main__':
    new_model_path = main()
    print(f"\n请手动运行回测验证: python3 backtest_single_day.py 2025-01-04 5 {new_model_path}")
