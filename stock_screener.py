"""
选股条件判断模块
综合所有条件进行选股
"""
from data_fetcher import DataFetcher
from technical_analysis import TechnicalAnalysis
import pandas as pd


class StockScreener:
    """选股器类"""
    
    def __init__(self):
        self.data_fetcher = DataFetcher()
        self.tech_analysis = TechnicalAnalysis()
        self.results = []
    
    def screen_stock(self, stock_code, stock_name, conditions=None):
        """
        对单只股票进行选股条件判断
        :param stock_code: 股票代码
        :param stock_name: 股票名称
        :param conditions: 选股条件字典，包含各条件的参数
        :return: 是否满足条件, 详细信息字典
        """
        # 默认条件参数
        default_conditions = {
            'condition1_enabled': True,  # 历史最大量
            'condition1_days': 365,      # 历史最大量查询天数
            
            'condition2_enabled': True,  # 年线之上
            'condition2_ma_period': 250, # 年线周期
            'condition2_recent_days': 30, # 重心稳步上移检查天数
            
            'condition3_enabled': True,  # 启动价识别
            'condition3_max_decline_months': 2,  # 最大连续下跌月数
            'condition3_ma_monthly_period': 20,   # 月均线周期
            'condition3_small_negative_max': -2, # 小阴线最大跌幅
            'condition3_small_positive_min': 1,    # 小阳线最小涨幅
            'condition3_small_positive_max': 10,  # 小阳线最大涨幅
            'condition3_large_positive_min': 20,  # 大阳线最小涨幅
            
            'condition4_enabled': True,  # 回到启动价附近
            'condition4_threshold': 0.03, # 启动价阈值（3%）
            
            'condition5_enabled': True,  # 近期大量成交
            'condition5_multiplier': 2.0, # 成交量倍数
            
            'condition6_enabled': True,  # 近期涨停
            'condition6_days': 10,       # 涨停查询天数
            
            'condition7_enabled': True,  # 月成交量最大
            'condition7_months': 12,     # 月成交量查询月数
            
            'condition8_enabled': True,  # 月线稳步上升
            'condition8_months': 6,      # 月线趋势检查月数
        }
        
        # 合并用户自定义条件
        if conditions:
            default_conditions.update(conditions)
        cond = default_conditions
        try:
            # 获取数据
            daily_df = self.data_fetcher.get_daily_kline(stock_code)
            if daily_df is None or daily_df.empty:
                return False, None
            
            monthly_df = self.data_fetcher.get_monthly_kline(stock_code)
            if monthly_df is None or monthly_df.empty:
                return False, None
            
            # 获取涨停信息（如果条件6启用）
            if cond['condition6_enabled']:
                has_limit_up, limit_up_days = self.data_fetcher.get_limit_up_info(stock_code, days=cond['condition6_days'])
            else:
                has_limit_up, limit_up_days = True, []  # 如果条件6禁用，默认满足
            
            # 当前价格
            current_price = daily_df.iloc[-1]['收盘']
            
            # 条件1: 历史最大量（过去一年内）
            condition1 = True
            if cond['condition1_enabled']:
                max_volume, max_volume_date, max_volume_price = self.tech_analysis.find_max_volume_date(
                    daily_df, days=cond['condition1_days'])
                condition1 = max_volume is not None
            else:
                max_volume, max_volume_date, max_volume_price = None, None, None
            
            # 条件2: 年线之上，重心稳步上移
            condition2 = True
            if cond['condition2_enabled']:
                ma = self.tech_analysis.calculate_ma(daily_df, period=cond['condition2_ma_period'])
                if ma is None:
                    return False, None
                current_above_ma, recent_above_ma = self.tech_analysis.check_price_above_ma(daily_df, ma)
                center_rising = self.tech_analysis.check_center_rising(daily_df, ma, days=cond['condition2_recent_days'])
                condition2 = current_above_ma and recent_above_ma and center_rising
            else:
                ma = None
            
            # 条件3: 启动价识别
            condition3 = True
            condition4 = True
            found_startup = False
            startup_price = None
            reversal_date = None
            reversal_low = None
            reversal_close = None
            
            if cond['condition3_enabled']:
                ma_monthly = self.tech_analysis.calculate_monthly_ma(monthly_df, period=cond['condition3_ma_monthly_period'])
                if ma_monthly is None:
                    return False, None
                
                found_startup, startup_price, reversal_date, reversal_low, reversal_close = \
                    self.tech_analysis.find_startup_price(monthly_df, ma_monthly)
                condition3 = found_startup
                
                # 条件4: 回到启动价附近
                if cond['condition4_enabled']:
                    if found_startup:
                        condition4 = self.tech_analysis.check_near_startup_price(
                            current_price, startup_price, reversal_low, threshold=cond['condition4_threshold']
                        )
                    else:
                        condition4 = False
                else:
                    condition4 = True  # 如果条件4禁用，默认满足
            else:
                condition3 = True  # 如果条件3禁用，默认满足
                if cond['condition4_enabled']:
                    condition4 = False  # 如果条件3禁用但条件4启用，则条件4无法满足
                else:
                    condition4 = True
            
            # 条件5: 近期大量成交
            if cond['condition5_enabled']:
                condition5 = self.tech_analysis.check_large_volume_recent(daily_df, multiplier=cond['condition5_multiplier'])
            else:
                condition5 = True  # 如果条件5禁用，默认满足
            
            # 条件6: 近期涨停
            if cond['condition6_enabled']:
                condition6 = has_limit_up
            else:
                condition6 = True  # 如果条件6禁用，默认满足
            
            # 条件7: 月成交量最大
            if cond['condition7_enabled']:
                max_monthly_volume, max_monthly_volume_date = \
                    self.tech_analysis.find_max_monthly_volume(monthly_df, months=cond['condition7_months'])
                condition7 = max_monthly_volume is not None
            else:
                condition7 = True  # 如果条件7禁用，默认满足
                max_monthly_volume, max_monthly_volume_date = None, None
            
            # 条件8: 月线稳步上升
            if cond['condition8_enabled']:
                condition8 = self.tech_analysis.check_monthly_trend_rising(monthly_df, months=cond['condition8_months'])
            else:
                condition8 = True  # 如果条件8禁用，默认满足
            
            # 综合判断：所有条件都满足
            all_conditions_met = (condition1 and condition2 and condition3 and condition4 and 
                                 condition5 and condition6 and condition7 and condition8)
            
            # 构建详细信息
            detail = {
                '股票代码': stock_code,
                '股票名称': stock_name,
                '当前价格': current_price,
                '条件1_历史最大量': condition1,
                '条件2_年线之上': condition2,
                '条件3_找到启动价': condition3,
                '条件4_回到启动价附近': condition4,
                '条件5_近期大量成交': condition5,
                '条件6_近期涨停': condition6,
                '条件7_月成交量最大': condition7,
                '条件8_月线稳步上升': condition8,
                '启动价': startup_price if found_startup else None,
                '反转日期': reversal_date if found_startup else None,
                '历史最大量日期': max_volume_date,
                '月成交量最大日期': max_monthly_volume_date,
                '涨停日期': limit_up_days if has_limit_up else []
            }
            
            return all_conditions_met, detail
            
        except Exception as e:
            print(f"分析 {stock_code} ({stock_name}) 时出错: {e}")
            return False, None
    
    def screen_all_stocks(self, limit=None, exclude_st=True, save_interval=100):
        """
        对所有A股进行选股
        :param limit: 限制分析股票数量（用于测试，None表示全部）
        :param exclude_st: 是否排除ST股票
        :param save_interval: 每分析多少只股票保存一次进度（默认100只）
        :return: 符合条件的股票列表
        """
        import time
        
        # 获取所有股票列表
        stock_list = self.data_fetcher.get_all_stocks()
        if stock_list is None or stock_list.empty:
            print("无法获取股票列表")
            return []
        
        # 排除ST股票
        if exclude_st:
            stock_list = stock_list[~stock_list['name'].str.contains('ST')]
        
        # 限制数量（用于测试）
        if limit:
            stock_list = stock_list.head(limit)
        
        print(f"\n开始分析 {len(stock_list)} 只股票...")
        print("=" * 80)
        print(f"进度保存间隔: 每 {save_interval} 只股票自动保存一次")
        print("=" * 80)
        
        results = []
        total = len(stock_list)
        start_time = time.time()
        
        for idx, row in stock_list.iterrows():
            stock_code = row['code']
            stock_name = row['name']
            
            # 计算进度和预计剩余时间
            elapsed = time.time() - start_time
            if idx > 0:
                avg_time = elapsed / (idx + 1)
                remaining = (total - idx - 1) * avg_time
                remaining_min = int(remaining / 60)
                remaining_sec = int(remaining % 60)
                progress_pct = (idx + 1) / total * 100
                elapsed_min = int(elapsed / 60)
                elapsed_sec = int(elapsed % 60)
                # 使用进度条样式
                bar_length = 40
                filled = int(bar_length * (idx + 1) / total)
                bar = '█' * filled + '░' * (bar_length - filled)
                print(f"\r[{idx+1}/{total}] [{bar}] {progress_pct:.1f}% | 已用: {elapsed_min}分{elapsed_sec}秒 | 剩余: {remaining_min}分{remaining_sec}秒 | {stock_code} {stock_name}", end='', flush=True)
            else:
                print(f"[{idx+1}/{total}] 正在分析: {stock_code} {stock_name}", end=' ... ', flush=True)
            
            try:
                is_selected, detail = self.screen_stock(stock_code, stock_name)
                
                if is_selected:
                    print(f" ✓ 符合条件！")
                    results.append(detail)
                else:
                    print(f" ✗", end='', flush=True)
                
                # 定期保存进度
                if (idx + 1) % save_interval == 0:
                    self.results = results
                    temp_file = f'选股结果_临时_{idx+1}.xlsx'
                    self.export_results(temp_file)
                    print(f"\n  ⚠ 已保存临时结果到: {temp_file} (找到 {len(results)} 只符合条件的股票)")
                
                # 添加小延迟，避免请求过快
                if (idx + 1) % 50 == 0:
                    time.sleep(1)  # 每50只股票休息1秒
                else:
                    time.sleep(0.1)  # 每只股票休息0.1秒
                    
            except Exception as e:
                print(f"✗ 分析出错: {e}")
                continue
        
        print("\n" + "=" * 80)
        total_time = time.time() - start_time
        total_min = int(total_time / 60)
        total_sec = int(total_time % 60)
        print(f"分析完成！共找到 {len(results)} 只符合条件的股票")
        print(f"总耗时: {total_min}分{total_sec}秒")
        
        self.results = results
        return results
    
    def export_results(self, filename='选股结果.xlsx'):
        """
        导出选股结果到Excel
        :param filename: 输出文件名
        """
        if not self.results:
            print("没有结果可导出")
            return
        
        df = pd.DataFrame(self.results)
        df.to_excel(filename, index=False, engine='openpyxl')
        print(f"结果已导出到: {filename}")

