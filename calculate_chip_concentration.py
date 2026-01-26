#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
计算22只个股最佳买点的筹码集中度
"""
import sys
sys.path.insert(0, '.')
from bull_stock_analyzer import BullStockAnalyzer
import json
import os
from datetime import datetime

def get_stock_name(fetcher, stock_code):
    """获取股票名称"""
    try:
        all_stocks = fetcher.get_all_stocks()
        if all_stocks is not None and not all_stocks.empty:
            stock_row = all_stocks[all_stocks['代码'] == str(stock_code)]
            if not stock_row.empty:
                return stock_row.iloc[0].get('名称', stock_code)
    except:
        pass
    return stock_code

def main():
    print("=" * 80)
    print("📊 计算22只个股最佳买点的筹码集中度")
    print("=" * 80)
    
    # 加载训练后的模型
    model_file = 'trained_model.json'
    if not os.path.exists(model_file):
        print(f"❌ 错误：找不到模型文件 {model_file}")
        return
    
    with open(model_file, 'r', encoding='utf-8') as f:
        model_data = json.load(f)
    
    training_stocks = model_data.get('buy_features', {}).get('training_stocks', [])
    print(f"\n📋 找到 {len(training_stocks)} 只训练股票\n")
    
    # 初始化分析器
    analyzer = BullStockAnalyzer(auto_load_default_stocks=False, auto_analyze_and_train=False)
    
    results = []
    
    for i, stock_code in enumerate(training_stocks, 1):
        try:
            print(f"[{i}/{len(training_stocks)}] 处理 {stock_code}...", end=' ', flush=True)
            
            # 获取股票名称
            stock_name = get_stock_name(analyzer.fetcher, stock_code)
            
            # 获取周线数据
            weekly_df = analyzer.fetcher.get_weekly_kline(stock_code, period="2y")
            if weekly_df is None or len(weekly_df) < 20:
                print(f"⚠️ 无法获取足够的周线数据")
                continue
            
            # 查找最佳买点（8周内涨幅达到300%的区间）
            # 直接使用find_buy_points的逻辑，找到涨幅最大的区间
            valid_intervals = []
            for start_idx in range(8, len(weekly_df)):
                max_price = 0
                max_price_date = None
                max_price_idx = start_idx
                
                # 检查接下来8周内的涨幅
                for end_idx in range(start_idx + 1, min(start_idx + 9, len(weekly_df))):
                    start_price = float(weekly_df.iloc[start_idx]['收盘'])
                    end_price = float(weekly_df.iloc[end_idx]['收盘'])
                    gain = (end_price - start_price) / start_price * 100
                    
                    current_price = float(weekly_df.iloc[end_idx]['收盘'])
                    if current_price > max_price:
                        max_price = current_price
                        max_price_idx = end_idx
                        max_price_date = weekly_df.iloc[end_idx]['日期']
                
                # 计算最终涨幅
                start_price = float(weekly_df.iloc[start_idx]['收盘'])
                final_price = float(weekly_df.iloc[max_price_idx]['收盘'])
                gain = (final_price - start_price) / start_price * 100
                weeks = max_price_idx - start_idx
                
                # 如果涨幅>=300%，记录这个区间
                if gain >= 300.0:
                    valid_intervals.append({
                        '起点索引': start_idx,
                        '终点索引': max_price_idx,
                        '涨幅': gain,
                        '周数': weeks,
                        '最高价': max_price,
                        '最高价日期': max_price_date
                    })
            
            if not valid_intervals:
                print(f"⚠️ 未找到符合条件的买点")
                continue
            
            # 找到涨幅最大的区间作为最佳买点
            best_interval = max(valid_intervals, key=lambda x: x['涨幅'])
            best_start_idx = best_interval['起点索引']
            
            # 获取最佳买点的日期和价格
            buy_date = weekly_df.iloc[best_start_idx]['日期']
            if hasattr(buy_date, 'strftime'):
                buy_date_str = buy_date.strftime('%Y-%m-%d')
            else:
                buy_date_str = str(buy_date)
            buy_price = float(weekly_df.iloc[best_start_idx]['收盘'])
            
            # 提取特征，获取筹码集中度
            features = analyzer.extract_features_at_start_point(
                stock_code, best_start_idx, lookback_weeks=40, weekly_df=weekly_df
            )
            
            if features and '筹码集中度' in features:
                chip_concentration = features.get('筹码集中度')
                profit_chips = features.get('盈利筹码比例', None)
                
                results.append({
                    '股票代码': stock_code,
                    '股票名称': stock_name,
                    '最佳买点日期': buy_date_str,
                    '最佳买点价格': round(buy_price, 2),
                    '区间涨幅': round(best_interval['涨幅'], 2),
                    '区间周数': best_interval['周数'],
                    '筹码集中度': chip_concentration,
                    '盈利筹码比例': profit_chips
                })
                
                print(f"✅ 日期={buy_date_str}, 价格={buy_price:.2f}, 涨幅={best_interval['涨幅']:.2f}%, 筹码集中度={chip_concentration}")
            else:
                print(f"⚠️ 无法提取筹码集中度特征")
                
        except Exception as e:
            print(f"❌ 处理失败: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "=" * 80)
    print("📊 计算结果汇总")
    print("=" * 80)
    print(f"\n共处理 {len(training_stocks)} 只股票，成功计算 {len(results)} 只\n")
    
    if results:
        # 按股票代码排序
        results.sort(key=lambda x: x['股票代码'])
        
        print(f"{'排名':<6} {'股票代码':<10} {'股票名称':<12} {'最佳买点日期':<12} {'最佳买点价格':<12} {'区间涨幅':<10} {'筹码集中度':<12} {'盈利筹码比例':<14}")
        print("-" * 110)
        for i, r in enumerate(results, 1):
            chip_conc = f"{r['筹码集中度']:.2f}" if r['筹码集中度'] is not None else "N/A"
            profit = f"{r['盈利筹码比例']:.2f}" if r['盈利筹码比例'] is not None else "N/A"
            print(f"{i:<6} {r['股票代码']:<10} {r['股票名称']:<12} {r['最佳买点日期']:<12} {r['最佳买点价格']:>10.2f} {r['区间涨幅']:>8.2f}% {chip_conc:>12} {profit:>14}")
        
        # 统计信息
        chip_values = [r['筹码集中度'] for r in results if r['筹码集中度'] is not None]
        profit_values = [r['盈利筹码比例'] for r in results if r['盈利筹码比例'] is not None]
        
        if chip_values:
            print(f"\n📈 筹码集中度统计:")
            print(f"   平均值: {sum(chip_values) / len(chip_values):.2f}")
            print(f"   最小值: {min(chip_values):.2f}")
            print(f"   最大值: {max(chip_values):.2f}")
        
        if profit_values:
            print(f"\n📈 盈利筹码比例统计:")
            print(f"   平均值: {sum(profit_values) / len(profit_values):.2f}")
            print(f"   最小值: {min(profit_values):.2f}")
            print(f"   最大值: {max(profit_values):.2f}")
        
        # 保存结果到JSON文件
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = f'training_stocks_chip_concentration_{timestamp}.json'
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump({
                '计算时间': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                '股票数量': len(results),
                '结果': results
            }, f, ensure_ascii=False, indent=2)
        print(f"\n✅ 结果已保存到: {output_file}")
    else:
        print("❌ 没有成功计算的结果")

if __name__ == '__main__':
    main()
