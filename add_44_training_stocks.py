#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
将44只训练股票添加到系统中，显示在主页面"已添加的大牛股"中
"""
import sys
sys.path.insert(0, '.')
from bull_stock_analyzer import BullStockAnalyzer
import json
from datetime import datetime

def add_44_training_stocks():
    """将44只训练股票添加到系统"""
    print("=" * 80)
    print("📝 将44只训练股票添加到系统")
    print("=" * 80)
    
    # 读取44只训练股票信息
    print("\n📊 加载44只训练股票信息...")
    with open('training_44_stocks.json', 'r', encoding='utf-8') as f:
        training_stocks = json.load(f)
    
    print(f"✅ 加载了 {len(training_stocks)} 只训练股票")
    
    # 创建分析器（不自动加载默认股票，避免重复）
    analyzer = BullStockAnalyzer(
        auto_load_default_stocks=False,
        auto_analyze_and_train=False
    )
    
    # 加载现有模型（如果存在），获取已添加的股票
    analyzer.load_model('trained_model.json', skip_network=True)
    
    print(f"\n📊 当前已有 {len(analyzer.bull_stocks)} 只股票")
    
    # 添加44只训练股票
    print("\n" + "=" * 80)
    print("📝 开始添加44只训练股票...")
    print("=" * 80)
    
    added_count = 0
    skipped_count = 0
    
    for i, stock_info in enumerate(training_stocks, 1):
        stock_code = stock_info['代码']
        stock_name = stock_info['名称']
        
        # 检查是否已存在
        existing = [s for s in analyzer.bull_stocks if s['代码'] == stock_code]
        if existing:
            print(f"[{i}/{len(training_stocks)}] ⏭️  {stock_code} {stock_name} 已存在，跳过")
            skipped_count += 1
            continue
        
        # 添加股票
        result = analyzer.add_bull_stock(stock_code)
        if result.get('success'):
            print(f"[{i}/{len(training_stocks)}] ✅ {stock_code} {stock_name} 添加成功")
            added_count += 1
        else:
            print(f"[{i}/{len(training_stocks)}] ❌ {stock_code} {stock_name} 添加失败: {result.get('message', '')}")
    
    print(f"\n✅ 添加完成！")
    print(f"   - 新增: {added_count} 只")
    print(f"   - 已存在: {skipped_count} 只")
    print(f"   - 总计: {len(analyzer.bull_stocks)} 只股票")
    
    # 保存模型（包含新添加的股票）
    print("\n💾 保存模型...")
    if analyzer.save_model('trained_model.json'):
        print("✅ 模型已保存，44只训练股票已添加到系统")
    else:
        print("❌ 模型保存失败")
    
    # 显示前10只股票
    print(f"\n📋 股票列表预览（前10只）:")
    for i, stock in enumerate(analyzer.bull_stocks[:10], 1):
        print(f"   {i}. {stock['代码']} {stock.get('名称', '')}")
    
    if len(analyzer.bull_stocks) > 10:
        print(f"   ... 还有 {len(analyzer.bull_stocks) - 10} 只股票")
    
    return analyzer

if __name__ == '__main__':
    add_44_training_stocks()
