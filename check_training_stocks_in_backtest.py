#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查训练股票在回测中的匹配度
"""
import sys
sys.path.insert(0, '.')
from bull_stock_analyzer import BullStockAnalyzer
from datetime import datetime, timedelta
import pandas as pd

# 11只训练股票
TRAINING_STOCKS = {
    '000592': '平潭发展',
    '002104': '恒宝股份',
    '002759': '天际股份',
    '300436': '广生堂',
    '301005': '超捷股份',
    '301232': '飞沃科技',
    '002788': '鹭燕医药',
    '603778': '国晟科技',
    '603122': '合富中国',
    '600343': '航天动力',
    '603216': '梦天家居'
}

def check_training_stocks_in_backtest():
    """检查训练股票在回测中的匹配度"""
    print("=" * 80)
    print("📊 检查训练股票在回测中的匹配度")
    print("=" * 80)
    print()
    
    # 加载模型
    analyzer = BullStockAnalyzer(auto_load_default_stocks=False, auto_analyze_and_train=False)
    if not analyzer.load_model('models/模型11.json', skip_network=True):
        print("❌ 模型加载失败")
        return
    
    print("✅ 模型加载成功")
    print()
    
    # 回测日期范围：每周扫描一次
    start_date = datetime(2025, 1, 1).date()
    end_date = datetime(2025, 12, 31).date()
    
    # 生成每周的扫描日期（每周一）
    scan_dates = []
    current = start_date
    while current <= end_date:
        # 找到下一个周一
        days_until_monday = (7 - current.weekday()) % 7
        if days_until_monday == 0 and current.weekday() == 0:
            scan_dates.append(current)
        elif days_until_monday > 0:
            next_monday = current + timedelta(days=days_until_monday)
            if next_monday <= end_date:
                scan_dates.append(next_monday)
        current += timedelta(days=7)
    
    # 限制扫描日期数量（测试前10个）
    scan_dates = scan_dates[:10]
    
    print(f"测试日期范围: {scan_dates[0]} 至 {scan_dates[-1]} (共 {len(scan_dates)} 个扫描日期)")
    print()
    
    results = []
    
    for scan_date in scan_dates:
        scan_date_str = scan_date.strftime('%Y-%m-%d')
        print(f"📅 扫描日期: {scan_date_str}")
        
        for stock_code, stock_name in TRAINING_STOCKS.items():
            try:
                # 使用_process_single_stock方法测试匹配度
                result = analyzer._process_single_stock(
                    stock_code,
                    scan_date=scan_date_str,
                    min_match_score=0.83,
                    max_market_cap=100.0
                )
                
                if result:
                    match_score = result.get('匹配度', 0)
                    market_cap = result.get('市值', 'N/A')
                    buy_price = result.get('买点价格', 0)
                    
                    results.append({
                        '股票代码': stock_code,
                        '股票名称': stock_name,
                        '扫描日期': scan_date_str,
                        '匹配度': match_score,
                        '市值(亿)': market_cap,
                        '买点价格': buy_price,
                        '是否通过': '是' if match_score >= 0.83 else '否'
                    })
                    
                    if match_score >= 0.83:
                        print(f"  ✅ {stock_code} {stock_name}: 匹配度 {match_score:.3f}, 市值 {market_cap}")
                    else:
                        print(f"  ❌ {stock_code} {stock_name}: 匹配度 {match_score:.3f} (<0.83)")
                else:
                    results.append({
                        '股票代码': stock_code,
                        '股票名称': stock_name,
                        '扫描日期': scan_date_str,
                        '匹配度': 0,
                        '市值(亿)': 'N/A',
                        '买点价格': 0,
                        '是否通过': '否（未通过筛选）'
                    })
                    print(f"  ❌ {stock_code} {stock_name}: 未通过筛选")
            except Exception as e:
                print(f"  ⚠️ {stock_code} {stock_name}: 错误 - {e}")
                results.append({
                    '股票代码': stock_code,
                    '股票名称': stock_name,
                    '扫描日期': scan_date_str,
                    '匹配度': 0,
                    '市值(亿)': 'N/A',
                    '买点价格': 0,
                    '是否通过': f'错误: {str(e)[:50]}'
                })
        
        print()
    
    # 保存结果
    if results:
        df = pd.DataFrame(results)
        csv_file = 'training_stocks_backtest_check.csv'
        df.to_csv(csv_file, index=False, encoding='utf-8-sig')
        print("=" * 80)
        print("📊 统计摘要")
        print("=" * 80)
        print()
        
        # 按股票统计
        for stock_code, stock_name in TRAINING_STOCKS.items():
            stock_data = df[df['股票代码'] == stock_code]
            passed_count = len(stock_data[stock_data['是否通过'] == '是'])
            total_count = len(stock_data)
            
            if total_count > 0:
                avg_match = stock_data['匹配度'].mean()
                max_match = stock_data['匹配度'].max()
                min_match = stock_data['匹配度'].min()
                
                print(f"{stock_code} {stock_name}:")
                print(f"  通过次数: {passed_count}/{total_count}")
                print(f"  匹配度: 平均 {avg_match:.3f}, 最高 {max_match:.3f}, 最低 {min_match:.3f}")
                print()
        
        print(f"✅ 详细结果已保存到: {csv_file}")

if __name__ == '__main__':
    check_training_stocks_in_backtest()
