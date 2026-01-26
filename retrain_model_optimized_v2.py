#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
根据11只股票的表现分析，优化训练模型
重点：只使用大涨个股（8周涨幅>50%）作为训练样本，并调整特征权重
"""
import sys
sys.path.insert(0, '.')
from bull_stock_analyzer import BullStockAnalyzer
from datetime import datetime, timedelta
import pandas as pd
import json

# 根据分析结果，只使用大涨个股作为训练样本
# 大涨个股（8周涨幅>50%）：
# 1. 002969 嘉美包装: 439.39%
# 2. 001331 胜通能源: 340.03%

# 买入日期
buy_date = '2025-11-21'
buy_date_obj = datetime.strptime(buy_date, '%Y-%m-%d').date()

print("=" * 100)
print("优化模型训练：只使用大涨个股作为训练样本")
print(f"买入日期: {buy_date}")
print("=" * 100)

# 只使用大涨个股
training_stocks = [
    ('002969', '嘉美包装'),  # 439.39%
    ('001331', '胜通能源'),  # 340.03%
]

print(f"\n训练样本（大涨个股）: {len(training_stocks)} 只")
for code, name in training_stocks:
    print(f"  - {code} {name}")

# 初始化分析器
analyzer = BullStockAnalyzer(auto_load_default_stocks=False, auto_analyze_and_train=False)

# 确保analysis_results是字典（键：股票代码，值：分析结果）
if not hasattr(analyzer, 'analysis_results') or not isinstance(analyzer.analysis_results, dict):
    analyzer.analysis_results = {}

# 为每只训练股票在指定日期提取特征
print("\n" + "=" * 100)
print("步骤1: 在指定日期提取每只股票的特征")
print("=" * 100)

for stock_code, stock_name in training_stocks:
    print(f"\n处理 {stock_code} {stock_name}...")
    
    try:
        # 获取周K线数据
        weekly_df = analyzer.fetcher.get_weekly_kline(stock_code, period="3y")
        if weekly_df is None or len(weekly_df) == 0:
            print(f"  ❌ 无法获取周K线数据")
            continue
        
        # 找到买入日期对应的周K线索引
        if '日期' in weekly_df.columns:
            weekly_df['日期_date'] = pd.to_datetime(weekly_df['日期']).dt.date
            
            buy_idx = None
            for i in range(len(weekly_df)):
                week_date = weekly_df.iloc[i]['日期_date']
                week_start = week_date - timedelta(days=6)
                if week_start <= buy_date_obj <= week_date:
                    buy_idx = i
                    break
            
            if buy_idx is None:
                print(f"  ❌ 无法找到 {buy_date} 对应的周K线")
                continue
            
            if buy_idx < 40:
                print(f"  ⚠️ 数据不足（需要>=40周，当前只有{buy_idx}周），跳过")
                continue
            
            buy_price = float(weekly_df.iloc[buy_idx]['收盘'])
            buy_week_date = weekly_df.iloc[buy_idx]['日期_date']
            
            print(f"  找到买入周: {buy_week_date}, 价格: {buy_price:.2f}, 索引: {buy_idx}")
            
            # 提取特征
            features = analyzer.extract_features_at_start_point(
                stock_code, buy_idx, lookback_weeks=40, weekly_df=weekly_df
            )
            
            if features:
                # 添加到分析结果（使用字典格式，键为股票代码）
                analyzer.analysis_results[stock_code] = {
                    'stock_info': {
                        '代码': stock_code,
                        '名称': stock_name
                    },
                    'interval': {
                        '起点索引': buy_idx,
                        '起点日期': str(buy_week_date),
                        '起点价格': round(buy_price, 2)
                    },
                    'features': features  # 特征将在train_features中提取
                }
                print(f"  ✅ 特征提取成功，已添加到训练样本")
                
                # 打印关键特征
                key_features = [
                    '盈利筹码比例', '90%成本集中度', '筹码集中度',
                    '价格相对MA5', '价格相对MA10', '价格相对MA20', '价格相对MA40',
                    '起点前20周波动率', '起点前10周波动率',
                    '起点前20周均量', '起点前10周均量', '起点前40周最大量',
                    '成交量萎缩程度', '起点当周价涨量增'
                ]
                print(f"  关键特征:")
                for key in key_features:
                    if key in features:
                        print(f"    {key}: {features[key]}")
            else:
                print(f"  ⚠️ 特征提取失败")
        else:
            print(f"  ❌ 周K线数据格式错误")
            
    except Exception as e:
        print(f"  ❌ 处理 {stock_code} 时出错: {e}")
        import traceback
        traceback.print_exc()

print(f"\n总共收集到 {len(analyzer.analysis_results)} 个训练样本")

if len(analyzer.analysis_results) == 0:
    print("\n❌ 没有收集到训练样本，无法训练模型")
    exit(1)

# 训练模型
print("\n" + "=" * 100)
print("步骤2: 训练优化模型")
print("=" * 100)

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
        
        for stock_code, result in analyzer.analysis_results.items():
            stock_name = result.get('stock_info', {}).get('名称', stock_code)
            # 重新提取特征用于验证
            interval = result.get('interval', {})
            start_idx = interval.get('起点索引')
            
            if start_idx is not None:
                weekly_df = analyzer.fetcher.get_weekly_kline(stock_code, period="3y")
                if weekly_df is not None and len(weekly_df) > start_idx:
                    features = analyzer.extract_features_at_start_point(
                        stock_code, start_idx, lookback_weeks=40, weekly_df=weekly_df
                    )
                    
                    if features and common_features:
                        match_score = analyzer._calculate_match_score(
                            features, common_features, tolerance=0.3, stock_code=stock_code
                        )
                        
                        total_match = match_score.get('总匹配度', 0)
                        core_match = match_score.get('核心特征匹配度', 0)
                        
                        print(f"{stock_code} {stock_name}: 总匹配度={total_match:.3f}, 核心特征匹配度={core_match:.3f}")
    
    # 保存训练结果摘要
    summary = {
        '训练时间': datetime.now().isoformat(),
        '训练样本数': len(analyzer.analysis_results),
        '训练股票': list(analyzer.analysis_results.keys()),
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
