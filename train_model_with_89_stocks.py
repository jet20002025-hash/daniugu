#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
使用89只大牛股作为训练数据，训练模型，确保所有训练样本匹配度达到0.9以上
"""
import sys
sys.path.insert(0, '.')
from bull_stock_analyzer import BullStockAnalyzer
import json
from datetime import datetime
import pandas as pd
import os

def train_model_with_89_stocks():
    """使用89只大牛股训练模型"""
    print("=" * 80)
    print("🎓 使用89只大牛股训练模型（确保所有样本匹配度>=0.9）")
    print("=" * 80)
    
    # 加载89只大牛股数据
    print("\n📊 加载89只大牛股数据...")
    with open('all_stocks_300pct_8weeks_20260113_175719.json', 'r', encoding='utf-8') as f:
        bull_stocks_data = json.load(f)
    
    print(f"✅ 加载了 {len(bull_stocks_data)} 只大牛股数据")
    
    # 创建分析器（不自动加载默认股票，不自动训练）
    analyzer = BullStockAnalyzer(
        auto_load_default_stocks=False,
        auto_analyze_and_train=False
    )
    
    # 清空现有的大牛股列表和分析结果
    analyzer.bull_stocks = []
    analyzer.analysis_results = {}
    
    # 步骤1: 分析所有大牛股，找到买点
    print("\n" + "=" * 80)
    print("📊 步骤1: 分析所有大牛股，找到买点")
    print("=" * 80)
    
    analyzed_count = 0
    
    for i, stock_data in enumerate(bull_stocks_data, 1):
        stock_code = stock_data['股票代码']
        stock_name = stock_data['股票名称']
        buy_date = stock_data['最佳买点日期']
        
        print(f"\n[{i}/{len(bull_stocks_data)}] 分析 {stock_name} ({stock_code})...")
        
        # 添加到大牛股列表
        analyzer.bull_stocks.append({
            '代码': stock_code,
            '名称': stock_name,
            '添加时间': datetime.now()
        })
        
        # 获取周K线数据
        weekly_df = analyzer.fetcher.get_weekly_kline(stock_code, period="3y")
        if weekly_df is None or len(weekly_df) == 0:
            print(f"  ⚠️ 无法获取 {stock_code} 的周线数据，跳过")
            continue
        
        # 过滤未来日期
        today = datetime.now().date()
        weekly_df['日期'] = pd.to_datetime(weekly_df['日期'])
        weekly_df = weekly_df[weekly_df['日期'].dt.date <= today].reset_index(drop=True)
        
        if len(weekly_df) < 8:
            print(f"  ⚠️ 数据不足（{len(weekly_df)} 周），跳过")
            continue
        
        # 根据买点日期找到对应的索引
        start_idx = None
        if buy_date:
            buy_date_dt = pd.to_datetime(buy_date).date()
            for idx, row in weekly_df.iterrows():
                row_date = pd.to_datetime(row['日期']).date()
                if row_date >= buy_date_dt:
                    start_idx = weekly_df.index.get_loc(idx)
                    break
        
        # 如果没有找到买点日期对应的索引，使用最大涨幅区间
        if start_idx is None:
            result = analyzer.find_max_gain_interval(stock_code, weekly_df=weekly_df, search_weeks=8, min_gain=300.0)
            if result.get('success') and result.get('interval'):
                start_idx = result['interval']['start_idx']
            else:
                print(f"  ⚠️ 未找到符合条件的买点，跳过")
                continue
        
        if start_idx is None:
            print(f"  ⚠️ 买点索引无效，跳过")
            continue
        
        # 记录分析结果（train_features方法需要这个）
        analyzer.analysis_results[stock_code] = {
            'success': True,
            'interval': {
                '起点索引': int(start_idx),
                '起点日期': weekly_df.iloc[start_idx]['日期'].strftime('%Y-%m-%d') if isinstance(weekly_df.iloc[start_idx]['日期'], pd.Timestamp) else str(weekly_df.iloc[start_idx]['日期']),
                '起点价格': float(weekly_df.iloc[start_idx]['收盘'])
            }
        }
        analyzed_count += 1
        print(f"  ✅ 找到买点: 索引 {start_idx}, 日期 {analyzer.analysis_results[stock_code]['interval']['起点日期']}")
    
    print(f"\n✅ 分析完成，共分析 {analyzed_count}/{len(bull_stocks_data)} 只股票")
    
    if analyzed_count == 0:
        print("\n❌ 没有成功分析的股票，无法训练模型")
        return None
    
    # 步骤2: 使用train_features方法训练模型（它会自动验证和调整，确保匹配度>=0.95）
    print("\n" + "=" * 80)
    print("🎓 步骤2: 训练买点特征模型（自动验证和调整，确保匹配度>=0.95）")
    print("=" * 80)
    
    train_result = analyzer.train_features()
    
    if not train_result.get('success'):
        print(f"\n❌ 买点特征模型训练失败: {train_result.get('message', '')}")
        return None
    
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
        passed_count = 0
        failed_count = 0
        min_score = 1.0
        max_score = 0.0
        total_score = 0.0
        
        for stock_code, info in match_scores.items():
            score = info.get('匹配度', 0)
            is_passed = info.get('达标', False)
            stock_name = info.get('股票名称', stock_code)
            
            if is_passed:
                passed_count += 1
                status = "✅"
            else:
                failed_count += 1
                status = "❌"
            
            min_score = min(min_score, score)
            max_score = max(max_score, score)
            total_score += score
            
            print(f"   {status} {stock_code} {stock_name}: {score:.3f}")
        
        avg_score = total_score / len(match_scores) if match_scores else 0
        print(f"\n📈 匹配度统计:")
        print(f"   - 通过数: {passed_count}/{len(match_scores)} ({passed_count/len(match_scores)*100:.1f}%)")
        print(f"   - 未通过数: {failed_count}/{len(match_scores)}")
        print(f"   - 平均匹配度: {avg_score:.3f}")
        print(f"   - 最低匹配度: {min_score:.3f}")
        print(f"   - 最高匹配度: {max_score:.3f}")
    
    if not all_pass:
        print(f"\n⚠️ 警告: 部分训练样本的匹配度未达到0.95")
        print(f"   建议: 检查训练样本的特征是否一致，或调整训练逻辑")
    else:
        print(f"\n🎉 成功！所有训练样本的匹配度都达到0.95以上！")
    
    # 步骤3: 保存模型
    print("\n" + "=" * 80)
    print("💾 步骤3: 保存模型")
    print("=" * 80)
    
    # 确保models目录存在
    os.makedirs('models', exist_ok=True)
    
    # 保存为带时间戳的模型文件
    model_filename = f"models/模型_89只大牛股_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    if analyzer.save_model(model_filename):
        print(f"✅ 模型已保存到 {model_filename}")
    else:
        print("❌ 模型保存失败")
    
    # 同时保存为trained_model.json（主模型，供系统使用）
    main_model_path = 'trained_model.json'
    if analyzer.save_model(main_model_path):
        print(f"✅ 模型已保存到 {main_model_path}（主模型）")
    else:
        print("❌ 主模型保存失败")
    
    # 最终验证
    print("\n" + "=" * 80)
    print("✅ 训练完成！最终验证")
    print("=" * 80)
    
    print(f"\n📊 训练样本数: {sample_count}")
    print(f"📊 特征数: {feature_count}")
    print(f"📊 匹配度目标: >= 0.95")
    print(f"📊 实际达标率: {passed_count}/{len(match_scores)} ({passed_count/len(match_scores)*100:.1f}%)" if match_scores else "未知")
    
    if all_pass:
        print(f"\n🎉 成功！所有训练样本的匹配度都达到0.95以上！")
    else:
        print(f"\n⚠️ 警告：仍有 {failed_count} 个样本的匹配度低于0.95")
        print(f"   最低匹配度: {min_score:.3f}")
    
    return analyzer

if __name__ == '__main__':
    train_model_with_89_stocks()
