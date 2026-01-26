#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
移除三只股票（002969嘉美包装、001331胜通能源、300986志特新材），只保留原有的11只个股
并重新分析这11只股票
"""
from bull_stock_analyzer import BullStockAnalyzer

def remove_and_reanalyze():
    """移除三只股票并重新分析"""
    print("=" * 80)
    print("🔧 移除三只股票，只保留原有的11只个股")
    print("=" * 80)
    
    # 要移除的股票代码
    stocks_to_remove = ['002969', '001331', '300986']
    
    # 原有的11只个股
    original_11_stocks = ['000592', '002104', '002759', '300436', '301005', '301232', '002788', '603778', '603122', '600343', '603216']
    
    # 创建分析器
    print("\n初始化分析器...")
    analyzer = BullStockAnalyzer(auto_load_default_stocks=False, auto_analyze_and_train=False)
    
    # 加载模型
    print("\n加载模型...")
    model_path = 'trained_model.json'
    analyzer.load_model(model_path, skip_network=True)
    
    print(f"\n当前模型中有 {len(analyzer.bull_stocks)} 只股票")
    
    # 移除三只股票
    print(f"\n移除股票: {', '.join(stocks_to_remove)}")
    removed_count = 0
    for stock_code in stocks_to_remove:
        # 从bull_stocks列表中移除
        analyzer.bull_stocks = [s for s in analyzer.bull_stocks if s['代码'] != stock_code]
        # 从analysis_results中移除
        if stock_code in analyzer.analysis_results:
            del analyzer.analysis_results[stock_code]
        removed_count += 1
        print(f"  ✅ 已移除: {stock_code}")
    
    print(f"\n已移除 {removed_count} 只股票")
    print(f"剩余 {len(analyzer.bull_stocks)} 只股票")
    
    # 确保只保留原有的11只个股
    print(f"\n确保只保留原有的11只个股...")
    analyzer.bull_stocks = [s for s in analyzer.bull_stocks if s['代码'] in original_11_stocks]
    
    # 清理analysis_results，只保留这11只股票的分析结果
    analyzer.analysis_results = {code: analyzer.analysis_results[code] 
                                for code in analyzer.analysis_results.keys() 
                                if code in original_11_stocks}
    
    print(f"✅ 已确保只保留 {len(analyzer.bull_stocks)} 只股票")
    print("\n保留的股票列表:")
    for stock in analyzer.bull_stocks:
        print(f"  {stock['代码']} - {stock['名称']}")
    
    # 重新分析所有11只股票
    print("\n" + "=" * 80)
    print("📊 重新分析11只股票")
    print("=" * 80)
    
    for stock in analyzer.bull_stocks:
        stock_code = stock['代码']
        stock_name = stock['名称']
        print(f"\n分析 {stock_name} ({stock_code})...")
        
        # 清空之前的分析结果
        if stock_code in analyzer.analysis_results:
            del analyzer.analysis_results[stock_code]
        
        # 重新分析
        result = analyzer.analyze_bull_stock(stock_code)
        
        if result.get('success'):
            interval = result.get('interval', {})
            start_date = interval.get('起点日期')
            start_price = interval.get('起点价格')
            gain = interval.get('涨幅', 0)
            print(f"  ✅ 起点日期: {start_date}, 起点价格: {start_price} 元, 涨幅: {gain:.2f}%")
        else:
            print(f"  ❌ 分析失败: {result.get('message', '')}")
    
    # 保存模型
    print("\n" + "=" * 80)
    print("💾 保存更新后的模型...")
    analyzer.save_model('trained_model.json')
    print("✅ 模型已保存")
    
    print("\n" + "=" * 80)
    print("📊 完成")
    print("=" * 80)
    print(f"✅ 已移除3只股票，保留11只股票")
    print(f"✅ 已重新分析所有11只股票")
    print(f"✅ 模型已保存")

if __name__ == '__main__':
    remove_and_reanalyze()
