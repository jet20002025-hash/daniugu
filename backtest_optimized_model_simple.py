#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
使用优化后的模型运行回测，只找出匹配度最高的5只个股，不计算收益
"""
import sys
sys.path.insert(0, '.')
from bull_stock_analyzer import BullStockAnalyzer
from model_validator import ModelValidator
from datetime import datetime, timedelta
import pandas as pd
import json

def run_simple_backtest():
    """运行简化回测，只找出匹配度最高的5只个股"""
    print("=" * 80)
    print("📊 使用优化模型运行回测（只找匹配度最高的5只个股）")
    print("=" * 80)
    print()
    
    # 加载优化后的模型
    analyzer = BullStockAnalyzer(auto_load_default_stocks=False, auto_analyze_and_train=False)
    if not analyzer.load_model('models/模型11_优化_v2.json', skip_network=True):
        print("❌ 模型加载失败")
        return
    
    print("✅ 优化模型加载成功")
    print()
    
    # 回测日期范围
    start_date = datetime(2025, 1, 1).date()
    end_date = datetime(2025, 12, 31).date()
    
    print(f"回测时间范围: {start_date} 至 {end_date}")
    print(f"扫描模式: 每周扫描")
    print(f"每次选择: 匹配度最高的5只股票")
    print(f"匹配度阈值: 0.8")
    print(f"市值上限: 100.0 亿元")
    print()
    print("开始扫描...")
    print()
    
    # 获取交易日列表（用于确定每周扫描日期）
    from backtest_engine import BacktestEngine
    engine = BacktestEngine(analyzer)
    all_trading_days = engine.get_trading_days(start_date, end_date)
    
    # 每周选择第一个交易日
    scan_dates = []
    current_week = None
    for day in all_trading_days:
        week_num = day.isocalendar()[1]
        year = day.year
        week_key = (year, week_num)
        if week_key != current_week:
            scan_dates.append(day)
            current_week = week_key
    
    print(f"✅ 需要扫描 {len(scan_dates)} 个日期")
    print()
    
    # 存储结果
    all_selected_stocks = []
    results = []
    
    # 遍历每个扫描日期
    for idx, scan_date in enumerate(scan_dates, 1):
        scan_date_str = scan_date.strftime('%Y-%m-%d')
        print(f"[{idx}/{len(scan_dates)}] 扫描日期: {scan_date_str}")
        
        try:
            # 使用指定日期进行扫描
            scan_result = analyzer.scan_all_stocks(
                min_match_score=0.8,
                max_market_cap=100.0,
                limit=None,
                use_parallel=True,
                max_workers=10,
                scan_date=scan_date_str
            )
            
            if not scan_result.get('success'):
                print(f"   ⚠️ 扫描失败: {scan_result.get('message', '未知错误')}")
                results.append({
                    'date': scan_date_str,
                    'stocks': [],
                    'error': scan_result.get('message', '扫描失败')
                })
                continue
            
            candidates = scan_result.get('candidates', [])
            
            if len(candidates) == 0:
                print(f"   ⚠️ 未找到符合条件的股票")
                results.append({
                    'date': scan_date_str,
                    'stocks': []
                })
                continue
            
            # 按匹配度排序，选择前5只
            candidates_sorted = sorted(candidates, key=lambda x: x.get('匹配度', 0), reverse=True)
            selected_stocks = candidates_sorted[:5]
            
            print(f"   ✅ 找到 {len(candidates)} 只候选股票，选择匹配度最高的 {len(selected_stocks)} 只")
            
            day_results = []
            for stock in selected_stocks:
                stock_code = stock.get('股票代码', '')
                stock_name = stock.get('股票名称', '')
                match_score = stock.get('匹配度', 0)
                market_cap = stock.get('市值', 'N/A')
                buy_price = stock.get('买点价格', 0)
                
                print(f"      📊 {stock_code} {stock_name} (匹配度: {match_score:.3f}, 市值: {market_cap})")
                
                day_results.append({
                    'stock_code': stock_code,
                    'stock_name': stock_name,
                    'match_score': match_score,
                    'market_cap': market_cap,
                    'buy_price': buy_price,
                    'buy_date': scan_date_str
                })
                
                all_selected_stocks.append({
                    '股票代码': stock_code,
                    '股票名称': stock_name,
                    '扫描日期': scan_date_str,
                    '匹配度': match_score,
                    '市值(亿)': market_cap,
                    '买点价格': buy_price
                })
            
            results.append({
                'date': scan_date_str,
                'stocks': day_results
            })
            
        except Exception as e:
            print(f"   ❌ 处理失败: {e}")
            results.append({
                'date': scan_date_str,
                'stocks': [],
                'error': str(e)
            })
        
        print()
    
    # 构建结果
    result = {
        'success': True,
        'statistics': {
            'total_days': len(scan_dates),
            'days_with_stocks': len([r for r in results if len(r.get('stocks', [])) > 0]),
            'valid_stocks': len(all_selected_stocks)
        },
        'detailed_results': results
    }
    
    if result.get('success'):
        print()
        print("=" * 80)
        print("✅ 回测完成")
        print("=" * 80)
        print()
        
        # 统计信息
        stats = result.get('statistics', {})
        print(f"📊 回测统计:")
        print(f"  总扫描次数: {stats.get('total_days', 0)}")
        print(f"  有效股票数: {stats.get('valid_stocks', 0)}")
        print()
        
        # 提取所有选中的股票
        all_selected_stocks = []
        if 'detailed_results' in result:
            for day_result in result['detailed_results']:
                scan_date = day_result.get('date', '')
                if 'stocks' in day_result:
                    for stock in day_result['stocks']:
                        all_selected_stocks.append({
                            '股票代码': stock.get('stock_code', ''),
                            '股票名称': stock.get('stock_name', ''),
                            '扫描日期': scan_date,
                            '匹配度': stock.get('match_score', 0),
                            '市值(亿)': stock.get('market_cap', 'N/A')
                        })
        
        if all_selected_stocks:
            df = pd.DataFrame(all_selected_stocks)
            
            # 保存详细列表
            csv_file = 'backtest_optimized_v2_all_stocks.csv'
            df.to_csv(csv_file, index=False, encoding='utf-8-sig')
            print(f"✅ 详细列表已保存到: {csv_file}")
            print()
            
            # 统计每只股票被选中的次数
            stock_counts = df.groupby(['股票代码', '股票名称']).size().reset_index(name='选中次数')
            stock_counts = stock_counts.sort_values('选中次数', ascending=False)
            
            print("=" * 80)
            print("📊 选中的股票统计（按选中次数排序）")
            print("=" * 80)
            print()
            
            for idx, row in stock_counts.iterrows():
                print(f"{idx+1:3d}. {row['股票代码']} {row['股票名称']:15s} - 被选中 {row['选中次数']:2d} 次")
            
            print()
            print(f"总计: {len(stock_counts)} 只不同的股票")
            print(f"总选中次数: {stock_counts['选中次数'].sum()} 次")
            print()
            
            # 保存统计结果
            stats_file = 'backtest_optimized_v2_stock_counts.csv'
            stock_counts.to_csv(stats_file, index=False, encoding='utf-8-sig')
            print(f"✅ 统计结果已保存到: {stats_file}")
            
            # 显示每周选中的股票（前10周）
            print()
            print("=" * 80)
            print("📅 每周选中的股票（前10周）")
            print("=" * 80)
            print()
            
            scan_dates = sorted(df['扫描日期'].unique())[:10]
            for scan_date in scan_dates:
                week_stocks = df[df['扫描日期'] == scan_date].sort_values('匹配度', ascending=False)
                print(f"{scan_date}:")
                for idx, stock in week_stocks.iterrows():
                    print(f"  {stock['股票代码']} {stock['股票名称']:15s} - 匹配度 {stock['匹配度']:.3f}, 市值 {stock['市值(亿)']}")
                print()
        else:
            print("⚠️ 未找到任何选中的股票")
        
        print()
        print(f"📄 详细报告已保存到:")
        print(f"  - {result.get('text_report_path', 'N/A')}")
        print(f"  - {result.get('json_report_path', 'N/A')}")
    else:
        print(f"❌ 回测失败: {result.get('message', '未知错误')}")

if __name__ == '__main__':
    try:
        run_simple_backtest()
    except KeyboardInterrupt:
        print("\n⚠️ 用户中断")
    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
        import traceback
        traceback.print_exc()
