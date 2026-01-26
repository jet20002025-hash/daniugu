#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
使用22只大牛股重新训练模型，使用调整权重后的参数
核心特征：盈利筹码比例、价格相对位置（权重更高）
"""
import sys
sys.path.insert(0, '.')
from bull_stock_analyzer import BullStockAnalyzer
import json
import os
from datetime import datetime

def main():
    print("=" * 100)
    print("🚀 使用22只大牛股重新训练模型（调整权重后的参数）")
    print("=" * 100)
    
    # 1. 读取当前训练模型，获取22只股票列表
    print("\n📖 读取当前训练模型，获取22只股票列表...")
    trained_model_path = 'trained_model.json'
    if not os.path.exists(trained_model_path):
        print(f"❌ 错误：找不到模型文件 {trained_model_path}")
        return
    
    with open(trained_model_path, 'r', encoding='utf-8') as f:
        model_data = json.load(f)
    
    buy_features = model_data.get('buy_features', {})
    training_stocks = buy_features.get('training_stocks', [])
    
    if len(training_stocks) != 22:
        print(f"⚠️ 警告：训练股票数不是22只，而是 {len(training_stocks)} 只")
        print(f"继续使用这 {len(training_stocks)} 只股票进行训练...")
    
    print(f"训练股票数: {len(training_stocks)} 只")
    print(f"股票列表: {', '.join(training_stocks)}")
    
    # 2. 创建分析器
    print("\n🔧 初始化分析器...")
    analyzer = BullStockAnalyzer(auto_load_default_stocks=False, auto_analyze_and_train=False)
    
    # 清空现有数据
    analyzer.analysis_results = {}
    analyzer.trained_features = None
    analyzer.bull_stocks = []
    
    # 3. 分析所有股票，找到最佳买点
    print("\n" + "=" * 100)
    print("📊 步骤1: 分析所有大牛股，找到最佳买点")
    print("=" * 100)
    
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
            
            # 确保有足够的数据（至少20周，而不是40周）
            if best_start_idx < 20:
                print(f"  ⚠️ 起点索引 {best_start_idx} < 20，数据严重不足，跳过")
                continue
            
            # 提取特征（根据实际可用周数调整lookback_weeks）
            # 如果起点索引<40，使用实际可用周数（但至少20周）
            actual_lookback = min(best_start_idx, 40)
            if actual_lookback < 20:
                print(f"  ⚠️ 实际可用周数 {actual_lookback} < 20，数据不足，跳过")
                continue
            
            features = analyzer.extract_features_at_start_point(
                stock_code, best_start_idx, lookback_weeks=actual_lookback, weekly_df=weekly_df
            )
            
            if not features:
                print(f"  ⚠️ 无法提取特征")
                continue
            
            # 获取买点日期和价格
            buy_date = weekly_df.iloc[best_start_idx]['日期']
            if hasattr(buy_date, 'strftime'):
                buy_date_str = buy_date.strftime('%Y-%m-%d')
            else:
                buy_date_str = str(buy_date)
            buy_price = float(weekly_df.iloc[best_start_idx]['收盘'])
            
            # 记录关键特征（用于信息展示）
            profit_chips = features.get('盈利筹码比例')
            chip_concentration_90 = features.get('90%成本集中度')
            price_position = features.get('价格相对位置')
            
            print(f"  ✅ 找到最佳买点: {buy_date_str}, 价格: {buy_price:.2f}")
            print(f"     盈利筹码比例: {profit_chips:.2f}%, 90%成本集中度: {chip_concentration_90:.2f}%, 价格相对位置: {price_position:.2f}%")
            
            # 添加到分析结果
            analyzer.analysis_results[stock_code] = {
                'stock_info': {
                    '代码': stock_code,
                    '名称': analyzer._get_stock_name(stock_code) or stock_code
                },
                'interval': {
                    '起点索引': best_start_idx,
                    '起点日期': buy_date_str,
                    '起点价格': round(buy_price, 2),
                    '涨幅': round(best_interval['涨幅'], 2),
                    '周数': best_interval['周数']
                },
                'features': features  # 特征将在train_features中提取
            }
            
            valid_stocks.append(stock_code)
            
        except Exception as e:
            print(f"  ❌ 处理 {stock_code} 时出错: {e}")
            import traceback
            traceback.print_exc()
            continue
    
    print(f"\n✅ 成功分析 {len(valid_stocks)} 只股票")
    
    if len(valid_stocks) == 0:
        print("❌ 没有找到有效的训练样本，无法训练模型")
        return
    
    # 4. 训练模型（使用调整权重后的参数）
    print("\n" + "=" * 100)
    print("🎯 步骤2: 训练模型（使用调整权重后的参数）")
    print("=" * 100)
    print("核心特征（权重4.0）：盈利筹码比例、价格相对位置、90%成本集中度")
    print("普通特征（权重1.0）：其他特征")
    
    train_result = analyzer.train_features()
    
    if train_result.get('success'):
        print("\n" + "=" * 100)
        print("✅ 模型训练成功！")
        print("=" * 100)
        
        # 保存模型
        output_file = 'trained_model_22_optimized.json'
        analyzer.save_model(output_file)
        print(f"\n模型已保存到: {output_file}")
        
        # 同时保存为优化模型
        import shutil
        models_dir = 'models'
        if not os.path.exists(models_dir):
            os.makedirs(models_dir, exist_ok=True)
        optimized_model_path = os.path.join(models_dir, '优化模型.json')
        shutil.copy(output_file, optimized_model_path)
        print(f"模型已复制到: {optimized_model_path}")
        
        # 验证训练结果：直接使用训练结果中的匹配度信息
        print("\n" + "=" * 100)
        print("📊 步骤3: 验证训练结果（使用训练时的匹配度信息）")
        print("=" * 100)
        
        if analyzer.trained_features:
            # 从训练结果中获取匹配度信息（train_result已经包含验证结果）
            match_scores_info = train_result.get('match_scores', {})
            all_pass = train_result.get('all_pass', False)
            
            if match_scores_info:
                match_scores = []
                for stock_code, match_info in match_scores_info.items():
                    stock_name = match_info.get('股票名称', stock_code)
                    total_match = match_info.get('匹配度', 0)
                    is_pass = match_info.get('达标', False)
                    
                    match_scores.append({
                        '股票代码': stock_code,
                        '股票名称': stock_name,
                        '总匹配度': total_match,
                        '达标': is_pass
                    })
                    
                    status = "✅" if is_pass else "⚠️"
                    print(f"{status} {stock_code} {stock_name}: 总匹配度={total_match:.3f}")
            else:
                # 如果没有保存匹配度信息，使用训练结果中的信息
                print("⚠️ 训练结果中未保存匹配度信息，使用训练时的验证结果")
                match_scores = []
                if all_pass:
                    print("✅ 训练时已验证：所有训练样本的匹配度都 >= 0.95")
                else:
                    print("⚠️ 训练时验证：部分训练样本的匹配度 < 0.95")
            
            # 统计匹配度
            if match_scores:
                avg_match = sum(m['总匹配度'] for m in match_scores) / len(match_scores)
                min_match = min(m['总匹配度'] for m in match_scores)
                max_match = max(m['总匹配度'] for m in match_scores)
                above_095 = sum(1 for m in match_scores if m.get('达标', m['总匹配度'] >= 0.95))
                
                print(f"\n📈 匹配度统计:")
                print(f"   平均匹配度: {avg_match:.3f}")
                print(f"   最低匹配度: {min_match:.3f}")
                print(f"   最高匹配度: {max_match:.3f}")
                print(f"   匹配度>=0.95: {above_095}/{len(match_scores)} 只")
                
                if above_095 == len(match_scores):
                    print(f"\n✅ 所有 {len(match_scores)} 只股票的匹配度都 >= 0.95！")
                else:
                    print(f"\n⚠️ 有 {len(match_scores) - above_095} 只股票的匹配度 < 0.95")
        
        # 保存训练结果摘要
        # 从训练结果中获取匹配度信息
        train_match_scores = train_result.get('match_scores', {})
        if train_match_scores:
            all_match_values = [m.get('匹配度', 0) for m in train_match_scores.values()]
            avg_match = sum(all_match_values) / len(all_match_values) if all_match_values else 0
            min_match = min(all_match_values) if all_match_values else 0
            max_match = max(all_match_values) if all_match_values else 0
            above_095 = sum(1 for m in train_match_scores.values() if m.get('达标', False))
        else:
            avg_match = min_match = max_match = above_095 = 0
        
        summary = {
            '训练时间': datetime.now().isoformat(),
            '训练样本数': len(analyzer.analysis_results),
            '训练股票': list(analyzer.analysis_results.keys()),
            '特征数量': len(analyzer.trained_features.get('common_features', {})) if analyzer.trained_features else 0,
            '训练结果': {
                'success': train_result.get('success', False),
                'message': train_result.get('message', ''),
                'sample_count': train_result.get('sample_count', 0),
                'all_pass': train_result.get('all_pass', False),
                'iterations': train_result.get('iterations', 0)
            },
            '匹配度统计': {
                '平均匹配度': round(avg_match, 3),
                '最低匹配度': round(min_match, 3),
                '最高匹配度': round(max_match, 3),
                '匹配度>=0.95数量': above_095,
                '总样本数': len(train_match_scores) if train_match_scores else len(analyzer.analysis_results)
            }
        }
        
        summary_file = 'retrain_22_optimized_summary.json'
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        
        print(f"\n训练摘要已保存到: {summary_file}")
        
    else:
        print("\n" + "=" * 100)
        print("❌ 模型训练失败")
        print("=" * 100)
        print(f"错误信息: {train_result.get('message', '未知错误')}")

if __name__ == '__main__':
    main()
