#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
训练模型，确保所有大牛股匹配度达到1.0
强调均线粘合度作为重要权重
"""
import os
import sys
import json
from datetime import datetime
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bull_stock_analyzer import BullStockAnalyzer

# 所有大牛股的买点信息（已更新）
ALL_BULL_STOCKS = {
    '301005': {'name': '超捷股份', 'buy_date': '2025-11-14', 'buy_price': 48.76, 'ma_diff_percent': 1.25},
    '000592': {'name': '平潭发展', 'buy_date': '2025-10-16', 'buy_price': 3.37, 'ma_diff_percent': 3.03},
    '600343': {'name': '航天动力', 'buy_date': '2025-10-31', 'buy_price': 15.30, 'ma_diff_percent': 3.59},
    '603122': {'name': '合富中国', 'buy_date': '2025-10-17', 'buy_price': 6.28, 'ma_diff_percent': 4.31},
    '002104': {'name': '恒宝股份', 'buy_date': '2025-05-23', 'buy_price': 7.13, 'ma_diff_percent': 6.81},
    '603778': {'name': '国晟科技', 'buy_date': '2025-10-10', 'buy_price': 3.48, 'ma_diff_percent': 7.59},
    '603216': {'name': '梦天家居', 'buy_date': '2025-11-05', 'buy_price': 15.70, 'ma_diff_percent': 8.17},
    '002788': {'name': '鹭燕医药', 'buy_date': '2025-12-11', 'buy_price': 10.52, 'ma_diff_percent': 9.30},
    '301232': {'name': '飞沃科技', 'buy_date': '2025-12-02', 'buy_price': 58.29, 'ma_diff_percent': 12.85},
    '300436': {'name': '广生堂', 'buy_date': '2025-07-02', 'buy_price': 35.65, 'ma_diff_percent': 4.46},
    '002759': {'name': '天际股份', 'buy_date': '2025-08-28', 'buy_price': 9.91, 'ma_diff_percent': 11.20},
}

# 目标匹配度：所有股票都达到1.0
TARGET_SCORE = 1.0

# 最大迭代次数（扩展参数后组合更多）
MAX_ITERATIONS = 200
# 快速模式：只试少量组合，便于本地验证；设为 0 禁用
QUICK_MODE_ITERATIONS = 0

# 选择性模式：紧参数、不激进扩区间，扫描时命中少、区分度高。与“匹配度1”相反。
SELECTIVE_MODE = os.environ.get('TRAIN_SELECTIVE', '0') == '1'


def extract_features_for_stock(analyzer, code, buy_date):
    """提取股票在买点日期的特征（仅用本地数据）"""
    try:
        weekly_df = analyzer.fetcher.get_weekly_kline(code, period='2y', use_cache=True, local_only=True)
        if weekly_df is None or len(weekly_df) == 0:
            return None, None
        
        weekly_df['日期'] = pd.to_datetime(weekly_df['日期'])
        buy_dt = pd.to_datetime(buy_date)
        weekly_df = weekly_df[weekly_df['日期'] <= buy_dt].copy()
        weekly_df = weekly_df.sort_values('日期').reset_index(drop=True)
        
        if len(weekly_df) < 40:
            return None, None
        
        buy_point_idx = len(weekly_df) - 1
        
        volume_surge_idx = analyzer.find_volume_surge_point(
            code, buy_point_idx, weekly_df=weekly_df, min_volume_ratio=3.0, lookback_weeks=52
        )
        
        if volume_surge_idx is not None and volume_surge_idx >= 40:
            feature_idx = volume_surge_idx
        else:
            feature_idx = max(0, buy_point_idx - 20)
        
        features = analyzer.extract_features_at_start_point(
            code, feature_idx, lookback_weeks=40, weekly_df=weekly_df
        )
        
        return features, feature_idx
    except Exception as e:
        print(f"  ⚠️ 提取 {code} 特征失败: {e}")
        return None, None


def verify_all_stocks(analyzer, precomputed_features=None, verbose=True):
    """验证所有股票的匹配度
    
    :param precomputed_features: 预提取的特征字典 {code: {'features': ..., ...}}
    :param verbose: 是否打印详细信息
    """
    results = {}
    
    if verbose:
        print(f"\n{'='*80}")
        print(f"验证匹配度（目标: {TARGET_SCORE:.3f}）")
        print(f"{'='*80}\n")
    
    for idx, (code, info) in enumerate(ALL_BULL_STOCKS.items(), 1):
        stock_name = info['name']
        buy_date = info['buy_date']
        ma_diff = info['ma_diff_percent']
        
        # ✅ 使用预提取的特征，避免重复计算
        if precomputed_features and code in precomputed_features:
            features = precomputed_features[code]['features']
        else:
            features, _ = extract_features_for_stock(analyzer, code, buy_date)
        
        if features is None:
            results[code] = {'score': 0, 'target': TARGET_SCORE, 'error': '无法提取特征'}
            if verbose:
                print(f"  ❌ {code} {stock_name}: 无法提取特征")
            continue
        
        common_features = analyzer._get_common_features()
        if not common_features:
            results[code] = {'score': 0, 'target': TARGET_SCORE, 'error': '特征模板为空'}
            if verbose:
                print(f"  ❌ {code} {stock_name}: 特征模板为空")
            continue
        
        match_result = analyzer._calculate_match_score(features, common_features, tolerance=0.3)
        match_score = match_result.get('总匹配度', 0)
        
        passed = match_score >= TARGET_SCORE
        status = "✅" if passed else "❌"
        results[code] = {
            'score': match_score,
            'target': TARGET_SCORE,
            'passed': passed,
            'name': stock_name,
            'ma_diff_percent': ma_diff
        }
        
        # 只在verbose模式下打印详细信息
        if verbose:
            ma_tag = "（均线粘合）" if ma_diff < 10 else "（均线分散）"
            print(f"  {status} {code} {stock_name}: {match_score:.3f} (目标: {TARGET_SCORE:.3f}, 均线差值: {ma_diff:.2f}%) {ma_tag} {'✓' if passed else '✗'}")
    
    passed_count = sum(1 for r in results.values() if r.get('passed', False))
    total_count = len(results)
    
    if verbose:
        print(f"\n{'='*80}")
        print(f"结果统计: {passed_count}/{total_count} 只股票达到目标 {TARGET_SCORE:.3f}")
        print(f"{'='*80}\n")
    
    all_passed = passed_count == total_count
    return results, all_passed


def create_model_from_all_stocks(analyzer, std_multiplier=3.0, range_buffer=0.5, ma_weight_factor=0.3, precomputed_features=None, excluded_big_bear_codes=None, selective=False):
    """
    基于所有大牛股的特征创建新模型。
    适度加权均线粘合度（ma_weight_factor=0.3，较低权重，避免过度偏向）。
    买点当日为大阴线的股票排除，不参与训练。
    
    :param precomputed_features: 预提取的特征字典 {code: {'features': ..., 'feature_idx': ..., ...}}
    :param excluded_big_bear_codes: 预先排除的大阴线股票代码集合
    :param selective: 选择性模式。True=紧参数、不激进扩区间，扫描命中少；False=匹配度1 的宽松逻辑。
    """
    all_features = []
    ma_convergence_features = []  # 均线粘合度低的股票特征（用于加权）
    
    for code, info in ALL_BULL_STOCKS.items():
        stock_name = info['name']
        buy_date = info['buy_date']
        ma_diff = info['ma_diff_percent']
        
        # ✅ 如果股票被预先排除（大阴线），跳过
        if excluded_big_bear_codes and code in excluded_big_bear_codes:
            continue
        
        # ✅ 如果提供了预提取特征，直接使用，跳过所有检查
        if precomputed_features and code in precomputed_features:
            features = precomputed_features[code]['features']
        else:
            # 回退：如果没有预提取，才进行检查和提取（这种情况不应该发生）
            if hasattr(analyzer, '_is_big_bearish_candle_on_date') and analyzer._is_big_bearish_candle_on_date(code, buy_date):
                continue
            features, _ = extract_features_for_stock(analyzer, code, buy_date)
        
        if features:
            features['股票代码'] = code
            features['股票名称'] = stock_name
            features['均线差值百分比'] = ma_diff
            all_features.append(features)
            
            # 均线粘合度低于10%的股票特征（用于适度加权）
            if ma_diff < 10:
                ma_convergence_features.append(features)
    
    if len(all_features) == 0:
        return None
    
    # 计算共同特征统计值
    common_features = {}
    
    # 获取所有特征名
    all_feature_names = set()
    for f in all_features:
        all_feature_names.update(f.keys())
    
    # 移除非特征字段
    all_feature_names.discard('股票代码')
    all_feature_names.discard('股票名称')
    all_feature_names.discard('均线差值百分比')
    
    # ✅ 优化：批量计算，减少循环开销
    feature_count = len(all_feature_names)
    processed = 0
    
    for feature_name in all_feature_names:
        processed += 1
        if processed % 10 == 0:
            print(f"  计算特征统计值: {processed}/{feature_count}...", end='\r', flush=True)
        
        # 所有股票的值
        all_values = []
        for f in all_features:
            val = f.get(feature_name)
            if val is not None and isinstance(val, (int, float)) and not np.isnan(val):
                all_values.append(float(val))
        
        if len(all_values) == 0:
            continue
        
        # 均线粘合度低的股票的值（用于适度加权）
        ma_values = []
        for f in ma_convergence_features:
            val = f.get(feature_name)
            if val is not None and isinstance(val, (int, float)) and not np.isnan(val):
                ma_values.append(float(val))
        
        # 计算统计值（适度加权均线粘合度，但不过度）
        mean_val = np.mean(all_values)
        median_val = np.median(all_values)
        std_val = np.std(all_values) if len(all_values) > 1 else abs(mean_val) * 0.2 if mean_val != 0 else 0.1
        min_val = np.min(all_values)
        max_val = np.max(all_values)
        
        # 如果均线粘合度低的股票有数据，使用适度加权（权重较低，避免过度偏向）
        if len(ma_values) > 0 and ma_weight_factor > 0:
            ma_mean = np.mean(ma_values)
            # 适度加权：均线粘合度低的股票权重较低（0.7 vs 0.3 * ma_weight_factor）
            # ma_weight_factor=0.3 时，加权后均值 = 0.7 * 全样本均值 + 0.3 * 0.3 * 均线粘合均值 = 0.7 * 全样本 + 0.09 * 均线粘合
            weighted_mean = (mean_val * 0.7 + ma_mean * 0.3 * ma_weight_factor) / (0.7 + 0.3 * ma_weight_factor)
            mean_val = weighted_mean
        
        # 标准差与 [min,max] 范围
        expanded_std = std_val * std_multiplier
        range_val = max_val - min_val
        
        if selective:
            # 选择性模式（严格版）：使用百分位数而非 min/max，排除极端值
            if range_val > 0 and len(all_values) >= 4:
                # 使用 25% 和 75% 分位数，排除极端值的影响
                q25 = np.percentile(all_values, 25)
                q75 = np.percentile(all_values, 75)
                iqr = q75 - q25  # 四分位距
                # 使用很小的 buffer（0.1-0.25 倍 IQR）
                buffer = iqr * range_buffer
                expanded_min = q25 - buffer
                expanded_max = q75 + buffer
                # 确保至少覆盖 min/max（但不扩展太多）
                expanded_min = min(expanded_min, min_val)
                expanded_max = max(expanded_max, max_val)
            elif range_val > 0:
                # 样本数太少，使用 min/max 但 buffer 很小
                buffer = range_val * range_buffer * 0.5  # 减半
                expanded_min = min_val - buffer
                expanded_max = max_val + buffer
            else:
                buf = abs(mean_val) * max(0.05, range_buffer * 0.3) if mean_val != 0 else 0.05
                expanded_min = mean_val - buf
                expanded_max = mean_val + buf
            # 不做“确保所有值都在范围内”的二次扩展
        else:
            # 匹配度1 模式：激进扩区间，确保所有大牛股都在范围内
            if range_val > 0:
                buffer = max(range_val * range_buffer, abs(mean_val) * 0.5)
                expanded_min = min_val - buffer
                expanded_max = max_val + buffer
            else:
                buffer = abs(mean_val) * max(0.5, range_buffer) if mean_val != 0 else 0.1
                expanded_min = mean_val - buffer
                expanded_max = mean_val + buffer
            for f in all_features:
                val = f.get(feature_name)
                if val is not None and isinstance(val, (int, float)) and not np.isnan(val):
                    if val < expanded_min:
                        expanded_min = val - max(abs(val) * 0.2, range_val * 0.3)
                    if val > expanded_max:
                        expanded_max = val + max(abs(val) * 0.2, range_val * 0.3)
        
        common_features[feature_name] = {
            '均值': round(float(mean_val), 4),
            '中位数': round(float(median_val), 4),
            '标准差': round(float(expanded_std), 4),
            '最小值': round(float(expanded_min), 4),
            '最大值': round(float(expanded_max), 4),
            '样本数': len(all_values),
            '均线粘合样本数': len(ma_values)
        }
    
    if processed > 0:
        print(f"  计算特征统计值: {processed}/{feature_count} ✅" + " " * 20)  # 清除进度行
    
    return {
        'common_features': common_features,
        'sample_count': len(all_features),
        'ma_convergence_count': len(ma_convergence_features),
        'trained_at': datetime.now().isoformat(),
        'model_type': 'selective_ma_weight_moderate' if selective else 'tuned_match_1_ma_weight_moderate',
        'sample_stocks': [f.get('股票代码') for f in all_features]
    }


def main():
    print("="*80)
    if SELECTIVE_MODE:
        print("训练模型：选择性模式（严格版 - 极紧参数、极少命中，扫描时区分度极高）")
    else:
        print("训练模型：确保所有大牛股匹配度达到1.0")
    print("均线粘合适度加权（在其他条件相同时，均线粘合度高的匹配度更高）")
    print("买点当日大阴线排除")
    print("数据：仅本地缓存，缺失时先下载完整数据")
    print("="*80)
    
    from download_training_data import ensure_training_data_local
    print("\n📥 检查训练数据：本地缺失则从网络下载完整数据...")
    ensure_training_data_local()
    print()
    
    # 下载完成后，训练阶段仅从本地读取，不再访问网络
    os.environ["TRAIN_LOCAL_ONLY"] = "1"
    
    # 加载当前模型
    analyzer = BullStockAnalyzer(auto_load_default_stocks=False, auto_analyze_and_train=False)
    if not analyzer.load_model('trained_model.json', skip_network=True):
        print("❌ 无法加载基础模型")
        return
    
    print(f"\n✅ 已加载基础模型")
    
    # ✅ 优化：预先提取所有股票的特征，避免每次迭代重复提取
    # 同时预先检查大阴线，避免在迭代中重复检查
    print("\n⚡ 预先提取所有股票特征（避免重复计算）...")
    precomputed_features = {}
    excluded_big_bear_codes = set()  # 记录被排除的股票代码
    
    for code, info in ALL_BULL_STOCKS.items():
        stock_name = info['name']
        buy_date = info['buy_date']
        print(f"  提取 {code} {stock_name} 的特征...", end='', flush=True)
        
        # 预先检查大阴线
        if hasattr(analyzer, '_is_big_bearish_candle_on_date') and analyzer._is_big_bearish_candle_on_date(code, buy_date):
            excluded_big_bear_codes.add(code)
            print(" ⏭️ 大阴线排除")
            continue
        
        features, feature_idx = extract_features_for_stock(analyzer, code, buy_date)
        if features:
            precomputed_features[code] = {'features': features, 'feature_idx': feature_idx, 'name': stock_name, 'buy_date': buy_date}
            print(" ✅")
        else:
            print(" ❌ 失败")
    
    print(f"✅ 成功预提取 {len(precomputed_features)}/{len(ALL_BULL_STOCKS)} 只股票的特征")
    if excluded_big_bear_codes:
        print(f"✅ 已排除买点当日大阴线: {len(excluded_big_bear_codes)} 只")
    
    # 验证初始状态（使用预提取特征，显示详细信息）
    print("\n📊 验证初始匹配度...")
    initial_results, _ = verify_all_stocks(analyzer, precomputed_features=precomputed_features, verbose=True)
    
    best_model = None
    best_score = -1.0
    best_avg = -1.0
    best_min = -1.0
    best_iteration = 0
    
    # 尝试不同的参数组合
    if SELECTIVE_MODE:
        # 选择性模式（严格版）：更紧的 std、更紧的 range，扫描命中极少
        std_multipliers = [1.0, 1.2, 1.5, 2.0]  # 从 1.5-3.0 收紧到 1.0-2.0
        range_buffers = [0.1, 0.15, 0.2, 0.25]  # 从 0.2-0.5 收紧到 0.1-0.25
        ma_weight_factors = [0.25, 0.3]
    elif QUICK_MODE_ITERATIONS and QUICK_MODE_ITERATIONS > 0:
        std_multipliers = [12.0, 18.0]
        range_buffers = [1.5, 2.0]
        ma_weight_factors = [0.3]
    else:
        # 匹配度1 模式：宽松网格
        std_multipliers = [10.0, 14.0, 18.0, 22.0]
        range_buffers = [1.2, 1.5, 2.0, 2.5]
        ma_weight_factors = [0.25, 0.35]
    
    iteration = 0
    all_passed = False
    total_iterations = len(std_multipliers) * len(range_buffers) * len(ma_weight_factors)
    
    for std_mult in std_multipliers:
        for range_buf in range_buffers:
            for ma_weight in ma_weight_factors:
                iteration += 1
                if iteration > MAX_ITERATIONS:
                    break
                
                print(f"\n[ {iteration}/{total_iterations} ] std={std_mult} range={range_buf} ma={ma_weight}")
                
                # 创建新模型（适度加权均线粘合度，使用预提取特征）
                new_model = create_model_from_all_stocks(
                    analyzer,
                    std_multiplier=std_mult,
                    range_buffer=range_buf,
                    ma_weight_factor=ma_weight,
                    precomputed_features=precomputed_features,
                    excluded_big_bear_codes=excluded_big_bear_codes,
                    selective=SELECTIVE_MODE
                )
                
                if new_model is None:
                    print("❌ 创建模型失败，跳过本次迭代")
                    continue
                
                analyzer.trained_features = {
                    'common_features': new_model['common_features'],
                    'sample_count': new_model['sample_count'],
                    'trained_at': new_model['trained_at'],
                    'model_type': new_model['model_type'],
                    'sample_stocks': new_model['sample_stocks']
                }
                
                # 验证匹配度（使用预提取特征，迭代中不打印详细信息）
                results, all_passed = verify_all_stocks(analyzer, precomputed_features=precomputed_features, verbose=False)
                avg_score = sum(r.get('score', 0) for r in results.values()) / len(results) if results else 0
                min_score = min(r.get('score', 0) for r in results.values()) if results else 0
                passed_count = sum(1 for r in results.values() if r.get('passed', False))
                
                # 综合得分：兼顾平均与最低分，优先提升短板股
                composite = 0.65 * avg_score + 0.35 * min_score
                print(f"  → 平均={avg_score:.3f} 最低={min_score:.3f} 综合={composite:.3f} 达标={passed_count}/{len(results)}", end='')
                
                # 用综合得分选最佳（兼顾平均与最低，优先提升短板股）
                if composite > best_score:
                    best_score = composite
                    best_avg = avg_score
                    best_min = min_score
                    best_model = new_model
                    best_iteration = iteration
                    print(f" ✅ 最佳")
                else:
                    print()
                
                if all_passed:
                    best_model = new_model
                    best_iteration = iteration
                    best_score = composite
                    best_avg = avg_score
                    best_min = min_score
                    print(f"\n🎉 所有股票都达到目标匹配度 {TARGET_SCORE:.3f}！")
                    break
            if all_passed:
                break
        if all_passed:
            break
        if iteration > MAX_ITERATIONS:
            break
    
    # 保存最佳模型
    if best_model:
        print(f"\n{'='*80}")
        print(f"微调完成")
        print(f"{'='*80}")
        
        # 使用最佳模型进行最终验证
        analyzer.trained_features = {
            'common_features': best_model['common_features'],
            'sample_count': best_model['sample_count'],
            'trained_at': best_model['trained_at'],
            'model_type': best_model['model_type'],
            'sample_stocks': best_model['sample_stocks']
        }
        
        # 加载大牛股列表（如果需要）
        if not hasattr(analyzer, 'bull_stocks') or not analyzer.bull_stocks:
            analyzer.bull_stocks = []
            for code, info in ALL_BULL_STOCKS.items():
                analyzer.bull_stocks.append({
                    '代码': code,
                    '名称': info['name'],
                    '买点日期': info['buy_date'],
                    '起点价格': info['buy_price']
                })
        
        # 确保 bull_stocks 中的日期是字符串格式（不是 datetime 对象）
        bull_stocks_for_save = []
        for stock in analyzer.bull_stocks if hasattr(analyzer, 'bull_stocks') else []:
            stock_copy = {}
            for key, value in stock.items():
                if isinstance(value, (pd.Timestamp, datetime)):
                    stock_copy[key] = value.strftime('%Y-%m-%d') if hasattr(value, 'strftime') else str(value)[:10]
                else:
                    stock_copy[key] = value
            bull_stocks_for_save.append(stock_copy)
        
        # 保存模型
        if SELECTIVE_MODE:
            model_filename = f'trained_model_选择性严格_均线适度加权_大阴线排除_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        else:
            model_filename = f'trained_model_匹配度1_均线适度加权_大阴线排除_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        
        model_data = {
            'buy_features': {
                'common_features': best_model['common_features'],
                'sample_count': best_model['sample_count'],
                'trained_at': best_model['trained_at'],
                'model_type': best_model['model_type'],
                'sample_stocks': best_model['sample_stocks']
            },
            'bull_stocks': bull_stocks_for_save  # 使用转换后的列表
        }
        
        with open(model_filename, 'w', encoding='utf-8') as f:
            json.dump(model_data, f, ensure_ascii=False, indent=2)
        
        print(f"💾 保存模型: {model_filename}")
        print(f"📊 最佳迭代: 第 {best_iteration} 次")
        print(f"📈 最佳综合: {best_score:.3f}  平均: {best_avg:.3f}  最低: {best_min:.3f}")
        
        # 最终验证（使用预提取特征，显示详细信息）
        print(f"\n{'='*80}")
        print("最终匹配度结果：")
        print(f"{'='*80}")
        final_results, final_all_passed = verify_all_stocks(analyzer, precomputed_features=precomputed_features, verbose=True)
        
        if final_all_passed:
            print("\n🎉 所有股票都达到目标匹配度 1.000！")
        else:
            print(f"\n⚠️ 部分股票未达到目标匹配度 {TARGET_SCORE:.3f}")
        
        print(f"\n✅ 训练脚本执行完成")
    else:
        print("\n❌ 未能创建有效模型")


if __name__ == '__main__':
    main()
