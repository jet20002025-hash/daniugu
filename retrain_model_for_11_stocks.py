#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
重新训练模型，确保11只大牛股的匹配度都能达到0.83以上
"""
import sys
sys.path.insert(0, '.')
from bull_stock_analyzer import BullStockAnalyzer
import json
from datetime import datetime

def test_all_stocks_match_score(analyzer, target_stocks, min_threshold=0.83):
    """测试所有股票的匹配度"""
    print("\n" + "=" * 80)
    print("📊 测试所有股票的匹配度")
    print("=" * 80)
    
    match_scores = {}
    success_count = 0
    
    common_features = analyzer.trained_features.get('common_features', {})
    
    for stock_code in target_stocks:
        try:
            # 获取股票名称
            stock_name = None
            for stock in analyzer.bull_stocks:
                if stock.get('代码') == stock_code:
                    stock_name = stock.get('名称', stock_code)
                    break
            
            if not stock_name:
                stock_name = stock_code
            
            # 测试匹配度
            result = analyzer._process_single_stock(
                stock_code=stock_code,
                stock_name=stock_name,
                common_features=common_features,
                min_match_score=0.0,  # 不设阈值，看实际匹配度
                max_market_cap=1000.0,
                idx=0,
                total_stocks=1,
                scan_date=None
            )
            
            if result:
                match_score = result.get('匹配度', 0)
                match_scores[stock_code] = {
                    '股票名称': stock_name,
                    '匹配度': match_score,
                    '达标': match_score >= min_threshold
                }
                if match_score >= min_threshold:
                    success_count += 1
                    print(f"✅ {stock_code} {stock_name}: {match_score:.3f} >= {min_threshold}")
                else:
                    print(f"❌ {stock_code} {stock_name}: {match_score:.3f} < {min_threshold}")
            else:
                match_scores[stock_code] = {
                    '股票名称': stock_name,
                    '匹配度': 0,
                    '达标': False
                }
                print(f"❌ {stock_code} {stock_name}: 未找到买点")
        except Exception as e:
            print(f"❌ {stock_code}: 错误 - {e}")
            match_scores[stock_code] = {
                '股票名称': stock_name if 'stock_name' in locals() else stock_code,
                '匹配度': 0,
                '达标': False,
                '错误': str(e)
            }
    
    print(f"\n📊 测试结果: {success_count}/{len(target_stocks)} 只股票达标（匹配度 >= {min_threshold}）")
    return success_count == len(target_stocks), match_scores

def main():
    print("=" * 80)
    print("🚀 重新训练模型（确保11只大牛股匹配度 >= 0.83）")
    print("=" * 80)
    
    # 11只大牛股列表
    target_stocks = ['000592', '002104', '002759', '300436', '301005', '301232', '002788', '603778', '603122', '600343', '603216']
    
    print(f"\n📊 目标股票: {', '.join(target_stocks)}")
    print(f"   共 {len(target_stocks)} 只股票")
    print(f"\n🎯 训练目标:")
    print(f"   - 确保所有11只股票的匹配度 >= 0.83")
    print(f"   - 优先确保训练样本的匹配度尽可能高")
    
    # 创建分析器（不自动训练，手动控制）
    print("\n1. 初始化分析器...")
    analyzer = BullStockAnalyzer(auto_load_default_stocks=False, auto_analyze_and_train=False)
    
    # 清空现有的分析结果和训练模型
    print("\n2. 清理现有数据...")
    analyzer.analysis_results = {}
    analyzer.trained_features = None
    analyzer.bull_stocks = []
    
    # 确保所有11只股票都已添加
    print("\n3. 添加11只目标股票...")
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
        stock_code = stock.get('代码')
        stock_name = stock.get('名称', stock_code)
        print(f"\n[{i}/{len(analyzer.bull_stocks)}] 分析: {stock_code} {stock_name}")
        
        if stock_code not in analyzer.analysis_results:
            result = analyzer.analyze_bull_stock(stock_code)
            if result.get('success'):
                analyzed_count += 1
                interval = result.get('interval', {})
                if interval:
                    start_idx = interval.get('起点索引', 'N/A')
                    gain = interval.get('涨幅', 'N/A')
                    print(f"  ✅ 分析成功: 起点索引 {start_idx}, 涨幅 {gain}")
                else:
                    print(f"  ⚠️ 分析成功但未找到涨幅区间")
            else:
                print(f"  ❌ 分析失败: {result.get('message', '未知错误')}")
        else:
            analyzed_count += 1
            print(f"  ✅ 已有分析结果，跳过")
    
    print(f"\n✅ 分析完成: {analyzed_count}/{len(analyzer.bull_stocks)} 只股票")
    
    if analyzed_count == 0:
        print("❌ 没有股票分析成功，无法训练模型")
        return
    
    # 步骤2: 训练买点特征模型
    print("\n" + "=" * 80)
    print("📊 步骤2: 训练买点特征模型")
    print("=" * 80)
    
    train_result = analyzer.train_features()
    if not train_result.get('success'):
        print(f"❌ 训练失败: {train_result.get('message', '未知错误')}")
        return
    
    print(f"✅ 训练成功: {train_result.get('message', '')}")
    
    # 步骤3: 测试所有股票的匹配度
    print("\n" + "=" * 80)
    print("📊 步骤3: 测试所有股票的匹配度")
    print("=" * 80)
    
    all_passed, match_scores = test_all_stocks_match_score(analyzer, target_stocks, min_threshold=0.83)
    
    # 步骤4: 保存模型
    print("\n" + "=" * 80)
    print("📊 步骤4: 保存模型")
    print("=" * 80)
    
    model_path = 'trained_model.json'
    save_result = analyzer.save_model(model_path)
    if save_result:
        print(f"✅ 模型已保存到: {model_path}")
    else:
        print(f"❌ 模型保存失败")
    
    # 输出最终结果
    print("\n" + "=" * 80)
    print("📊 训练结果总结")
    print("=" * 80)
    
    if all_passed:
        print("✅ 所有11只股票的匹配度都 >= 0.83！")
    else:
        print("⚠️  部分股票的匹配度 < 0.83")
        print("\n详细匹配度:")
        for stock_code, info in match_scores.items():
            status = "✅" if info['达标'] else "❌"
            print(f"{status} {stock_code} {info['股票名称']}: {info['匹配度']:.3f}")
    
    # 保存训练结果
    output_file = f"retrain_result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            '训练时间': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            '目标股票': target_stocks,
            '匹配度阈值': 0.83,
            '所有股票达标': all_passed,
            '匹配度详情': match_scores,
            '模型文件': model_path
        }, f, ensure_ascii=False, indent=2)
    
    print(f"\n💾 训练结果已保存到: {output_file}")
    
    return all_passed

if __name__ == '__main__':
    main()
