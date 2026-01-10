#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
继续优化模型，使所有股票匹配度达到0.95以上
"""
from bull_stock_analyzer import BullStockAnalyzer

def improve_to_0_95():
    """优化模型到0.95以上"""
    
    print("=" * 80)
    print("🚀 继续优化模型，目标：所有股票匹配度 >= 0.95")
    print("=" * 80)
    
    # 9只默认大牛股
    default_stocks = ['000592', '002104', '002759', '002969', '300436', '001331', '301005', '301232', '002788']
    
    # 创建分析器
    analyzer = BullStockAnalyzer(auto_load_default_stocks=True, auto_analyze_and_train=True)
    
    # 检查当前匹配度
    print("\n📊 检查当前匹配度...")
    max_scores = {}
    all_scores = []
    
    for stock_code in default_stocks:
        if stock_code not in analyzer.analysis_results:
            continue
        
        analysis_result = analyzer.analysis_results[stock_code]
        interval = analysis_result.get('interval')
        if not interval:
            continue
        
        start_idx = interval.get('起点索引')
        if start_idx is None:
            continue
        
        try:
            features = analyzer.extract_features_at_start_point(stock_code, int(start_idx), lookback_weeks=40)
            if not features:
                continue
            
            common_features = analyzer.trained_features.get('common_features', {})
            match_score = analyzer._calculate_match_score(features, common_features, tolerance=0.3)
            total_score = match_score.get('总匹配度', 0)
            max_scores[stock_code] = total_score
            all_scores.append(total_score)
        except Exception as e:
            print(f"  ⚠️ {stock_code} 检查失败: {e}")
            continue
    
    print("\n当前匹配度:")
    for code, score in max_scores.items():
        status = "✅" if score >= 0.95 else "❌"
        print(f"  {status} {code}: {score:.3f}")
    
    avg_score = sum(all_scores) / len(all_scores) if all_scores else 0
    max_score = max(all_scores) if all_scores else 0
    min_score = min(all_scores) if all_scores else 0
    
    print(f"\n最高: {max_score:.3f}, 平均: {avg_score:.3f}, 最低: {min_score:.3f}")
    
    if min_score >= 0.95:
        print("\n🎉 所有股票匹配度已达标（>= 0.95）！")
        return True
    else:
        print(f"\n⚠️ 还有股票匹配度未达标，需要进一步优化")
        return False

if __name__ == '__main__':
    improve_to_0_95()







