#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
回溯测试：使用模型23，回溯一个月的每个交易日
从2025-12-12到2026-01-12，每天找市值<100亿、匹配度>0.93的最大匹配度股票
计算选中后两周的涨幅
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bull_stock_analyzer import BullStockAnalyzer
from data_fetcher import DataFetcher
import pandas as pd
from datetime import datetime, timedelta
import json

def get_trading_days(start_date, end_date):
    """
    获取指定日期范围内的所有交易日
    :param start_date: 开始日期 (datetime.date)
    :param end_date: 结束日期 (datetime.date)
    :return: 交易日列表 (datetime.date)
    """
    fetcher = DataFetcher()
    # 获取一只股票的日K线数据，通过日期列来获取交易日
    # 使用一只常见股票（如000001）来获取交易日历
    daily_df = fetcher.get_daily_kline('000001', period="1y")
    if daily_df is None or len(daily_df) == 0:
        print("⚠️ 无法获取交易日历，使用所有工作日")
        # 备用方案：生成所有工作日
        trading_days = []
        current = start_date
        while current <= end_date:
            # 排除周末
            if current.weekday() < 5:  # 0-4 是周一到周五
                trading_days.append(current)
            current += timedelta(days=1)
        return trading_days
    
    # 从日K线数据中提取日期
    if '日期' in daily_df.columns:
        daily_df['日期'] = pd.to_datetime(daily_df['日期'])
        daily_df['日期_date'] = daily_df['日期'].dt.date
        # 筛选日期范围
        trading_days = daily_df[
            (daily_df['日期_date'] >= start_date) & 
            (daily_df['日期_date'] <= end_date)
        ]['日期_date'].unique().tolist()
        trading_days.sort()
        return trading_days
    else:
        print("⚠️ 日K线数据中没有日期列")
        return []

def calculate_gain_after_days(stock_code, buy_date, days=14):
    """
    计算股票从买入日期到N天后的涨幅
    :param stock_code: 股票代码
    :param buy_date: 买入日期 (datetime.date)
    :param days: 天数（默认14天，约2周）
    :return: 涨幅百分比，如果无法计算返回None
    """
    fetcher = DataFetcher()
    
    # 获取日K线数据
    daily_df = fetcher.get_daily_kline(stock_code, period="1y")
    if daily_df is None or len(daily_df) == 0:
        return None
    
    # 确保日期列是datetime类型
    if '日期' in daily_df.columns:
        daily_df['日期'] = pd.to_datetime(daily_df['日期'])
        daily_df['日期_date'] = daily_df['日期'].dt.date
        daily_df = daily_df.sort_values('日期').reset_index(drop=True)
        
        # 找到买入日期当天的数据
        buy_data = daily_df[daily_df['日期_date'] == buy_date]
        if len(buy_data) == 0:
            # 如果买入日期没有数据，找最近的一个交易日
            buy_data = daily_df[daily_df['日期_date'] <= buy_date]
            if len(buy_data) == 0:
                return None
            buy_data = buy_data.iloc[-1:]
        
        buy_price = float(buy_data.iloc[0]['收盘'])
        buy_idx = buy_data.index[0]
        
        # 找到N天后的数据（或最后一个交易日）
        target_date = buy_date + timedelta(days=days)
        end_data = daily_df[
            (daily_df['日期_date'] > buy_date) & 
            (daily_df['日期_date'] <= target_date)
        ]
        
        if len(end_data) == 0:
            # 如果N天内没有数据，使用最后一个交易日
            end_data = daily_df[daily_df['日期_date'] > buy_date]
            if len(end_data) == 0:
                return None
        
        # 使用最后一个交易日的收盘价
        end_price = float(end_data.iloc[-1]['收盘'])
        end_date = end_data.iloc[-1]['日期_date']
        
        # 计算涨幅
        gain = (end_price - buy_price) / buy_price * 100
        
        return {
            'gain': gain,
            'buy_price': buy_price,
            'end_price': end_price,
            'buy_date': buy_date,
            'end_date': end_date,
            'actual_days': (end_date - buy_date).days
        }
    
    return None

