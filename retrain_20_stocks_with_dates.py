#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
使用用户指定的20只股票及其最佳买点日期重新训练模型
"""

import sys
import json
from datetime import datetime
from bull_stock_analyzer import BullStockAnalyzer

def main():
    print("=" * 80)
    print("使用用户指定的20只股票及其最佳买点日期重新训练模型")
    print("=" * 80)
    
    # 用户指定的股票代码和最佳买点日期
    training_stocks = [
        {'code': '300489', 'buy_date': '2024-09-18'},
        {'code': '300377', 'buy_date': '2024-09-19'},
        {'code': '000062', 'buy_date': '2024-08-14'},
        {'code': '688656', 'buy_date': '2024-10-23'},
        {'code': '688585', 'buy_date': '2025-06-30'},
        {'code': '300436', 'buy_date': '2025-07-03'},
        {'code': '001331', 'buy_date': '2025-12-04'},
        {'code': '002094', 'buy_date': '2024-09-24'},
        {'code': '300251', 'buy_date': '2025-02-05'},
        {'code': '688165', 'buy_date': '2024-11-04'},
        {'code': '301292', 'buy_date': '2025-09-29'},
        {'code': '605225', 'buy_date': '2025-08-14'},
        {'code': '300077', 'buy_date': '2024-09-27'},
        {'code': '688108', 'buy_date': '2025-08-06'},
        {'code': '603268', 'buy_date': '2024-09-25'},
        {'code': '300204', 'buy_date': '2025-05-20'},
        {'code': '002969', 'buy_date': '2025-12-08'},
        {'code': '603122', 'buy_date': '2025-10-27'},
        {'code': '000759', 'buy_date': '2025-12-02'},
        {'code': '002628', 'buy_date': '2024-09-24'},
    ]
    
    # 初始化分析器
    analyzer = BullStockAnalyzer(auto_load_default_stocks=False, auto_analyze_and_train=False)
    
    # 提取所有股票的特征
    all_features_list = []
    stock_codes = []
    
    print(f"\n📊 开始提取 {len(training_stocks)} 只股票的最佳买点特征...")
    
    for idx, stock_info in enumerate(training_stocks, 1):
        stock_code = stock_info['code']
        buy_date = stock_info['buy_date']
        stock_codes.append(stock_code)
        
        print(f"\n[{idx}/{len(training_stocks)}] 处理 {stock_code} (最佳买点: {buy_date})")
        
        try:
            # 使用日线数据，聚合为周线数据，然后提取特征（提供更多历史数据）
            print(f"  📊 获取日K线数据...")
            daily_df = analyzer.fetcher.get_daily_kline(stock_code, period="3y")
            if daily_df is None or len(daily_df) == 0:
                print(f"  ⚠️ 无法获取 {stock_code} 的日K线数据，跳过")
                continue
            
            # 处理日期列
            if '日期' in daily_df.columns:
                daily_df['日期'] = pd.to_datetime(daily_df['日期'])
                daily_df = daily_df.sort_values('日期').reset_index(drop=True)
            
            # 找到最佳买点日期对应的索引（日线数据，精确匹配）
            from datetime import datetime as dt
            buy_date_obj = dt.strptime(buy_date, '%Y-%m-%d').date()
            buy_idx_daily = None
            
            for i in range(len(daily_df)):
                row_date = daily_df.iloc[i]['日期']
                if isinstance(row_date, pd.Timestamp):
                    row_date = row_date.date()
                elif isinstance(row_date, str):
                    row_date = dt.strptime(row_date, '%Y-%m-%d').date()
                else:
                    continue
                
                # 精确匹配日期（日线数据可以精确匹配）
                if row_date == buy_date_obj:
                    buy_idx_daily = i
                    break
            
            if buy_idx_daily is None:
                print(f"  ⚠️ 在日K线数据中找不到 {buy_date} 对应的日期，跳过")
                continue
            
            # 获取该日期的收盘价作为最佳买点价格
            buy_price = float(daily_df.iloc[buy_idx_daily]['收盘'])
            actual_date = daily_df.iloc[buy_idx_daily]['日期']
            if isinstance(actual_date, pd.Timestamp):
                actual_date_str = actual_date.strftime('%Y-%m-%d')
            else:
                actual_date_str = str(actual_date)
            
            print(f"  ✅ 找到买点: 日期 {actual_date_str}, 价格 {buy_price:.2f} 元")
            print(f"  📊 买点前可用数据: {buy_idx_daily} 个交易日（约 {buy_idx_daily // 5} 周）")
            
            # 将日线数据聚合为周线数据（从最早数据到买点日期）
            print(f"  📊 将日线数据聚合为周线数据...")
            daily_to_use = daily_df.iloc[:buy_idx_daily + 1].copy()  # 包含买点当日
            
            # 聚合为周线数据
            weekly_df = analyzer.fetcher._aggregate_daily_to_weekly(daily_to_use)
            
            if weekly_df is None or len(weekly_df) == 0:
                print(f"  ⚠️ 聚合周线数据失败，跳过")
                continue
            
            # 找到买点日期对应的周线索引
            buy_idx_weekly = None
            for i in range(len(weekly_df)):
                row_date = weekly_df.iloc[i]['日期']
                if isinstance(row_date, pd.Timestamp):
                    row_date = row_date.date()
                elif isinstance(row_date, str):
                    row_date = dt.strptime(row_date, '%Y-%m-%d').date()
                else:
                    continue
                
                # 允许日期匹配有一定的容差（±7天），因为周K线的日期可能是周内任意一天
                if abs((row_date - buy_date_obj).days) <= 7:
                    buy_idx_weekly = i
                    break
            
            if buy_idx_weekly is None:
                print(f"  ⚠️ 在聚合的周K线数据中找不到 {buy_date} 对应的日期，跳过")
                continue
            
            print(f"  ✅ 周线数据: 共 {len(weekly_df)} 周，买点索引: {buy_idx_weekly}")
            print(f"  📊 买点前可用周数: {buy_idx_weekly} 周")
            
            # 优化特征起点选择逻辑：优先保证有足够的历史数据
            # 策略1：尝试查找成交量突增点（但要求至少有5周历史数据）
            volume_surge_idx = analyzer.find_volume_surge_point(
                stock_code, buy_idx_weekly, weekly_df=weekly_df,
                min_volume_ratio=2.0, lookback_weeks=min(40, buy_idx_weekly)
            )
            
            # 策略2：如果找到成交量突增点，检查是否有足够历史数据
            if volume_surge_idx is not None and volume_surge_idx >= 5:
                # 成交量突增点有至少5周历史数据，可以使用
                feature_start_idx = volume_surge_idx
            else:
                # 策略3：使用买点前尽可能多的周数，但至少保留5周历史数据
                # 优先使用20周，如果不够则使用所有可用数据（至少5周）
                preferred_weeks = min(20, buy_idx_weekly - 5)  # 保留至少5周历史数据
                if preferred_weeks >= 5:
                    feature_start_idx = max(0, buy_idx_weekly - preferred_weeks)
                else:
                    # 如果买点前数据不足20周，使用所有可用数据（至少5周）
                    feature_start_idx = max(0, buy_idx_weekly - max(5, buy_idx_weekly - 5))
            
            # 计算实际可用的历史周数
            available_weeks = buy_idx_weekly - feature_start_idx
            
            # 确保至少有5周历史数据（如果数据不足，使用所有可用数据）
            if available_weeks < 5:
                feature_start_idx = max(0, buy_idx_weekly - max(5, buy_idx_weekly))
                available_weeks = buy_idx_weekly - feature_start_idx
            
            # 如果仍然不足5周，至少使用1周（允许提取部分特征）
            if available_weeks < 1:
                feature_start_idx = max(0, buy_idx_weekly - 1)
                available_weeks = buy_idx_weekly - feature_start_idx
            
            lookback_weeks = min(40, available_weeks)  # 使用实际可用的周数，最多40周
            
            print(f"  📍 特征提取起点: 索引 {feature_start_idx} (买点前 {available_weeks} 周，回看 {lookback_weeks} 周)")
            
            # 如果历史数据不足，先尝试提前买点日期
            if available_weeks < 5:
                print(f"  ⚠️ {stock_code} 历史数据不足（只有{available_weeks}周），尝试提前买点日期...")
                should_retry = True
            else:
                should_retry = False
                # 提取特征（使用周线数据，与训练时一致）
                try:
                    features = analyzer.extract_features_at_start_point(
                        stock_code, feature_start_idx, lookback_weeks=lookback_weeks, weekly_df=weekly_df
                    )
                except Exception as e:
                    print(f"  ⚠️ 提取特征时出错: {e}")
                    import traceback
                    traceback.print_exc()
                    features = None
                    should_retry = True
            
            # 如果特征提取失败或数据不足，尝试提前买点日期
            if should_retry or (features is None or len(features) == 0):
                if features is None or len(features) == 0:
                    print(f"  ⚠️ 无法提取 {stock_code} 的特征，尝试提前买点日期...")
                else:
                    print(f"  ⚠️ {stock_code} 历史数据不足（只有{available_weeks}周），尝试提前买点日期...")
                
                # 尝试提前买点日期（最多提前7天，但在一周内）
                from datetime import timedelta
                retry_success = False
                
                for days_back in range(1, 8):  # 提前1-7天
                    try_buy_date_obj = buy_date_obj - timedelta(days=days_back)
                    try_buy_date_str = try_buy_date_obj.strftime('%Y-%m-%d')
                    
                    # 重新查找买点日期对应的索引（日线数据）
                    try_buy_idx_daily = None
                    for i in range(len(daily_df)):
                        row_date = daily_df.iloc[i]['日期']
                        if isinstance(row_date, pd.Timestamp):
                            row_date = row_date.date()
                        elif isinstance(row_date, str):
                            row_date = dt.strptime(row_date, '%Y-%m-%d').date()
                        else:
                            continue
                        
                        if row_date == try_buy_date_obj:
                            try_buy_idx_daily = i
                            break
                    
                    if try_buy_idx_daily is None:
                        continue
                    
                    # 重新聚合周线数据
                    daily_to_use_retry = daily_df.iloc[:try_buy_idx_daily + 1].copy()
                    weekly_df_retry = analyzer.fetcher._aggregate_daily_to_weekly(daily_to_use_retry)
                    
                    if weekly_df_retry is None or len(weekly_df_retry) == 0:
                        continue
                    
                    # 找到买点日期对应的周线索引
                    try_buy_idx_weekly = None
                    for i in range(len(weekly_df_retry)):
                        row_date = weekly_df_retry.iloc[i]['日期']
                        if isinstance(row_date, pd.Timestamp):
                            row_date = row_date.date()
                        elif isinstance(row_date, str):
                            row_date = dt.strptime(row_date, '%Y-%m-%d').date()
                        else:
                            continue
                        
                        if abs((row_date - try_buy_date_obj).days) <= 7:
                            try_buy_idx_weekly = i
                            break
                    
                    if try_buy_idx_weekly is None:
                        continue
                    
                    # 重新选择特征起点
                    volume_surge_idx_retry = analyzer.find_volume_surge_point(
                        stock_code, try_buy_idx_weekly, weekly_df=weekly_df_retry,
                        min_volume_ratio=2.0, lookback_weeks=min(40, try_buy_idx_weekly)
                    )
                    
                    if volume_surge_idx_retry is not None and volume_surge_idx_retry >= 5:
                        feature_start_idx_retry = volume_surge_idx_retry
                    else:
                        if try_buy_idx_weekly >= 25:
                            feature_start_idx_retry = try_buy_idx_weekly - 20
                        elif try_buy_idx_weekly >= 10:
                            feature_start_idx_retry = try_buy_idx_weekly - 5
                        else:
                            feature_start_idx_retry = 0
                    
                    available_weeks_retry = try_buy_idx_weekly - feature_start_idx_retry
                    if available_weeks_retry < 1:
                        feature_start_idx_retry = max(0, try_buy_idx_weekly - 1)
                        available_weeks_retry = try_buy_idx_weekly - feature_start_idx_retry
                    
                    lookback_weeks_retry = min(40, available_weeks_retry)
                    
                    # 尝试提取特征
                    try:
                        features_retry = analyzer.extract_features_at_start_point(
                            stock_code, feature_start_idx_retry, lookback_weeks=lookback_weeks_retry, weekly_df=weekly_df_retry
                        )
                        
                        if features_retry is not None and len(features_retry) > 0:
                            print(f"  ✅ 提前 {days_back} 天后成功提取特征（新买点日期: {try_buy_date_str}）")
                            features = features_retry
                            buy_idx_weekly = try_buy_idx_weekly
                            feature_start_idx = feature_start_idx_retry
                            actual_date_str = try_buy_date_str
                            buy_price = float(daily_df.iloc[try_buy_idx_daily]['收盘'])
                            retry_success = True
                            break
                    except Exception:
                        continue
                
                if not retry_success:
                    print(f"  ⚠️ 即使提前买点日期也无法提取 {stock_code} 的特征，跳过")
                    continue
            
            # 添加股票代码和买点信息
            features['_stock_code'] = stock_code
            features['_buy_date'] = actual_date_str
            features['_buy_price'] = buy_price
            features['_buy_idx'] = buy_idx_weekly  # 使用周线索引
            features['股票代码'] = stock_code
            features['股票名称'] = analyzer._get_stock_name(stock_code) or stock_code
            
            all_features_list.append(features)
            print(f"  ✅ 成功提取特征，共 {len(features)} 个特征")
            
            # 将特征数据放入analysis_results中，供train_features使用
            # 使用周线索引（feature_start_idx和buy_idx_weekly都是周线索引）
            # 同时保存聚合的周线数据，供train_features阶段使用
            analyzer.analysis_results[stock_code] = {
                'interval': {
                    '起点索引': feature_start_idx,  # 周线索引
                    '终点索引': buy_idx_weekly,  # 周线索引
                    '涨幅': 0,  # 这里不需要实际涨幅，只是占位
                    '周数': buy_idx_weekly - feature_start_idx
                },
                'features': features,
                '_weekly_df': weekly_df  # 保存聚合的周线数据，供train_features阶段使用
            }
            
        except Exception as e:
            print(f"  ❌ 处理 {stock_code} 时出错: {e}")
            import traceback
            traceback.print_exc()
            continue
    
    if len(all_features_list) == 0:
        print("\n❌ 没有成功提取任何股票的特征，无法训练模型")
        return
    
    print(f"\n✅ 成功提取 {len(all_features_list)} 只股票的特征")
    print(f"📊 开始训练模型，目标匹配度: 0.95...")
    
    # 训练模型（train_features会从analysis_results中读取数据）
    train_result = analyzer.train_features()
    
    if not train_result.get('success'):
        print(f"\n❌ 训练失败: {train_result.get('message', '未知错误')}")
        return
    
    # train_features已经自动迭代训练，确保所有训练样本匹配度>=0.95
    # 这里只需要验证最终结果
    print(f"\n📊 验证最终训练结果...")
    common_features = analyzer.trained_features.get('common_features')
    match_scores = {}
    
    # 从train_result中获取匹配度（如果可用）
    if train_result.get('match_scores'):
        match_scores = {code: info.get('匹配度', 0.0) for code, info in train_result.get('match_scores', {}).items()}
    else:
        # 如果没有，重新计算
        for features in all_features_list:
            stock_code = features.get('_stock_code')
            match_result = analyzer._calculate_match_score(
                features, common_features, tolerance=0.3, stock_code=stock_code
            )
            match_score = round(float(match_result.get('总匹配度', 0.0)), 3)
            match_scores[stock_code] = match_score
    
    # 显示匹配度（按匹配度排序）
    print(f"\n匹配度列表（按匹配度从高到低）:")
    for code, score in sorted(match_scores.items(), key=lambda x: x[1], reverse=True):
        status = "✅" if score >= 0.95 else "⚠️"
        print(f"  {status} {code}: {score:.3f}")
    
    # 检查是否所有股票都达到0.95
    target_score = 0.95
    all_above_095 = train_result.get('all_pass', False) or all(score >= target_score for score in match_scores.values())
    
    if all_above_095:
        print(f"\n✅ 所有 {len(match_scores)} 只股票的匹配度都达到 {target_score} 以上！")
    else:
        below_095 = [code for code, score in match_scores.items() if score < target_score]
        print(f"\n⚠️ 以下 {len(below_095)} 只股票的匹配度未达到 {target_score}:")
        for code in sorted(below_095, key=lambda x: match_scores[x]):
            print(f"  {code}: {match_scores[code]:.3f}")
        
        print(f"\n💡 提示：经过 {train_result.get('iterations', 1)} 次迭代训练，仍有部分股票的匹配度未达到目标。")
        print(f"   这可能是由于这些股票的特征与训练样本差异较大。")
        print(f"   可以考虑：")
        print(f"   1. 增加更多类似的训练样本")
        print(f"   2. 调整特征权重")
        print(f"   3. 检查特征提取逻辑")
    
    # 注意：train_features已经自动迭代训练，确保所有训练样本匹配度>=0.95
    # 上面的验证已经显示了最终结果，这里不需要重复验证
    
    # 保存模型
    model_name = "用户指定20只股票模型"
    model_path = f"models/{model_name}.json"
    
    # 准备保存的数据
    save_data = {
        'model_name': model_name,
        'training_time': datetime.now().isoformat(),
        'training_stocks': stock_codes,
        'stock_buy_points': [
            {
                'stock_code': features.get('_stock_code'),
                'buy_date': features.get('_buy_date'),
                'buy_price': features.get('_buy_price')
            }
            for features in all_features_list
        ],
        'common_features': common_features,
        'match_scores': match_scores,
        'sample_count': len(all_features_list),
        'min_match_score': min(match_scores.values()) if match_scores else 0,
        'max_match_score': max(match_scores.values()) if match_scores else 0,
        'avg_match_score': sum(match_scores.values()) / len(match_scores) if match_scores else 0
    }
    
    # 保存到文件
    import os
    os.makedirs('models', exist_ok=True)
    
    with open(model_path, 'w', encoding='utf-8') as f:
        json.dump(save_data, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ 模型已保存到: {model_path}")
    print(f"\n📊 训练摘要:")
    print(f"  训练股票数: {len(stock_codes)}")
    print(f"  成功提取特征: {len(all_features_list)}")
    print(f"  最低匹配度: {min(match_scores.values()):.3f}" if match_scores else "  N/A")
    print(f"  最高匹配度: {max(match_scores.values()):.3f}" if match_scores else "  N/A")
    print(f"  平均匹配度: {sum(match_scores.values()) / len(match_scores):.3f}" if match_scores else "  N/A")
    
    # 保存训练摘要
    summary_path = f"retrain_20_stocks_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(summary_path, 'w', encoding='utf-8') as f:
        json.dump(save_data, f, ensure_ascii=False, indent=2)
    print(f"  训练摘要已保存到: {summary_path}")

if __name__ == '__main__':
    import pandas as pd
    main()
