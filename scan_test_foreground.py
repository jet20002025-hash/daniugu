#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
前台扫描测试脚本
- 匹配度阈值: 1.0
- 最大市值: 100亿
- 扫描全市场
- 输出找到的个股名称和买点
"""
import sys
from bull_stock_analyzer import BullStockAnalyzer
import json

def main():
    print("=" * 80)
    print("全自动扫描测试（前台运行）")
    print("=" * 80)
    print("参数设置:")
    print("  - 匹配度阈值: 0.9")
    print("  - 最大市值: 100亿")
    print("  - 扫描范围: 全市场")
    print("=" * 80)
    print()
    
    # 创建分析器实例（自动加载默认大牛股，但不自动训练，因为我们要测试）
    print("📊 初始化分析器...")
    analyzer = BullStockAnalyzer(auto_load_default_stocks=True, auto_analyze_and_train=False)
    
    # 检查是否已训练特征模型
    if analyzer.trained_features is None:
        print("⚠️  特征模型未训练，开始训练...")
        print("   分析所有大牛股...")
        analyzer.analyze_all_bull_stocks()
        print("   训练特征模型...")
        analyzer.train_features()
        print("✅ 特征模型训练完成")
    else:
        print("✅ 特征模型已存在")
    
    print()
    print("=" * 80)
    print("开始扫描全市场...")
    print("=" * 80)
    print()
    
    # 执行扫描
    # 匹配度阈值: 1.0（用户要求）
    # 最大市值: 100亿
    # 不限制数量
    try:
        result = analyzer.scan_all_stocks(
            min_match_score=0.9,  # 匹配度阈值（与网页端一致）
            max_market_cap=100.0,  # 最大市值100亿
            limit=None  # 不限制数量，扫描全市场
        )
        
        print()
        print("=" * 80)
        print("扫描完成")
        print("=" * 80)
        
        if result.get('success'):
            candidates = result.get('candidates', [])
            total_scanned = result.get('total_scanned', 0)
            found_count = result.get('found_count', 0)
            
            print(f"📊 扫描统计:")
            print(f"   - 总扫描股票数: {total_scanned}")
            print(f"   - 找到符合条件的股票: {found_count} 只")
            print()
            
            if found_count > 0:
                print("=" * 80)
                print("找到的个股及买点:")
                print("=" * 80)
                print()
                
                # 按匹配度排序
                candidates_sorted = sorted(candidates, key=lambda x: x.get('匹配度', 0), reverse=True)
                
                for i, stock in enumerate(candidates_sorted, 1):
                    stock_code = stock.get('股票代码', 'N/A')
                    stock_name = stock.get('股票名称', 'N/A')
                    match_score = stock.get('匹配度', 0)
                    buy_date = stock.get('最佳买点日期', 'N/A')
                    buy_price = stock.get('最佳买点价格', 0)
                    current_price = stock.get('当前价格', 0)
                    market_cap = stock.get('市值', None)
                    
                    print(f"{i}. {stock_code} {stock_name}")
                    print(f"   匹配度: {match_score:.3f}")
                    print(f"   最佳买点日期: {buy_date}")
                    print(f"   最佳买点价格: {buy_price:.2f} 元")
                    print(f"   当前价格: {current_price:.2f} 元")
                    if market_cap:
                        print(f"   市值: {market_cap:.2f} 亿元")
                    print()
            else:
                print("⚠️  未找到符合条件的股票")
                print("   提示: 匹配度阈值设置为0.9，如果仍未找到，可以进一步降低到0.8")
        else:
            print(f"❌ 扫描失败: {result.get('message', '未知错误')}")
            
    except KeyboardInterrupt:
        print("\n\n⚠️  扫描被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 扫描过程出错: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    print("=" * 80)
    print("测试完成")
    print("=" * 80)

if __name__ == '__main__':
    main()

