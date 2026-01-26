#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
2025年12月回测：每周选出匹配度前5的个股
基于本地缓存数据，使用最新模型 trained_model.json
"""
import sys
import os
import json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bull_stock_analyzer import BullStockAnalyzer


def get_dec_2025_weeks():
    """
    获取2025年12月的每周日期
    返回每周五的日期（作为该周的扫描截止日期）
    """
    weeks = [
        '2025-12-05',  # 第1周（12月第一个完整交易周）
        '2025-12-12',  # 第2周
        '2025-12-19',  # 第3周
        '2025-12-26',  # 第4周
        '2025-12-31',  # 第5周（月末）
    ]
    return weeks


def backtest_single_week(analyzer, scan_date, common_features, top_n=5, min_match_score=0.95, max_market_cap=100.0):
    """
    对单周进行回测，找出匹配度最高的N只股票
    
    :param analyzer: BullStockAnalyzer实例
    :param scan_date: 扫描日期（该周末的日期）
    :param common_features: 训练好的特征模板
    :param top_n: 返回前N只匹配度最高的股票
    :param min_match_score: 最低匹配度阈值（用于初步筛选）
    :param max_market_cap: 最大流通市值（亿元）
    :return: 匹配度前N的股票列表
    """
    print(f"\n{'='*60}")
    print(f"📅 扫描日期: {scan_date}")
    print(f"   匹配度阈值: {min_match_score} | 流通市值上限: {max_market_cap}亿")
    print(f"{'='*60}")
    
    # 获取股票列表（从本地缓存）
    cache_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cache')
    stock_list_path = os.path.join(cache_dir, 'stock_list_all.json')
    
    if not os.path.exists(stock_list_path):
        print("❌ 股票列表缓存不存在")
        return []
    
    with open(stock_list_path, 'r', encoding='utf-8') as f:
        stock_list = json.load(f)
    
    # 加载流通市值数据
    market_cap_path = os.path.join(cache_dir, 'market_cap.json')
    market_cap_data = {}
    if os.path.exists(market_cap_path):
        with open(market_cap_path, 'r', encoding='utf-8') as f:
            market_cap_data = json.load(f)
    
    print(f"📊 共 {len(stock_list)} 只股票待扫描")
    
    # 扫描所有股票
    candidates = []
    processed = 0
    skipped = 0
    skipped_market_cap = 0
    
    for stock_info in stock_list:
        stock_code = stock_info.get('code', '')
        stock_name = stock_info.get('name', '')
        
        # 排除ST股票
        if 'ST' in stock_name.upper():
            skipped += 1
            continue
        
        # 排除北交所股票（8开头、9开头）
        if stock_code.startswith('8') or stock_code.startswith('9'):
            skipped += 1
            continue
        
        # 流通市值筛选
        cap_info = market_cap_data.get(stock_code, {})
        circulating_cap = cap_info.get('circulating_cap', 0)
        if circulating_cap > max_market_cap:
            skipped_market_cap += 1
            continue
        
        processed += 1
        
        # 显示进度
        if processed % 500 == 0:
            print(f"   进度: {processed} | 已找到候选: {len(candidates)}")
        
        # 处理单只股票
        result = process_single_stock(
            analyzer, stock_code, stock_name, 
            common_features, scan_date, min_match_score
        )
        
        if result:
            result['流通市值'] = round(circulating_cap, 2)
            candidates.append(result)
    
    print(f"✅ 扫描完成: 处理 {processed} 只 | 市值过大跳过 {skipped_market_cap} 只 | 找到 {len(candidates)} 只候选")
    
    # 按匹配度排序，取前N只
    candidates_sorted = sorted(candidates, key=lambda x: x.get('匹配度', 0), reverse=True)
    top_stocks = candidates_sorted[:top_n]
    
    # 显示结果
    if top_stocks:
        print(f"\n📈 {scan_date} 匹配度前{top_n}的个股 (匹配度≥{min_match_score}):")
        print(f"{'排名':<4} {'代码':<8} {'名称':<12} {'匹配度':<8} {'价格':<8} {'流通市值':<10}")
        print("-" * 60)
        for i, stock in enumerate(top_stocks, 1):
            cap_str = f"{stock.get('流通市值', 0):.1f}亿"
            print(f"{i:<4} {stock['股票代码']:<8} {stock['股票名称']:<12} "
                  f"{stock['匹配度']:.3f}    {stock['价格']:.2f}    {cap_str}")
    else:
        print("⚠️ 未找到符合条件的股票")
    
    return top_stocks


def process_single_stock(analyzer, stock_code, stock_name, common_features, scan_date, min_match_score):
    """
    处理单只股票，计算匹配度
    """
    try:
        # 从本地缓存获取周K线数据
        cache_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cache', 'weekly_kline')
        
        # 尝试不同的缓存文件格式
        csv_path = os.path.join(cache_dir, f'{stock_code}.csv')
        json_path = os.path.join(cache_dir, f'{stock_code}.json')
        
        weekly_df = None
        
        if os.path.exists(csv_path):
            weekly_df = pd.read_csv(csv_path)
        elif os.path.exists(json_path):
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            weekly_df = pd.DataFrame(data)
        else:
            return None
        
        if weekly_df is None or len(weekly_df) < 40:
            return None
        
        # 标准化列名
        column_mapping = {
            '日期': '日期',
            'date': '日期',
            '收盘': '收盘',
            'close': '收盘',
            '开盘': '开盘',
            'open': '开盘',
            '最高': '最高',
            'high': '最高',
            '最低': '最低',
            'low': '最低',
            '周成交量': '周成交量',
            '成交量': '周成交量',
            'volume': '周成交量',
        }
        
        weekly_df = weekly_df.rename(columns=column_mapping)
        
        # 确保日期列存在
        if '日期' not in weekly_df.columns:
            return None
        
        # 按日期筛选（截止到scan_date）
        try:
            scan_ts = pd.to_datetime(scan_date, errors='coerce')
            weekly_df['__dt'] = pd.to_datetime(weekly_df['日期'], errors='coerce')
            weekly_df = weekly_df.dropna(subset=['__dt'])
            weekly_df = weekly_df[weekly_df['__dt'] <= scan_ts]
            weekly_df = weekly_df.drop(columns=['__dt'])
            
            if len(weekly_df) < 40:
                return None
        except Exception:
            return None
        
        # 使用最后一条作为当前点
        current_idx = len(weekly_df) - 1
        
        # 提取特征
        features = analyzer.extract_features_at_start_point(
            stock_code, current_idx, lookback_weeks=40, weekly_df=weekly_df
        )
        
        if features is None:
            return None
        
        # 计算匹配度
        match_result = analyzer._calculate_match_score(features, common_features, tolerance=0.3)
        total_match = match_result['总匹配度']
        
        if total_match < min_match_score:
            return None
        
        # 获取当前价格
        current_price = float(weekly_df.iloc[current_idx]['收盘'])
        current_date = weekly_df.iloc[current_idx]['日期']
        
        if isinstance(current_date, pd.Timestamp):
            current_date_str = current_date.strftime('%Y-%m-%d')
        else:
            current_date_str = str(current_date)
        
        return {
            '股票代码': stock_code,
            '股票名称': stock_name,
            '匹配度': round(total_match, 3),
            '价格': round(current_price, 2),
            '日期': current_date_str,
            '核心特征匹配': match_result.get('核心特征匹配', {})
        }
        
    except Exception as e:
        return None


def calculate_future_returns(top_stocks, scan_date, periods=[1, 2, 4, 8]):
    """
    计算选出的股票在未来N周的收益
    
    :param top_stocks: 选出的股票列表
    :param scan_date: 扫描日期
    :param periods: 收益计算周期（周数）
    :return: 带有收益信息的股票列表
    """
    cache_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cache', 'weekly_kline')
    
    for stock in top_stocks:
        stock_code = stock['股票代码']
        buy_price = stock['价格']
        
        # 读取周K线数据
        csv_path = os.path.join(cache_dir, f'{stock_code}.csv')
        json_path = os.path.join(cache_dir, f'{stock_code}.json')
        
        weekly_df = None
        if os.path.exists(csv_path):
            weekly_df = pd.read_csv(csv_path)
        elif os.path.exists(json_path):
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            weekly_df = pd.DataFrame(data)
        
        if weekly_df is None or len(weekly_df) == 0:
            continue
        
        # 标准化列名
        if 'close' in weekly_df.columns:
            weekly_df = weekly_df.rename(columns={'close': '收盘', 'date': '日期'})
        
        # 转换日期
        weekly_df['__dt'] = pd.to_datetime(weekly_df['日期'], errors='coerce')
        weekly_df = weekly_df.dropna(subset=['__dt'])
        weekly_df = weekly_df.sort_values('__dt').reset_index(drop=True)
        
        # 找到买入点
        scan_ts = pd.to_datetime(scan_date)
        buy_idx = None
        for i, row in weekly_df.iterrows():
            if row['__dt'] <= scan_ts:
                buy_idx = i
            else:
                break
        
        if buy_idx is None:
            continue
        
        # 计算各周期收益
        for period in periods:
            future_idx = buy_idx + period
            if future_idx < len(weekly_df):
                future_price = float(weekly_df.iloc[future_idx]['收盘'])
                ret = (future_price - buy_price) / buy_price * 100
                stock[f'{period}周后收益'] = round(ret, 2)
            else:
                stock[f'{period}周后收益'] = None
    
    return top_stocks


def main():
    """主函数"""
    print("=" * 80)
    print("🚀 2025年12月回测 - 每周选出匹配度前5的个股")
    print("=" * 80)
    print()
    
    # 加载模型
    model_path = 'trained_model.json'
    print(f"📂 加载模型: {model_path}")
    
    analyzer = BullStockAnalyzer(auto_load_default_stocks=False, auto_analyze_and_train=False)
    
    if not analyzer.load_model(model_path, skip_network=True):
        print("❌ 模型加载失败")
        return
    
    print("✅ 模型加载成功")
    
    # 获取特征模板
    common_features = analyzer.trained_features.get('common_features', {})
    print(f"📊 特征模板包含 {len(common_features)} 个特征")
    print()
    
    # 获取12月每周日期
    weeks = get_dec_2025_weeks()
    print(f"📅 回测周数: {len(weeks)} 周")
    print(f"   日期: {', '.join(weeks)}")
    print()
    
    # 存储所有结果
    all_results = []
    
    # 逐周回测
    for week_date in weeks:
        top_stocks = backtest_single_week(
            analyzer, week_date, common_features, 
            top_n=5, min_match_score=0.95, max_market_cap=100.0
        )
        
        # 计算未来收益
        if top_stocks:
            top_stocks = calculate_future_returns(top_stocks, week_date)
            
            for stock in top_stocks:
                stock['扫描周'] = week_date
                all_results.append(stock)
    
    # 汇总结果
    print("\n" + "=" * 80)
    print("📊 回测汇总")
    print("=" * 80)
    
    if all_results:
        df = pd.DataFrame(all_results)
        
        # 显示汇总表格
        print("\n各周选股结果:")
        print("-" * 100)
        
        # 按周分组显示
        for week_date in weeks:
            week_stocks = [s for s in all_results if s.get('扫描周') == week_date]
            if week_stocks:
                print(f"\n📅 {week_date}:")
                print(f"{'排名':<4} {'代码':<8} {'名称':<12} {'匹配度':<8} {'买入价':<8} "
                      f"{'1周收益':<10} {'2周收益':<10} {'4周收益':<10}")
                print("-" * 90)
                for i, s in enumerate(week_stocks, 1):
                    ret_1w = s.get('1周后收益', '--')
                    ret_2w = s.get('2周后收益', '--')
                    ret_4w = s.get('4周后收益', '--')
                    ret_1w_str = f"{ret_1w}%" if ret_1w is not None else '--'
                    ret_2w_str = f"{ret_2w}%" if ret_2w is not None else '--'
                    ret_4w_str = f"{ret_4w}%" if ret_4w is not None else '--'
                    print(f"{i:<4} {s['股票代码']:<8} {s['股票名称']:<12} "
                          f"{s['匹配度']:.3f}    {s['价格']:<8.2f} "
                          f"{ret_1w_str:<10} {ret_2w_str:<10} {ret_4w_str:<10}")
        
        # 统计平均收益
        print("\n" + "=" * 80)
        print("📈 收益统计:")
        print("-" * 50)
        
        for period in [1, 2, 4, 8]:
            col = f'{period}周后收益'
            if col in df.columns:
                valid_returns = df[col].dropna()
                if len(valid_returns) > 0:
                    avg_ret = valid_returns.mean()
                    win_rate = (valid_returns > 0).sum() / len(valid_returns) * 100
                    max_ret = valid_returns.max()
                    min_ret = valid_returns.min()
                    print(f"{period}周后: 平均收益 {avg_ret:.2f}% | 胜率 {win_rate:.1f}% | "
                          f"最高 {max_ret:.2f}% | 最低 {min_ret:.2f}%")
        
        # 保存结果
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = f'backtest_dec_2025_weekly_{timestamp}.csv'
        df.to_csv(output_file, index=False, encoding='utf-8-sig')
        print(f"\n✅ 结果已保存到: {output_file}")
        
    else:
        print("⚠️ 未找到任何符合条件的股票")
    
    print("\n" + "=" * 80)
    print("回测完成！")
    print("=" * 80)


if __name__ == '__main__':
    main()
