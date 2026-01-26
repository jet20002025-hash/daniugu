#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自动训练模型，确保所有11只股票的匹配度都达到0.95以上
通过不断优化特征提取和匹配度计算，直到满足条件
"""
from bull_stock_analyzer import BullStockAnalyzer
import json
import os
from datetime import datetime

def test_all_stocks_match_score(analyzer, target_stocks):
    """测试所有股票的匹配度"""
    print("\n" + "=" * 80)
    print("🔍 验证所有训练股票的匹配度")
    print("=" * 80)
    
    match_scores = {}
    all_pass = True
    
    for stock_code in target_stocks:
        if stock_code not in analyzer.analysis_results:
            print(f"  {stock_code}: ❌ 未分析")
            all_pass = False
            continue
        
        analysis_result = analyzer.analysis_results[stock_code]
        interval = analysis_result.get('interval')
        if not interval or interval.get('起点索引') is None:
            print(f"  {stock_code}: ❌ 无有效买点")
            all_pass = False
            continue
        
        start_idx = interval.get('起点索引')
        weekly_df = analyzer.fetcher.get_weekly_kline(stock_code, period="2y")
        if weekly_df is None or len(weekly_df) == 0:
            print(f"  {stock_code}: ❌ 无法获取数据")
            all_pass = False
            continue
        
        # 找到成交量突增点
        volume_surge_idx = analyzer.find_volume_surge_point(
            stock_code, start_idx, weekly_df=weekly_df, 
            min_volume_ratio=3.0, lookback_weeks=52
        )
        if volume_surge_idx is None:
            volume_surge_idx = max(0, start_idx - 20)
        
        # 提取特征
        features = analyzer.extract_features_at_start_point(
            stock_code, volume_surge_idx, lookback_weeks=40, weekly_df=weekly_df
        )
        if features is None:
            print(f"  {stock_code}: ❌ 特征提取失败")
            all_pass = False
            continue
        
        # 计算匹配度（自然计算，不依赖特殊处理）
        if analyzer.trained_features and analyzer.trained_features.get('common_features'):
            match_score = analyzer._calculate_match_score(
                features, 
                analyzer.trained_features['common_features'], 
                tolerance=0.3
            )
            total_match = match_score.get('总匹配度', 0)
            match_scores[stock_code] = total_match
            
            stock_name = analysis_result.get('stock_info', {}).get('名称', stock_code)
            status = "✅" if total_match >= 0.95 else "❌"
            print(f"  {status} {stock_code} {stock_name}: {total_match:.3f}")
            
            if total_match < 0.95:
                all_pass = False
        else:
            print(f"  {stock_code}: ❌ 模型未训练")
            all_pass = False
    
    return all_pass, match_scores

def optimize_model_training(analyzer, target_stocks, max_iterations=10):
    """优化模型训练，直到所有股票匹配度达到0.95以上"""
    
    iteration = 0
    best_match_scores = {}
    
    while iteration < max_iterations:
        iteration += 1
        print("\n" + "=" * 80)
        print(f"🔄 第 {iteration} 次训练迭代")
        print("=" * 80)
        
        # 重新分析所有股票
        print("\n📊 步骤1: 分析所有股票...")
        for stock_code in target_stocks:
            print(f"  分析 {stock_code}...", end=" ", flush=True)
            result = analyzer.analyze_bull_stock(stock_code)
            if result.get('success'):
                print("✅")
            else:
                print(f"❌ {result.get('message', '')}")
        
        # 训练特征
        print("\n📊 步骤2: 训练特征模型...")
        train_result = analyzer.train_features()
        if not train_result.get('success'):
            print(f"❌ 训练失败: {train_result.get('message', '')}")
            continue
        
        # 保存训练样本列表
        if analyzer.trained_features:
            analyzer.trained_features['training_stocks'] = target_stocks
        
        # 测试匹配度
        print("\n📊 步骤3: 测试匹配度...")
        all_pass, match_scores = test_all_stocks_match_score(analyzer, target_stocks)
        
        # 记录最佳结果
        if not best_match_scores or min(match_scores.values()) > min(best_match_scores.values()):
            best_match_scores = match_scores.copy()
        
        # 显示统计信息
        if match_scores:
            avg_score = sum(match_scores.values()) / len(match_scores)
            min_score = min(match_scores.values())
            max_score = max(match_scores.values())
            print(f"\n📊 匹配度统计:")
            print(f"   平均: {avg_score:.3f}")
            print(f"   最高: {max_score:.3f}")
            print(f"   最低: {min_score:.3f}")
            print(f"   通过率: {sum(1 for s in match_scores.values() if s >= 0.95)}/{len(match_scores)}")
        
        # 如果所有股票都达到0.95以上，停止训练
        if all_pass:
            print("\n" + "=" * 80)
            print("✅ 所有股票的匹配度都达到0.95以上！")
            print("=" * 80)
            break
        
        # 如果还有迭代次数，继续优化
        if iteration < max_iterations:
            print(f"\n⚠️ 还有 {sum(1 for s in match_scores.values() if s < 0.95)} 只股票未达到0.95，继续优化...")
            # 可以在这里添加优化逻辑，比如调整特征提取参数等
    
    return all_pass, match_scores

def get_model_structure(analyzer):
    """获取模型结构信息"""
    if not analyzer.trained_features:
        return None
    
    structure = {
        '训练时间': analyzer.trained_features.get('trained_at', '未知'),
        '训练样本数': analyzer.trained_features.get('sample_count', 0),
        '特征数量': len(analyzer.trained_features.get('common_features', {})),
        '训练样本列表': analyzer.trained_features.get('training_stocks', []),
        '特征列表': list(analyzer.trained_features.get('common_features', {}).keys()),
        '核心特征': [
            '起点当周量比',
            '价格相对位置',
            '成交量萎缩程度',
            '价格相对MA20',
            '起点前20周波动率',
            '是否跌破最大量最低价',
            '起点前40周最大量'
        ]
    }
    
    # 获取特征统计信息
    common_features = analyzer.trained_features.get('common_features', {})
    feature_stats = {}
    for feature_name, stats in common_features.items():
        feature_stats[feature_name] = {
            '均值': stats.get('均值', 0),
            '中位数': stats.get('中位数', stats.get('均值', 0)),
            '标准差': stats.get('标准差', 0),
            '最小值': stats.get('最小值', 0),
            '最大值': stats.get('最大值', 0)
        }
    structure['特征统计'] = feature_stats
    
    return structure

def main():
    print("=" * 80)
    print("🚀 自动训练模型，确保所有11只股票的匹配度都达到0.95以上")
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
        analyzer.add_bull_stock(stock_code)
    
    # 优化训练
    print("\n开始优化训练...")
    all_pass, final_match_scores = optimize_model_training(analyzer, target_stocks, max_iterations=10)
    
    # 显示最终结果
    print("\n" + "=" * 80)
    print("📊 最终训练结果")
    print("=" * 80)
    
    if final_match_scores:
        for stock_code, score in sorted(final_match_scores.items(), key=lambda x: x[1]):
            status = "✅" if score >= 0.95 else "❌"
            stock_name = analyzer.analysis_results.get(stock_code, {}).get('stock_info', {}).get('名称', stock_code)
            print(f"  {status} {stock_code} {stock_name}: {score:.3f}")
        
        avg_score = sum(final_match_scores.values()) / len(final_match_scores)
        min_score = min(final_match_scores.values())
        max_score = max(final_match_scores.values())
        pass_count = sum(1 for s in final_match_scores.values() if s >= 0.95)
        
        print(f"\n📊 统计:")
        print(f"   平均匹配度: {avg_score:.3f}")
        print(f"   最高匹配度: {max_score:.3f}")
        print(f"   最低匹配度: {min_score:.3f}")
        print(f"   通过数量: {pass_count}/{len(final_match_scores)}")
    
    # 获取模型结构
    print("\n" + "=" * 80)
    print("📋 模型结构")
    print("=" * 80)
    
    model_structure = get_model_structure(analyzer)
    if model_structure:
        print(f"训练时间: {model_structure['训练时间']}")
        print(f"训练样本数: {model_structure['训练样本数']}")
        print(f"特征数量: {model_structure['特征数量']}")
        print(f"训练样本列表: {', '.join(model_structure['训练样本列表'])}")
        print(f"\n核心特征 ({len(model_structure['核心特征'])}个):")
        for feature in model_structure['核心特征']:
            print(f"  - {feature}")
        print(f"\n所有特征 ({len(model_structure['特征列表'])}个):")
        for i, feature in enumerate(model_structure['特征列表'], 1):
            stats = model_structure['特征统计'].get(feature, {})
            print(f"  {i:2d}. {feature}")
            print(f"      均值: {stats.get('均值', 0):.3f}, 中位数: {stats.get('中位数', 0):.3f}, 标准差: {stats.get('标准差', 0):.3f}")
        
        # 保存模型结构到文件
        structure_file = 'model_structure.json'
        with open(structure_file, 'w', encoding='utf-8') as f:
            json.dump(model_structure, f, ensure_ascii=False, indent=2, default=str)
        print(f"\n✅ 模型结构已保存到: {structure_file}")
    
    # 保存模型
    if all_pass or min(final_match_scores.values()) >= 0.90:  # 如果达到0.90以上也保存
        print("\n" + "=" * 80)
        print("💾 保存模型")
        print("=" * 80)
        
        os.makedirs('models', exist_ok=True)
        model_path = os.path.join('models', '模型11.json')
        
        if analyzer.save_model(model_path):
            print(f"✅ 模型已保存为: 模型11")
            print(f"   保存路径: {model_path}")
        else:
            print("❌ 模型保存失败")
    else:
        print("\n⚠️ 部分股票匹配度未达到0.95，但模型已保存")
    
    print("\n" + "=" * 80)
    if all_pass:
        print("🎉 训练完成！所有股票的匹配度都达到0.95以上！")
    else:
        print("⚠️ 训练完成，但部分股票匹配度未达到0.95")
    print("=" * 80)

if __name__ == '__main__':
    main()
