#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
训练基础模型脚本
自动完成：
1. 分析所有11只大牛股
2. 训练特征模型（自动验证和调整，确保匹配度>=0.95）
3. 保存模型
"""
import sys
sys.path.insert(0, '.')
from bull_stock_analyzer import BullStockAnalyzer
import json
from datetime import datetime
import os

def train_base_model():
    """训练基础模型"""
    print("=" * 80)
    print("🚀 开始训练基础模型")
    print("=" * 80)
    
    # 创建分析器（不自动加载和训练，手动控制）
    analyzer = BullStockAnalyzer(
        auto_load_default_stocks=True,
        auto_analyze_and_train=False
    )
    
    print(f"\n✅ 已加载 {len(analyzer.bull_stocks)} 只大牛股")
    print(f"   股票列表: {', '.join([s['代码'] for s in analyzer.bull_stocks])}")
    
    # 步骤1: 分析所有大牛股（找到涨幅最大区间）
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
            start_price = interval.get('起点价格', 0)
            print(f"  ✅ 分析完成: 涨幅 {gain:.2f}%, 起点日期: {start_date}, 起点价格: {start_price:.2f}元")
            analyzed_count += 1
        else:
            print(f"  ❌ 分析失败: {result.get('message', '')}")
    
    print(f"\n✅ 分析完成，共分析 {analyzed_count}/{len(analyzer.bull_stocks)} 只股票")
    
    if analyzed_count == 0:
        print("\n❌ 没有成功分析的股票，无法训练模型")
        return False
    
    # 步骤2: 训练买点特征模型（会自动验证和调整）
    print("\n" + "=" * 80)
    print("🎓 步骤2: 训练买点特征模型（自动验证和调整，确保匹配度>=0.95）")
    print("=" * 80)
    
    train_result = analyzer.train_features()
    
    if not train_result.get('success'):
        print(f"\n❌ 买点特征模型训练失败: {train_result.get('message', '')}")
        return False
    
    feature_count = len(train_result.get('common_features', {}))
    sample_count = train_result.get('sample_count', 0)
    all_pass = train_result.get('all_pass', False)
    iterations = train_result.get('iterations', 0)
    match_scores = train_result.get('match_scores', {})
    
    print(f"\n✅ 买点特征模型训练完成")
    print(f"   - 特征数量: {feature_count}")
    print(f"   - 样本数量: {sample_count}")
    print(f"   - 迭代次数: {iterations}")
    print(f"   - 所有样本达标: {'是' if all_pass else '否'}")
    
    if match_scores:
        print(f"\n📊 训练样本匹配度详情:")
        for stock_code, info in match_scores.items():
            status = "✅" if info.get('达标', False) else "❌"
            print(f"   {status} {stock_code} {info.get('股票名称', '')}: {info.get('匹配度', 0):.3f}")
    
    if not all_pass:
        print(f"\n⚠️ 警告: 部分训练样本的匹配度未达到0.95")
        print(f"   建议: 检查训练样本的特征是否一致，或调整训练逻辑")
    
    # 步骤3: 保存模型
    print("\n" + "=" * 80)
    print("💾 步骤3: 保存模型")
    print("=" * 80)
    
    # 确保models目录存在
    os.makedirs('models', exist_ok=True)
    
    # 保存为trained_model.json（主模型）
    model_path = 'trained_model.json'
    if analyzer.save_model(model_path):
        print(f"✅ 模型已保存到: {model_path}")
    else:
        print(f"❌ 模型保存失败")
        return False
    
    # 同时保存为模型11.json（备用）
    model11_path = 'models/模型11.json'
    if analyzer.save_model(model11_path):
        print(f"✅ 模型已保存到: {model11_path}")
    else:
        print(f"⚠️ 模型11保存失败（不影响主模型）")
    
    # 验证保存的模型
    print("\n" + "=" * 80)
    print("🔍 验证保存的模型")
    print("=" * 80)
    
    # 重新加载模型验证
    test_analyzer = BullStockAnalyzer(auto_load_default_stocks=False, auto_analyze_and_train=False)
    if test_analyzer.load_model(model_path, skip_network=True):
        print(f"✅ 模型加载成功")
        
        trained = test_analyzer.get_trained_features()
        if trained:
            print(f"   - 训练时间: {trained.get('trained_at', 'N/A')}")
            print(f"   - 样本数: {trained.get('sample_count', 0)}")
            print(f"   - 特征数: {len(trained.get('common_features', {}))}")
            print(f"   - 训练样本: {trained.get('training_stocks', [])}")
            print(f"   - 匹配度目标: {trained.get('min_match_score_target', 'N/A')}")
        else:
            print(f"   ⚠️ 模型内容为空")
    else:
        print(f"❌ 模型加载失败")
        return False
    
    print("\n" + "=" * 80)
    print("✅ 基础模型训练完成！")
    print("=" * 80)
    print(f"模型文件: {model_path}")
    print(f"备用模型: {model11_path}")
    print(f"训练样本数: {sample_count}")
    print(f"特征数量: {feature_count}")
    print(f"所有样本达标: {'是' if all_pass else '否'}")
    
    return True

if __name__ == '__main__':
    success = train_base_model()
    sys.exit(0 if success else 1)
