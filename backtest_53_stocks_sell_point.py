#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
对53只股票进行卖点回测
卖点规则：涨停后，第二天如果没涨停，收盘价卖出
"""
from data_fetcher import DataFetcher
from bull_stock_analyzer import BullStockAnalyzer
from datetime import datetime, timedelta
import pandas as pd
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
    :return: (卖出日期, 卖出价格, 持有天数, 收益率, 是否触发涨停卖出)
    """
    try:
        # 获取日K线数据
        daily_df = fetcher.get_daily_kline(stock_code, period="1y")
        if daily_df is None or len(daily_df) == 0:
            return None, None, None, None, False
        
        # 确保日期列是datetime类型
        if '日期' not in daily_df.columns:
            return None, None, None, None, False
        
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
            return None, None, None, None, False
        
        # 从买入日期开始，逐日检查
        limit_up_date = None
        for i in range(buy_idx, len(daily_df)):
            current_date = daily_df.iloc[i]['日期_date']
            if isinstance(current_date, pd.Timestamp):
                current_date = current_date.date()
            
            is_limit_up, limit_up_pct = check_limit_up(stock_code, current_date, fetcher)
            
            if is_limit_up:
                limit_up_date = current_date
                # 检查第二天是否涨停
                if i + 1 < len(daily_df):
                    next_date = daily_df.iloc[i + 1]['日期_date']
                    if isinstance(next_date, pd.Timestamp):
                        next_date = next_date.date()
                    next_is_limit_up, _ = check_limit_up(stock_code, next_date, fetcher)
                    
                    if not next_is_limit_up:
                        # 第二天没涨停，卖出
                        sell_date = next_date
                        sell_data = daily_df.iloc[i + 1]
                        sell_price = sell_data['收盘']
                        hold_days = (sell_date - buy_date).days
                        gain = (sell_price - buy_price) / buy_price * 100
                        return sell_date, sell_price, hold_days, gain, True
        
        # 如果买入后一直没有涨停，或者涨停后第二天也涨停，则持有到最后
        # 设置一个最大持有天数，比如140天（20周）
        max_hold_days = 140
        end_date = buy_date + timedelta(days=max_hold_days)
        
        # 找到最接近end_date的交易日
        sell_idx = None
        for i in range(buy_idx, len(daily_df)):
            date_val = daily_df.iloc[i]['日期_date']
            if isinstance(date_val, pd.Timestamp):
                date_val = date_val.date()
            if date_val > end_date:
                if i > buy_idx:
                    sell_idx = i - 1
                break
        
        if sell_idx is None:
            # 如果数据不够，使用最后一天
            sell_idx = len(daily_df) - 1
        
        sell_date = daily_df.iloc[sell_idx]['日期_date']
        if isinstance(sell_date, pd.Timestamp):
            sell_date = sell_date.date()
        sell_price = daily_df.iloc[sell_idx]['收盘']
        hold_days = (sell_date - buy_date).days
        gain = (sell_price - buy_price) / buy_price * 100
        
        return sell_date, sell_price, hold_days, gain, False
        
    except Exception as e:
        print(f"      ⚠️ 找卖点失败: {e}")
        import traceback
        traceback.print_exc()
        return None, None, None, None, False

