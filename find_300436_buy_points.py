#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
查找广生堂（300436）的最佳买点
"""
import sys
sys.path.insert(0, '.')
from bull_stock_analyzer import BullStockAnalyzer

def find_guangsheng_buy_points():
    """查找广生堂的最佳买点"""
    print("=" * 80)
    print("🔍 查找广生堂（300436）的最佳买点")
    print("=" * 80)
    
    # 创建分析器
    analyzer = BullStockAnalyzer(
        auto_load_default_stocks=False,
        auto_analyze_and_train=False
    )
    
    # 加载模型
    print("\n📦 加载训练好的模型...")
    if analyzer.load_model('trained_model.json', skip_network=True):
        print("✅ 模型加载成功")
        trained = analyzer.get_trained_features()
        if trained:
            print(f"   - 训练样本数: {trained.get('sample_count', 0)}")
            print(f"   - 特征数量: {len(trained.get('common_features', {}))}")
            print(f"   - 匹配度目标: {trained.get('min_match_score_target', 'N/A')}")
    else:
        print("❌ 模型加载失败，请先训练模型")
        return
    
    stock_code = '300436'
    stock_name = '广生堂'
    
    print(f"\n🔍 查找 {stock_code} {stock_name} 的历史买点...")
    print("=" * 80)
    
    # 查找买点（搜索最近2年的历史数据，匹配度阈值0.83）
    buy_points_result = analyzer.find_buy_points(
        stock_code,
        tolerance=0.3,
        search_years=2,  # 搜索最近2年
        match_threshold=0.83  # 匹配度阈值
    )
    
    if buy_points_result.get('success') and buy_points_result.get('buy_points'):
        buy_points = buy_points_result.get('buy_points', [])
        
        print(f"\n✅ 找到 {len(buy_points)} 个符合条件的买点：")
        print("=" * 80)
        
        # 按匹配度排序
        buy_points.sort(key=lambda x: x.get('匹配度', 0), reverse=True)
        
        # 显示前10个最佳买点
        for i, bp in enumerate(buy_points[:10], 1):
            print(f"\n【买点 {i}】")
            print(f"  日期: {bp.get('日期', 'N/A')}")
            print(f"  价格: {bp.get('价格', 0):.2f} 元")
            print(f"  匹配度: {bp.get('匹配度', 0):.3f}")
            
            # 显示核心特征匹配
            core_match = bp.get('核心特征匹配', {})
            if core_match:
                print(f"  核心特征匹配:")
                for feature, score in list(core_match.items())[:5]:  # 只显示前5个
                    print(f"    - {feature}: {score:.3f}")
            
            # 如果有涨幅信息
            if '涨幅' in bp:
                print(f"  涨幅: {bp.get('涨幅', 0):.2f}%")
    
    else:
        print(f"\n❌ 未找到符合条件的买点")
        print(f"   结果: {buy_points_result.get('message', '未知错误')}")
    
    print("\n" + "=" * 80)
    print("✅ 查找完成")
    print("=" * 80)

if __name__ == '__main__':
    find_guangsheng_buy_points()
