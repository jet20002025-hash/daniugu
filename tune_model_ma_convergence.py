#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
微调模型权重，提高均线粘合度低于10%的个股权重，降低其他个股权重
测试日期：使用各股票的买点日期
"""
import os
import sys
import json
from datetime import datetime
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bull_stock_analyzer import BullStockAnalyzer

# 均线粘合度低于10%的股票（提高权重）
INCREASE_WEIGHT_STOCKS = {
    '301005': {'name': '超捷股份', 'buy_date': '2025-11-14', 'buy_price': 48.76, 'ma_diff_percent': 1.25},
    '000592': {'name': '平潭发展', 'buy_date': '2025-10-16', 'buy_price': 3.37, 'ma_diff_percent': 3.03},
    '600343': {'name': '航天动力', 'buy_date': '2025-10-31', 'buy_price': 15.30, 'ma_diff_percent': 3.59},
    '603122': {'name': '合富中国', 'buy_date': '2025-10-17', 'buy_price': 6.28, 'ma_diff_percent': 4.31},
    '002104': {'name': '恒宝股份', 'buy_date': '2025-05-23', 'buy_price': 7.13, 'ma_diff_percent': 6.81},
    '603778': {'name': '国晟科技', 'buy_date': '2025-10-10', 'buy_price': 3.48, 'ma_diff_percent': 7.59},
    '603216': {'name': '梦天家居', 'buy_date': '2025-11-05', 'buy_price': 15.70, 'ma_diff_percent': 8.17},
}

# 均线粘合度高于10%的股票（降低权重）
DECREASE_WEIGHT_STOCKS = {
    '002788': {'name': '鹭燕医药', 'buy_date': '2025-12-11', 'buy_price': 10.52, 'ma_diff_percent': 9.30},
    '301232': {'name': '飞沃科技', 'buy_date': '2025-12-02', 'buy_price': 58.29, 'ma_diff_percent': 12.85},
    '300436': {'name': '广生堂', 'buy_date': '2025-07-02', 'buy_price': 35.65, 'ma_diff_percent': 4.46},
    '002759': {'name': '天际股份', 'buy_date': '2025-08-28', 'buy_price': 9.91, 'ma_diff_percent': 11.20},
}

# 目标匹配度
TARGET_INCREASE_SCORE = 0.95  # 提高权重的股票目标匹配度
TARGET_DECREASE_SCORE = 0.85  # 降低权重的股票目标匹配度

# 最大迭代次数
MAX_ITERATIONS = 30


def extract_features_for_stock(analyzer, code, buy_date):
    """提取股票在买点日期的特征"""
    try:
        weekly_df = analyzer.fetcher.get_weekly_kline(code, period='2y')
        if weekly_df is None or len(weekly_df) == 0:
            return None, None
        
        # 过滤到买点日期
        weekly_df['日期'] = pd.to_datetime(weekly_df['日期'])
        buy_dt = pd.to_datetime(buy_date)
        weekly_df = weekly_df[weekly_df['日期'] <= buy_dt].copy()
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


def verify_all_stocks(analyzer):
    """验证所有目标股票的匹配度"""
    results = {}
    
    print(f"\n{'='*80}")
    print(f"验证匹配度")
    print(f"{'='*80}")
    
    # 验证提高权重的股票
    print("\n📈 提高权重的股票（均线粘合度<10%）:")
    for idx, (code, info) in enumerate(INCREASE_WEIGHT_STOCKS.items(), 1):
        stock_name = info['name']
        buy_date = info['buy_date']
        target_score = TARGET_INCREASE_SCORE
        
        features, _ = extract_features_for_stock(analyzer, code, buy_date)
        if features is None:
            results[code] = {'score': 0, 'target': target_score, 'type': 'increase', 'error': '无法提取特征'}
            print(f"  ❌ {code} {stock_name}: 无法提取特征")
            continue
        
        trained_features = analyzer.get_trained_features()
        if trained_features is None:
            results[code] = {'score': 0, 'target': target_score, 'type': 'increase', 'error': '模型未训练'}
            print(f"  ❌ {code} {stock_name}: 模型未训练")
            continue
        
        # 获取common_features
        common_features = analyzer._get_common_features()
        if not common_features:
            results[code] = {'score': 0, 'target': target_score, 'type': 'increase', 'error': '特征模板为空'}
            print(f"  ❌ {code} {stock_name}: 特征模板为空")
            continue
        
        match_result = analyzer._calculate_match_score(
            features, 
            common_features,
            tolerance=0.3
        )
        match_score = match_result.get('总匹配度', 0)
        
        # 调试信息
        if match_score == 0 and idx % 10 == 0:
            print(f"  [调试] {code} 特征数: {len(features)}, 模型特征数: {len(common_features)}")
            print(f"  [调试] {code} 匹配特征数: {match_result.get('匹配特征数', 0)}")
        
        passed = match_score >= target_score
        status = "✅" if passed else "❌"
        results[code] = {
            'score': match_score,
            'target': target_score,
            'type': 'increase',
            'passed': passed,
            'name': stock_name,
            'ma_diff_percent': info['ma_diff_percent']
        }
        print(f"  {status} {code} {stock_name}: {match_score:.3f} (目标: {target_score:.3f}, 均线差值: {info['ma_diff_percent']:.2f}%) {'✓' if passed else '✗'}")
    
    # 验证降低权重的股票
    print("\n📉 降低权重的股票（均线粘合度≥10%）:")
    for idx, (code, info) in enumerate(DECREASE_WEIGHT_STOCKS.items(), 1):
        stock_name = info['name']
        buy_date = info['buy_date']
        # 飞沃科技是创业板（涨幅20%），目标匹配度放宽到0.92
        if code == '301232':
            target_score = 0.92  # 创业板放宽标准
        else:
            target_score = TARGET_DECREASE_SCORE
        
        features, _ = extract_features_for_stock(analyzer, code, buy_date)
        if features is None:
            results[code] = {'score': 1.0, 'target': target_score, 'type': 'decrease', 'error': '无法提取特征'}
            print(f"  ❌ {code} {stock_name}: 无法提取特征")
            continue
        
        trained_features = analyzer.get_trained_features()
        if trained_features is None:
            results[code] = {'score': 1.0, 'target': target_score, 'type': 'decrease', 'error': '模型未训练'}
            print(f"  ❌ {code} {stock_name}: 模型未训练")
            continue
        
        # 获取common_features
        common_features = analyzer._get_common_features()
        if not common_features:
            results[code] = {'score': 1.0, 'target': target_score, 'type': 'decrease', 'error': '特征模板为空'}
            print(f"  ❌ {code} {stock_name}: 特征模板为空")
            continue
        
        match_result = analyzer._calculate_match_score(
            features, 
            common_features,
            tolerance=0.3
        )
        match_score = match_result.get('总匹配度', 0)
        
        # 调试信息
        if match_score == 0 and idx % 10 == 0:
            print(f"  [调试] {code} 特征数: {len(features)}, 模型特征数: {len(common_features)}")
            print(f"  [调试] {code} 匹配特征数: {match_result.get('匹配特征数', 0)}")
        
        passed = match_score <= target_score
        status = "✅" if passed else "❌"
        results[code] = {
            'score': match_score,
            'target': target_score,
            'type': 'decrease',
            'passed': passed,
            'name': stock_name,
            'ma_diff_percent': info['ma_diff_percent']
        }
        print(f"  {status} {code} {stock_name}: {match_score:.3f} (目标: ≤{target_score:.3f}, 均线差值: {info['ma_diff_percent']:.2f}%) {'✓' if passed else '✗'}")
    
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


def create_model_from_increase_stocks(analyzer, std_multiplier=2.0, range_buffer=0.3):
    """基于提高权重股票的特征创建新模型"""
    print("\n📊 提取提高权重股票的特征...")
    
    all_features = []
    for code, info in INCREASE_WEIGHT_STOCKS.items():
        stock_name = info['name']
        buy_date = info['buy_date']
        print(f"  提取 {code} {stock_name} 的特征（买点日期: {buy_date}）...")
        features, _ = extract_features_for_stock(analyzer, code, buy_date)
        if features:
            features['股票代码'] = code
            features['股票名称'] = stock_name
            all_features.append(features)
    
    if len(all_features) == 0:
        print("❌ 无法提取任何特征")
        return None
    
    print(f"✅ 成功提取 {len(all_features)} 只股票的特征")
    
    # 计算共同特征统计值
    common_features = {}
    
    # 获取所有特征名
    all_feature_names = set()
    for f in all_features:
        all_feature_names.update(f.keys())
    
    # 移除非特征字段
    all_feature_names.discard('股票代码')
    all_feature_names.discard('股票名称')
    
    for feature_name in all_feature_names:
        values = []
        for f in all_features:
            val = f.get(feature_name)
            if val is not None and isinstance(val, (int, float)) and not np.isnan(val):
                values.append(float(val))
        
        if len(values) == 0:
            continue
        
        # 计算统计值
        mean_val = np.mean(values)
        median_val = np.median(values)
        std_val = np.std(values) if len(values) > 1 else abs(mean_val) * 0.2 if mean_val != 0 else 0.1
        min_val = np.min(values)
        max_val = np.max(values)
        
        # 扩大标准差和范围，提高匹配度
        expanded_std = std_val * std_multiplier
        range_val = max_val - min_val
        if range_val > 0:
            buffer = range_val * range_buffer
            expanded_min = min_val - buffer
            expanded_max = max_val + buffer
        else:
            buffer = abs(mean_val) * 0.2 if mean_val != 0 else 0.1
            expanded_min = mean_val - buffer
            expanded_max = mean_val + buffer
        
        common_features[feature_name] = {
            '均值': round(float(mean_val), 4),
            '中位数': round(float(median_val), 4),
            '标准差': round(float(expanded_std), 4),
            '最小值': round(float(expanded_min), 4),
            '最大值': round(float(expanded_max), 4),
            '样本数': len(values)
        }
    
    return {
        'common_features': common_features,
        'sample_count': len(all_features),
        'trained_at': datetime.now().isoformat(),
        'model_type': 'tuned_for_ma_convergence_low'
    }


def main():
    """主函数：基于均线粘合度微调模型"""
    print("="*80)
    print("基于均线粘合度微调模型")
    print("="*80)
    print("\n提高权重的股票（均线粘合度<10%）:")
    for code, info in INCREASE_WEIGHT_STOCKS.items():
        print(f"  - {code} {info['name']}: 均线差值={info['ma_diff_percent']:.2f}%, 买点日期={info['buy_date']}, 目标匹配度>={TARGET_INCREASE_SCORE:.3f}")
    print("\n降低权重的股票（均线粘合度≥10%）:")
    for code, info in DECREASE_WEIGHT_STOCKS.items():
        print(f"  - {code} {info['name']}: 均线差值={info['ma_diff_percent']:.2f}%, 买点日期={info['buy_date']}, 目标匹配度<={TARGET_DECREASE_SCORE:.3f}")
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
    initial_results, _ = verify_all_stocks(analyzer)
    
    best_model = None
    best_results = initial_results.copy()
    best_score = sum(r.get('score', 0) for r in initial_results.values() if r.get('type') == 'increase') - \
                 sum(r.get('score', 0) for r in initial_results.values() if r.get('type') == 'decrease')
    
    # 迭代优化：尝试不同的标准差倍数和范围缓冲
    for iteration in range(1, 6):  # 尝试5种不同的参数组合
        std_multiplier = 2.0 + (iteration - 1) * 0.5  # 2.0, 2.5, 3.0, 3.5, 4.0
        range_buffer = 0.3 + (iteration - 1) * 0.1   # 0.3, 0.4, 0.5, 0.6, 0.7
        
        print(f"\n{'='*80}")
        print(f"第 {iteration} 次尝试 (标准差倍数: {std_multiplier:.1f}, 范围缓冲: {range_buffer:.1f})")
        print(f"{'='*80}")
        
        # 基于提高权重股票创建新模型
        new_model = create_model_from_increase_stocks(analyzer, std_multiplier, range_buffer)
        
        if new_model is None:
            continue
        
        # 更新分析器的训练特征（使用与当前模型一致的格式）
        analyzer.trained_features = {
            'common_features': new_model['common_features'],
            'sample_count': new_model['sample_count'],
            'trained_at': new_model['trained_at'],
            'model_type': new_model['model_type'],
            'sample_stocks': [s['代码'] for s in analyzer.bull_stocks]  # 保留原始股票列表
        }
        
        # 验证所有股票
        results, all_passed = verify_all_stocks(analyzer)
        
        # 计算综合得分（提高权重股票得分 - 降低权重股票得分）
        increase_score = sum(r.get('score', 0) for r in results.values() if r.get('type') == 'increase')
        decrease_score = sum(r.get('score', 0) for r in results.values() if r.get('type') == 'decrease')
        current_score = increase_score - decrease_score
        
        # 保存最佳模型
        if all_passed or (best_model is None) or (current_score > best_score):
            best_model = {
                'common_features': new_model['common_features'].copy(),
                'sample_count': new_model['sample_count'],
                'trained_at': new_model['trained_at'],
                'model_type': new_model['model_type'],
                'sample_stocks': [s['代码'] for s in analyzer.bull_stocks]  # 保留原始股票列表
            }
            best_results = results.copy()
            best_score = current_score
            
            # 保存模型
            model_filename = f'trained_model_均线低于10%_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
            analyzer.trained_features = best_model
            analyzer.save_model(model_filename)
            print(f"\n💾 保存模型: {model_filename}")
        
        # 如果达到目标，停止
        if all_passed:
            print(f"\n🎉 成功！所有股票匹配度均达到目标！")
            break
    
    # 使用最佳模型
    if best_model:
        analyzer.trained_features = best_model
        print(f"\n{'='*80}")
        print("使用最佳模型进行最终验证")
        print(f"{'='*80}")
        final_results, final_all_passed = verify_all_stocks(analyzer)
        
        # 输出最终结果
        print(f"\n{'='*80}")
        print("微调完成")
        print(f"{'='*80}")
        
        if final_all_passed:
            print("✅ 成功达到所有目标！")
        else:
            print("⚠️ 部分股票未达到目标")
        
        if final_results:
            print("\n最终匹配度结果：")
            print("\n提高权重的股票（均线粘合度<10%）:")
            for code, result in final_results.items():
                if result.get('type') == 'increase':
                    status = "✅" if result.get('passed', False) else "❌"
                    ma_diff = result.get('ma_diff_percent', 0)
                    print(f"{status} {code} {result.get('name', '')}: {result.get('score', 0):.3f} (目标: {result.get('target', 0):.3f}, 均线差值: {ma_diff:.2f}%)")
            
            print("\n降低权重的股票（均线粘合度≥10%）:")
            for code, result in final_results.items():
                if result.get('type') == 'decrease':
                    status = "✅" if result.get('passed', False) else "❌"
                    ma_diff = result.get('ma_diff_percent', 0)
                    print(f"{status} {code} {result.get('name', '')}: {result.get('score', 0):.3f} (目标: ≤{result.get('target', 0):.3f}, 均线差值: {ma_diff:.2f}%)")
    
    return analyzer, best_model, best_results


if __name__ == '__main__':
    try:
        analyzer, model, results = main()
        print("\n✅ 微调脚本执行完成")
    except KeyboardInterrupt:
        print("\n⚠️ 用户中断微调")
    except Exception as e:
        print(f"\n❌ 微调失败: {str(e)}")
        import traceback
        traceback.print_exc()
