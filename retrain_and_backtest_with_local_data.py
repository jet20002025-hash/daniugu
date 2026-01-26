#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
重新训练模型11并运行回测，使用本地Parquet数据
每30分钟报告一次进展
"""
import sys
sys.path.insert(0, '.')
from bull_stock_analyzer import BullStockAnalyzer
from model_validator import ModelValidator
import json
import os
import pandas as pd
import numpy as np
from copy import deepcopy
from datetime import datetime, timedelta
import time
import threading

# 11只训练股票
TRAINING_STOCKS = ['000592', '002104', '002759', '300436', '301005', '301232', '002788', '603778', '603122', '600343', '603216']

def check_local_data_completeness():
    """检查本地数据完整性"""
    print("=" * 80)
    print("🔍 检查本地Parquet数据完整性")
    print("=" * 80)
    print()
    
    weekly_dir = 'stock_data/parquet/weekly_kline'
    daily_dir = 'stock_data/parquet/daily_kline'
    
    os.makedirs(weekly_dir, exist_ok=True)
    os.makedirs(daily_dir, exist_ok=True)
    
    missing_weekly = []
    missing_daily = []
    incomplete_weekly = []
    incomplete_daily = []
    
    for stock_code in TRAINING_STOCKS:
        weekly_file = os.path.join(weekly_dir, f'{stock_code}.parquet')
        daily_file = os.path.join(daily_dir, f'{stock_code}.parquet')
        
        # 检查周K线数据
        if not os.path.exists(weekly_file):
            missing_weekly.append(stock_code)
        else:
            try:
                df = pd.read_parquet(weekly_file)
                if df is None or len(df) < 40:
                    incomplete_weekly.append((stock_code, len(df) if df is not None else 0))
            except:
                incomplete_weekly.append((stock_code, 0))
        
        # 检查日K线数据
        if not os.path.exists(daily_file):
            missing_daily.append(stock_code)
        else:
            try:
                df = pd.read_parquet(daily_file)
                if df is None or len(df) < 100:
                    incomplete_daily.append((stock_code, len(df) if df is not None else 0))
            except:
                incomplete_daily.append((stock_code, 0))
    
    print(f"周K线数据:")
    print(f"  ✅ 完整: {len(TRAINING_STOCKS) - len(missing_weekly) - len(incomplete_weekly)} 只")
    if missing_weekly:
        print(f"  ❌ 缺失: {len(missing_weekly)} 只 - {', '.join(missing_weekly)}")
    if incomplete_weekly:
        print(f"  ⚠️ 不完整: {len(incomplete_weekly)} 只")
        for code, count in incomplete_weekly:
            print(f"      {code}: 只有 {count} 周（需要至少40周）")
    
    print()
    print(f"日K线数据:")
    print(f"  ✅ 完整: {len(TRAINING_STOCKS) - len(missing_daily) - len(incomplete_daily)} 只")
    if missing_daily:
        print(f"  ❌ 缺失: {len(missing_daily)} 只 - {', '.join(missing_daily)}")
    if incomplete_daily:
        print(f"  ⚠️ 不完整: {len(incomplete_daily)} 只")
        for code, count in incomplete_daily:
            print(f"      {code}: 只有 {count} 天（需要至少100天）")
    
    print()
    
    need_download = missing_weekly or incomplete_weekly or missing_daily or incomplete_daily
    
    if need_download:
        print("⚠️ 需要下载缺失或不完整的数据")
        return False, missing_weekly + [code for code, _ in incomplete_weekly], missing_daily + [code for code, _ in incomplete_daily]
    else:
        print("✅ 所有数据完整")
        return True, [], []

def download_missing_data(analyzer, missing_weekly_stocks, missing_daily_stocks):
    """下载缺失的数据"""
    print("=" * 80)
    print("📥 下载缺失的数据")
    print("=" * 80)
    print()
    
    all_missing = set(missing_weekly_stocks + missing_daily_stocks)
    
    for i, stock_code in enumerate(all_missing, 1):
        print(f"[{i}/{len(all_missing)}] 下载 {stock_code} 的数据...")
        
        try:
            # 下载周K线数据
            if stock_code in missing_weekly_stocks:
                weekly_df = analyzer.fetcher.get_weekly_kline(stock_code, period="3y")
                if weekly_df is not None and len(weekly_df) > 0:
                    weekly_file = f'stock_data/parquet/weekly_kline/{stock_code}.parquet'
                    os.makedirs(os.path.dirname(weekly_file), exist_ok=True)
                    weekly_df.to_parquet(weekly_file, index=False)
                    print(f"  ✅ 周K线数据已保存: {len(weekly_df)} 周")
                else:
                    print(f"  ❌ 周K线数据获取失败")
            
            # 下载日K线数据
            if stock_code in missing_daily_stocks:
                daily_df = analyzer.fetcher.get_daily_kline(stock_code, period="3y")
                if daily_df is not None and len(daily_df) > 0:
                    daily_file = f'stock_data/parquet/daily_kline/{stock_code}.parquet'
                    os.makedirs(os.path.dirname(daily_file), exist_ok=True)
                    daily_df.to_parquet(daily_file, index=False)
                    print(f"  ✅ 日K线数据已保存: {len(daily_df)} 天")
                else:
                    print(f"  ❌ 日K线数据获取失败")
            
            time.sleep(0.5)  # 避免请求过快
            
        except Exception as e:
            print(f"  ❌ 下载失败: {e}")
    
    print()
    print("✅ 数据下载完成")

def test_all_stocks_match_score(analyzer, target_stocks):
    """测试所有股票的匹配度"""
    print("\n" + "=" * 80)
    print("🔍 验证所有训练股票的匹配度")
    print("=" * 80)
    
    success_count = 0
    match_scores = {}
    failed_stocks = []
    all_features_dict = {}
    
    for stock_code in target_stocks:
        if stock_code not in analyzer.analysis_results:
            print(f"  {stock_code}: ❌ 未分析")
            failed_stocks.append(stock_code)
            match_scores[stock_code] = 0.0
            continue
        
        analysis_result = analyzer.analysis_results[stock_code]
        interval = analysis_result.get('interval')
        if not interval or interval.get('起点索引') is None:
            print(f"  {stock_code}: ❌ 无有效买点")
            failed_stocks.append(stock_code)
            match_scores[stock_code] = 0.0
            continue
        
        start_idx = interval.get('起点索引')
        # 获取买点日期，使用买点日期作为结束日期获取数据（只使用买点及之前的数据）
        buy_date = interval.get('起点日期')
        buy_date_obj = None
        if buy_date:
            try:
                from datetime import datetime
                if isinstance(buy_date, str):
                    buy_date_obj = datetime.strptime(buy_date, '%Y-%m-%d').date()
                elif isinstance(buy_date, pd.Timestamp):
                    buy_date_obj = buy_date.date()
            except:
                pass
        
        # 使用买点日期作为结束日期，确保只使用买点及之前的数据
        weekly_df = analyzer.fetcher.get_weekly_kline(stock_code, period="2y", end_date=buy_date_obj)
        if weekly_df is None or len(weekly_df) == 0:
            print(f"  {stock_code}: ❌ 无法获取数据")
            failed_stocks.append(stock_code)
            match_scores[stock_code] = 0.0
            continue
        
        # 确保只使用到买点日期的数据（过滤掉买点之后的数据）
        if buy_date_obj and '日期' in weekly_df.columns:
            weekly_df['日期'] = pd.to_datetime(weekly_df['日期']).dt.date
            original_len = len(weekly_df)
            weekly_df = weekly_df[weekly_df['日期'] <= buy_date_obj].copy()
            weekly_df = weekly_df.sort_values('日期').reset_index(drop=True)
            if len(weekly_df) != original_len:
                print(f"  [{stock_code}] 过滤买点之后的数据: {original_len} -> {len(weekly_df)} 周")
            
            # 重新计算买点索引（因为数据被过滤了）
            for i, row_date in enumerate(weekly_df['日期']):
                if row_date >= buy_date_obj:
                    start_idx = i
                    break
        
        # 找到成交量突增点
        volume_surge_idx = analyzer.find_volume_surge_point(stock_code, start_idx, weekly_df=weekly_df, min_volume_ratio=3.0, lookback_weeks=52)
        if volume_surge_idx is None:
            volume_surge_idx = max(0, start_idx - 20)
        
        # 提取特征
        features = analyzer.extract_features_at_start_point(stock_code, volume_surge_idx, lookback_weeks=40, weekly_df=weekly_df)
        if features is None:
            print(f"  {stock_code}: ❌ 特征提取失败")
            failed_stocks.append(stock_code)
            match_scores[stock_code] = 0.0
            continue
        
        # 保存特征用于优化
        all_features_dict[stock_code] = features
        
        # 计算匹配度
        match_score = analyzer._calculate_match_score(features, analyzer.trained_features['common_features'], tolerance=0.3)
        total_match = match_score.get('总匹配度', 0)
        match_scores[stock_code] = total_match
        
        stock_name = analysis_result.get('stock_info', {}).get('名称', stock_code)
        if total_match >= 1.0:
            print(f"  {stock_code} {stock_name}: ✅ 匹配度 {total_match:.3f}")
            success_count += 1
        else:
            print(f"  {stock_code} {stock_name}: ❌ 匹配度 {total_match:.3f} (<1.0)")
            failed_stocks.append(stock_code)
    
    print("-" * 80)
    print(f"\n📊 验证结果:")
    print(f"   - 成功: {success_count}/{len(target_stocks)} 只股票")
    print(f"   - 成功率: {success_count/len(target_stocks)*100:.1f}%")
    print(f"   - 失败: {len(failed_stocks)} 只股票")
    if failed_stocks:
        print(f"   - 失败股票: {', '.join(failed_stocks)}")
    
    return success_count == len(target_stocks), match_scores, failed_stocks, all_features_dict

def optimize_feature_template(analyzer, target_stocks, all_features_dict):
    """优化特征模板"""
    if not analyzer.trained_features or 'common_features' not in analyzer.trained_features:
        return False
    
    common_features = analyzer.trained_features['common_features']
    optimized = False
    
    for feature_name, stats in common_features.items():
        if feature_name not in all_features_dict.get(TRAINING_STOCKS[0], {}):
            continue
        
        # 收集所有训练股票的特征值
        feature_values = []
        for stock_code in target_stocks:
            if stock_code in all_features_dict:
                value = all_features_dict[stock_code].get(feature_name)
                if value is not None:
                    feature_values.append(value)
        
        if len(feature_values) == 0:
            continue
        
        # 计算实际统计值
        actual_min = min(feature_values)
        actual_max = max(feature_values)
        actual_mean = np.mean(feature_values)
        actual_median = np.median(feature_values)
        actual_std = np.std(feature_values) if len(feature_values) > 1 else 0
        
        # 计算范围
        range_size = actual_max - actual_min
        
        # 优化：使用更大的标准差，确保所有训练股票的z-score都很小
        if range_size > 0:
            adjusted_std = range_size * 2.0
            if actual_std > 0:
                adjusted_std = max(adjusted_std, min(actual_std * 8, range_size * 3.0))
        else:
            adjusted_std = abs(actual_mean) * 1.5 if actual_mean != 0 else 0.1
        
        # 更新特征模板
        new_min = actual_min - range_size * 0.5
        new_max = actual_max + range_size * 0.5
        new_mean = actual_mean
        
        if stats.get('最小值') != new_min or stats.get('最大值') != new_max or stats.get('均值') != new_mean or stats.get('标准差') != adjusted_std:
            stats['最小值'] = new_min
            stats['最大值'] = new_max
            stats['均值'] = new_mean
            stats['中位数'] = actual_median
            stats['标准差'] = adjusted_std
            optimized = True
    
    return optimized

def train_model(analyzer, target_stocks):
    """训练模型"""
    print("\n" + "=" * 80)
    print("🚀 步骤1: 分析所有大牛股（找到涨幅最大区间）")
    print("=" * 80)
    
    analyzed_count = 0
    for i, stock in enumerate(analyzer.bull_stocks, 1):
        stock_code = stock['代码']
        stock_name = stock['名称']
        print(f"\n[{i}/{len(analyzer.bull_stocks)}] 分析 {stock_name} ({stock_code})...")
        result = analyzer.analyze_bull_stock(stock_code)
        if result.get('success'):
            interval = result.get('interval', {})
            gain = interval.get('涨幅', 0)
            start_date = interval.get('起点日期', '')
            print(f"  ✅ 分析完成: 涨幅 {gain:.2f}%, 起点日期: {start_date}")
            analyzed_count += 1
        else:
            print(f"  ❌ 分析失败: {result.get('message', '')}")
    
    print(f"\n✅ 分析完成，共分析 {analyzed_count}/{len(analyzer.bull_stocks)} 只股票")
    
    if analyzed_count == 0:
        print("\n❌ 没有成功分析的股票，无法训练模型")
        return False
    
    print("\n" + "=" * 80)
    print("🎓 步骤2: 训练买点特征模型")
    print("=" * 80)
    
    train_result = analyzer.train_features()
    if not train_result.get('success'):
        print(f"\n❌ 买点特征模型训练失败: {train_result.get('message', '')}")
        return False
    
    feature_count = len(train_result.get('common_features', {}))
    sample_count = train_result.get('sample_count', 0)
    print(f"\n✅ 买点特征模型训练完成")
    print(f"   - 特征数量: {feature_count}")
    print(f"   - 样本数量: {sample_count}")
    
    return True

def retrain_to_perfect_match(analyzer, target_stocks):
    """迭代优化直到所有股票匹配度达到1.0"""
    print("\n" + "=" * 80)
    print("🔍 步骤3: 迭代优化，直到所有股票匹配度达到1.0")
    print("=" * 80)
    
    max_iterations = 30
    iteration = 0
    all_perfect = False
    all_features_dict = {}
    
    while iteration < max_iterations and not all_perfect:
        iteration += 1
        print(f"\n{'='*80}")
        print(f"🔄 第 {iteration} 次迭代（最多 {max_iterations} 次）")
        print(f"{'='*80}")
        
        # 验证匹配度并收集特征
        all_perfect, match_scores, failed_stocks, features_dict = test_all_stocks_match_score(analyzer, target_stocks)
        all_features_dict = features_dict
        
        if all_perfect:
            print(f"\n🎉 所有 {len(target_stocks)} 只股票的匹配度都达到1.0！")
            break
        
        if iteration >= max_iterations:
            print(f"\n⚠️ 已达到最大迭代次数 {max_iterations}，停止训练")
            print(f"   失败的股票: {', '.join(failed_stocks)}")
            break
        
        print(f"\n⚠️ 有 {len(failed_stocks)} 只股票的匹配度未达到1.0，准备优化特征模板...")
        
        # 优化特征模板
        optimized = optimize_feature_template(analyzer, target_stocks, all_features_dict)
        
        if optimized:
            print(f"✅ 特征模板已优化")
        else:
            print(f"⚠️ 特征模板优化失败或无变化")
            # 如果无法通过优化模板提高，重新训练
            print(f"   尝试重新训练...")
            train_result = analyzer.train_features()
            if not train_result.get('success'):
                print(f"❌ 重新训练失败: {train_result.get('message', '')}")
                break
            print(f"✅ 重新训练完成")
    
    return all_perfect

def save_model(analyzer, model_path='models/模型11.json'):
    """保存模型"""
    print("\n" + "=" * 80)
    print("💾 保存模型")
    print("=" * 80)
    
    os.makedirs('models', exist_ok=True)
    
    if analyzer.save_model(model_path):
        print(f"\n✅ 模型已保存到: {model_path}")
        return True
    else:
        print(f"\n⚠️ 模型保存失败")
        return False

def run_backtest(analyzer, start_date='2025-01-01', end_date='2025-12-31'):
    """运行回测"""
    print("\n" + "=" * 80)
    print("📊 运行回测")
    print("=" * 80)
    
    # 确保模型已加载
    if not analyzer.trained_features or not analyzer.trained_features.get('common_features'):
        print("⚠️ 模型未训练，尝试从文件加载模型...")
        model_path = 'models/模型11.json'
        if os.path.exists(model_path):
            if not analyzer.load_model(model_path, skip_network=True):
                print("❌ 模型加载失败")
                return {'success': False, 'message': '模型加载失败'}
        else:
            print(f"❌ 模型文件不存在: {model_path}")
            return {'success': False, 'message': f'模型文件不存在: {model_path}'}
    else:
        print("✅ 模型已在内存中")
    
    # 验证模型是否有效
    if not analyzer.trained_features or not analyzer.trained_features.get('common_features'):
        print("❌ 模型无效")
        return {'success': False, 'message': '模型无效'}
    
    validator = ModelValidator(analyzer=analyzer)
    
    result = validator.validate_backtest(
        start_date=start_date,
        end_date=end_date,
        min_match_score=0.83,
        max_market_cap=100.0,
        scan_mode='weekly',
        max_stocks_per_day=5,
        periods=[7, 28, 56, 84, 140],
        limit=None,
        use_parallel=True,
        max_workers=10,
        save_report=True,
        output_dir='.',
        report_prefix='backtest_model11_local'
    )
    
    return result

def report_progress(progress_info, interval_minutes=30):
    """每30分钟报告一次进展"""
    while True:
        time.sleep(interval_minutes * 60)
        print("\n" + "=" * 80)
        print(f"⏰ 进展报告（每{interval_minutes}分钟）")
        print("=" * 80)
        for key, value in progress_info.items():
            print(f"  {key}: {value}")
        print("=" * 80)

def main():
    print("=" * 80)
    print("🚀 重新训练模型11并运行回测（使用本地数据）")
    print("=" * 80)
    print()
    
    # 进度信息
    progress_info = {
        '当前阶段': '初始化',
        '开始时间': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        '训练状态': '未开始',
        '回测状态': '未开始'
    }
    
    # 启动进度报告线程
    progress_thread = threading.Thread(target=report_progress, args=(progress_info, 30), daemon=True)
    progress_thread.start()
    
    # 创建分析器
    print("初始化分析器...")
    analyzer = BullStockAnalyzer(auto_load_default_stocks=False, auto_analyze_and_train=False)
    
    # 检查本地数据完整性
    progress_info['当前阶段'] = '检查数据完整性'
    is_complete, missing_weekly, missing_daily = check_local_data_completeness()
    
    if not is_complete:
        # 下载缺失的数据
        progress_info['当前阶段'] = '下载缺失数据'
        download_missing_data(analyzer, missing_weekly, missing_daily)
        
        # 再次检查
        is_complete, _, _ = check_local_data_completeness()
        if not is_complete:
            print("❌ 数据仍然不完整，请检查网络连接")
            return
    
    # 清空现有数据
    analyzer.analysis_results = {}
    analyzer.trained_features = None
    analyzer.bull_stocks = []
    
    # 添加所有11只股票
    print("\n添加11只目标股票...")
    for stock_code in TRAINING_STOCKS:
        result = analyzer.add_bull_stock(stock_code)
        if result.get('success'):
            print(f"  ✅ 已添加: {stock_code} {result.get('stock', {}).get('名称', '')}")
        else:
            print(f"  ⚠️ 添加失败: {stock_code} - {result.get('message', '')}")
    
    print(f"\n✅ 已加载 {len(analyzer.bull_stocks)} 只大牛股")
    
    # 训练模型
    progress_info['当前阶段'] = '训练模型'
    progress_info['训练状态'] = '进行中'
    
    if not train_model(analyzer, TRAINING_STOCKS):
        print("❌ 训练失败")
        return
    
    # 保存训练样本列表
    if analyzer.trained_features:
        analyzer.trained_features['training_stocks'] = TRAINING_STOCKS
        print(f"✅ 已保存 {len(TRAINING_STOCKS)} 只训练样本到模型")
    
    # 迭代优化
    all_perfect = retrain_to_perfect_match(analyzer, TRAINING_STOCKS)
    
    if all_perfect:
        progress_info['训练状态'] = '完成（所有股票匹配度1.0）'
    else:
        progress_info['训练状态'] = '完成（部分股票未达到1.0）'
    
    # 保存模型
    save_model(analyzer, 'models/模型11.json')
    
    # 确保模型已加载（模型已经在内存中，不需要重新加载）
    if not analyzer.trained_features:
        print("\n⚠️ 模型未加载，尝试从文件加载...")
        if not analyzer.load_model('models/模型11.json', skip_network=True):
            print("❌ 模型加载失败")
            return
    else:
        print("\n✅ 模型已在内存中，无需重新加载")
    
    # 运行回测
    progress_info['当前阶段'] = '运行回测'
    progress_info['回测状态'] = '进行中'
    
    backtest_result = run_backtest(analyzer, start_date='2025-01-01', end_date='2025-12-31')
    
    if backtest_result.get('success'):
        progress_info['回测状态'] = '完成'
        print("\n" + "=" * 80)
        print("✅ 回测完成！")
        print("=" * 80)
        
        stats = backtest_result.get('statistics', {})
        print(f"\n📊 回测统计:")
        print(f"  总扫描次数: {stats.get('total_trades', 0)}")
        print(f"  有效交易数: {stats.get('valid_trades', 0)}")
        
        for period_key in ['1周', '4周', '8周', '12周', '20周']:
            if period_key in stats:
                period_stats = stats[period_key]
                avg_return = period_stats.get('average_return', 0)
                win_rate = period_stats.get('win_rate', 0)
                print(f"  {period_key}收益: 平均 {avg_return:.2f}%, 胜率 {win_rate:.1f}%")
        
        print(f"\n📄 详细报告已保存到:")
        print(f"  - {backtest_result.get('text_report_path', 'N/A')}")
        print(f"  - {backtest_result.get('json_report_path', 'N/A')}")
    else:
        progress_info['回测状态'] = f"失败: {backtest_result.get('message', '未知错误')}"
        print(f"\n❌ 回测失败: {backtest_result.get('message', '未知错误')}")
    
    progress_info['当前阶段'] = '完成'
    progress_info['结束时间'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    print("\n" + "=" * 80)
    print("✅ 所有任务完成！")
    print("=" * 80)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n⚠️ 用户中断")
    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
        import traceback
        traceback.print_exc()
