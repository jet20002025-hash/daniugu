#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
训练模型，使三只股票在1月5号的匹配度达到目标值
- 300141 和顺电气: 0.961
- 300986 志特新材: 0.956
- 300238 冠昊生物: 0.943
"""
import os
import sys
import json
from datetime import datetime
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bull_stock_analyzer import BullStockAnalyzer

# 目标股票和目标匹配度
TARGET_STOCKS = {
    '300141': {'name': '和顺电气', 'target_score': 0.961},
    '300986': {'name': '志特新材', 'target_score': 0.956},
    '300238': {'name': '冠昊生物', 'target_score': 0.943}
}

# 验证日期
VERIFY_DATE = '2026-01-05'

# 最大训练次数
MAX_ITERATIONS = 50


def verify_match_scores(analyzer, target_date):
    """验证三只股票在指定日期的匹配度"""
    results = {}
    all_passed = True
    
    print(f"\n{'='*80}")
    print(f"验证日期: {target_date}")
    print(f"{'='*80}")
    
    for code, info in TARGET_STOCKS.items():
        stock_name = info['name']
        target_score = info['target_score']
        
        try:
            # 获取股票在指定日期的周K线数据
            weekly_df = analyzer.fetcher.get_weekly_kline(code, period='2y')
            if weekly_df is None or len(weekly_df) == 0:
                print(f"❌ {code} {stock_name}: 无法获取数据")
                results[code] = {'score': 0, 'passed': False, 'error': '无法获取数据'}
                all_passed = False
                continue
            
            # 过滤到指定日期（与扫描器逻辑一致）
            weekly_df['日期'] = pd.to_datetime(weekly_df['日期'])
            target_date_ts = pd.to_datetime(target_date)
            weekly_df = weekly_df[weekly_df['日期'] <= target_date_ts].copy()
            weekly_df = weekly_df.sort_values('日期').reset_index(drop=True)
            
            if len(weekly_df) < 40:
                print(f"❌ {code} {stock_name}: 数据不足（需要至少40周，当前{len(weekly_df)}周）")
                results[code] = {'score': 0, 'passed': False, 'error': f'数据不足（{len(weekly_df)}周）'}
                all_passed = False
                continue
            
            # 使用最后一周作为潜在的买点（与扫描器逻辑一致）
            buy_point_idx = len(weekly_df) - 1
            
            # 找成交量突增点（与扫描器逻辑一致）
            volume_surge_idx = analyzer.find_volume_surge_point(
                code, 
                buy_point_idx, 
                weekly_df=weekly_df, 
                min_volume_ratio=3.0, 
                lookback_weeks=52
            )
            
            # 确定特征起点（与扫描器逻辑一致）
            if volume_surge_idx is not None and volume_surge_idx >= 40:
                feature_idx = volume_surge_idx
            else:
                feature_idx = max(0, buy_point_idx - 20)
            
            # 提取特征
            features = analyzer.extract_features_at_start_point(
                code, 
                feature_idx, 
                lookback_weeks=40, 
                weekly_df=weekly_df
            )
            
            if features is None:
                print(f"❌ {code} {stock_name}: 无法提取特征")
                results[code] = {'score': 0, 'passed': False, 'error': '无法提取特征'}
                all_passed = False
                continue
            
            # 计算匹配度
            trained_features = analyzer.get_trained_features()
            if trained_features is None:
                print(f"❌ {code} {stock_name}: 模型未训练")
                results[code] = {'score': 0, 'passed': False, 'error': '模型未训练'}
                all_passed = False
                continue
            
            match_result = analyzer._calculate_match_score(
                features, 
                trained_features.get('common_features', {}),
                tolerance=0.3
            )
            # ✅ 匹配度的键名是 '总匹配度'
            match_score = match_result.get('总匹配度', 0) or match_result.get('match_score', 0)
            
            passed = match_score >= target_score
            status = "✅" if passed else "❌"
            
            print(f"{status} {code} {stock_name}: 匹配度 {match_score:.3f} (目标: {target_score:.3f}) {'✓' if passed else '✗'}")
            
            results[code] = {
                'score': match_score,
                'target': target_score,
                'passed': passed,
                'name': stock_name
            }
            
            if not passed:
                all_passed = False
                
        except Exception as e:
            print(f"❌ {code} {stock_name}: 验证失败 - {str(e)}")
            import traceback
            traceback.print_exc()
            results[code] = {'score': 0, 'passed': False, 'error': str(e)}
            all_passed = False
    
    print(f"{'='*80}")
    if all_passed:
        print("✅ 所有股票匹配度均达到目标！")
    else:
        print("❌ 部分股票匹配度未达到目标")
    print(f"{'='*80}\n")
    
    return results, all_passed


def train_model_iteratively():
    """迭代训练模型直到达到目标"""
    print("="*80)
    print("开始训练模型，目标：")
    for code, info in TARGET_STOCKS.items():
        print(f"  - {code} {info['name']}: 匹配度 >= {info['target_score']:.3f} (日期: {VERIFY_DATE})")
    print("="*80)
    
    analyzer = BullStockAnalyzer(
        auto_load_default_stocks=True,
        auto_analyze_and_train=False  # 手动控制训练
    )
    
    # 加载默认大牛股列表
    training_stocks = analyzer.bull_stocks
    print(f"\n使用 {len(training_stocks)} 只大牛股进行训练")
    
    # ✅ 先分析所有大牛股（训练前必须完成）
    print("\n📊 开始分析大牛股...")
    for idx, stock in enumerate(training_stocks, 1):
        stock_code = stock.get('代码', '')
        stock_name = stock.get('名称', '')
        print(f"[{idx}/{len(training_stocks)}] 分析 {stock_code} {stock_name}...")
        try:
            analyzer.analyze_bull_stock(stock_code)
        except Exception as e:
            print(f"  ⚠️ 分析 {stock_code} 失败: {e}")
    
    print(f"\n✅ 大牛股分析完成，共分析了 {len(analyzer.analysis_results)} 只股票")
    
    best_model = None
    best_results = None
    best_all_passed = False
    
    for iteration in range(1, MAX_ITERATIONS + 1):
        print(f"\n{'='*80}")
        print(f"第 {iteration} 次训练")
        print(f"{'='*80}")
        
        try:
            # 训练模型
            print("\n📊 开始训练模型...")
            trained_model = analyzer.train_features()
            
            if trained_model is None or not trained_model.get('common_features'):
                print("❌ 训练失败，跳过本次迭代")
                continue
            
            print(f"✅ 模型训练完成")
            print(f"   - 特征数: {len(trained_model.get('common_features', {}))}")
            print(f"   - 样本数: {trained_model.get('sample_count', 0)}")
            
            # 验证匹配度
            results, all_passed = verify_match_scores(analyzer, VERIFY_DATE)
            
            # 保存最佳模型
            current_total_score = sum(r.get('score', 0) for r in results.values())
            best_total_score = sum(r.get('score', 0) for r in (best_results.values() if best_results else {}))
            
            if all_passed or (best_model is None) or (current_total_score > best_total_score):
                best_model = trained_model.copy()
                best_results = results.copy()
                best_all_passed = all_passed
                
                # 保存模型
                model_filename = f'trained_model_3stocks_target_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
                analyzer.save_model(model_filename)
                print(f"\n💾 保存模型: {model_filename}")
            
            # 如果达到目标，停止训练
            if all_passed:
                print(f"\n🎉 成功！所有股票匹配度均达到目标！")
                print(f"   训练次数: {iteration}")
                break
            
            # 如果未达到目标，尝试调整训练参数
            # 这里可以添加一些调整逻辑，比如调整特征权重等
            # 目前先简单重复训练，依赖随机性
            
        except Exception as e:
            print(f"❌ 第 {iteration} 次训练失败: {str(e)}")
            import traceback
            traceback.print_exc()
            continue
    
    # 输出最终结果
    print(f"\n{'='*80}")
    print("训练完成")
    print(f"{'='*80}")
    
    if best_all_passed:
        print("✅ 成功达到所有目标！")
    else:
        print("⚠️ 未完全达到目标，但已保存最佳模型")
    
    if best_results:
        print("\n最终匹配度结果：")
        for code, result in best_results.items():
            status = "✅" if result.get('passed', False) else "❌"
            print(f"{status} {code} {result.get('name', '')}: {result.get('score', 0):.3f} (目标: {result.get('target', 0):.3f})")
    
    return analyzer, best_model, best_results


if __name__ == '__main__':
    try:
        analyzer, model, results = train_model_iteratively()
        print("\n✅ 训练脚本执行完成")
    except KeyboardInterrupt:
        print("\n⚠️ 用户中断训练")
    except Exception as e:
        print(f"\n❌ 训练失败: {str(e)}")
        import traceback
        traceback.print_exc()
