"""
查找已添加股票的涨幅最大区间
"""
from surge_stock_analyzer import SurgeStockAnalyzer
from data_fetcher import DataFetcher
import pandas as pd
import numpy as np

def find_max_gain_interval(stock_code, stock_name, days=20):
    """
    找到股票涨幅最大的区间（指定天数内）
    :param stock_code: 股票代码
    :param stock_name: 股票名称
    :param days: 区间天数（默认20个交易日，约一个月）
    :return: 涨幅最大区间的信息
    """
    print(f"\n正在分析 {stock_code} {stock_name}...")
    print(f"查找 {days} 个交易日内涨幅最大的区间...")
    
    fetcher = DataFetcher()
    daily_df = fetcher.get_daily_kline(stock_code)
    
    if daily_df is None or len(daily_df) == 0:
        print(f"❌ 无法获取 {stock_code} 的数据")
        return None
    
    if len(daily_df) < days:
        print(f"❌ 数据不足，需要至少 {days} 天数据，实际只有 {len(daily_df)} 天")
        return None
    
    # 找到涨幅最大的区间（在指定天数内）
    max_gain = 0
    max_gain_start_idx = None
    max_gain_end_idx = None
    max_gain_start_price = None
    max_gain_end_price = None
    max_gain_start_date = None
    max_gain_end_date = None
    
    # 遍历所有可能的起点
    for start_idx in range(len(daily_df) - days + 1):
        start_price = daily_df.iloc[start_idx]['收盘']
        start_date = daily_df.iloc[start_idx]['日期']
        
        # 在起点后的days个交易日内，找到最高价格
        end_idx = min(start_idx + days, len(daily_df))
        window_df = daily_df.iloc[start_idx:end_idx]
        
        # 找到窗口内的最高价格和对应日期
        # 使用最高价而不是收盘价，因为可能盘中涨停
        max_price_idx = window_df['最高'].idxmax()
        max_price = window_df.loc[max_price_idx, '最高']
        max_price_date = window_df.loc[max_price_idx, '日期']
        
        # 计算涨幅（使用最高价）
        gain = (max_price - start_price) / start_price * 100
        
        if gain > max_gain:
            max_gain = gain
            max_gain_start_idx = start_idx
            # 找到最高价在原始数据中的索引
            max_gain_end_idx = daily_df.index.get_loc(max_price_idx)
            max_gain_start_price = start_price
            max_gain_end_price = max_price
            max_gain_start_date = start_date
            max_gain_end_date = max_price_date
    
    if max_gain_start_idx is not None:
        # 计算交易日数
        trading_days = max_gain_end_idx - max_gain_start_idx
        
        result = {
            '股票代码': stock_code,
            '股票名称': stock_name,
            '起点日期': str(max_gain_start_date),
            '起点价格': float(max_gain_start_price),
            '终点日期': str(max_gain_end_date),
            '终点价格': float(max_gain_end_price),
            '涨幅': float(max_gain),
            '交易日数': trading_days,
            '区间天数': days
        }
        
        print(f"✅ 找到 {days} 个交易日内涨幅最大区间:")
        print(f"   起点日期: {max_gain_start_date}")
        print(f"   起点价格: {max_gain_start_price:.2f} 元")
        print(f"   终点日期: {max_gain_end_date}")
        print(f"   终点价格: {max_gain_end_price:.2f} 元")
        print(f"   涨幅: {max_gain:.2f}% (翻{max_gain/100:.2f}倍)")
        print(f"   实际交易日数: {trading_days} 天")
        
        return result
    else:
        print(f"❌ 未找到涨幅区间")
        return None


if __name__ == '__main__':
    import sys
    
    analyzer = SurgeStockAnalyzer()
    
    # 如果命令行提供了股票代码，直接分析
    if len(sys.argv) > 1:
        stock_code = sys.argv[1]
        stock_name = sys.argv[2] if len(sys.argv) > 2 else stock_code
        result = find_max_gain_interval(stock_code, stock_name)
        if result:
            print("\n" + "=" * 80)
            print("分析结果:")
            print("=" * 80)
            print(f"股票: {result['股票名称']} ({result['股票代码']})")
            print(f"起点: {result['起点日期']} @ {result['起点价格']:.2f} 元")
            print(f"终点: {result['终点日期']} @ {result['终点价格']:.2f} 元")
            print(f"涨幅: {result['涨幅']:.2f}% (翻{result['涨幅']/100:.2f}倍)")
            print(f"交易日数: {result['交易日数']} 天")
    else:
        # 获取已添加的股票
        if len(analyzer.surge_stocks) == 0:
            print("❌ 没有已添加的股票")
            print("\n使用方法:")
            print("  python3 find_max_gain.py <股票代码> [股票名称]")
            print("  例如: python3 find_max_gain.py 001331 胜通能源")
        else:
            print(f"\n找到 {len(analyzer.surge_stocks)} 只已添加的股票")
            print("=" * 80)
            
            results = []
            for stock in analyzer.surge_stocks:
                stock_code = stock.get('股票代码')
                stock_name = stock.get('股票名称')
                
                if stock_code and stock_name:
                    result = find_max_gain_interval(stock_code, stock_name)
                    if result:
                        results.append(result)
            
            # 汇总显示
            print("\n" + "=" * 80)
            print("汇总结果:")
            print("=" * 80)
            for i, result in enumerate(results, 1):
                print(f"\n{i}. {result['股票名称']} ({result['股票代码']})")
                print(f"   起点: {result['起点日期']} @ {result['起点价格']:.2f} 元")
                print(f"   终点: {result['终点日期']} @ {result['终点价格']:.2f} 元")
                print(f"   涨幅: {result['涨幅']:.2f}% (翻{result['涨幅']/100:.2f}倍)")
                print(f"   交易日数: {result['交易日数']} 天")