def main():
    """主函数"""
    print("=" * 80)
    print("53只股票卖点回测（涨停后第二天卖出策略）")
    print("=" * 80)
    print()
    
    # 读取之前的回测结果
    json_file = 'backtest_20_stocks_model_20260117_081505.json'
    
    import os
    if not os.path.exists(json_file):
        print(f"❌ 回测结果文件不存在: {json_file}")
        return
    
    print(f"📁 读取回测结果: {json_file}")
    
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # 提取所有交易记录，每周只取匹配度最高的1只
    results = data.get('detailed_results', [])
    stocks = []
    
    for result in results:
        date = result.get('date', '')
        stocks_list = result.get('stocks', [])
        
        if len(stocks_list) == 0:
            continue
        
        # 每周只取第一只（匹配度最高的）
        stock = stocks_list[0]
        if 'error' in stock:
            continue
        
        stocks.append({
            'scan_date': date,
            'buy_date': stock.get('buy_date', date),
            'stock_code': stock.get('stock_code', ''),
            'stock_name': stock.get('stock_name', ''),
            'match_score': stock.get('match_score', 0),
            'buy_price': stock.get('buy_price', 0)
        })
    
    print(f"✅ 找到 {len(stocks)} 只股票")
    print()
    
    # 创建数据获取器
    fetcher = DataFetcher()
    
    print("=" * 80)
    print("开始计算卖点和收益...")
    print("=" * 80)
    print()
    
    try:
        # 处理每只股票的卖点
        backtest_results = []
        for idx, stock in enumerate(stocks, 1):
            stock_code = stock['stock_code']
            stock_name = stock['stock_name']
            match_score = stock['match_score']
            buy_price = stock['buy_price']
            buy_date_str = stock['buy_date']
            scan_date = stock['scan_date']
            
            try:
                buy_date = datetime.strptime(buy_date_str, '%Y-%m-%d').date()
            except:
                try:
                    buy_date = datetime.strptime(scan_date, '%Y-%m-%d').date()
                except:
                    print(f"   ⚠️ [{idx}/{len(stocks)}] 日期格式错误: {buy_date_str} 或 {scan_date}")
                    continue
            
            print(f"[{idx}/{len(stocks)}] {scan_date}: {stock_code} {stock_name} (匹配度: {match_score:.3f}, 买入价: {buy_price:.2f})")
            
            # 找卖点
            sell_date, sell_price, hold_days, gain, triggered_by_limit_up = find_sell_point(
                stock_code, buy_date, buy_price, fetcher
            )
            
            if sell_date:
                backtest_results.append({
                    'scan_date': scan_date,
                    'buy_date': buy_date_str,
                    'sell_date': sell_date.strftime('%Y-%m-%d'),
                    'stock_code': stock_code,
                    'stock_name': stock_name,
                    'match_score': match_score,
                    'buy_price': buy_price,
                    'sell_price': sell_price,
                    'hold_days': hold_days,
                    'gain': gain,
                    'triggered_by_limit_up': triggered_by_limit_up
                })
                trigger_msg = "（涨停触发）" if triggered_by_limit_up else "（持有到期）"
                print(f"   ✅ 卖出: {sell_date.strftime('%Y-%m-%d')}, 价格: {sell_price:.2f}, 持有: {hold_days}天, 收益: {gain:+.2f}% {trigger_msg}")
            else:
                print(f"   ⚠️ 无法找到卖点")
                backtest_results.append({
                    'scan_date': scan_date,
                    'buy_date': buy_date_str,
                    'sell_date': None,
                    'stock_code': stock_code,
                    'stock_name': stock_name,
                    'match_score': match_score,
                    'buy_price': buy_price,
                    'sell_price': None,
                    'hold_days': None,
                    'gain': None,
                    'triggered_by_limit_up': False,
                    'error': '无法找到卖点'
                })
        
        print()
        print("=" * 80)
        print("✅ 回测完成！")
        print("=" * 80)
        
        # 统计信息
        valid_results = [r for r in backtest_results if r.get('gain') is not None]
        if len(valid_results) > 0:
            gains = [r['gain'] for r in valid_results]
            avg_gain = sum(gains) / len(gains)
            max_gain = max(gains)
            min_gain = min(gains)
            positive_count = sum(1 for g in gains if g > 0)
            positive_rate = positive_count / len(gains) * 100
            
            hold_days_list = [r['hold_days'] for r in valid_results if r.get('hold_days')]
            avg_hold_days = sum(hold_days_list) / len(hold_days_list) if hold_days_list else 0
            
            # 涨停触发的统计
            limit_up_triggered = [r for r in valid_results if r.get('triggered_by_limit_up')]
            limit_up_count = len(limit_up_triggered)
            limit_up_rate = limit_up_count / len(valid_results) * 100 if valid_results else 0
            
            if limit_up_count > 0:
                limit_up_gains = [r['gain'] for r in limit_up_triggered]
                avg_limit_up_gain = sum(limit_up_gains) / len(limit_up_gains)
            else:
                avg_limit_up_gain = 0
            
            print(f"\n📊 回测统计:")
            print(f"  总交易数: {len(backtest_results)}")
            print(f"  有效交易数: {len(valid_results)}")
            print(f"  平均收益: {avg_gain:.2f}%")
            print(f"  最大收益: {max_gain:.2f}%")
            print(f"  最小收益: {min_gain:.2f}%")
            print(f"  胜率: {positive_rate:.1f}% ({positive_count}/{len(valid_results)})")
            print(f"  平均持有天数: {avg_hold_days:.1f} 天")
            print(f"\n📈 涨停触发统计:")
            print(f"  涨停触发次数: {limit_up_count} ({limit_up_rate:.1f}%)")
            if limit_up_count > 0:
                print(f"  涨停触发平均收益: {avg_limit_up_gain:.2f}%")
        
        # 保存结果
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = f'backtest_53_stocks_sell_point_{timestamp}.json'
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump({
                'backtest_config': {
                    'source_file': json_file,
                    'total_stocks': len(stocks),
                    'sell_rule': '涨停后，第二天如果没涨停，收盘价卖出'
                },
                'statistics': {
                    'total_trades': len(backtest_results),
                    'valid_trades': len(valid_results),
                    'avg_gain': avg_gain if valid_results else None,
                    'max_gain': max_gain if valid_results else None,
                    'min_gain': min_gain if valid_results else None,
                    'positive_rate': positive_rate if valid_results else None,
                    'avg_hold_days': avg_hold_days if valid_results else None,
                    'limit_up_triggered_count': limit_up_count if valid_results else 0,
                    'limit_up_triggered_rate': limit_up_rate if valid_results else 0,
                    'avg_limit_up_gain': avg_limit_up_gain if valid_results else 0
                },
                'results': backtest_results
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
