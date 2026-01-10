#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查用户提供的大牛股是否符合要求
"""
from bull_stock_analyzer import BullStockAnalyzer

# 用户提供的大牛股代码
stock_codes = ['000592', '002104', '002759', '002969', '300436']

print("="*80)
print("检查大牛股是否符合要求（一个月内涨幅超过100%）")
print("="*80)

analyzer = BullStockAnalyzer()

results = {}
for code in stock_codes:
    print(f"\n检查股票: {code}")
    try:
        # 使用分析器的find_max_gain_interval方法
        result = analyzer.find_max_gain_interval(code, search_weeks=10, min_gain=100.0)
        
        if result.get('success') and result.get('interval'):
            interval = result['interval']
            gain = interval.get('涨幅', 0)
            weeks = interval.get('实际周数', 0)
            
            if gain >= 100.0:
                results[code] = {
                    'is_bull': True,
                    'gain': gain,
                    'weeks': weeks,
                    'start_date': interval.get('起点日期'),
                    'end_date': interval.get('终点日期'),
                    'start_price': interval.get('起点价格'),
                    'end_price': interval.get('终点价格')
                }
                print(f"✅ {code} 符合大牛股要求！涨幅: {gain:.2f}%，周数: {weeks}")
            else:
                results[code] = {
                    'is_bull': False,
                    'gain': gain,
                    'message': result.get('message', '')
                }
                print(f"❌ {code} 不符合大牛股要求，最大涨幅: {gain:.2f}%")
        else:
            max_gain = result.get('max_gain', 0)
            results[code] = {
                'is_bull': False,
                'gain': max_gain,
                'message': result.get('message', '未找到符合条件的区间')
            }
            print(f"❌ {code} 不符合大牛股要求: {result.get('message', '未找到符合条件的区间')}")
    except Exception as e:
        import traceback
        print(f"❌ 检查 {code} 时出错: {str(e)}")
        results[code] = {
            'is_bull': False,
            'error': str(e)
        }

# 汇总结果
print("\n" + "="*80)
print("检查结果汇总:")
print("="*80)

valid_bull_stocks = []
invalid_bull_stocks = []

for code, result in results.items():
    if result.get('is_bull'):
        valid_bull_stocks.append(code)
        print(f"\n✅ {code}: 符合大牛股要求")
        print(f"   涨幅: {result['gain']:.2f}%")
        print(f"   周数: {result['weeks']} 周")
        print(f"   起点: {result['start_date']} ({result['start_price']:.2f}元)")
        print(f"   终点: {result['end_date']} ({result['end_price']:.2f}元)")
    else:
        invalid_bull_stocks.append(code)
        print(f"\n❌ {code}: 不符合大牛股要求")
        if 'gain' in result:
            print(f"   最大涨幅: {result['gain']:.2f}%")
        if 'message' in result:
            print(f"   原因: {result['message']}")
        if 'error' in result:
            print(f"   错误: {result['error']}")

print(f"\n符合要求的股票: {len(valid_bull_stocks)} 只 - {', '.join(valid_bull_stocks) if valid_bull_stocks else '无'}")
print(f"不符合要求的股票: {len(invalid_bull_stocks)} 只 - {', '.join(invalid_bull_stocks) if invalid_bull_stocks else '无'}")

if invalid_bull_stocks:
    print(f"\n⚠️ 以下股票不符合大牛股要求: {', '.join(invalid_bull_stocks)}")
    print("   大牛股定义：在一个月内（约4-5周）涨幅必须超过100%（翻倍）")








