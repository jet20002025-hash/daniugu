#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
微调模型权重，提高目标股票的匹配度，降低不需要股票的匹配度
测试日期：2026-01-04
"""
import os
import sys
import json
from datetime import datetime
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bull_stock_analyzer import BullStockAnalyzer

# 提高权重的股票（目标：匹配度提高）
INCREASE_WEIGHT_STOCKS = {
    '300599': {'name': '雄塑科技', 'target_score': 0.95},  # 当前0.937
    '002254': {'name': '泰和新材', 'target_score': 0.95},  # 当前0.933
    '600215': {'name': '派斯林', 'target_score': 0.93},    # 当前0.911
    '603808': {'name': '歌力思', 'target_score': 0.93},    # 当前0.911
    '600834': {'name': '申通地铁', 'target_score': 0.93},  # 当前0.910
    '300986': {'name': '志特新材', 'target_score': 0.93},  # 当前0.906
    '300234': {'name': '开尔新材', 'target_score': 0.93},  # 当前0.905
}

# 降低权重的股票（目标：匹配度降低）
DECREASE_WEIGHT_STOCKS = {
    '300205': {'name': '*ST天喻', 'target_score': 0.85},   # 当前0.934，目标降低
    '300778': {'name': '新城市', 'target_score': 0.85},    # 当前0.926，目标降低
    '603648': {'name': '畅联股份', 'target_score': 0.85},  # 当前0.923，目标降低
    '002599': {'name': '盛通股份', 'target_score': 0.85},  # 当前0.913，目标降低
    '603838': {'name': '*ST四通', 'target_score': 0.85},   # 当前0.912，目标降低
    '600719': {'name': '大连热电', 'target_score': 0.85},  # 当前0.911，目标降低
    '688609': {'name': '九联科技', 'target_score': 0.85},  # 当前0.911，目标降低
    '002908': {'name': '德生科技', 'target_score': 0.85},  # 当前0.905，目标降低
}

# 测试日期
TEST_DATE = '2026-01-04'

# 最大迭代次数
MAX_ITERATIONS = 30


def extract_features_for_stock(analyzer, code, scan_date):
    """提取股票在指定日期的特征"""
    try:
        weekly_df = analyzer.fetcher.get_weekly_kline(code, period='2y')
        if weekly_df is None or len(weekly_df) == 0:
            return None, None
        
        # 过滤到指定日期
        weekly_df['日期'] = pd.to_datetime(weekly_df['日期'])
        scan_dt = pd.to_datetime(scan_date)
        weekly_df = weekly_df[weekly_df['日期'] <= scan_dt].copy()
        weekly_df = weekly_df.sort_values('日期').reset_index(drop=True)
        
        if len(weekly_df) < 40:
            return None, None
        
        # 使用最后一周作为潜在的买点
        buy_point_idx = len(weekly_df) - 1
        
        # 找成交量突增点
        volume_surge_idx = analyzer.find_volume_surge_point(
            code, 
            buy_point_idx, 
            weekly_df=weekly_df, 
            min_volume_ratio=3.0, 
            lookback_weeks=52
        )
        
        # 确定特征起点
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
        
        return features, feature_idx
    except Exception as e:
        print(f"  ⚠️ 提取 {code} 特征失败: {e}")
        return None, None


def verify_all_stocks(analyzer, scan_date):
    """验证所有目标股票的匹配度"""
    results = {}
    
    print(f"\n{'='*80}")
    print(f"验证日期: {scan_date}")
    print(f"{'='*80}")
    
    # 验证提高权重的股票
    print("\n📈 提高权重的股票:")
    for code, info in INCREASE_WEIGHT_STOCKS.items():
        stock_name = info['name']
        target_score = info['target_score']
        
        features, _ = extract_features_for_stock(analyzer, code, scan_date)
        if features is None:
            results[code] = {'score': 0, 'target': target_score, 'type': 'increase', 'error': '无法提取特征'}
            print(f"  ❌ {code} {stock_name}: 无法提取特征")
            continue
        
        trained_features = analyzer.get_trained_features()
        if trained_features is None:
            results[code] = {'score': 0, 'target': target_score, 'type': 'increase', 'error': '模型未训练'}
            print(f"  ❌ {code} {stock_name}: 模型未训练")
            continue
        
        match_result = analyzer._calculate_match_score(
            features, 
            trained_features.get('common_features', {}),
            tolerance=0.3
        )
        match_score = match_result.get('总匹配度', 0)
        
        passed = match_score >= target_score
        status = "✅" if passed else "❌"
        results[code] = {
            'score': match_score,
            'target': target_score,
            'type': 'increase',
            'passed': passed,
            'name': stock_name
        }
        print(f"  {status} {code} {stock_name}: {match_score:.3f} (目标: {target_score:.3f}) {'✓' if passed else '✗'}")
    
    # 验证降低权重的股票
    print("\n📉 降低权重的股票:")
    for code, info in DECREASE_WEIGHT_STOCKS.items():
        stock_name = info['name']
        target_score = info['target_score']
        
        features, _ = extract_features_for_stock(analyzer, code, scan_date)
        if features is None:
            results[code] = {'score': 1.0, 'target': target_score, 'type': 'decrease', 'error': '无法提取特征'}
            print(f"  ❌ {code} {stock_name}: 无法提取特征")
            continue
        
        trained_features = analyzer.get_trained_features()
        if trained_features is None:
            results[code] = {'score': 1.0, 'target': target_score, 'type': 'decrease', 'error': '模型未训练'}
            print(f"  ❌ {code} {stock_name}: 模型未训练")
            continue
        
        match_result = analyzer._calculate_match_score(
            features, 
            trained_features.get('common_features', {}),
            tolerance=0.3
        )
        match_score = match_result.get('总匹配度', 0)
        
        passed = match_score <= target_score
        status = "✅" if passed else "❌"
        results[code] = {
            'score': match_score,
            'target': target_score,
            'type': 'decrease',
            'passed': passed,
            'name': stock_name
        }
        print(f"  {status} {code} {stock_name}: {match_score:.3f} (目标: ≤{target_score:.3f}) {'✓' if passed else '✗'}")
    
    # 统计结果
    increase_passed = sum(1 for r in results.values() if r.get('type') == 'increase' and r.get('passed', False))
    decrease_passed = sum(1 for r in results.values() if r.get('type') == 'decrease' and r.get('passed', False))
    total_passed = increase_passed + decrease_passed
    total_stocks = len(INCREASE_WEIGHT_STOCKS) + len(DECREASE_WEIGHT_STOCKS)
    
    print(f"\n{'='*80}")
    print(f"结果统计: {total_passed}/{total_stocks} 只股票达到目标")
    print(f"  - 提高权重: {increase_passed}/{len(INCREASE_WEIGHT_STOCKS)} 只达到目标")
    print(f"  - 降低权重: {decrease_passed}/{len(DECREASE_WEIGHT_STOCKS)} 只达到目标")
    print(f"{'='*80}\n")
    
    all_passed = total_passed == total_stocks
    return results, all_passed


def analyze_feature_differences(analyzer, scan_date):
    """分析提高权重和降低权重股票的特征差异"""
    increase_features = []
    decrease_features = []
    
    # 提取提高权重股票的特征
    for code in INCREASE_WEIGHT_STOCKS.keys():
        features, _ = extract_features_for_stock(analyzer, code, scan_date)
        if features:
            increase_features.append(features)
    
    # 提取降低权重股票的特征
    for code in DECREASE_WEIGHT_STOCKS.keys():
        features, _ = extract_features_for_stock(analyzer, code, scan_date)
        if features:
            decrease_features.append(features)
    
    if len(increase_features) == 0 or len(decrease_features) == 0:
        return None
    
    # 计算特征差异
    feature_diffs = {}
    
    # 获取所有特征名
    all_feature_names = set()
    for f in increase_features + decrease_features:
        all_feature_names.update(f.keys())
    
    for feature_name in all_feature_names:
        increase_values = [f.get(feature_name) for f in increase_features if f.get(feature_name) is not None]
        decrease_values = [f.get(feature_name) for f in decrease_features if f.get(feature_name) is not None]
        
        if len(increase_values) > 0 and len(decrease_values) > 0:
            try:
                increase_mean = np.mean([float(v) for v in increase_values if isinstance(v, (int, float))])
                decrease_mean = np.mean([float(v) for v in decrease_values if isinstance(v, (int, float))])
                
                if isinstance(increase_mean, (int, float)) and isinstance(decrease_mean, (int, float)):
                    diff = increase_mean - decrease_mean
                    feature_diffs[feature_name] = {
                        'increase_mean': increase_mean,
                        'decrease_mean': decrease_mean,
                        'diff': diff
                    }
            except:
                pass
    
    return feature_diffs


def adjust_model_weights(analyzer, feature_diffs, iteration, increase_features_list, decrease_features_list):
    """根据特征差异调整模型权重（改进版：更激进的调整策略）"""
    trained_features = analyzer.get_trained_features()
    if trained_features is None:
        return None
    
    common_features = trained_features.get('common_features', {}).copy()
    
    # 更激进的调整策略：直接调整标准差和中位数
    # 调整幅度：从0.3逐渐减小到0.15
    base_adjustment = 0.3
    adjustment_factor = base_adjustment * (1.0 - 0.3 * iteration / MAX_ITERATIONS)
    
    # 计算提高权重股票的特征统计值
    increase_stats = {}
    
    # 获取所有特征名
    all_feature_names = set()
    for f in increase_features_list:
        all_feature_names.update(f.keys())
    
    for feature_name in all_feature_names:
        # 计算提高权重股票的特征值列表
        increase_values = []
        for f in increase_features_list:
            val = f.get(feature_name)
            if val is not None and isinstance(val, (int, float)) and not np.isnan(val):
                increase_values.append(float(val))
        
        if len(increase_values) > 0:
            increase_stats[feature_name] = {
                'mean': np.mean(increase_values),
                'median': np.median(increase_values),
                'std': np.std(increase_values) if len(increase_values) > 1 else abs(increase_values[0]) * 0.1 if increase_values[0] != 0 else 0.1,
                'min': np.min(increase_values),
                'max': np.max(increase_values)
            }
    
    # 调整模型特征统计值
    for feature_name in all_feature_names:
        if feature_name not in common_features:
            continue
        
        if feature_name not in increase_stats:
            continue
        
        stats = common_features[feature_name]
        increase_stat = increase_stats[feature_name]
        
        # 当前模型的值
        current_median = stats.get('中位数', stats.get('均值', 0))
        current_std = stats.get('标准差', 0)
        current_min = stats.get('最小值', current_median - 2 * current_std if current_std > 0 else current_median - 1)
        current_max = stats.get('最大值', current_median + 2 * current_std if current_std > 0 else current_median + 1)
        
        # 目标：使模型的中位数更接近提高权重股票的中位数
        target_median = increase_stat['median']
        target_std = increase_stat['std']
        
        # 调整中位数（向提高权重股票的中位数移动）
        diff_median = target_median - current_median
        new_median = current_median + adjustment_factor * diff_median
        
        # 调整标准差：增大标准差可以降低z-score，提高匹配度
        # 但要确保标准差不会太小（太小会导致匹配度降低）
        if target_std > 0:
            # 如果当前标准差太小，增大它
            if current_std < target_std * 1.5:
                # 增大标准差（提高匹配度）
                new_std = current_std + adjustment_factor * (target_std * 1.5 - current_std)
            else:
                # 如果当前标准差已经很大，稍微减小
                new_std = current_std - adjustment_factor * 0.1 * current_std
            new_std = max(0.01, new_std)  # 确保标准差>0
        else:
            new_std = current_std
        
        # 调整最小值/最大值范围（扩大范围可以提高匹配度）
        range_increase = increase_stat['max'] - increase_stat['min']
        if range_increase > 0:
            # 扩大范围
            buffer = range_increase * 0.2 * adjustment_factor
            new_min = min(current_min, increase_stat['min'] - buffer)
            new_max = max(current_max, increase_stat['max'] + buffer)
        else:
            new_min = current_min
            new_max = current_max
        
        # 更新统计值
        stats['中位数'] = new_median
        if '均值' in stats:
            stats['均值'] = new_median  # 也更新均值
        stats['标准差'] = new_std
        stats['最小值'] = new_min
        stats['最大值'] = new_max
    
    return common_features


def tune_model_iteratively():
    """迭代微调模型"""
    print("="*80)
    print("开始微调模型权重")
    print("="*80)
    print("\n提高权重的股票:")
    for code, info in INCREASE_WEIGHT_STOCKS.items():
        print(f"  - {code} {info['name']}: 目标匹配度 >= {info['target_score']:.3f}")
    print("\n降低权重的股票:")
    for code, info in DECREASE_WEIGHT_STOCKS.items():
        print(f"  - {code} {info['name']}: 目标匹配度 <= {info['target_score']:.3f}")
    print(f"\n测试日期: {TEST_DATE}")
    print("="*80)
    
    # 加载当前模型
    analyzer = BullStockAnalyzer(
        auto_load_default_stocks=False,
        auto_analyze_and_train=False
    )
    
    print("\n📦 加载当前模型...")
    if not analyzer.load_model('trained_model.json', skip_network=True):
        print("❌ 无法加载当前模型")
        return None, None, None
    
    trained_features = analyzer.get_trained_features()
    if trained_features:
        print(f"✅ 模型加载成功")
        print(f"   - 特征数: {len(trained_features.get('common_features', {}))}")
        print(f"   - 样本数: {trained_features.get('sample_count', 0)}")
    
    # 先验证当前状态
    print("\n📊 验证当前模型状态...")
    initial_results, _ = verify_all_stocks(analyzer, TEST_DATE)
    
    best_model = None
    best_results = initial_results.copy()
    best_score = sum(r.get('score', 0) for r in initial_results.values() if r.get('type') == 'increase') - \
                 sum(r.get('score', 0) for r in initial_results.values() if r.get('type') == 'decrease')
    
    # 分析特征差异
    print("\n📊 分析特征差异...")
    feature_diffs = analyze_feature_differences(analyzer, TEST_DATE)
    if feature_diffs:
        print(f"✅ 找到 {len(feature_diffs)} 个有差异的特征")
        # 显示差异最大的前10个特征
        sorted_diffs = sorted(feature_diffs.items(), key=lambda x: abs(x[1]['diff']), reverse=True)
        print("\n差异最大的特征（前10个）:")
        for i, (name, diff_info) in enumerate(sorted_diffs[:10], 1):
            print(f"  {i}. {name}: 提高权重均值={diff_info['increase_mean']:.3f}, "
                  f"降低权重均值={diff_info['decrease_mean']:.3f}, "
                  f"差异={diff_info['diff']:.3f}")
    
    # 迭代微调
    increase_features_list = []
    decrease_features_list = []
    
    # 预先提取所有特征
    print("\n📊 提取所有股票的特征...")
    for code in INCREASE_WEIGHT_STOCKS.keys():
        features, _ = extract_features_for_stock(analyzer, code, TEST_DATE)
        if features:
            increase_features_list.append(features)
    
    for code in DECREASE_WEIGHT_STOCKS.keys():
        features, _ = extract_features_for_stock(analyzer, code, TEST_DATE)
        if features:
            decrease_features_list.append(features)
    
    print(f"✅ 提取完成: 提高权重 {len(increase_features_list)} 只, 降低权重 {len(decrease_features_list)} 只")
    
    for iteration in range(1, MAX_ITERATIONS + 1):
        print(f"\n{'='*80}")
        print(f"第 {iteration} 次微调")
        print(f"{'='*80}")
        
        try:
            # 调整模型权重
            if increase_features_list and decrease_features_list:
                adjusted_features = adjust_model_weights(
                    analyzer, 
                    feature_diffs, 
                    iteration,
                    increase_features_list,
                    decrease_features_list
                )
                if adjusted_features:
                    # 更新模型
                    analyzer.trained_features = {
                        'common_features': adjusted_features,
                        'sample_count': trained_features.get('sample_count', 0),
                        'trained_at': datetime.now().isoformat()
                    }
            
            # 验证调整后的效果
            results, all_passed = verify_all_stocks(analyzer, TEST_DATE)
            
            # 计算综合得分（提高权重股票得分 - 降低权重股票得分）
            current_score = sum(r.get('score', 0) for r in results.values() if r.get('type') == 'increase') - \
                           sum(r.get('score', 0) for r in results.values() if r.get('type') == 'decrease')
            
            # 保存最佳模型
            if all_passed or (best_model is None) or (current_score > best_score):
                best_model = analyzer.trained_features.copy() if analyzer.trained_features else None
                best_results = results.copy()
                best_score = current_score
                
                # 保存模型
                model_filename = f'trained_model_tuned_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
                analyzer.save_model(model_filename)
                print(f"\n💾 保存模型: {model_filename}")
            
            # 如果达到目标，停止
            if all_passed:
                print(f"\n🎉 成功！所有股票匹配度均达到目标！")
                print(f"   微调次数: {iteration}")
                break
            
        except Exception as e:
            print(f"❌ 第 {iteration} 次微调失败: {str(e)}")
            import traceback
            traceback.print_exc()
            continue
    
    # 输出最终结果
    print(f"\n{'='*80}")
    print("微调完成")
    print(f"{'='*80}")
    
    if best_results:
        print("\n最终匹配度结果：")
        print("\n提高权重的股票:")
        for code, result in best_results.items():
            if result.get('type') == 'increase':
                status = "✅" if result.get('passed', False) else "❌"
                print(f"{status} {code} {result.get('name', '')}: {result.get('score', 0):.3f} (目标: {result.get('target', 0):.3f})")
        
        print("\n降低权重的股票:")
        for code, result in best_results.items():
            if result.get('type') == 'decrease':
                status = "✅" if result.get('passed', False) else "❌"
                print(f"{status} {code} {result.get('name', '')}: {result.get('score', 0):.3f} (目标: ≤{result.get('target', 0):.3f})")
    
    return analyzer, best_model, best_results


if __name__ == '__main__':
    try:
        analyzer, model, results = tune_model_iteratively()
        print("\n✅ 微调脚本执行完成")
    except KeyboardInterrupt:
        print("\n⚠️ 用户中断微调")
    except Exception as e:
        print(f"\n❌ 微调失败: {str(e)}")
        import traceback
        traceback.print_exc()
