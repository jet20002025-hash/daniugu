#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
根据11只股票的表现分析，优化训练模型
重点：只使用大涨个股（8周涨幅>50%）作为训练样本，并调整特征权重
"""
import sys
sys.path.insert(0, '.')
from bull_stock_analyzer import BullStockAnalyzer
from datetime import datetime
import json

# 根据分析结果，只使用大涨个股作为训练样本
# 大涨个股（8周涨幅>50%）：
# 1. 002969 嘉美包装: 439.39%
# 2. 001331 胜通能源: 340.03%

# 表现差个股（排除）：
# - 603038 华立股份: 2.52%（匹配度0.944但表现很差）
# - 其他表现差的个股

print("=" * 100)
print("优化模型训练：只使用大涨个股作为训练样本")
print("=" * 100)

# 只使用大涨个股
training_stocks = [
    '002969',  # 嘉美包装: 439.39%
    '001331',  # 胜通能源: 340.03%
]

print(f"\n训练样本（大涨个股）: {len(training_stocks)} 只")
for code in training_stocks:
    print(f"  - {code}")

# 初始化分析器
analyzer = BullStockAnalyzer(auto_load_default_stocks=False, auto_analyze_and_train=False)

# 加载现有模型（如果有）
trained_model_path = 'models/筹码模型.json'
if analyzer.load_model(trained_model_path, skip_network=True):
    print(f"\n✅ 已加载现有模型: {trained_model_path}")
else:
    print(f"\n⚠️ 未找到现有模型，将创建新模型")

# 为每只训练股票找到最佳买点并提取特征
print("\n" + "=" * 100)
print("步骤1: 找到每只股票的最佳买点并提取特征")
print("=" * 100)

for stock_code in training_stocks:
    print(f"\n处理 {stock_code}...")
    
    # 找到最佳买点（使用简化逻辑：8周内涨幅300%）
    buy_points_result = analyzer.find_buy_points(stock_code, search_years=3)
    
    if buy_points_result.get('success') and buy_points_result.get('buy_points'):
        best_buy_point = buy_points_result['buy_points'][0]  # 取第一个（最佳买点）
        buy_date = best_buy_point.get('日期')
        buy_price = best_buy_point.get('价格')
        
        print(f"  找到最佳买点: {buy_date}, 价格: {buy_price}")
        
        # 获取周K线数据，找到对应的索引
        weekly_df = analyzer.fetcher.get_weekly_kline(stock_code, period="3y")
        if weekly_df is not None and len(weekly_df) > 0:
            # 找到买入日期对应的索引
            from datetime import datetime, timedelta
            import pandas as pd
            
            buy_date_obj = datetime.strptime(buy_date, '%Y-%m-%d').date()
            if '日期' in weekly_df.columns:
                weekly_df['日期_date'] = pd.to_datetime(weekly_df['日期']).dt.date
                
                buy_idx = None
                for i in range(len(weekly_df)):
                    week_date = weekly_df.iloc[i]['日期_date']
                    week_start = week_date - timedelta(days=6)
                    if week_start <= buy_date_obj <= week_date:
                        buy_idx = i
                        break
                
                if buy_idx is not None and buy_idx >= 40:
                    # 提取特征
                    features = analyzer.extract_features_at_start_point(
                        stock_code, buy_idx, lookback_weeks=40, weekly_df=weekly_df
                    )
                    
                    if features:
                        # 添加到分析结果
                        analyzer.analysis_results.append({
                            '股票代码': stock_code,
                            '股票名称': analyzer._get_stock_name(stock_code) or stock_code,
                            '最佳买点日期': buy_date,
                            '最佳买点价格': buy_price,
                            '特征': features
                        })
                        print(f"  ✅ 特征提取成功，已添加到训练样本")
                    else:
                        print(f"  ⚠️ 特征提取失败")
                else:
                    print(f"  ⚠️ 无法找到买入日期对应的索引或数据不足（需要>=40周）")
    else:
        print(f"  ⚠️ 未找到买点")

print(f"\n总共收集到 {len(analyzer.analysis_results)} 个训练样本")

# 训练模型
print("\n" + "=" * 100)
print("步骤2: 训练优化模型")
print("=" * 100)

# 修改核心特征权重，重点突出盈利筹码比例和价格相对位置
# 在训练前，我们需要修改_calculate_match_score方法中的核心特征列表
# 但为了不影响现有逻辑，我们在训练时调整特征模板的范围

train_result = analyzer.train_features()

if train_result.get('success'):
    print("\n" + "=" * 100)
    print("✅ 模型训练成功！")
    print("=" * 100)
    
    # 保存模型
    output_file = 'trained_model_optimized.json'
    analyzer.save_model(output_file)
    print(f"\n模型已保存到: {output_file}")
    
    # 验证训练结果：计算每只训练股票的匹配度
    print("\n" + "=" * 100)
    print("步骤3: 验证训练结果（计算每只训练股票的匹配度）")
    print("=" * 100)
    
    if analyzer.trained_features:
        common_features = analyzer.trained_features.get('common_features', {})
        
        for result in analyzer.analysis_results:
            stock_code = result['股票代码']
            features = result['特征']
            
            if features and common_features:
                match_score = analyzer._calculate_match_score(
                    features, common_features, tolerance=0.3, stock_code=stock_code
                )
                
                total_match = match_score.get('总匹配度', 0)
                core_match = match_score.get('核心特征匹配度', 0)
                
                print(f"{stock_code} {result['股票名称']}: 总匹配度={total_match:.3f}, 核心特征匹配度={core_match:.3f}")
    
    # 保存训练结果摘要
    summary = {
        '训练时间': datetime.now().isoformat(),
        '训练样本数': len(analyzer.analysis_results),
        '训练股票': [r['股票代码'] for r in analyzer.analysis_results],
        '特征数量': len(analyzer.trained_features.get('common_features', {})),
        '训练结果': train_result
    }
    
    summary_file = 'retrain_optimized_summary.json'
    with open(summary_file, 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    
    print(f"\n训练摘要已保存到: {summary_file}")
    
else:
    print("\n" + "=" * 100)
    print("❌ 模型训练失败")
    print("=" * 100)
    print(f"错误信息: {train_result.get('message', '未知错误')}")
