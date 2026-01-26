#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
查找11只训练样本股票的最佳买点时间
"""
import sys
sys.path.insert(0, '.')
from bull_stock_analyzer import BullStockAnalyzer
import json
from datetime import datetime

def find_best_buy_points_for_training_stocks():
    """查找11只训练样本股票的最佳买点"""
    print("=" * 80)
    print("🔍 查找11只训练样本股票的最佳买点时间")
    print("=" * 80)
    
    # 11只训练样本股票
    training_stocks = [
        '000592',  # 平潭发展
        '002104',  # 恒宝股份
        '002759',  # 天际股份
        '300436',  # 广生堂
        '301005',  # 超捷股份
        '301232',  # 飞沃科技
        '002788',  # 鹭燕医药
        '603778',  # 国晟科技
        '603122',  # 合富中国
        '600343',  # 航天动力
        '603216',  # 梦天家居
    ]
    
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
    
    # 获取股票名称
    print("\n📊 获取股票名称...")
    all_stocks = analyzer.fetcher.get_all_stocks()
    stock_names = {}
    if all_stocks is not None and len(all_stocks) > 0:
        for _, row in all_stocks.iterrows():
            code = str(row.get('code', '')).zfill(6)
            name = row.get('name', '')
            if code in training_stocks:
                stock_names[code] = name
    
    print("\n" + "=" * 80)
    print("🔍 开始查找每只股票的最佳买点...")
    print("=" * 80)
    
    results = []
    
    for idx, stock_code in enumerate(training_stocks, 1):
        stock_name = stock_names.get(stock_code, stock_code)
        print(f"\n[{idx}/11] 查找 {stock_code} {stock_name} 的最佳买点...")
        print("-" * 80)
        
        try:
            # 查找买点（搜索最近2年的历史数据，匹配度阈值0.83）
            buy_points_result = analyzer.find_buy_points(
                stock_code,
                tolerance=0.3,
                search_years=2,  # 搜索最近2年
                match_threshold=0.83  # 匹配度阈值
            )
            
            if buy_points_result.get('success') and buy_points_result.get('buy_points'):
                buy_points = buy_points_result.get('buy_points', [])
                
                if len(buy_points) > 0:
                    # 按匹配度排序，取最高
                    buy_points.sort(key=lambda x: x.get('匹配度', 0), reverse=True)
                    best_buy_point = buy_points[0]
                    
                    buy_date = best_buy_point.get('日期', 'N/A')
                    buy_price = best_buy_point.get('价格', 0)
                    match_score = best_buy_point.get('匹配度', 0)
                    
                    print(f"  ✅ 找到最佳买点:")
                    print(f"     日期: {buy_date}")
                    print(f"     价格: {buy_price:.2f} 元")
                    print(f"     匹配度: {match_score:.3f}")
                    print(f"     找到 {len(buy_points)} 个符合条件的买点")
                    
                    results.append({
                        '股票代码': stock_code,
                        '股票名称': stock_name,
                        '最佳买点日期': buy_date,
                        '最佳买点价格': round(buy_price, 2),
                        '匹配度': round(match_score, 3),
                        '买点总数': len(buy_points)
                    })
                else:
                    print(f"  ⚠️ 未找到符合条件的买点")
                    results.append({
                        '股票代码': stock_code,
                        '股票名称': stock_name,
                        '最佳买点日期': '未找到',
                        '最佳买点价格': None,
                        '匹配度': None,
                        '买点总数': 0
                    })
            else:
                print(f"  ❌ 查找失败: {buy_points_result.get('message', '未知错误')}")
                results.append({
                    '股票代码': stock_code,
                    '股票名称': stock_name,
                    '最佳买点日期': '查找失败',
                    '最佳买点价格': None,
                    '匹配度': None,
                    '买点总数': 0
                })
        except Exception as e:
            print(f"  ❌ 发生错误: {e}")
            results.append({
                '股票代码': stock_code,
                '股票名称': stock_name,
                '最佳买点日期': f'错误: {str(e)}',
                '最佳买点价格': None,
                '匹配度': None,
                '买点总数': 0
            })
    
    # 汇总结果
    print("\n" + "=" * 80)
    print("📊 11只训练样本股票的最佳买点汇总")
    print("=" * 80)
    
    print(f"\n{'序号':<4} {'股票代码':<8} {'股票名称':<12} {'最佳买点日期':<12} {'价格(元)':<10} {'匹配度':<8} {'买点总数':<8}")
    print("-" * 80)
    
    for idx, result in enumerate(results, 1):
        code = result['股票代码']
        name = result['股票名称']
        date = result['最佳买点日期']
        price = f"{result['最佳买点价格']:.2f}" if result['最佳买点价格'] else "N/A"
        match = f"{result['匹配度']:.3f}" if result['匹配度'] else "N/A"
        count = result['买点总数']
        
        print(f"{idx:<4} {code:<8} {name:<12} {date:<12} {price:<10} {match:<8} {count:<8}")
    
    # 保存结果到JSON文件
    output_file = f"training_stocks_best_buy_points_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ 结果已保存到: {output_file}")
    
    # 统计信息
    success_count = sum(1 for r in results if r['最佳买点日期'] not in ['未找到', '查找失败'] and not r['最佳买点日期'].startswith('错误'))
    avg_match = sum(r['匹配度'] for r in results if r['匹配度'] is not None) / max(1, sum(1 for r in results if r['匹配度'] is not None))
    total_buy_points = sum(r['买点总数'] for r in results)
    
    print(f"\n📈 统计信息:")
    print(f"   - 成功找到买点: {success_count}/11 只股票")
    print(f"   - 平均匹配度: {avg_match:.3f}")
    print(f"   - 总买点数: {total_buy_points} 个")
    
    print("\n" + "=" * 80)
    print("✅ 查找完成")
    print("=" * 80)
    
    return results

if __name__ == '__main__':
    find_best_buy_points_for_training_stocks()
