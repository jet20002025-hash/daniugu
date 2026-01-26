#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
重新训练模型，确保所有训练股票的匹配度都达到1.0
"""
from bull_stock_analyzer import BullStockAnalyzer
import json
import os

def test_all_stocks_match_score(analyzer, target_stocks):
    """测试所有股票的匹配度"""
    print("\n" + "=" * 80)
    print("🔍 验证所有训练股票的匹配度")
    print("=" * 80)
    
    success_count = 0
    match_scores = {}
    
    for stock_code in target_stocks:
        if stock_code not in analyzer.analysis_results:
            print(f"  {stock_code}: ❌ 未分析")
            continue
        
        analysis_result = analyzer.analysis_results[stock_code]
        interval = analysis_result.get('interval')
        if not interval or interval.get('起点索引') is None:
            print(f"  {stock_code}: ❌ 无有效买点")
            continue
        
        start_idx = interval.get('起点索引')
        weekly_df = analyzer.fetcher.get_weekly_kline(stock_code, period="2y")
        if weekly_df is None or len(weekly_df) == 0:
            print(f"  {stock_code}: ❌ 无法获取数据")
            continue
        
        # 找到成交量突增点
        volume_surge_idx = analyzer.find_volume_surge_point(stock_code, start_idx, weekly_df=weekly_df, min_volume_ratio=3.0, lookback_weeks=52)
        if volume_surge_idx is None:
            volume_surge_idx = max(0, start_idx - 20)
        
        # 提取特征
        features = analyzer.extract_features_at_start_point(stock_code, volume_surge_idx, lookback_weeks=40, weekly_df=weekly_df)
        if features is None:
            print(f"  {stock_code}: ❌ 特征提取失败")
            continue
        
        # 计算匹配度
        match_score = analyzer._calculate_match_score(features, analyzer.trained_features['common_features'], tolerance=0.3)
        total_match = match_score.get('总匹配度', 0)
        match_scores[stock_code] = total_match
        
        stock_name = analysis_result.get('stock_info', {}).get('名称', stock_code)
        if total_match >= 1.0:
            print(f"  {stock_code} {stock_name}: ✅ 匹配度 {total_match:.3f}")
            success_count += 1
        else:
            print(f"  {stock_code} {stock_name}: ❌ 匹配度 {total_match:.3f} (<1.0)")
    
    print("-" * 80)
    print(f"\n📊 验证结果:")
    print(f"   - 成功: {success_count}/{len(target_stocks)} 只股票")
    print(f"   - 成功率: {success_count/len(target_stocks)*100:.1f}%")
    
    return success_count == len(target_stocks), match_scores

def main():
    print("=" * 80)
    print("🚀 重新训练模型（确保所有训练股票匹配度达到1.0）")
    print("=" * 80)
    
    # 11只大牛股列表
    target_stocks = ['000592', '002104', '002759', '300436', '301005', '301232', '002788', '603778', '603122', '600343', '603216']
    
    print(f"\n📊 目标股票: {', '.join(target_stocks)}")
    print(f"   共 {len(target_stocks)} 只股票")
    
    # 创建分析器
    print("\n初始化分析器...")
    analyzer = BullStockAnalyzer(auto_load_default_stocks=False, auto_analyze_and_train=False)
    
    # 清空现有数据
    analyzer.analysis_results = {}
    analyzer.trained_features = None
    analyzer.bull_stocks = []
    
    # 添加所有11只股票
    print("\n添加11只目标股票...")
    for stock_code in target_stocks:
        result = analyzer.add_bull_stock(stock_code)
        if result.get('success'):
            print(f"  ✅ 已添加: {stock_code} {result.get('stock', {}).get('名称', '')}")
        else:
            print(f"  ⚠️ 添加失败: {stock_code} - {result.get('message', '')}")
    
    print(f"\n✅ 已加载 {len(analyzer.bull_stocks)} 只大牛股")
    
    # 步骤1: 分析所有11只大牛股
    print("\n" + "=" * 80)
    print("📊 步骤1: 分析所有大牛股（找到涨幅最大区间）")
    print("=" * 80)
    
    analyzed_count = 0
    for i, stock in enumerate(analyzer.bull_stocks, 1):
        stock_code = stock['代码']
        stock_name = stock['名称']
        print(f"\n[{i}/{len(analyzer.bull_stocks)}] 分析 {stock_name} ({stock_code})...")
        result = analyzer.analyze_bull_stock(stock_code)
        if result.get('success'):
            interval = result.get('interval', {})
            gain = interval.get('涨幅', 0)
            start_date = interval.get('起点日期', '')
            print(f"  ✅ 分析完成: 涨幅 {gain:.2f}%, 起点日期: {start_date}")
            analyzed_count += 1
        else:
            print(f"  ❌ 分析失败: {result.get('message', '')}")
    
    print(f"\n✅ 分析完成，共分析 {analyzed_count}/{len(analyzer.bull_stocks)} 只股票")
    
    if analyzed_count == 0:
        print("\n❌ 没有成功分析的股票，无法训练模型")
        return
    
    # 步骤2: 训练买点特征模型
    print("\n" + "=" * 80)
    print("🎓 步骤2: 训练买点特征模型")
    print("=" * 80)
    
    train_result = analyzer.train_features()
    if not train_result.get('success'):
        print(f"\n❌ 买点特征模型训练失败: {train_result.get('message', '')}")
        return
    
    feature_count = len(train_result.get('common_features', {}))
    sample_count = train_result.get('sample_count', 0)
    print(f"\n✅ 买点特征模型训练完成")
    print(f"   - 特征数量: {feature_count}")
    print(f"   - 样本数量: {sample_count}")
    
    # 步骤3: 调整匹配度计算，让所有训练股票匹配度达到1.0
    print("\n" + "=" * 80)
    print("🔧 步骤3: 调整匹配度计算（让所有训练股票匹配度达到1.0）")
    print("=" * 80)
    
    # 策略：修改common_features，让每个特征的范围覆盖所有训练样本
    # 这样每只训练股票的匹配度都会达到1.0
    print("\n调整特征模板范围，确保覆盖所有训练样本...")
    
    if not analyzer.trained_features or not analyzer.trained_features.get('common_features'):
        print("❌ 训练特征为空，无法调整")
        return
    
    common_features = analyzer.trained_features['common_features']
    
    # 重新计算特征范围，确保所有训练样本都在范围内
    all_features_list = []
    for stock_code in target_stocks:
        if stock_code not in analyzer.analysis_results:
            continue
        
        analysis_result = analyzer.analysis_results[stock_code]
        interval = analysis_result.get('interval')
        if not interval or interval.get('起点索引') is None:
            continue
        
        start_idx = interval.get('起点索引')
        weekly_df = analyzer.fetcher.get_weekly_kline(stock_code, period="2y")
        if weekly_df is None or len(weekly_df) == 0:
            continue
        
        # 找到成交量突增点
        volume_surge_idx = analyzer.find_volume_surge_point(stock_code, start_idx, weekly_df=weekly_df, min_volume_ratio=3.0, lookback_weeks=52)
        if volume_surge_idx is None:
            volume_surge_idx = max(0, start_idx - 20)
        
        # 提取特征
        features = analyzer.extract_features_at_start_point(stock_code, volume_surge_idx, lookback_weeks=40, weekly_df=weekly_df)
        if features:
            all_features_list.append(features)
    
    if len(all_features_list) == 0:
        print("❌ 无法提取特征，无法调整")
        return
    
    # 重新计算特征统计值，扩大范围
    print(f"\n重新计算 {len(all_features_list)} 只股票的特征统计值...")
    
    adjusted_features = {}
    feature_names = set()
    
    for features in all_features_list:
        feature_names.update([k for k in features.keys() if k not in ['股票代码', '股票名称', '起点日期']])
    
    for feature_name in feature_names:
        values = []
        for features in all_features_list:
            if feature_name in features:
                val = features[feature_name]
                if isinstance(val, (int, float)) and not pd.isna(val):
                    values.append(float(val))
        
        if len(values) > 0:
            import numpy as np
            min_val = min(values)
            max_val = max(values)
            mean_val = np.mean(values)
            median_val = np.median(values)
            std_val = np.std(values)
            
            # 扩大范围，确保所有值都在范围内（添加20%的缓冲）
            range_val = max_val - min_val
            if range_val > 0:
                buffer = range_val * 0.2  # 20%缓冲
                min_val = min_val - buffer
                max_val = max_val + buffer
            else:
                # 如果所有值相同，添加小范围
                buffer = abs(mean_val) * 0.1 if mean_val != 0 else 0.1
                min_val = mean_val - buffer
                max_val = mean_val + buffer
            
            # 调整标准差，使其能够覆盖所有值
            # 使用3倍标准差覆盖99.7%的数据
            if std_val > 0:
                adjusted_std = max(std_val, (max_val - min_val) / 6)
            else:
                adjusted_std = (max_val - min_val) / 6 if (max_val - min_val) > 0 else 0.1
            
            adjusted_features[feature_name] = {
                '均值': round(float(mean_val), 3),
                '中位数': round(float(median_val), 3),
                '最小值': round(float(min_val), 3),
                '最大值': round(float(max_val), 3),
                '标准差': round(float(adjusted_std), 3),
                '样本数': len(values)
            }
    
    # 更新训练特征
    analyzer.trained_features['common_features'] = adjusted_features
    
    print(f"✅ 特征模板已调整，共 {len(adjusted_features)} 个特征")
    
    # 步骤4: 验证匹配度
    print("\n" + "=" * 80)
    print("🔍 步骤4: 验证匹配度（确保所有训练股票匹配度达到1.0）")
    print("=" * 80)
    
    all_perfect, match_scores = test_all_stocks_match_score(analyzer, target_stocks)
    
    if not all_perfect:
        print("\n⚠️ 部分股票的匹配度未达到1.0，尝试进一步调整...")
        # 可以进一步调整，但这里先保存模型
    
    # 步骤5: 保存模型
    print("\n" + "=" * 80)
    print("💾 步骤5: 保存模型")
    print("=" * 80)
    
    model_path = 'trained_model.json'
    if analyzer.save_model(model_path):
        print(f"\n✅ 模型已保存到: {model_path}")
    else:
        print(f"\n⚠️ 模型保存失败")
    
    print("\n" + "=" * 80)
    if all_perfect:
        print("🎉 所有训练股票的匹配度都达到1.0！")
    else:
        print("⚠️ 部分训练股票的匹配度未达到1.0")
        print(f"   匹配度详情:")
        for stock_code, score in match_scores.items():
            print(f"   - {stock_code}: {score:.3f}")
    print("=" * 80)

if __name__ == '__main__':
    import pandas as pd
    import numpy as np
    main()
