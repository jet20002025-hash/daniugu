#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
列出11只大牛股的买点
"""
import sys
sys.path.insert(0, '.')
from bull_stock_analyzer import BullStockAnalyzer
import json
from datetime import datetime

def list_11_stocks_buy_points():
    """列出11只大牛股的买点"""
    print("=" * 80)
    print("📋 列出11只大牛股的买点")
    print("=" * 80)
    
    # 11只大牛股列表
    training_stocks = [
        ('000592', '平潭发展'),
        ('002104', '恒宝股份'),
        ('002759', '天际股份'),
        ('300436', '广生堂'),
        ('301005', '超捷股份'),
        ('301232', '飞沃科技'),
        ('002788', '鹭燕医药'),
        ('603778', '国晟科技'),
        ('603122', '合富中国'),
        ('600343', '航天动力'),
        ('603216', '梦天家居'),
    ]
    
    # 创建分析器
    analyzer = BullStockAnalyzer(
        auto_load_default_stocks=False,
        auto_analyze_and_train=False
    )
    
    # 加载模型
    print("\n📦 加载训练好的模型...")
    if not analyzer.load_model('trained_model.json', skip_network=True):
        print("❌ 模型加载失败，请先训练模型")
        return
    
    print("✅ 模型加载成功")
    
    # 结果列表
    all_results = []
    
    print("\n" + "=" * 80)
    print("🔍 开始查找每只股票的买点...")
    print("=" * 80)
    
    for idx, (stock_code, stock_name) in enumerate(training_stocks, 1):
        print(f"\n[{idx}/11] {stock_code} {stock_name}")
        print("-" * 80)
        
        try:
            # 直接查找买点（简化逻辑：8周内涨幅300%）
            result = analyzer.find_buy_points(
                stock_code,
                tolerance=0.3,
                search_years=2,
                match_threshold=0.83,
                max_pullback=20.0
            )
            
            if result.get('success') and result.get('buy_points'):
                buy_points = result.get('buy_points', [])
                if len(buy_points) > 0:
                    best_buy_point = buy_points[0]  # 第一个就是最佳买点（按涨幅排序）
                    
                    print(f"  ✅ 找到买点:")
                    print(f"     日期: {best_buy_point.get('日期')}")
                    print(f"     价格: {best_buy_point.get('价格'):.2f} 元")
                    print(f"     区间涨幅: {best_buy_point.get('区间涨幅'):.2f}%")
                    print(f"     区间周数: {best_buy_point.get('区间周数')} 周")
                    print(f"     最高价: {best_buy_point.get('最高价'):.2f} 元 ({best_buy_point.get('最高价日期')})")
                    
                    all_results.append({
                        '股票代码': stock_code,
                        '股票名称': stock_name,
                        '最佳买点日期': best_buy_point.get('日期'),
                        '最佳买点价格': best_buy_point.get('价格'),
                        '区间涨幅': best_buy_point.get('区间涨幅'),
                        '区间周数': best_buy_point.get('区间周数'),
                        '最高价': best_buy_point.get('最高价'),
                        '最高价日期': best_buy_point.get('最高价日期'),
                        '买点总数': len(buy_points)
                    })
                else:
                    print(f"  ❌ 未找到符合条件的买点")
            else:
                print(f"  ❌ 未找到符合条件的买点: {result.get('message', '未知错误')}")
                all_results.append({
                    '股票代码': stock_code,
                    '股票名称': stock_name,
                    '最佳买点日期': '未找到',
                    '最佳买点价格': None,
                    '匹配度': None,
                    '区间涨幅': None,
                    '区间周数': None,
                    '最高价': None,
                    '最高价日期': None,
                    '回调阈值': None,
                    '买点总数': 0
                })
        except Exception as e:
            print(f"  ❌ 发生错误: {e}")
            import traceback
            traceback.print_exc()
            all_results.append({
                '股票代码': stock_code,
                '股票名称': stock_name,
                '最佳买点日期': f'错误: {str(e)[:50]}',
                '最佳买点价格': None,
                '匹配度': None,
                '区间涨幅': None,
                '区间周数': None,
                '最高价': None,
                '最高价日期': None,
                '回调阈值': None,
                '买点总数': 0
            })
    
    # 打印汇总
    print("\n" + "=" * 80)
    print("📊 11只大牛股买点汇总")
    print("=" * 80)
    
    print(f"\n{'序号':<4} {'股票代码':<8} {'股票名称':<12} {'最佳买点日期':<12} {'价格(元)':<10} {'区间涨幅':<10} {'区间周数':<8} {'最高价':<10}")
    print("-" * 90)
    
    for idx, result in enumerate(all_results, 1):
        code = result['股票代码']
        name = result['股票名称']
        date = result['最佳买点日期']
        price = f"{result['最佳买点价格']:.2f}" if result['最佳买点价格'] else "N/A"
        gain = f"{result['区间涨幅']:.2f}%" if result['区间涨幅'] else "N/A"
        weeks = f"{result['区间周数']}" if result['区间周数'] else "N/A"
        max_price = f"{result['最高价']:.2f}" if result['最高价'] else "N/A"
        
        print(f"{idx:<4} {code:<8} {name:<12} {date:<12} {price:<10} {gain:<10} {weeks:<8} {max_price:<10}")
    
    # 保存结果
    output_file = f"11_stocks_buy_points_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ 结果已保存到: {output_file}")
    
    # 统计
    success_count = sum(1 for r in all_results if r['最佳买点日期'] not in ['未找到'] and not str(r['最佳买点日期']).startswith('错误'))
    print(f"\n📈 统计: 成功找到买点 {success_count}/11 只股票")
    
    return all_results

if __name__ == '__main__':
    list_11_stocks_buy_points()
