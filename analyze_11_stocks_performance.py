#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
分析2025-11-21扫描出的11只股票在接下来8周的表现
找出大涨个股和表现差个股的核心差异
"""
import sys
sys.path.insert(0, '.')
from bull_stock_analyzer import BullStockAnalyzer
from data_fetcher import DataFetcher
import pandas as pd
from datetime import datetime, timedelta
import json

# 11只股票代码和名称
stocks = [
    ('001331', '胜通能源'),
    ('603038', '华立股份'),
    ('002969', '嘉美包装'),
    ('002094', '青岛金王'),
    ('603955', '大千生态'),
    ('000759', '中百集团'),
    ('300489', '光智科技'),
    ('002628', '成都路桥'),
    ('603122', '合富中国'),
    ('688108', '赛诺医疗'),
    ('600421', '*ST华嵘'),
]

# 买入日期
buy_date = '2025-11-21'
buy_date_obj = datetime.strptime(buy_date, '%Y-%m-%d').date()

# 8周后的日期（约56天）
end_date_obj = buy_date_obj + timedelta(days=56)
end_date = end_date_obj.strftime('%Y-%m-%d')

print("=" * 100)
print(f"分析11只股票从 {buy_date} 到 {end_date} (8周) 的表现")
print("=" * 100)

analyzer = BullStockAnalyzer(auto_load_default_stocks=False, auto_analyze_and_train=False)
fetcher = DataFetcher()

results = []

for stock_code, stock_name in stocks:
    print(f"\n{'='*100}")
    print(f"分析 {stock_code} {stock_name}")
    print(f"{'='*100}")
    
    try:
        # 获取周K线数据
        weekly_df = fetcher.get_weekly_kline(stock_code, period="1y")
        if weekly_df is None or len(weekly_df) == 0:
            print(f"  ❌ 无法获取 {stock_code} 的周K线数据")
            continue
        
        # 找到买入日期对应的周K线
        if '日期' in weekly_df.columns:
            weekly_df['日期_date'] = pd.to_datetime(weekly_df['日期']).dt.date
            buy_week_idx = None
            
            for i in range(len(weekly_df)):
                week_date = weekly_df.iloc[i]['日期_date']
                week_start = week_date - timedelta(days=6)
                if week_start <= buy_date_obj <= week_date:
                    buy_week_idx = i
                    break
            
            if buy_week_idx is None:
                print(f"  ❌ 无法找到 {buy_date} 对应的周K线")
                continue
            
            buy_price = float(weekly_df.iloc[buy_week_idx]['收盘'])
            buy_week_date = weekly_df.iloc[buy_week_idx]['日期_date']
            
            # 找到8周后的价格（买入周之后的第8周）
            target_week_idx = buy_week_idx + 8
            if target_week_idx >= len(weekly_df):
                # 如果数据不足8周，使用最新数据
                target_week_idx = len(weekly_df) - 1
                actual_weeks = target_week_idx - buy_week_idx
                print(f"  ⚠️ 数据不足8周，只有 {actual_weeks} 周数据")
            else:
                actual_weeks = 8
            
            sell_price = float(weekly_df.iloc[target_week_idx]['收盘'])
            sell_week_date = weekly_df.iloc[target_week_idx]['日期_date']
            
            # 计算涨幅
            gain = (sell_price - buy_price) / buy_price * 100
            
            # 计算8周内的最高价和最大涨幅
            period_df = weekly_df.iloc[buy_week_idx:target_week_idx+1]
            max_price = float(period_df['最高'].max())
            max_gain = (max_price - buy_price) / buy_price * 100
            
            # 计算8周内的最低价和最大回撤
            min_price = float(period_df['最低'].min())
            max_drawdown = (min_price - buy_price) / buy_price * 100
            
            # 提取买入时的特征
            print(f"  买入日期: {buy_week_date}, 买入价格: {buy_price:.2f}")
            print(f"  卖出日期: {sell_week_date}, 卖出价格: {sell_price:.2f}")
            print(f"  8周涨幅: {gain:.2f}%")
            print(f"  最大涨幅: {max_gain:.2f}%")
            print(f"  最大回撤: {max_drawdown:.2f}%")
            
            # 提取买入时的特征
            try:
                features = analyzer.extract_features_at_start_point(
                    stock_code, buy_week_idx, lookback_weeks=40, weekly_df=weekly_df
                )
                
                if features:
                    print(f"  特征提取成功")
                    # 打印关键特征
                    key_features = [
                        'MA5值', 'MA10值', 'MA20值', 'MA40值',
                        '价格相对MA5', '价格相对MA10', '价格相对MA20', '价格相对MA40',
                        '起点前20周均量', '起点前10周均量', '起点前40周最大量',
                        '成交量萎缩程度', '起点前20周波动率',
                        '筹码集中度', '盈利筹码比例', '90%成本集中度',
                        '起点当周价涨量增', '是否跌破最大量最低价'
                    ]
                    for key in key_features:
                        if key in features:
                            print(f"    {key}: {features[key]}")
                else:
                    print(f"  ⚠️ 特征提取失败")
                    features = {}
            except Exception as e:
                print(f"  ⚠️ 特征提取异常: {e}")
                features = {}
            
            results.append({
                '股票代码': stock_code,
                '股票名称': stock_name,
                '买入日期': str(buy_week_date),
                '买入价格': round(buy_price, 2),
                '卖出日期': str(sell_week_date),
                '卖出价格': round(sell_price, 2),
                '8周涨幅': round(gain, 2),
                '最大涨幅': round(max_gain, 2),
                '最大回撤': round(max_drawdown, 2),
                '实际周数': actual_weeks,
                '特征': features
            })
            
        else:
            print(f"  ❌ 周K线数据格式错误")
            
    except Exception as e:
        print(f"  ❌ 分析 {stock_code} 时出错: {e}")
        import traceback
        traceback.print_exc()

# 按涨幅排序
results.sort(key=lambda x: x['8周涨幅'], reverse=True)

print("\n" + "=" * 100)
print("11只股票8周表现汇总（按涨幅排序）")
print("=" * 100)
print(f"{'排名':<6} {'股票代码':<10} {'股票名称':<15} {'买入价格':<10} {'卖出价格':<10} {'8周涨幅':<10} {'最大涨幅':<10} {'最大回撤':<10}")
print("-" * 100)

for idx, r in enumerate(results, 1):
    print(f"{idx:<6} {r['股票代码']:<10} {r['股票名称']:<15} {r['买入价格']:<10.2f} {r['卖出价格']:<10.2f} {r['8周涨幅']:<10.2f}% {r['最大涨幅']:<10.2f}% {r['最大回撤']:<10.2f}%")

# 分类：大涨（涨幅>50%）和表现差（涨幅<20%）
big_gainers = [r for r in results if r['8周涨幅'] > 50]
poor_performers = [r for r in results if r['8周涨幅'] < 20]

print("\n" + "=" * 100)
print("大涨个股（8周涨幅>50%）")
print("=" * 100)
for r in big_gainers:
    print(f"{r['股票代码']} {r['股票名称']}: {r['8周涨幅']:.2f}%")

print("\n" + "=" * 100)
print("表现差个股（8周涨幅<20%）")
print("=" * 100)
for r in poor_performers:
    print(f"{r['股票代码']} {r['股票名称']}: {r['8周涨幅']:.2f}%")

# 分析特征差异
if big_gainers and poor_performers:
    print("\n" + "=" * 100)
    print("特征差异分析")
    print("=" * 100)
    
    # 提取所有特征名称
    all_features = set()
    for r in results:
        if r['特征']:
            all_features.update(r['特征'].keys())
    
    # 计算平均特征值
    big_gainer_features = {}
    poor_performer_features = {}
    
    for feature in all_features:
        big_values = []
        poor_values = []
        
        for r in big_gainers:
            if r['特征'] and feature in r['特征']:
                val = r['特征'][feature]
                if isinstance(val, (int, float)) and pd.notna(val):
                    big_values.append(float(val))
        
        for r in poor_performers:
            if r['特征'] and feature in r['特征']:
                val = r['特征'][feature]
                if isinstance(val, (int, float)) and pd.notna(val):
                    poor_values.append(float(val))
        
        if big_values:
            big_gainer_features[feature] = {
                '均值': sum(big_values) / len(big_values),
                '数量': len(big_values)
            }
        
        if poor_values:
            poor_performer_features[feature] = {
                '均值': sum(poor_values) / len(poor_values),
                '数量': len(poor_values)
            }
    
    # 找出差异最大的特征
    print("\n关键特征对比（大涨 vs 表现差）:")
    print(f"{'特征名称':<25} {'大涨均值':<15} {'表现差均值':<15} {'差异':<15}")
    print("-" * 70)
    
    feature_diffs = []
    for feature in all_features:
        if feature in big_gainer_features and feature in poor_performer_features:
            big_mean = big_gainer_features[feature]['均值']
            poor_mean = poor_performer_features[feature]['均值']
            diff = big_mean - poor_mean
            feature_diffs.append((feature, big_mean, poor_mean, diff))
    
    # 按差异绝对值排序
    feature_diffs.sort(key=lambda x: abs(x[3]), reverse=True)
    
    for feature, big_mean, poor_mean, diff in feature_diffs[:20]:  # 显示前20个差异最大的特征
        print(f"{feature:<25} {big_mean:<15.2f} {poor_mean:<15.2f} {diff:<15.2f}")

# 特别分析华立股份
print("\n" + "=" * 100)
print("特别分析：华立股份（603038）")
print("=" * 100)
huali = [r for r in results if r['股票代码'] == '603038']
if huali:
    huali = huali[0]
    print(f"8周涨幅: {huali['8周涨幅']:.2f}%")
    print(f"最大涨幅: {huali['最大涨幅']:.2f}%")
    print(f"最大回撤: {huali['最大回撤']:.2f}%")
    print("\n特征值:")
    if huali['特征']:
        for key, value in sorted(huali['特征'].items()):
            if isinstance(value, (int, float)) and pd.notna(value):
                print(f"  {key}: {value}")

# 保存结果到JSON文件
output_file = f'11_stocks_performance_analysis_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
with open(output_file, 'w', encoding='utf-8') as f:
    json.dump({
        '买入日期': buy_date,
        '分析日期': end_date,
        '分析周期': '8周',
        '结果': results,
        '大涨个股': big_gainers,
        '表现差个股': poor_performers,
        '特征差异': {
            '大涨个股特征均值': big_gainer_features,
            '表现差个股特征均值': poor_performer_features
        }
    }, f, ensure_ascii=False, indent=2)

print(f"\n结果已保存到: {output_file}")
