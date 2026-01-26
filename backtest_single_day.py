#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
单日回测：找出指定日期匹配度排名前N的个股
"""
import sys
sys.path.insert(0, '.')
from bull_stock_analyzer import BullStockAnalyzer
from datetime import datetime
import pandas as pd

def backtest_single_day(scan_date_str, top_n=5, model_path='models/模型11.json'):
    """单日回测，找出匹配度最高的N只股票"""
    print("=" * 80)
    print(f"📅 单日回测: {scan_date_str}")
    print(f"📊 模型: {model_path}")
    print(f"🎯 目标: 找出匹配度前{top_n}的个股")
    print("=" * 80)
    print()
    
    # 加载模型
    analyzer = BullStockAnalyzer(auto_load_default_stocks=False, auto_analyze_and_train=False)
    if not analyzer.load_model(model_path, skip_network=True):
        print("❌ 模型加载失败")
        return []
    
    print("✅ 模型加载成功")
    print()
    
    # 扫描全市场
    print(f"🔍 开始扫描全市场（日期: {scan_date_str}）...")
    print()
    
    # 使用较低的匹配度阈值，以便找到更多候选
    result = analyzer.scan_all_stocks(
        min_match_score=0.3,  # 低阈值，收集更多候选
        max_market_cap=200.0,  # 放宽市值限制
        scan_date=scan_date_str,
        use_parallel=True
    )
    
    if not result.get('success'):
        print(f"❌ 扫描失败: {result.get('message', '')}")
        return []
    
    candidates = result.get('candidates', [])
    print()
    print(f"✅ 扫描完成，找到 {len(candidates)} 只候选股票")
    print()
    
    if len(candidates) == 0:
        print("⚠️ 未找到任何候选股票")
        return []
    
    # 按匹配度排序
    candidates_sorted = sorted(candidates, key=lambda x: x.get('匹配度', 0), reverse=True)
    
    # 取前N只
    top_stocks = candidates_sorted[:top_n]
    
    print("=" * 80)
    print(f"📊 {scan_date_str} 匹配度排名前{top_n}的个股:")
    print("=" * 80)
    print()
    print(f"{'排名':<4} {'股票代码':<8} {'股票名称':<10} {'匹配度':<8} {'价格':<8} {'市值(亿)':<10}")
    print("-" * 60)
    
    for i, stock in enumerate(top_stocks, 1):
        code = stock.get('股票代码', 'N/A')
        name = stock.get('股票名称', 'N/A')
        match_score = stock.get('匹配度', 0)
        price = stock.get('买点价格', 'N/A')
        market_cap = stock.get('流通市值', 'N/A')
        
        price_str = f"{price:.2f}" if isinstance(price, (int, float)) else str(price)
        cap_str = f"{market_cap:.2f}" if isinstance(market_cap, (int, float)) else str(market_cap)
        
        print(f"{i:<4} {code:<8} {name:<10} {match_score:.3f}    {price_str:<8} {cap_str}")
    
    print()
    
    # 保存结果
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    csv_file = f'backtest_{scan_date_str.replace("-", "")}_{timestamp}.csv'
    
    df = pd.DataFrame(top_stocks)
    df.to_csv(csv_file, index=False, encoding='utf-8-sig')
    print(f"✅ 结果已保存到: {csv_file}")
    
    return top_stocks


if __name__ == '__main__':
    import sys
    
    # 默认参数
    scan_date = '2025-01-04'
    top_n = 5
    model_path = 'models/模型11.json'
    
    # 从命令行参数获取
    if len(sys.argv) > 1:
        scan_date = sys.argv[1]
    if len(sys.argv) > 2:
        top_n = int(sys.argv[2])
    if len(sys.argv) > 3:
        model_path = sys.argv[3]
    
    backtest_single_day(scan_date, top_n, model_path)
