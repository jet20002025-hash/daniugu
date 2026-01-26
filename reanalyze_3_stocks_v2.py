#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
重新分析三只股票的最佳买点：002969嘉美包装、001331胜通能源、300986志特新材
"""
from bull_stock_analyzer import BullStockAnalyzer
import pandas as pd

def reanalyze_stocks():
    """重新分析三只股票"""
    print("=" * 80)
    print("🔍 重新分析三只股票的最佳买点")
    print("=" * 80)
    
    stocks_to_analyze = [
        ('002969', '嘉美包装'),
        ('001331', '胜通能源'),
        ('300986', '志特新材')
    ]
    
    # 创建分析器
    print("\n初始化分析器...")
    analyzer = BullStockAnalyzer(auto_load_default_stocks=False, auto_analyze_and_train=False)
    
    # 加载模型
    print("\n加载模型...")
    model_path = 'trained_model.json'
    analyzer.load_model(model_path, skip_network=True)
    
    # 先添加这三只股票（如果不存在）
    for stock_code, stock_name in stocks_to_analyze:
        # 检查是否已存在
        existing = [s for s in analyzer.bull_stocks if s['代码'] == stock_code]
        if not existing:
            result = analyzer.add_bull_stock(stock_code)
            if result.get('success'):
                print(f"✅ 已添加: {stock_code} {stock_name}")
    
    results = {}
    
    for stock_code, stock_name in stocks_to_analyze:
        print("\n" + "=" * 80)
        print(f"📊 分析 {stock_name} ({stock_code})")
        print("=" * 80)
        
        # 重新分析股票（清空之前的分析结果）
        if stock_code in analyzer.analysis_results:
            del analyzer.analysis_results[stock_code]
            print(f"已清空 {stock_code} 之前的分析结果")
        
        # 分析股票
        print(f"\n开始分析 {stock_code} {stock_name}...")
        analysis_result = analyzer.analyze_bull_stock(stock_code)
        
        if not analysis_result.get('success'):
            print(f"❌ 分析失败: {analysis_result.get('message', '')}")
            continue
        
        interval = analysis_result.get('interval', {})
        start_idx = interval.get('起点索引')
        start_date = interval.get('起点日期')
        start_price = interval.get('起点价格')
        end_date = interval.get('终点日期')
        end_price = interval.get('终点价格')
        gain = interval.get('涨幅', 0)
        
        print(f"\n✅ 分析结果:")
        print(f"   - 起点日期: {start_date}")
        print(f"   - 起点价格: {start_price} 元")
        print(f"   - 起点索引: {start_idx}")
        print(f"   - 终点日期: {end_date}")
        print(f"   - 终点价格: {end_price} 元")
        print(f"   - 涨幅: {gain:.2f}%")
        
        # 获取周K线数据，查看买点前后的详细情况
        print(f"\n📈 查看周K线数据...")
        weekly_df = analyzer.fetcher.get_weekly_kline(stock_code, period="2y")
        if weekly_df is None or len(weekly_df) == 0:
            print(f"❌ 无法获取周K线数据")
            continue
        
        print(f"   - 总周数: {len(weekly_df)}")
        
        if start_idx is not None:
            # 显示买点前后各10周的数据，更详细
            print(f"\n📊 买点前后各10周的数据:")
            print("-" * 80)
            start_range = max(0, start_idx - 10)
            end_range = min(len(weekly_df), start_idx + 11)
            
            for i in range(start_range, end_range):
                row = weekly_df.iloc[i]
                date = row['日期']
                close = row['收盘']
                volume = row.get('周成交量', row.get('成交量', 0))
                change_pct = row.get('涨跌幅', 0)
                
                marker = " ⭐ 买点" if i == start_idx else ""
                print(f"   [{i:3d}] {date} | 收盘: {close:.2f} | 成交量: {volume:,.0f} | 涨跌幅: {change_pct:+.2f}%{marker}")
        
        # 查找买点
        print(f"\n🔍 查找历史买点...")
        buy_points_result = analyzer.find_buy_points(
            stock_code, 
            tolerance=0.3, 
            search_years=5, 
            match_threshold=0.6
        )
        
        if buy_points_result.get('success'):
            buy_points = buy_points_result.get('buy_points', [])
            print(f"\n✅ 找到 {len(buy_points)} 个买点")
            
            if buy_points:
                print(f"\n前10个买点:")
                for i, bp in enumerate(buy_points[:10], 1):
                    match_score = bp.get('匹配度', 0) or 0
                    buy_date = bp.get('日期', '') or ''
                    buy_price = bp.get('价格', 0) or 0
                    is_best = bp.get('是否最佳买点', False)
                    gain_10w = bp.get('买入后10周涨幅', 0) or 0
                    max_gain_10w = bp.get('10周内最大涨幅', 0) or 0
                    
                    print(f"   {i}. {buy_date} | 价格: {buy_price:.2f} | 匹配度: {match_score:.3f} | 10周涨幅: {gain_10w:.2f}% | 最大涨幅: {max_gain_10w:.2f}% | {'⭐ 最佳买点' if is_best else ''}")
                
                # 检查训练时的最佳买点是否在结果中
                best_bp = buy_points[0]
                if start_idx is not None:
                    # 检查最佳买点的日期是否与训练时的起点日期一致
                    best_date = best_bp.get('日期', '')
                    if best_date == str(start_date):
                        print(f"\n✅ 最佳买点与训练时的起点日期一致: {best_date}")
                    else:
                        print(f"\n⚠️ 最佳买点日期 ({best_date}) 与训练时的起点日期 ({start_date}) 不一致")
                        print(f"   建议：可能需要调整分析参数或重新训练模型")
        
        results[stock_code] = {
            'analysis': analysis_result,
            'buy_points': buy_points_result
        }
    
    print("\n" + "=" * 80)
    print("📊 分析完成")
    print("=" * 80)
    
    return results

if __name__ == '__main__':
    reanalyze_stocks()
