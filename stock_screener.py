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
    
    def screen_stock(self, stock_code, stock_name, conditions=None, as_of_date=None):
        """
        对单只股票进行选股条件判断
        :param stock_code: 股票代码
        :param stock_name: 股票名称
        :param conditions: 选股条件字典，包含各条件的参数
        :param as_of_date: 截止日期（用于历史回测/训练）。为 None 时使用最新数据。
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
            
            'condition4_enabled': True,  # 近期涨停
            'condition4_days': 10,       # 涨停查询天数
            
            'condition5_enabled': True,  # 月成交量最大
            'condition5_months': 12,     # 月成交量查询月数
            
            'condition6_enabled': True,  # 月线稳步上升
            'condition6_months': 6,      # 月线趋势检查月数
            
            'condition7_enabled': True,  # 股价突破月线最大量最高价
            'condition7_months': 12,     # 查询月数
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

            # 如果指定截止日期，裁剪到该日期（用于历史回测/训练）
            if as_of_date is not None:
                try:
                    as_of_ts = pd.to_datetime(as_of_date, errors='coerce')
                    if pd.notna(as_of_ts):
                        daily_df = daily_df[daily_df['日期'] <= as_of_ts].copy()
                        monthly_df = monthly_df[monthly_df['日期'] <= as_of_ts].copy()
                except Exception:
                    pass
                if daily_df is None or daily_df.empty or monthly_df is None or monthly_df.empty:
                    return False, None
            
            # 获取涨停信息（如果条件6启用）
            # 训练/回测场景下（as_of_date 不为空）不走网络接口，直接基于 daily_df 计算
            if cond['condition6_enabled']:
                has_limit_up, limit_up_days = self._get_limit_up_info_from_daily_df(
                    daily_df, days=cond['condition6_days']
                )
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
                    # 数据不足（例如历史不足250日），视为不满足，但不直接中断（训练/回测也需要拿到detail）
                    condition2 = False
                else:
                    current_above_ma, recent_above_ma = self.tech_analysis.check_price_above_ma(daily_df, ma)
                    center_rising = self.tech_analysis.check_center_rising(daily_df, ma, days=cond['condition2_recent_days'])
                    condition2 = current_above_ma and recent_above_ma and center_rising
            else:
                ma = None
            
            # 条件3: 启动价识别
            condition3 = True
            found_startup = False
            startup_price = None
            reversal_date = None
            reversal_low = None
            reversal_close = None
            
            if cond['condition3_enabled']:
                ma_monthly = self.tech_analysis.calculate_monthly_ma(monthly_df, period=cond['condition3_ma_monthly_period'])
                if ma_monthly is None:
                    # 月线数据不足，无法识别启动价：视为不满足，但不直接中断
                    found_startup, startup_price, reversal_date, reversal_low, reversal_close = False, None, None, None, None
                    condition3 = False
                    ma_monthly = None
                else:
                    found_startup, startup_price, reversal_date, reversal_low, reversal_close = \
                        self.tech_analysis.find_startup_price(monthly_df, ma_monthly)
                    condition3 = found_startup
            else:
                condition3 = True  # 如果条件3禁用，默认满足
            
            # 条件4: 近期涨停
            if cond['condition4_enabled']:
                condition4 = has_limit_up
            else:
                condition4 = True  # 如果条件4禁用，默认满足
            
            # 条件5: 月成交量最大
            if cond['condition5_enabled']:
                max_monthly_volume, max_monthly_volume_date = \
                    self.tech_analysis.find_max_monthly_volume(monthly_df, months=cond['condition5_months'])
                condition5 = max_monthly_volume is not None
            else:
                condition5 = True  # 如果条件5禁用，默认满足
                max_monthly_volume, max_monthly_volume_date = None, None
            
            # 条件6: 月线稳步上升
            if cond['condition6_enabled']:
                condition6 = self.tech_analysis.check_monthly_trend_rising(monthly_df, months=cond['condition6_months'])
            else:
                condition6 = True  # 如果条件6禁用，默认满足
            
            # 条件7: 股价突破月线最大量最高价
            max_volume_high = None
            if cond['condition7_enabled']:
                _, _, max_volume_high = self.tech_analysis.find_max_monthly_volume_high(
                    monthly_df, months=cond['condition7_months'])
                condition7 = self.tech_analysis.check_price_above_max_volume_high(
                    current_price, max_volume_high)
            else:
                condition7 = True  # 如果条件7禁用，默认满足
            
            # 综合判断：所有条件都满足
            all_conditions_met = (condition1 and condition2 and condition3 and 
                                 condition4 and condition5 and condition6 and condition7)
            
            # 构建详细信息
            detail = {
                '股票代码': stock_code,
                '股票名称': stock_name,
                '当前价格': current_price,
                '条件1_历史最大量': condition1,
                '条件2_年线之上': condition2,
                '条件3_找到启动价': condition3,
                '条件4_近期涨停': condition4,
                '条件5_月成交量最大': condition5,
                '条件6_月线稳步上升': condition6,
                '条件7_突破月线最大量最高价': condition7,
                '启动价': startup_price if found_startup else None,
                '反转日期': reversal_date if found_startup else None,
                '历史最大量日期': max_volume_date,
                '月成交量最大日期': max_monthly_volume_date,
                '月线最大量最高价': max_volume_high,
                '涨停日期': limit_up_days if has_limit_up else []
            }
            
            return all_conditions_met, detail
            
        except Exception as e:
            print(f"分析 {stock_code} ({stock_name}) 时出错: {e}")
            return False, None

    @staticmethod
    def _get_limit_up_info_from_daily_df(daily_df, days=10):
        """
        基于已有日线数据计算最近N个交易日是否出现涨停（避免训练/回测时额外网络请求）
        :return: (has_limit_up: bool, limit_up_days: list[Timestamp])
        """
        try:
            if daily_df is None or daily_df.empty:
                return False, []
            df = daily_df.sort_values('日期').reset_index(drop=True).copy()
            if len(df) < 2:
                return False, []

            # 只取最近 N 个交易日窗口
            recent = df.tail(days).copy()
            # 使用收盘价计算涨跌幅（%），避免依赖 akshare 列名/位置
            recent['__pct'] = recent['收盘'].pct_change() * 100
            # 第一行pct为NaN，填充为0避免误判
            recent['__pct'] = recent['__pct'].fillna(0)

            # 简化：以 >= 9.5% 作为涨停判定（与原 DataFetcher.get_limit_up_info 一致）
            limit_up_mask = recent['__pct'] >= 9.5
            limit_up_days = recent.loc[limit_up_mask, '日期'].tolist()
            return len(limit_up_days) > 0, limit_up_days
        except Exception:
            return False, []
    
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

