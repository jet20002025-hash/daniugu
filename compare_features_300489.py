#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
对比300489在训练买点（2024-09-18）和今天（2026-01-14）的特征
"""
import sys
sys.path.insert(0, '.')
from bull_stock_analyzer import BullStockAnalyzer
from data_fetcher import DataFetcher
import pandas as pd
from datetime import datetime

print("=" * 80)
print("对比300489在训练买点和今天的特征")
print("=" * 80)

analyzer = BullStockAnalyzer(auto_load_default_stocks=False, auto_analyze_and_train=False)

# 加载模型
print("\n1. 加载模型...")
model_loaded = analyzer.load_model('models/用户指定20只股票模型.json', skip_network=True)
if not model_loaded:
    print("❌ 模型加载失败")
    sys.exit(1)

print("✅ 模型加载成功")
print(f"   训练股票数: {len(analyzer.trained_features.get('training_stocks', []))}")
print(f"   特征数量: {len(analyzer.trained_features.get('common_features', {}))}")

# 获取训练时的买点特征（2024-09-18）
print("\n2. 提取训练买点（2024-09-18）的特征...")
train_date = '2024-09-18'
train_date_obj = datetime.strptime(train_date, '%Y-%m-%d').date()

# 获取日线数据
daily_df = analyzer.fetcher.get_daily_kline('300489', period='3y')
if daily_df is None or len(daily_df) == 0:
    print("❌ 无法获取日线数据")
    sys.exit(1)

# 处理日期列
if '日期' in daily_df.columns:
    daily_df['日期'] = pd.to_datetime(daily_df['日期'])
    daily_df = daily_df.sort_values('日期').reset_index(drop=True)

# 找到训练买点日期对应的索引
train_buy_idx_daily = None
for i in range(len(daily_df)):
    row_date = daily_df.iloc[i]['日期'].date()
    if row_date == train_date_obj:
        train_buy_idx_daily = i
        break

if train_buy_idx_daily is None:
    print(f"❌ 找不到训练买点日期 {train_date}")
    sys.exit(1)

print(f"✅ 找到训练买点: 日期 {train_date}, 价格 {daily_df.iloc[train_buy_idx_daily]['收盘']:.2f} 元")

# 聚合为周线数据
daily_to_use_train = daily_df.iloc[:train_buy_idx_daily + 1].copy()
weekly_df_train = analyzer.fetcher._aggregate_daily_to_weekly(daily_to_use_train)

# 找到买点对应的周线索引
train_buy_idx_weekly = None
for i in range(len(weekly_df_train)):
    row_date = weekly_df_train.iloc[i]['日期'].date()
    if abs((row_date - train_date_obj).days) <= 7:
        train_buy_idx_weekly = i
        break

if train_buy_idx_weekly is None:
    print("❌ 找不到训练买点对应的周线索引")
    sys.exit(1)

# 选择特征起点
volume_surge_idx_train = analyzer.find_volume_surge_point(
    '300489', train_buy_idx_weekly, weekly_df=weekly_df_train,
    min_volume_ratio=2.0, lookback_weeks=min(40, train_buy_idx_weekly)
)

if volume_surge_idx_train is not None and volume_surge_idx_train >= 5:
    feature_start_idx_train = volume_surge_idx_train
else:
    if train_buy_idx_weekly >= 25:
        feature_start_idx_train = train_buy_idx_weekly - 20
    elif train_buy_idx_weekly >= 10:
        feature_start_idx_train = train_buy_idx_weekly - 5
    else:
        feature_start_idx_train = 0

available_weeks_train = train_buy_idx_weekly - feature_start_idx_train
lookback_weeks_train = min(40, available_weeks_train)

# 提取训练买点的特征
train_features = analyzer.extract_features_at_start_point(
    '300489', feature_start_idx_train, lookback_weeks=lookback_weeks_train, weekly_df=weekly_df_train
)

if train_features is None:
    print("❌ 无法提取训练买点的特征")
    sys.exit(1)

print(f"✅ 成功提取训练买点特征，共 {len(train_features)} 个特征")

# 获取今天的特征（2026-01-14）
print("\n3. 提取今天（2026-01-14）的特征...")
today_date = '2026-01-14'
today_date_obj = datetime.strptime(today_date, '%Y-%m-%d').date()

# 找到今天对应的索引
today_buy_idx_daily = None
for i in range(len(daily_df)):
    row_date = daily_df.iloc[i]['日期'].date()
    if row_date == today_date_obj:
        today_buy_idx_daily = i
        break

if today_buy_idx_daily is None:
    print(f"❌ 找不到今天日期 {today_date}")
    sys.exit(1)

print(f"✅ 找到今天: 日期 {today_date}, 价格 {daily_df.iloc[today_buy_idx_daily]['收盘']:.2f} 元")

# 聚合为周线数据
daily_to_use_today = daily_df.iloc[:today_buy_idx_daily + 1].copy()
weekly_df_today = analyzer.fetcher._aggregate_daily_to_weekly(daily_to_use_today)

# 找到今天对应的周线索引
today_buy_idx_weekly = None
for i in range(len(weekly_df_today)):
    row_date = weekly_df_today.iloc[i]['日期'].date()
    if abs((row_date - today_date_obj).days) <= 7:
        today_buy_idx_weekly = i
        break

if today_buy_idx_weekly is None:
    print("❌ 找不到今天对应的周线索引")
    sys.exit(1)

# 选择特征起点
volume_surge_idx_today = analyzer.find_volume_surge_point(
    '300489', today_buy_idx_weekly, weekly_df=weekly_df_today,
    min_volume_ratio=2.0, lookback_weeks=min(40, today_buy_idx_weekly)
)

if volume_surge_idx_today is not None and volume_surge_idx_today >= 5:
    feature_start_idx_today = volume_surge_idx_today
else:
    if today_buy_idx_weekly >= 25:
        feature_start_idx_today = today_buy_idx_weekly - 20
    elif today_buy_idx_weekly >= 10:
        feature_start_idx_today = today_buy_idx_weekly - 5
    else:
        feature_start_idx_today = 0

available_weeks_today = today_buy_idx_weekly - feature_start_idx_today
lookback_weeks_today = min(40, available_weeks_today)

# 提取今天的特征
today_features = analyzer.extract_features_at_start_point(
    '300489', feature_start_idx_today, lookback_weeks=lookback_weeks_today, weekly_df=weekly_df_today
)

if today_features is None:
    print("❌ 无法提取今天的特征")
    sys.exit(1)

print(f"✅ 成功提取今天特征，共 {len(today_features)} 个特征")

# 计算匹配度
print("\n4. 计算匹配度...")
common_features = analyzer.trained_features.get('common_features', {})
match_result_train = analyzer._calculate_match_score(train_features, common_features, tolerance=0.3, stock_code='300489')
match_result_today = analyzer._calculate_match_score(today_features, common_features, tolerance=0.3, stock_code='300489')

print(f"训练买点匹配度: {match_result_train['总匹配度']:.3f}")
print(f"今天匹配度: {match_result_today['总匹配度']:.3f}")

# 对比特征值
print("\n5. 对比关键特征值...")
print(f"{'特征名称':<30} {'训练买点值':<20} {'今天值':<20} {'差异':<20}")
print("-" * 90)

key_features = [
    '价格相对位置', '盈利筹码比例', '90%成本集中度', '起点当日量比', 
    '成交量萎缩程度', '价格相对MA20', '起点前20天波动率', '相对高点跌幅'
]

for feature_name in key_features:
    if feature_name in train_features and feature_name in today_features:
        train_val = train_features[feature_name]
        today_val = today_features[feature_name]
        diff = abs(train_val - today_val) if isinstance(train_val, (int, float)) and isinstance(today_val, (int, float)) else 'N/A'
        print(f"{feature_name:<30} {str(train_val):<20} {str(today_val):<20} {str(diff):<20}")

# 对比所有特征
print("\n6. 特征相似度分析...")
all_features = set(train_features.keys()) | set(today_features.keys())
numeric_features = []
for f in all_features:
    if f in ['股票代码', '股票名称', '起点日期']:
        continue
    if f in train_features and f in today_features:
        train_val = train_features[f]
        today_val = today_features[f]
        if isinstance(train_val, (int, float)) and isinstance(today_val, (int, float)):
            numeric_features.append((f, train_val, today_val))

similar_count = 0
total_count = 0
for f, train_val, today_val in numeric_features:
    total_count += 1
    diff_pct = abs(train_val - today_val) / (abs(train_val) + 1e-10) * 100
    if diff_pct < 10:  # 差异小于10%认为相似
        similar_count += 1

print(f"总特征数: {total_count}")
print(f"相似特征数（差异<10%）: {similar_count}")
print(f"相似度: {similar_count / total_count * 100:.1f}%")

print("\n" + "=" * 80)
print("结论:")
if match_result_today['总匹配度'] > 0.9:
    print("⚠️ 今天匹配度很高，但需要检查特征是否真的相似")
    if similar_count / total_count > 0.5:
        print("   特征相似度较高，可能模型过于宽泛")
    else:
        print("   特征相似度较低，但匹配度却很高，可能匹配度计算有问题")
else:
    print("✅ 今天匹配度较低，符合预期")
