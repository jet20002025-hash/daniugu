#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
以90%的筹码集中度为核心指标，以筹码盈利95%以上的买点为指标，再次训练系统
"""
import sys
sys.path.insert(0, '.')
from bull_stock_analyzer import BullStockAnalyzer
import json
import os
from datetime import datetime

def main():
    print("=" * 80)
    print("🚀 以90%筹码集中度为核心指标，盈利筹码比例>=95%重新训练模型")
    print("=" * 80)
    
    # 1. 读取当前训练模型，获取股票列表
    print("\n📖 读取当前训练模型...")
    trained_model_path = 'trained_model.json'
    if not os.path.exists(trained_model_path):
        print(f"❌ 错误：找不到模型文件 {trained_model_path}")
        return
    
    with open(trained_model_path, 'r', encoding='utf-8') as f:
        model_data = json.load(f)
    
    buy_features = model_data.get('buy_features', {})
    training_stocks = buy_features.get('training_stocks', [])
    
    print(f"当前训练股票数: {len(training_stocks)} 只")
    
    # 2. 创建分析器
    print("\n🔧 初始化分析器...")
    analyzer = BullStockAnalyzer(auto_load_default_stocks=False, auto_analyze_and_train=False)
    
    # 清空现有数据
    analyzer.analysis_results = {}
    analyzer.trained_features = None
    analyzer.bull_stocks = []
    
    # 3. 分析所有股票，找到最佳买点（盈利筹码比例>=95%）
    print("\n" + "=" * 80)
    print("📊 步骤1: 分析所有大牛股，筛选盈利筹码比例>=95%的买点")
    print("=" * 80)
    
    valid_stocks = []
    
    for i, stock_code in enumerate(training_stocks, 1):
        print(f"\n[{i}/{len(training_stocks)}] 处理 {stock_code}...")
        
        try:
            # 获取周K线数据
            weekly_df = analyzer.fetcher.get_weekly_kline(stock_code, period="3y")
            
            if weekly_df is None or len(weekly_df) < 8:
                print(f"  ⚠️ 无法获取足够的周线数据")
                continue
            
            # 查找涨幅最大区间（8周内涨幅达到300%）
            valid_intervals = []
            for start_idx in range(len(weekly_df) - 8):
                for end_idx in range(start_idx + 1, min(start_idx + 9, len(weekly_df))):
                    start_price = float(weekly_df.iloc[start_idx]['收盘'])
                    interval_df = weekly_df.iloc[start_idx:end_idx]
                    max_price = float(interval_df['最高'].max())
                    gain = (max_price - start_price) / start_price * 100
                    
                    if gain >= 300.0:
                        valid_intervals.append({
                            '起点索引': start_idx,
                            '终点索引': end_idx,
                            '涨幅': gain,
                            '周数': end_idx - start_idx
                        })
            
            if not valid_intervals:
                print(f"  ⚠️ 未找到符合条件的买点（8周内涨幅>=300%）")
                continue
            
            # 找到涨幅最大的区间
            best_interval = max(valid_intervals, key=lambda x: x['涨幅'])
            best_start_idx = best_interval['起点索引']
            
            # 提取特征
            features = analyzer.extract_features_at_start_point(
                stock_code, best_start_idx, lookback_weeks=40, weekly_df=weekly_df
            )
            
            if not features:
                print(f"  ⚠️ 无法提取特征")
                continue
            
            # 检查盈利筹码比例是否>=95%
            profit_chips = features.get('盈利筹码比例')
            chip_concentration_90 = features.get('90%成本集中度')
            
            if profit_chips is not None and profit_chips >= 95.0:
                # 添加到分析结果
                analyzer.analysis_results[stock_code] = {
                    'features': features,
                    'start_idx': best_start_idx,
                    'interval': best_interval,
                    'profit_chips': profit_chips,
                    'chip_concentration_90': chip_concentration_90
                }
                valid_stocks.append(stock_code)
                print(f"  ✅ 成功：盈利筹码比例={profit_chips:.2f}%, 90%成本集中度={chip_concentration_90 if chip_concentration_90 else 'N/A'}")
            else:
                print(f"  ⚠️ 盈利筹码比例不足95%（当前: {profit_chips if profit_chips else 'N/A'}）")
        except Exception as e:
            print(f"  ❌ 处理失败: {e}")
            import traceback
            traceback.print_exc()
    
    print(f"\n✅ 筛选完成：找到 {len(valid_stocks)}/{len(training_stocks)} 只符合条件的股票（盈利筹码比例>=95%）")
    
    if len(valid_stocks) == 0:
        print("❌ 错误：没有找到符合条件的股票（盈利筹码比例>=95%）")
        print("💡 提示：可以降低盈利筹码比例阈值，或者检查数据")
        return
    
    # 4. 训练特征模型
    print("\n" + "=" * 80)
    print("📊 步骤2: 训练特征模型（以90%成本集中度为核心指标）")
    print("=" * 80)
    print("📝 注意：90%成本集中度已添加到核心特征列表")
    
    train_result = analyzer.train_features()
    
    if not train_result.get('success'):
        print(f"\n❌ 训练失败: {train_result.get('message', '未知错误')}")
        return
    
    print(f"\n✅ 训练完成！")
    print(f"训练样本数: {train_result.get('sample_count', 0)}")
    print(f"特征数量: {len(train_result.get('common_features', {}))}")
    
    # 5. 保存模型
    print("\n" + "=" * 80)
    print("💾 步骤3: 保存模型")
    print("=" * 80)
    
    output_file = 'trained_model_chip.json'
    
    # 构建模型数据结构（与trained_model.json格式一致）
    model_data = {
        'trained_at': datetime.now().isoformat(),
        'buy_features': analyzer.trained_features
    }
    
    # 保存训练结果
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(model_data, f, ensure_ascii=False, indent=2, default=str)
    
    print(f"✅ 模型已保存到: {output_file}")
    
    # 6. 测试匹配度
    print("\n" + "=" * 80)
    print("📊 步骤4: 测试训练样本的匹配度")
    print("=" * 80)
    
    common_features = analyzer.trained_features.get('common_features', {})
    match_scores = {}
    
    for stock_code in valid_stocks:
        if stock_code in analyzer.analysis_results:
            features = analyzer.analysis_results[stock_code].get('features')
            if features:
                match_score = analyzer._calculate_match_score(
                    features, common_features, tolerance=0.3, stock_code=stock_code
                )
                total_match = match_score.get('总匹配度', 0)
                match_scores[stock_code] = total_match
                print(f"  {stock_code}: {total_match:.3f}")
    
    if match_scores:
        avg_score = sum(match_scores.values()) / len(match_scores)
        min_score = min(match_scores.values())
        max_score = max(match_scores.values())
        print(f"\n📊 匹配度统计:")
        print(f"   平均匹配度: {avg_score:.3f}")
        print(f"   最低匹配度: {min_score:.3f}")
        print(f"   最高匹配度: {max_score:.3f}")
    
    print("\n" + "=" * 80)
    print("✅ 训练完成！")
    print("=" * 80)
    print(f"\n📋 总结:")
    print(f"   - 训练股票数: {len(valid_stocks)} 只（盈利筹码比例>=95%）")
    print(f"   - 核心特征: 已添加'90%成本集中度'")
    print(f"   - 模型文件: {output_file}")

if __name__ == '__main__':
    main()
