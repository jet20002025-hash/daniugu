#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基于11只大牛股重新训练模型，确保11只股票的买点全部符合要求
"""
from bull_stock_analyzer import BullStockAnalyzer
import json
import os

def main():
    print("=" * 80)
    print("🚀 基于11只大牛股重新训练模型")
    print("=" * 80)
    
    # 11只大牛股列表
    target_stocks = ['000592', '002104', '002759', '300436', '301005', '301232', '002788', '603778', '603122', '600343', '603216']
    
    print(f"\n📊 目标股票: {', '.join(target_stocks)}")
    print(f"   共 {len(target_stocks)} 只股票")
    
    # 创建分析器（不自动训练，手动控制）
    print("\n初始化分析器...")
    analyzer = BullStockAnalyzer(auto_load_default_stocks=True, auto_analyze_and_train=False)
    
    # 清空现有的分析结果和训练模型
    print("\n清理现有数据...")
    analyzer.analysis_results = {}
    analyzer.trained_features = None
    analyzer.bull_stocks = []
    
    # 确保所有11只股票都已添加
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
    if train_result.get('success'):
        feature_count = len(train_result.get('common_features', {}))
        sample_count = train_result.get('sample_count', 0)
        print(f"\n✅ 买点特征模型训练完成")
        print(f"   - 特征数量: {feature_count}")
        print(f"   - 样本数量: {sample_count}")
    else:
        print(f"\n❌ 买点特征模型训练失败: {train_result.get('message', '')}")
        return
    
    # 步骤3: 保存模型
    print("\n" + "=" * 80)
    print("💾 步骤3: 保存模型")
    print("=" * 80)
    
    model_path = 'trained_model.json'
    if analyzer.save_model(model_path):
        print(f"\n✅ 模型已保存到: {model_path}")
    else:
        print(f"\n⚠️ 模型保存失败")
    
    # 步骤4: 验证匹配度 - 确保11只股票的买点全部符合要求
    print("\n" + "=" * 80)
    print("🔍 步骤4: 验证匹配度（确保11只股票的买点全部符合要求）")
    print("=" * 80)
    
    # 检查匹配度
    is_ready, max_score = analyzer._check_match_score()
    print(f"\n匹配度检查结果:")
    print(f"   - 最高匹配度: {max_score:.3f}")
    print(f"   - 是否达标 (>=0.8): {'✅ 是' if is_ready else '❌ 否'}")
    
    # 测试每只股票的买点匹配度
    print(f"\n测试每只股票的买点匹配度:")
    print("-" * 80)
    
    success_count = 0
    for stock_code in target_stocks:
        if stock_code not in analyzer.analysis_results:
            print(f"  {stock_code}: ❌ 未分析")
            continue
        
        analysis_result = analyzer.analysis_results[stock_code]
        interval = analysis_result.get('interval')
        if not interval or interval.get('起点索引') is None:
            print(f"  {stock_code}: ❌ 无有效买点")
            continue
        
        # 获取特征
        start_idx = interval.get('起点索引')
        weekly_df = analyzer.fetcher.get_weekly_kline(stock_code, period="2y")
        if weekly_df is None or len(weekly_df) == 0:
            print(f"  {stock_code}: ❌ 无法获取数据")
            continue
        
        # 提取特征
        features = analyzer.extract_features_at_start_point(stock_code, start_idx, lookback_weeks=40, weekly_df=weekly_df)
        if features is None:
            print(f"  {stock_code}: ❌ 特征提取失败")
            continue
        
        # 计算匹配度
        match_score = analyzer._calculate_match_score(features, analyzer.trained_features['common_features'], tolerance=0.3)
        total_match = match_score.get('总匹配度', 0)
        
        stock_name = analysis_result.get('stock_info', {}).get('名称', stock_code)
        if total_match >= 0.6:  # 使用扫描时的阈值
            print(f"  {stock_code} {stock_name}: ✅ 匹配度 {total_match:.3f}")
            success_count += 1
        else:
            print(f"  {stock_code} {stock_name}: ❌ 匹配度 {total_match:.3f} (低于0.6)")
    
    print("-" * 80)
    print(f"\n📊 验证结果:")
    print(f"   - 成功: {success_count}/{len(target_stocks)} 只股票")
    print(f"   - 成功率: {success_count/len(target_stocks)*100:.1f}%")
    
    if success_count == len(target_stocks):
        print(f"\n✅ 所有11只股票的买点都符合要求！")
    else:
        print(f"\n⚠️ 有 {len(target_stocks) - success_count} 只股票的买点不符合要求")
    
    print("\n" + "=" * 80)
    print("🎉 训练完成！")
    print("=" * 80)

if __name__ == '__main__':
    main()
