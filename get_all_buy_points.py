#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
获取所有9只大牛股的买点信息
"""
from bull_stock_analyzer import BullStockAnalyzer
import json

def get_all_buy_points():
    """获取所有9只大牛股的买点"""
    
    # 9只默认大牛股
    default_stocks = ['000592', '002104', '002759', '002969', '300436', '001331', '301005', '301232', '002788']
    
    print("=" * 80)
    print("📊 获取所有9只大牛股的买点信息")
    print("=" * 80)
    
    # 创建分析器（自动加载默认股票）
    analyzer = BullStockAnalyzer(auto_load_default_stocks=True)
    
    # 确保已训练特征模型
    if analyzer.trained_features is None or len(analyzer.trained_features.get('common_features', {})) == 0:
        print("\n🎓 训练特征模型...")
        # 先分析所有股票
        print("  分析所有股票...")
        for stock_code in default_stocks:
            print(f"    分析 {stock_code}...", end=" ", flush=True)
            result = analyzer.analyze_bull_stock(stock_code)
            if result.get('success'):
                print("✅")
            else:
                print(f"❌ {result.get('message', '')}")
        
        # 训练特征
        print("  训练特征...")
        train_result = analyzer.train_features()
        if not train_result.get('success'):
            print(f"❌ 训练失败: {train_result.get('message', '')}")
            return
        print(f"  ✅ 训练完成（特征数: {train_result.get('feature_count', 0)}）")
    
    print(f"\n✅ 特征模型已就绪（特征数: {len(analyzer.trained_features.get('common_features', {}))}）")
    
    # 获取每只股票的买点
    all_buy_points = {}
    match_threshold = 0.25  # 使用优化后的阈值
    
    print("\n🔍 开始查找买点...")
    print("=" * 80)
    
    for stock_code in default_stocks:
        print(f"\n📈 {stock_code}...", end=" ", flush=True)
        
        # 先使用标准阈值
        result = analyzer.find_buy_points(
            stock_code, 
            tolerance=0.3, 
            search_years=5, 
            match_threshold=match_threshold
        )
        
        # 如果没找到，且最高匹配度接近阈值，使用更低阈值重试
        if (not result.get('success') or len(result.get('buy_points', [])) == 0) and result.get('max_match_score', 0) > 0.2:
            max_match = result.get('max_match_score', 0)
            lower_threshold = max(0.2, max_match * 0.95)  # 使用最高匹配度的95%
            print(f" (最高匹配度: {max_match:.3f}, 降低阈值到 {lower_threshold:.3f} 重试...", end=" ", flush=True)
            result = analyzer.find_buy_points(
                stock_code, 
                tolerance=0.3, 
                search_years=5, 
                match_threshold=lower_threshold
            )
        
        if result.get('success') and len(result.get('buy_points', [])) > 0:
            buy_points = result.get('buy_points', [])
            print(f"✅ 找到 {len(buy_points)} 个买点")
            
            # 获取股票名称
            stock_name = stock_code
            for stock in analyzer.bull_stocks:
                if stock['代码'] == stock_code:
                    stock_name = stock.get('名称', stock_code)
                    break
            
            all_buy_points[stock_code] = {
                'stock_code': stock_code,
                'stock_name': stock_name,
                'buy_points_count': len(buy_points),
                'max_match_score': result.get('max_match_score', 0),
                'avg_match_score': result.get('avg_match_score', 0),
                'buy_points': buy_points,
                'statistics': result.get('statistics', {})
            }
        else:
            max_match = result.get('max_match_score', 0)
            print(f"❌ 未找到买点 (最高匹配度: {max_match:.3f})")
            all_buy_points[stock_code] = {
                'stock_code': stock_code,
                'stock_name': stock_code,
                'buy_points_count': 0,
                'max_match_score': max_match,
                'avg_match_score': result.get('avg_match_score', 0),
                'buy_points': [],
                'statistics': {}
            }
    
    # 汇总结果
    print("\n" + "=" * 80)
    print("📊 买点汇总结果")
    print("=" * 80)
    
    total_buy_points = 0
    total_best_buy_points = 0
    
    for stock_code, data in all_buy_points.items():
        buy_count = data['buy_points_count']
        max_match = data['max_match_score']
        best_count = data['statistics'].get('best_buy_points', 0)
        
        total_buy_points += buy_count
        total_best_buy_points += best_count
        
        status = "✅" if buy_count > 0 else "❌"
        print(f"{status} {stock_code}: {buy_count} 个买点 (最高匹配度: {max_match:.3f}, 最佳买点: {best_count})")
    
    print("\n" + "=" * 80)
    print(f"📈 总计: {total_buy_points} 个买点，其中 {total_best_buy_points} 个最佳买点（10周内翻倍）")
    print("=" * 80)
    
    # 保存到JSON文件
    output_file = 'all_buy_points.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(all_buy_points, f, ensure_ascii=False, indent=2, default=str)
    
    print(f"\n💾 买点数据已保存到: {output_file}")
    
    # 显示详细信息（前3只股票的前3个买点）
    print("\n" + "=" * 80)
    print("📋 买点详细信息（示例：前3只股票的前3个买点）")
    print("=" * 80)
    
    shown_count = 0
    for stock_code, data in list(all_buy_points.items())[:3]:
        if data['buy_points_count'] > 0:
            print(f"\n📈 {stock_code} - 共 {data['buy_points_count']} 个买点:")
            for i, bp in enumerate(data['buy_points'][:3], 1):
                print(f"  {i}. 日期: {bp.get('日期', 'N/A')}, 价格: {bp.get('价格', 0):.2f}, 匹配度: {bp.get('匹配度', 0):.3f}")
                print(f"     4周涨幅: {bp.get('买入后4周涨幅', 'N/A')}, 10周涨幅: {bp.get('买入后10周涨幅', 'N/A')}")
                print(f"     是否最佳买点: {'是' if bp.get('是否最佳买点', False) else '否'}")
            shown_count += 1
            if shown_count >= 3:
                break
    
    return all_buy_points

if __name__ == '__main__':
    get_all_buy_points()

