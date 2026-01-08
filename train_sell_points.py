#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
训练已知大牛股的最佳卖点数据
"""
from bull_stock_analyzer import BullStockAnalyzer
import json

def train_sell_points():
    """训练卖点特征模型"""
    
    print("=" * 80)
    print("🎓 训练已知大牛股的最佳卖点数据")
    print("=" * 80)
    
    # 创建分析器（自动加载默认大牛股）
    print("\n📊 初始化分析器...")
    analyzer = BullStockAnalyzer(
        auto_load_default_stocks=True,
        auto_analyze_and_train=False  # 手动控制训练过程
    )
    
    # 1. 确保所有大牛股都已分析
    print("\n📊 步骤1: 分析所有大牛股（获取起点和终点）...")
    print("-" * 80)
    
    default_stocks = analyzer.default_bull_stocks
    analyzed_count = 0
    
    for stock_code in default_stocks:
        # 检查是否已分析
        if stock_code not in analyzer.analysis_results:
            print(f"  分析 {stock_code}...", end=" ", flush=True)
            result = analyzer.analyze_bull_stock(stock_code)
            if result.get('success'):
                print("✅")
                analyzed_count += 1
            else:
                print(f"❌ {result.get('message', '')}")
        else:
            # 检查是否有有效的起点和终点
            analysis_result = analyzer.analysis_results[stock_code]
            interval = analysis_result.get('interval')
            if interval and interval.get('起点索引') is not None and interval.get('终点索引') is not None:
                print(f"  ✅ {stock_code} 已分析（起点: {interval.get('起点索引')}, 终点: {interval.get('终点索引')}）")
            else:
                print(f"  重新分析 {stock_code}...", end=" ", flush=True)
                result = analyzer.analyze_bull_stock(stock_code)
                if result.get('success'):
                    print("✅")
                    analyzed_count += 1
                else:
                    print(f"❌ {result.get('message', '')}")
    
    # 统计有效的大牛股数量
    valid_stocks = [code for code, result in analyzer.analysis_results.items() 
                   if result.get('interval') and result['interval'].get('起点索引') is not None 
                   and result['interval'].get('终点索引') is not None]
    
    print(f"\n✅ 分析完成，有效大牛股数量: {len(valid_stocks)}/{len(default_stocks)}")
    
    if len(valid_stocks) == 0:
        print("\n❌ 没有有效的大牛股数据，无法训练卖点特征")
        return
    
    # 2. 训练卖点特征模型
    print("\n🎓 步骤2: 训练卖点特征模型...")
    print("-" * 80)
    
    train_result = analyzer.train_sell_point_features()
    
    if train_result.get('success'):
        print("\n" + "=" * 80)
        print("✅ 卖点特征训练成功！")
        print("=" * 80)
        print(f"训练样本数: {train_result.get('sample_count', 0)}")
        print(f"特征数量: {len(train_result.get('common_features', {}))}")
        print(f"训练时间: {analyzer.trained_sell_features.get('trained_at', 'N/A')}")
        print(f"样本股票: {', '.join(analyzer.trained_sell_features.get('sample_stocks', []))}")
        
        # 显示部分特征统计
        common_features = train_result.get('common_features', {})
        if common_features:
            print("\n📊 部分卖点特征统计（前10个）:")
            print("-" * 80)
            count = 0
            for feature_name, stats in common_features.items():
                if count >= 10:
                    break
                print(f"  {feature_name}:")
                print(f"    均值: {stats.get('均值', 'N/A')}")
                print(f"    中位数: {stats.get('中位数', 'N/A')}")
                print(f"    范围: [{stats.get('最小值', 'N/A')}, {stats.get('最大值', 'N/A')}]")
                print(f"    标准差: {stats.get('标准差', 'N/A')}")
                print(f"    样本数: {stats.get('样本数', 'N/A')}")
                print()
                count += 1
        
        print("\n✅ 卖点特征模型已保存，可以在找买点时使用预测卖点功能")
    else:
        print(f"\n❌ 卖点特征训练失败: {train_result.get('message', '')}")
        return
    
    print("\n" + "=" * 80)
    print("训练完成！")
    print("=" * 80)

if __name__ == '__main__':
    train_sell_points()


