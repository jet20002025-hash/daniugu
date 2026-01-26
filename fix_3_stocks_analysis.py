#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修复三只股票的最佳买点分析：002969嘉美包装、001331胜通能源、300986志特新材
"""
from bull_stock_analyzer import BullStockAnalyzer
import pandas as pd
from datetime import datetime

def fix_stocks_analysis():
    """重新分析并修复三只股票"""
    print("=" * 80)
    print("🔧 修复三只股票的最佳买点分析")
    print("=" * 80)
    
    stocks_to_fix = [
        ('002969', '嘉美包装'),
        ('001331', '胜通能源'),
        ('300986', '志特新材')
    ]
    
    # 创建分析器
    print("\n初始化分析器...")
    analyzer = BullStockAnalyzer(auto_load_default_stocks=False, auto_analyze_and_train=False)
    
    # 加载模型
    print("\n加载模型...")
    model_path = 'trained_model.json'
    analyzer.load_model(model_path, skip_network=True)
    
    # 确保这三只股票已添加
    for stock_code, stock_name in stocks_to_fix:
        existing = [s for s in analyzer.bull_stocks if s['代码'] == stock_code]
        if not existing:
            result = analyzer.add_bull_stock(stock_code)
            if result.get('success'):
                print(f"✅ 已添加: {stock_code} {stock_name}")
        else:
            print(f"✅ 已存在: {stock_code} {stock_name}")
    
    # 重新分析每只股票
    for stock_code, stock_name in stocks_to_fix:
        print("\n" + "=" * 80)
        print(f"📊 重新分析 {stock_name} ({stock_code})")
        print("=" * 80)
        
        # 清空之前的分析结果
        if stock_code in analyzer.analysis_results:
            del analyzer.analysis_results[stock_code]
            print(f"已清空 {stock_code} 之前的分析结果")
        
        # 获取周K线数据
        print(f"\n📈 获取周K线数据...")
        weekly_df = analyzer.fetcher.get_weekly_kline(stock_code, period="2y")
        if weekly_df is None or len(weekly_df) == 0:
            print(f"❌ 无法获取周K线数据")
            continue
        
        print(f"   - 总周数: {len(weekly_df)}")
        print(f"   - 数据日期范围: {weekly_df.iloc[0]['日期']} 至 {weekly_df.iloc[-1]['日期']}")
        
        # 显示所有数据（用于检查）
        print(f"\n📊 完整周K线数据:")
        print("-" * 100)
        print(f"{'索引':<6} {'日期':<12} {'收盘':<8} {'最高':<8} {'最低':<8} {'成交量':<15} {'涨跌幅':<8}")
        print("-" * 100)
        for i in range(len(weekly_df)):
            row = weekly_df.iloc[i]
            date = row['日期']
            close = row['收盘']
            high = row.get('最高', close)
            low = row.get('最低', close)
            volume = row.get('周成交量', row.get('成交量', 0))
            change_pct = row.get('涨跌幅', 0)
            print(f"{i:<6} {str(date):<12} {close:<8.2f} {high:<8.2f} {low:<8.2f} {volume:<15,.0f} {change_pct:<8.2f}%")
        
        # 分析股票
        print(f"\n开始分析 {stock_code} {stock_name}...")
        analysis_result = analyzer.analyze_bull_stock(stock_code)
        
        if not analysis_result.get('success'):
            print(f"❌ 分析失败: {analysis_result.get('message', '')}")
            continue
        
        interval = analysis_result.get('interval', {})
        start_idx = interval.get('起点索引')
        start_date = interval.get('起点日期')
        start_price = interval.get('起点价格')
        end_date = interval.get('终点日期')
        end_price = interval.get('终点价格')
        gain = interval.get('涨幅', 0)
        
        print(f"\n✅ 分析结果:")
        print(f"   - 起点日期: {start_date}")
        print(f"   - 起点价格: {start_price} 元")
        print(f"   - 起点索引: {start_idx}")
        print(f"   - 终点日期: {end_date}")
        print(f"   - 终点价格: {end_price} 元")
        print(f"   - 涨幅: {gain:.2f}%")
        
        # 验证日期是否合理（不能是未来日期）
        if start_date:
            try:
                start_date_obj = pd.to_datetime(start_date)
                today = datetime.now()
                if start_date_obj > today:
                    print(f"\n⚠️ 警告：起点日期 {start_date} 是未来日期，分析可能有误！")
                    print(f"   当前日期: {today.strftime('%Y-%m-%d')}")
                    print(f"   建议：检查数据或分析逻辑")
            except:
                pass
    
    # 保存更新后的模型
    print("\n" + "=" * 80)
    print("💾 保存更新后的模型...")
    analyzer.save_model('trained_model.json')
    print("✅ 模型已保存")
    
    print("\n" + "=" * 80)
    print("📊 修复完成")
    print("=" * 80)

if __name__ == '__main__':
    fix_stocks_analysis()
