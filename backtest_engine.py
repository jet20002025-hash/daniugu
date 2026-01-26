#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
回测引擎模块
提供历史回测的核心功能
"""
from bull_stock_analyzer import BullStockAnalyzer
from data_fetcher import DataFetcher
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import time


class BacktestEngine:
    """回测引擎类"""
    
    def __init__(self, analyzer: BullStockAnalyzer):
        """
        初始化回测引擎
        :param analyzer: BullStockAnalyzer实例，必须已加载模型
        """
        self.analyzer = analyzer
        self.fetcher = DataFetcher()
        
        # 验证模型是否已加载
        if not analyzer.trained_features or not analyzer.trained_features.get('common_features'):
            raise ValueError("模型未加载，请先加载模型后再进行回测")
    
    def get_trading_days(self, start_date: datetime.date, end_date: datetime.date) -> List[datetime.date]:
        """
        获取指定日期范围内的所有交易日
        :param start_date: 开始日期
        :param end_date: 结束日期
        :return: 交易日列表
        """
        # 获取一只股票的日K线数据，通过日期列来获取交易日
        daily_df = self.fetcher.get_daily_kline('000001', period="1y")
        if daily_df is None or len(daily_df) == 0:
            print("⚠️ 无法获取交易日历，使用所有工作日")
            # 备用方案：生成所有工作日
            trading_days = []
            current = start_date
            while current <= end_date:
                # 排除周末
                if current.weekday() < 5:  # 0-4 是周一到周五
                    trading_days.append(current)
                current += timedelta(days=1)
            return trading_days
        
        # 从日K线数据中提取日期
        if '日期' in daily_df.columns:
            daily_df['日期'] = pd.to_datetime(daily_df['日期'])
            daily_df['日期_date'] = daily_df['日期'].dt.date
            # 确保日期列是date类型，筛选日期范围
            trading_days = []
            for date_val in daily_df['日期_date'].unique():
                # 确保date_val是date类型
                if isinstance(date_val, str):
                    date_val = datetime.strptime(date_val, '%Y-%m-%d').date()
                elif hasattr(date_val, 'date') and not isinstance(date_val, datetime.date):
                    date_val = date_val.date()
                # 确保是date类型后再比较
                from datetime import date as date_type
                if isinstance(date_val, date_type) and start_date <= date_val <= end_date:
                    trading_days.append(date_val)
            trading_days.sort()
            return trading_days
        else:
            print("⚠️ 日K线数据中没有日期列")
            return []
    
    def calculate_gain_after_periods(
        self, 
        stock_code: str, 
        buy_date: datetime.date, 
        periods: List[int] = [14, 28, 56, 84, 140]
    ) -> Dict:
        """
        计算股票从买入日期到多个周期后的涨幅
        :param stock_code: 股票代码
        :param buy_date: 买入日期
        :param periods: 周期列表（天数），默认[14, 28, 56, 84, 140]对应2周、4周、8周、12周、20周
        :return: 包含各周期涨幅的字典
        """
        # 获取日K线数据
        daily_df = self.fetcher.get_daily_kline(stock_code, period="1y")
        if daily_df is None or len(daily_df) == 0:
            return None
        
        # 确保日期列是datetime类型
        if '日期' not in daily_df.columns:
            return None
        
        daily_df['日期'] = pd.to_datetime(daily_df['日期'])
        daily_df['日期_date'] = daily_df['日期'].dt.date
        daily_df = daily_df.sort_values('日期').reset_index(drop=True)
        
        # 找到买入日期当天的数据
        buy_data = daily_df[daily_df['日期_date'] == buy_date]
        if len(buy_data) == 0:
            # 如果买入日期没有数据，找最近的一个交易日
            buy_data = daily_df[daily_df['日期_date'] <= buy_date]
            if len(buy_data) == 0:
                return None
            buy_data = buy_data.iloc[-1:]
        
        buy_price = float(buy_data.iloc[0]['收盘'])
        buy_idx = buy_data.index[0]
        actual_buy_date = buy_data.iloc[0]['日期_date']
        
        # 计算各周期的涨幅
        results = {
            'buy_price': buy_price,
            'buy_date': actual_buy_date.strftime('%Y-%m-%d'),
            'periods': {}
        }
        
        for days in periods:
            # 找到N天后的数据
            target_date = actual_buy_date + timedelta(days=days)
            end_data = daily_df[
                (daily_df['日期_date'] > actual_buy_date) & 
                (daily_df['日期_date'] <= target_date)
            ]
            
            if len(end_data) == 0:
                # 如果N天内没有数据，使用最后一个交易日
                end_data = daily_df[daily_df['日期_date'] > actual_buy_date]
                if len(end_data) == 0:
                    results['periods'][f'{days}天'] = None
                    continue
            
            # 使用最后一个交易日的收盘价
            end_price = float(end_data.iloc[-1]['收盘'])
            end_date = end_data.iloc[-1]['日期_date']
            
            # 计算涨幅
            gain = (end_price - buy_price) / buy_price * 100
            actual_days = (end_date - actual_buy_date).days
            
            results['periods'][f'{days}天'] = {
                'gain': round(gain, 2),
                'end_price': round(end_price, 2),
                'end_date': end_date.strftime('%Y-%m-%d'),
                'actual_days': actual_days
            }
        
        return results
    
    def run_backtest(
        self,
        start_date: datetime.date,
        end_date: datetime.date,
        min_match_score: float = 0.83,
        max_market_cap: float = 100.0,
        scan_mode: str = 'daily',
        max_stocks_per_day: int = 1,
        periods: List[int] = [14, 28, 56, 84, 140],
        limit: Optional[int] = None,
        use_parallel: bool = True,
        max_workers: int = 10
    ) -> Dict:
        """
        运行回测
        :param start_date: 开始日期
        :param end_date: 结束日期
        :param min_match_score: 最小匹配度阈值
        :param max_market_cap: 最大市值（亿元）
        :param scan_mode: 扫描模式，'daily'=每日，'weekly'=每周，'monthly'=每月
        :param max_stocks_per_day: 每天最多选择的股票数量（选择匹配度最高的N只）
        :param periods: 计算收益的周期列表（天数）
        :param limit: 限制扫描股票数量（None表示全部）
        :param use_parallel: 是否使用并行处理
        :param max_workers: 最大并发线程数
        :return: 回测结果字典
        """
        print("=" * 80)
        print("🚀 开始回测")
        print("=" * 80)
        print(f"时间范围: {start_date} 至 {end_date}")
        print(f"扫描模式: {scan_mode}")
        print(f"匹配度阈值: {min_match_score:.3f}")
        print(f"市值上限: {max_market_cap} 亿元")
        print(f"每天最多选择: {max_stocks_per_day} 只股票")
        print(f"收益周期: {periods} 天")
        print()
        
        # 获取交易日列表
        print(f"正在获取交易日列表...")
        # 确保start_date和end_date是date类型
        if isinstance(start_date, str):
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        if isinstance(end_date, str):
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        all_trading_days = self.get_trading_days(start_date, end_date)
        print(f"✅ 找到 {len(all_trading_days)} 个交易日")
        
        # 根据扫描模式筛选日期
        if scan_mode == 'daily':
            scan_dates = all_trading_days
        elif scan_mode == 'weekly':
            # 每周选择第一个交易日
            scan_dates = []
            current_week = None
            for day in all_trading_days:
                week_num = day.isocalendar()[1]  # 周数
                year = day.year
                week_key = (year, week_num)
                if week_key != current_week:
                    scan_dates.append(day)
                    current_week = week_key
        elif scan_mode == 'monthly':
            # 每月选择第一个交易日
            scan_dates = []
            current_month = None
            for day in all_trading_days:
                month_key = (day.year, day.month)
                if month_key != current_month:
                    scan_dates.append(day)
                    current_month = month_key
        else:
            raise ValueError(f"不支持的扫描模式: {scan_mode}")
        
        print(f"✅ 筛选后需要扫描 {len(scan_dates)} 个日期")
        print()
        
        # 存储结果
        results = []
        start_time = time.time()
        
        # 遍历每个扫描日期
        for idx, scan_date in enumerate(scan_dates, 1):
            print(f"[{idx}/{len(scan_dates)}] 扫描日期: {scan_date}")
            print("-" * 80)
            
            try:
                # 使用指定日期进行扫描
                scan_result = self.analyzer.scan_all_stocks(
                    min_match_score=min_match_score,
                    max_market_cap=max_market_cap,
                    limit=limit,
                    use_parallel=use_parallel,
                    max_workers=max_workers,
                    scan_date=scan_date.strftime('%Y-%m-%d')
                )
                
                if not scan_result.get('success'):
                    print(f"   ⚠️ 扫描失败: {scan_result.get('message', '未知错误')}")
                    results.append({
                        'date': scan_date.strftime('%Y-%m-%d'),
                        'stocks': [],
                        'error': scan_result.get('message', '扫描失败')
                    })
                    continue
                
                candidates = scan_result.get('candidates', [])
                
                if len(candidates) == 0:
                    print(f"   ⚠️ 未找到符合条件的股票")
                    results.append({
                        'date': scan_date.strftime('%Y-%m-%d'),
                        'stocks': [],
                        'error': '未找到符合条件的股票'
                    })
                    continue
                
                # 按匹配度排序，选择前N只
                candidates_sorted = sorted(candidates, key=lambda x: x.get('匹配度', 0), reverse=True)
                selected_stocks = candidates_sorted[:max_stocks_per_day]
                
                print(f"   ✅ 找到 {len(candidates)} 只候选股票，选择匹配度最高的 {len(selected_stocks)} 只")
                
                # 计算每只股票的收益
                day_results = []
                for stock in selected_stocks:
                    stock_code = stock.get('股票代码')
                    stock_name = stock.get('股票名称')
                    match_score = stock.get('匹配度', 0)
                    
                    print(f"      📊 {stock_code} {stock_name} (匹配度: {match_score:.3f})")
                    
                    # 计算多周期收益
                    gain_info = self.calculate_gain_after_periods(stock_code, scan_date, periods)
                    
                    if gain_info:
                        day_results.append({
                            'stock_code': stock_code,
                            'stock_name': stock_name,
                            'match_score': match_score,
                            'buy_price': gain_info['buy_price'],
                            'buy_date': gain_info['buy_date'],
                            'gains': gain_info['periods']
                        })
                        
                        # 显示关键周期的收益
                        key_periods = ['14天', '28天', '56天']
                        for period in key_periods:
                            if period in gain_info['periods'] and gain_info['periods'][period]:
                                gain = gain_info['periods'][period]['gain']
                                print(f"         {period}: {gain:+.2f}%")
                    else:
                        print(f"         ⚠️ 无法计算收益（可能数据不足）")
                        day_results.append({
                            'stock_code': stock_code,
                            'stock_name': stock_name,
                            'match_score': match_score,
                            'error': '无法计算收益'
                        })
                
                results.append({
                    'date': scan_date.strftime('%Y-%m-%d'),
                    'stocks': day_results
                })
                
            except Exception as e:
                print(f"   ❌ 处理失败: {e}")
                import traceback
                traceback.print_exc()
                results.append({
                    'date': scan_date.strftime('%Y-%m-%d'),
                    'stocks': [],
                    'error': str(e)
                })
            
            print()
        
        # 计算总耗时
        elapsed_time = time.time() - start_time
        elapsed_min = int(elapsed_time // 60)
        elapsed_sec = int(elapsed_time % 60)
        
        print("=" * 80)
        print(f"✅ 回测完成，总耗时: {elapsed_min}分{elapsed_sec}秒")
        print("=" * 80)
        
        return {
            'start_date': start_date.strftime('%Y-%m-%d'),
            'end_date': end_date.strftime('%Y-%m-%d'),
            'scan_mode': scan_mode,
            'scan_dates_count': len(scan_dates),
            'total_trading_days': len(all_trading_days),
            'min_match_score': min_match_score,
            'max_market_cap': max_market_cap,
            'max_stocks_per_day': max_stocks_per_day,
            'periods': periods,
            'results': results,
            'elapsed_time_seconds': elapsed_time
        }
