#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
改进模型，使最高匹配度达到0.8以上
"""
from bull_stock_analyzer import BullStockAnalyzer
import json

def improve_model():
    """改进模型，提高匹配度到0.8以上"""
    
    print("=" * 80)
    print("🚀 开始改进模型，目标：最高匹配度 >= 0.8")
    print("=" * 80)
    
    # 9只默认大牛股
    default_stocks = ['000592', '002104', '002759', '002969', '300436', '001331', '301005', '301232', '002788']
    
    # 创建分析器
    analyzer = BullStockAnalyzer(auto_load_default_stocks=True)
    
    # 1. 分析所有股票
    print("\n📊 步骤1: 分析所有大牛股...")
    for stock_code in default_stocks:
        print(f"  分析 {stock_code}...", end=" ", flush=True)
        result = analyzer.analyze_bull_stock(stock_code)
        if result.get('success'):
            print("✅")
        else:
            print(f"❌ {result.get('message', '')}")
    
    # 2. 训练特征模型
    print("\n🎓 步骤2: 训练特征模型...")
    train_result = analyzer.train_features()
    if not train_result.get('success'):
        print(f"❌ 训练失败: {train_result.get('message', '')}")
        return
    
    print(f"✅ 训练完成，特征数: {train_result.get('feature_count', 0)}")
    
    # 3. 测试每只股票的匹配度
    print("\n🔍 步骤3: 测试匹配度...")
    print("=" * 80)
    
    max_scores = {}
    all_scores = []
    
    for stock_code in default_stocks:
        print(f"\n测试 {stock_code}...", end=" ", flush=True)
        
        # 获取该股票的起点特征
        if stock_code not in analyzer.analysis_results:
            print("❌ 未找到分析结果")
            continue
        
        analysis_result = analyzer.analysis_results[stock_code]
        interval = analysis_result.get('interval')
        if not interval:
            print("❌ 未找到涨幅区间")
            continue
        
        start_idx = interval.get('起点索引')
        if start_idx is None:
            print("❌ 未找到起点索引")
            continue
        
        # 提取该股票起点的特征
        features = analyzer.extract_features_at_start_point(stock_code, int(start_idx), lookback_weeks=40)
        if not features:
            print("❌ 特征提取失败")
            continue
        
        # 计算与训练模型的匹配度
        common_features = analyzer.trained_features.get('common_features', {})
        match_score = analyzer._calculate_match_score(features, common_features, tolerance=0.3)
        
        total_score = match_score.get('总匹配度', 0)
        max_scores[stock_code] = total_score
        all_scores.append(total_score)
        
        print(f"匹配度: {total_score:.3f}")
        print(f"  核心特征匹配: {match_score.get('核心特征匹配', {})}")
    
    print("\n" + "=" * 80)
    print("📊 匹配度统计")
    print("=" * 80)
    
    for stock_code, score in max_scores.items():
        status = "✅" if score >= 0.8 else "❌"
        print(f"{status} {stock_code}: {score:.3f}")
    
    avg_score = sum(all_scores) / len(all_scores) if all_scores else 0
    max_score = max(all_scores) if all_scores else 0
    min_score = min(all_scores) if all_scores else 0
    
    print(f"\n最高匹配度: {max_score:.3f}")
    print(f"平均匹配度: {avg_score:.3f}")
    print(f"最低匹配度: {min_score:.3f}")
    
    if max_score >= 0.8:
        print("\n🎉 成功！最高匹配度已达到 0.8 以上！")
    else:
        print(f"\n⚠️ 最高匹配度 {max_score:.3f} 低于 0.8，需要进一步优化")
        print("\n💡 优化建议:")
        print("   1. 检查特征提取是否准确")
        print("   2. 调整匹配算法，提高核心特征权重")
        print("   3. 优化容差计算方式")
        print("   4. 考虑使用更精确的特征归一化方法")
    
    return max_scores

if __name__ == '__main__':
    improve_model()







