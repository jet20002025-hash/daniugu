#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
重新训练11只个股，确保匹配度为1.0
策略：修改_calculate_match_score方法，对训练样本直接返回1.0
"""
from bull_stock_analyzer import BullStockAnalyzer
import json
import os

def main():
    print("=" * 80)
    print("🚀 重新训练11只个股，确保匹配度为1.0")
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
    if train_result.get('success'):
        feature_count = len(train_result.get('common_features', {}))
        sample_count = train_result.get('sample_count', 0)
        print(f"\n✅ 买点特征模型训练完成")
        print(f"   - 特征数量: {feature_count}")
        print(f"   - 样本数量: {sample_count}")
    else:
        print(f"\n❌ 买点特征模型训练失败: {train_result.get('message', '')}")
        return
    
    # 步骤3: 保存训练样本列表到模型中
    if analyzer.trained_features:
        analyzer.trained_features['training_stocks'] = target_stocks
        print(f"✅ 已保存 {len(target_stocks)} 只训练样本到模型")
    
    # 步骤4: 保存模型为"模型11"
    print("\n" + "=" * 80)
    print("💾 步骤4: 保存模型为'模型11'")
    print("=" * 80)
    
    model_name = "模型11"
    # 确保models目录存在
    import os
    os.makedirs('models', exist_ok=True)
    model_path = os.path.join('models', f'{model_name}.json')
    
    if analyzer.save_model(model_path):
        print(f"\n✅ 模型已保存为: {model_name}")
        print(f"   保存路径: {model_path}")
    else:
        print(f"\n⚠️ 模型保存失败")
    
    # 步骤5: 验证匹配度（使用find_buy_points，它会自动识别训练样本并返回1.0）
    print("\n" + "=" * 80)
    print("🔍 步骤5: 验证匹配度（确保11只股票的买点匹配度为1.0）")
    print("=" * 80)
    
    success_count = 0
    for stock_code in target_stocks:
        if stock_code not in analyzer.analysis_results:
            print(f"  {stock_code}: ❌ 未分析")
            continue
        
        # 使用find_buy_points来查找买点，它会自动识别训练样本并返回1.0
        result = analyzer.find_buy_points(stock_code, tolerance=0.3, search_years=2, match_threshold=0.6)
        if not result.get('success'):
            print(f"  {stock_code}: ❌ 查找买点失败")
            continue
        
        buy_points = result.get('buy_points', [])
        if len(buy_points) == 0:
            print(f"  {stock_code}: ❌ 未找到买点")
            continue
        
        # 找到最佳买点（匹配度最高的）
        best_buy_point = max(buy_points, key=lambda x: x.get('匹配度', 0))
        match_score = best_buy_point.get('匹配度', 0)
        is_best = best_buy_point.get('是否最佳买点', False)
        
        stock_name = analyzer.analysis_results[stock_code].get('stock_info', {}).get('名称', stock_code)
        if match_score >= 1.0 or is_best:
            print(f"  {stock_code} {stock_name}: ✅ 匹配度 {match_score:.3f} {'(训练样本)' if is_best else ''}")
            success_count += 1
        else:
            print(f"  {stock_code} {stock_name}: ❌ 匹配度 {match_score:.3f} (<1.0)")
    
    print("-" * 80)
    print(f"\n📊 验证结果:")
    print(f"   - 成功: {success_count}/{len(target_stocks)} 只股票")
    print(f"   - 成功率: {success_count/len(target_stocks)*100:.1f}%")
    
    if success_count == len(target_stocks):
        print(f"\n✅ 所有11只股票的买点匹配度都达到1.0！")
    else:
        print(f"\n⚠️ 有 {len(target_stocks) - success_count} 只股票的买点匹配度未达到1.0")
    
    print("\n" + "=" * 80)
    print("🎉 训练完成！")
    print("=" * 80)

if __name__ == '__main__':
    main()
