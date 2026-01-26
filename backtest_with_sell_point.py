#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
带卖点的回测脚本
规则：
1. 每周选择匹配度最高的1只股票
2. 买入后，监控是否涨停
3. 如果涨停，第二天如果没涨停，收盘价卖出
"""
from model_validator import ModelValidator
from data_fetcher import DataFetcher
from bull_stock_analyzer import BullStockAnalyzer
from datetime import datetime, timedelta
import pandas as pd
import time
import json

def check_limit_up(stock_code, date, fetcher):
    """
    检查指定日期是否涨停
    :param stock_code: 股票代码
    :param date: 日期（datetime.date）
    :param fetcher: DataFetcher实例
    :return: (是否涨停, 涨停限制百分比)
    """
    try:
        # 获取股票板块信息
        board_name, limit_up_pct = BullStockAnalyzer.get_stock_board_info(stock_code)
        
        # 获取日K线数据
        daily_df = fetcher.get_daily_kline(stock_code, period="1y")
        if daily_df is None or len(daily_df) == 0:
            return False, limit_up_pct
        
        # 确保日期列是datetime类型
        if '日期' not in daily_df.columns:
            return False, limit_up_pct
        
        daily_df['日期'] = pd.to_datetime(daily_df['日期'])
        daily_df['日期_date'] = daily_df['日期'].dt.date
        daily_df = daily_df.sort_values('日期').reset_index(drop=True)
        
        # 找到指定日期的数据
        day_data = daily_df[daily_df['日期_date'] == date]
        if len(day_data) == 0:
            return False, limit_up_pct
        
        # 获取涨跌幅
        if '涨跌幅' in day_data.columns:
            pct_change = day_data.iloc[0]['涨跌幅']
            # 判断是否涨停（考虑ST股是5%，其他是10%或20%）
            if limit_up_pct == 20.0:
                is_limit_up = pct_change >= 19.5  # 创业板/科创板
            elif limit_up_pct == 10.0:
                is_limit_up = pct_change >= 9.5   # 主板/中小板
            else:
                is_limit_up = pct_change >= (limit_up_pct - 0.5)
            
            return is_limit_up, limit_up_pct
        
        return False, limit_up_pct
    except Exception as e:
        print(f"      ⚠️ 检查涨停失败: {e}")
        return False, 10.0

def find_sell_point(stock_code, buy_date, buy_price, fetcher):
    """
    找到卖点：涨停后，第二天如果没涨停，收盘价卖出
    :param stock_code: 股票代码
    :param buy_date: 买入日期
    :param buy_price: 买入价格
    :param fetcher: DataFetcher实例
    :return: (卖出日期, 卖出价格, 持有天数, 收益率)
    """
    try:
        # 获取日K线数据
        daily_df = fetcher.get_daily_kline(stock_code, period="1y")
        if daily_df is None or len(daily_df) == 0:
            return None, None, None, None
        
        # 确保日期列是datetime类型
        if '日期' not in daily_df.columns:
            return None, None, None, None
        
        daily_df['日期'] = pd.to_datetime(daily_df['日期'])
        daily_df['日期_date'] = daily_df['日期'].dt.date
        daily_df = daily_df.sort_values('日期').reset_index(drop=True)
        
        # 找到买入日期在数据中的位置
        buy_idx = None
        for i in range(len(daily_df)):
            date_val = daily_df.iloc[i]['日期_date']
            # 确保date_val是date类型
            if isinstance(date_val, str):
                date_val = datetime.strptime(date_val, '%Y-%m-%d').date()
            elif isinstance(date_val, pd.Timestamp):
                date_val = date_val.date()
            # 确保buy_date是date类型
            if isinstance(buy_date, str):
                buy_date = datetime.strptime(buy_date, '%Y-%m-%d').date()
            
            if date_val >= buy_date:
                buy_idx = i
                break
        
        if buy_idx is None:
            return None, None, None, None
        
        # 从买入日期开始，逐日检查
        limit_up_date = None
        for i in range(buy_idx, len(daily_df)):
            current_date = daily_df.iloc[i]['日期_date']
            is_limit_up, limit_up_pct = check_limit_up(stock_code, current_date, fetcher)
            
            if is_limit_up:
                limit_up_date = current_date
                # 检查第二天是否涨停
                if i + 1 < len(daily_df):
                    next_date = daily_df.iloc[i + 1]['日期_date']
                    next_is_limit_up, _ = check_limit_up(stock_code, next_date, fetcher)
                    
                    if not next_is_limit_up:
                        # 第二天没涨停，卖出
                        sell_date = next_date
                        sell_data = daily_df.iloc[i + 1]
                        sell_price = sell_data['收盘']
                        hold_days = (sell_date - buy_date).days
                        gain = (sell_price - buy_price) / buy_price * 100
                        return sell_date, sell_price, hold_days, gain
        
        # 如果买入后一直没有涨停，或者涨停后第二天也涨停，则持有到最后
        # 这里可以设置一个最大持有天数，比如140天（20周）
        max_hold_days = 140
        end_date = buy_date + timedelta(days=max_hold_days)
        
        # 找到最接近end_date的交易日
        sell_idx = None
        for i in range(buy_idx, len(daily_df)):
            if daily_df.iloc[i]['日期_date'] > end_date:
                if i > buy_idx:
                    sell_idx = i - 1
                break
        
        if sell_idx is None:
            # 如果数据不够，使用最后一天
            sell_idx = len(daily_df) - 1
        
        sell_date = daily_df.iloc[sell_idx]['日期_date']
        sell_price = daily_df.iloc[sell_idx]['收盘']
        hold_days = (sell_date - buy_date).days
        gain = (sell_price - buy_price) / buy_price * 100
        
        return sell_date, sell_price, hold_days, gain
        
    except Exception as e:
        print(f"      ⚠️ 找卖点失败: {e}")
        import traceback
        traceback.print_exc()
        return None, None, None, None

def main():
    """主函数"""
    print("=" * 80)
    print("带卖点的回测验证（涨停后第二天卖出策略）")
    print("=" * 80)
    print()
    
    # 模型文件路径
    model_path = 'models/用户指定20只股票模型.json'
    
    import os
    if not os.path.exists(model_path):
        print(f"❌ 模型文件不存在: {model_path}")
        return
    
    print(f"📁 模型文件: {model_path}")
    print()
    
    # 创建验证器和数据获取器
    validator = ModelValidator(model_path=model_path)
    fetcher = DataFetcher()
    
    if not validator.analyzer.trained_features:
        print("❌ 模型加载失败")
        return
    
    # 设置回测参数
    print("📊 回测参数设置:")
    print("  - 时间范围: 2025-01-01 至 2025-12-31")
    print("  - 扫描模式: 每周扫描一次")
    print("  - 最小匹配度: 0.83")
    print("  - 最大市值: 100 亿元")
    print("  - 每周选择: 匹配度最高的1只股票")
    print("  - 卖点规则: 涨停后，第二天如果没涨停，收盘价卖出")
    print()
    
    # 回测时间范围：2025年
    start_date = '2025-01-01'
    end_date = '2025-12-31'
    
    # 运行回测
    print("🚀 开始回测...")
    print("   这可能需要较长时间，请耐心等待...")
    print()
    
    try:
        # 创建回测引擎
        from backtest_engine import BacktestEngine
        engine = BacktestEngine(validator.analyzer)
        
        # 运行基础回测，获取买入点
        backtest_result = engine.run_backtest(
            start_date=start_date,
            end_date=end_date,
            min_match_score=0.83,
            max_market_cap=100.0,
            scan_mode='weekly',
            max_stocks_per_day=1,  # 每周只选择1只
            periods=[7, 28, 56, 84, 140],
            limit=None,
            use_parallel=True,
            max_workers=10
        )
        
        print()
        print("=" * 80)
        print("开始计算卖点和收益...")
        print("=" * 80)
        print()
        
        # 处理每只股票的卖点
        results = []
        for result in backtest_result.get('results', []):
            date = result.get('date', '')
            stocks = result.get('stocks', [])
            
            if len(stocks) == 0:
                continue
            
            # 每周只取第一只（匹配度最高的）
            stock = stocks[0]
            if 'error' in stock:
                continue
            
            stock_code = stock.get('stock_code', '')
            stock_name = stock.get('stock_name', '')
            match_score = stock.get('match_score', 0)
            buy_price = stock.get('buy_price', 0)
            buy_date_str = stock.get('buy_date', date)
            
            try:
                buy_date = datetime.strptime(buy_date_str, '%Y-%m-%d').date()
            except:
                try:
                    buy_date = datetime.strptime(date, '%Y-%m-%d').date()
                except:
                    print(f"   ⚠️ 日期格式错误: {buy_date_str} 或 {date}")
                    continue
            
            # 确保buy_date是date类型
            if not isinstance(buy_date, datetime.date):
                if isinstance(buy_date, str):
                    buy_date = datetime.strptime(buy_date, '%Y-%m-%d').date()
                else:
                    print(f"   ⚠️ 买入日期类型错误: {type(buy_date)}")
                    continue
            
            print(f"📊 {date}: {stock_code} {stock_name} (匹配度: {match_score:.3f}, 买入价: {buy_price:.2f})")
            
            # 找卖点
            sell_date, sell_price, hold_days, gain = find_sell_point(
                stock_code, buy_date, buy_price, fetcher
            )
            
            if sell_date:
                results.append({
                    'scan_date': date,
                    'buy_date': buy_date_str,
                    'sell_date': sell_date.strftime('%Y-%m-%d'),
                    'stock_code': stock_code,
                    'stock_name': stock_name,
                    'match_score': match_score,
                    'buy_price': buy_price,
                    'sell_price': sell_price,
                    'hold_days': hold_days,
                    'gain': gain
                })
                print(f"   ✅ 卖出: {sell_date.strftime('%Y-%m-%d')}, 价格: {sell_price:.2f}, 持有: {hold_days}天, 收益: {gain:+.2f}%")
            else:
                print(f"   ⚠️ 无法找到卖点")
                results.append({
                    'scan_date': date,
                    'buy_date': buy_date_str,
                    'sell_date': None,
                    'stock_code': stock_code,
                    'stock_name': stock_name,
                    'match_score': match_score,
                    'buy_price': buy_price,
                    'sell_price': None,
                    'hold_days': None,
                    'gain': None,
                    'error': '无法找到卖点'
                })
        
        print()
        print("=" * 80)
        print("✅ 回测完成！")
        print("=" * 80)
        
        # 统计信息
        valid_results = [r for r in results if r.get('gain') is not None]
        if len(valid_results) > 0:
            gains = [r['gain'] for r in valid_results]
            avg_gain = sum(gains) / len(gains)
            max_gain = max(gains)
            min_gain = min(gains)
            positive_count = sum(1 for g in gains if g > 0)
            positive_rate = positive_count / len(gains) * 100
            
            hold_days_list = [r['hold_days'] for r in valid_results if r.get('hold_days')]
            avg_hold_days = sum(hold_days_list) / len(hold_days_list) if hold_days_list else 0
            
            print(f"\n📊 回测统计:")
            print(f"  总交易数: {len(results)}")
            print(f"  有效交易数: {len(valid_results)}")
            print(f"  平均收益: {avg_gain:.2f}%")
            print(f"  最大收益: {max_gain:.2f}%")
            print(f"  最小收益: {min_gain:.2f}%")
            print(f"  胜率: {positive_rate:.1f}% ({positive_count}/{len(valid_results)})")
            print(f"  平均持有天数: {avg_hold_days:.1f} 天")
        
        # 保存结果
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = f'backtest_with_sell_point_{timestamp}.json'
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump({
                'backtest_config': {
                    'start_date': start_date,
                    'end_date': end_date,
                    'scan_mode': 'weekly',
                    'min_match_score': 0.83,
                    'max_market_cap': 100.0,
                    'max_stocks_per_day': 1,
                    'sell_rule': '涨停后，第二天如果没涨停，收盘价卖出'
                },
                'statistics': {
                    'total_trades': len(results),
                    'valid_trades': len(valid_results),
                    'avg_gain': avg_gain if valid_results else None,
                    'max_gain': max_gain if valid_results else None,
                    'min_gain': min_gain if valid_results else None,
                    'positive_rate': positive_rate if valid_results else None,
                    'avg_hold_days': avg_hold_days if valid_results else None
                },
                'results': results
            }, f, ensure_ascii=False, indent=2)
        
        print(f"\n📄 结果已保存到: {output_file}")
            
    except KeyboardInterrupt:
        print("\n⚠️ 用户中断回测")
    except Exception as e:
        print(f"\n❌ 回测过程出错: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