def main():
    print("=" * 80)
    print("模型23回溯测试：一个月交易日回溯")
    print("=" * 80)
    print("时间范围: 2025-12-12 至 2026-01-12")
    print("条件: 市值 < 100亿, 匹配度 > 0.93, 选匹配度最大的股票")
    print("计算: 选中后两周的涨幅")
    print()
    
    # 初始化分析器
    analyzer = BullStockAnalyzer(
        auto_load_default_stocks=False,
        auto_analyze_and_train=False
    )
    
    # 加载模型23
    print("正在加载模型23...")
    try:
        analyzer.load_model('models/模型23.json', skip_network=True)
        print("✅ 模型23加载成功")
        
        if analyzer.trained_features:
            print(f"   特征数: {len(analyzer.trained_features.get('common_features', {}))}")
            print(f"   样本数: {analyzer.trained_features.get('sample_count', 0)}")
        print()
    except Exception as e:
        print(f"❌ 加载模型失败: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # 获取交易日列表
    start_date = datetime(2025, 12, 12).date()
    end_date = datetime(2026, 1, 12).date()
    
    print(f"正在获取交易日列表 ({start_date} 至 {end_date})...")
    trading_days = get_trading_days(start_date, end_date)
    print(f"✅ 找到 {len(trading_days)} 个交易日")
    print()
    
    # 存储结果
    results = []
    
    # 遍历每个交易日
    for idx, scan_date in enumerate(trading_days, 1):
        print(f"[{idx}/{len(trading_days)}] 扫描日期: {scan_date}")
        print("-" * 80)
        
        try:
            # 使用指定日期进行扫描
            scan_result = analyzer.scan_all_stocks(
                min_match_score=0.93,
                max_market_cap=100.0,
                limit=None,
                use_parallel=True,
                max_workers=10,
                scan_date=scan_date.strftime('%Y-%m-%d')
            )
            
            if not scan_result.get('success'):
                print(f"   ⚠️ 扫描失败: {scan_result.get('message', '未知错误')}")
                results.append({
                    'date': scan_date.strftime('%Y-%m-%d'),
                    'stock_code': None,
                    'stock_name': None,
                    'match_score': None,
                    'gain_2w': None,
                    'error': scan_result.get('message', '扫描失败')
                })
                continue
            
            candidates = scan_result.get('candidates', [])
            
            if len(candidates) == 0:
                print(f"   ⚠️ 未找到符合条件的股票")
                results.append({
                    'date': scan_date.strftime('%Y-%m-%d'),
                    'stock_code': None,
                    'stock_name': None,
                    'match_score': None,
                    'gain_2w': None,
                    'error': '未找到符合条件的股票'
                })
                continue
            
            # 找到匹配度最大的股票
            best_stock = max(candidates, key=lambda x: x.get('匹配度', 0))
            stock_code = best_stock.get('股票代码')
            stock_name = best_stock.get('股票名称')
            match_score = best_stock.get('匹配度', 0)
            
            print(f"   ✅ 找到最佳股票: {stock_code} {stock_name} (匹配度: {match_score:.3f})")
            
            # 计算两周涨幅
            print(f"   正在计算两周涨幅...")
            gain_info = calculate_gain_after_days(stock_code, scan_date, days=14)
            
            if gain_info:
                gain_2w = gain_info['gain']
                print(f"   📈 两周涨幅: {gain_2w:.2f}% (买入价: {gain_info['buy_price']:.2f}, 卖出价: {gain_info['end_price']:.2f})")
                print(f"      实际天数: {gain_info['actual_days']} 天 (买入: {gain_info['buy_date']}, 卖出: {gain_info['end_date']})")
                
                results.append({
                    'date': scan_date.strftime('%Y-%m-%d'),
                    'stock_code': stock_code,
                    'stock_name': stock_name,
                    'match_score': match_score,
                    'gain_2w': gain_2w,
                    'buy_price': gain_info['buy_price'],
                    'end_price': gain_info['end_price'],
                    'buy_date': gain_info['buy_date'].strftime('%Y-%m-%d'),
                    'end_date': gain_info['end_date'].strftime('%Y-%m-%d'),
                    'actual_days': gain_info['actual_days']
                })
            else:
                print(f"   ⚠️ 无法计算涨幅（可能数据不足）")
                results.append({
                    'date': scan_date.strftime('%Y-%m-%d'),
                    'stock_code': stock_code,
                    'stock_name': stock_name,
                    'match_score': match_score,
                    'gain_2w': None,
                    'error': '无法计算涨幅'
                })
            
        except Exception as e:
            print(f"   ❌ 处理失败: {e}")
            import traceback
            traceback.print_exc()
            results.append({
                'date': scan_date.strftime('%Y-%m-%d'),
                'stock_code': None,
                'stock_name': None,
                'match_score': None,
                'gain_2w': None,
                'error': str(e)
            })
        
        print()
    
    # 显示汇总结果
    print("=" * 80)
    print("回溯测试结果汇总")
    print("=" * 80)
    print(f"{'日期':<12} {'股票代码':<12} {'股票名称':<20} {'匹配度':<10} {'两周涨幅':<12} {'实际天数':<10}")
    print("-" * 80)
    
    valid_results = [r for r in results if r.get('gain_2w') is not None]
    invalid_results = [r for r in results if r.get('gain_2w') is None]
    
    for result in results:
        date = result.get('date', 'N/A')
        code = result.get('stock_code', 'N/A')
        name = result.get('stock_name', 'N/A')
        match = result.get('match_score', 0)
        gain = result.get('gain_2w')
        days = result.get('actual_days', 'N/A')
        
        if gain is not None:
            gain_str = f"{gain:.2f}%"
            days_str = f"{days}天"
        else:
            gain_str = result.get('error', 'N/A')
            days_str = 'N/A'
        
        match_str = f"{match:.3f}" if match else "N/A"
        
        print(f"{date:<12} {code:<12} {name:<20} {match_str:<10} {gain_str:<12} {days_str:<10}")
    
    print("=" * 80)
    
    # 统计信息
    if valid_results:
        gains = [r['gain_2w'] for r in valid_results]
        avg_gain = sum(gains) / len(gains)
        max_gain = max(gains)
        min_gain = min(gains)
        positive_count = sum(1 for g in gains if g > 0)
        positive_rate = positive_count / len(gains) * 100
        
        print(f"\n📊 统计信息:")
        print(f"   有效结果: {len(valid_results)}/{len(results)}")
        print(f"   平均涨幅: {avg_gain:.2f}%")
        print(f"   最大涨幅: {max_gain:.2f}%")
        print(f"   最小涨幅: {min_gain:.2f}%")
        print(f"   盈利次数: {positive_count}/{len(valid_results)} ({positive_rate:.1f}%)")
    
    # 保存结果到文件
    output_file = f"backtest_model23_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            'model_name': '模型23',
            'start_date': start_date.strftime('%Y-%m-%d'),
            'end_date': end_date.strftime('%Y-%m-%d'),
            'trading_days_count': len(trading_days),
            'results': results,
            'statistics': {
                'total_days': len(results),
                'valid_results': len(valid_results),
                'avg_gain': avg_gain if valid_results else None,
                'max_gain': max_gain if valid_results else None,
                'min_gain': min_gain if valid_results else None,
                'positive_rate': positive_rate if valid_results else None
            } if valid_results else {}
        }, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ 结果已保存到: {output_file}")

if __name__ == '__main__':
    main()
