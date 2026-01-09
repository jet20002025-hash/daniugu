"""
数据获取模块
使用akshare获取A股市场数据
"""
import akshare as ak
import pandas as pd
import time
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')


class DataFetcher:
    """数据获取类"""
    
    def __init__(self):
        self.stock_list = None
        self._market_cap_cache = None  # 缓存市值数据，避免重复获取
        
    def get_all_stocks(self, timeout=10, max_retries=3):
        """
        获取所有A股股票列表
        返回: DataFrame，包含股票代码、名称等信息
        :param timeout: 超时时间（秒），默认10秒
        :param max_retries: 最大重试次数，默认3次
        """
        import signal
        import threading
        
        for attempt in range(max_retries):
            try:
                print(f"[get_all_stocks] 尝试获取股票列表（第 {attempt + 1}/{max_retries} 次）...")
                
                # 使用线程和超时机制
                result = [None]
                error = [None]
                
                def fetch_stocks():
                    try:
                        result[0] = ak.stock_info_a_code_name()
                    except Exception as e:
                        error[0] = e
                        import traceback
                        print(f"[get_all_stocks] 获取失败: {e}")
                        print(f"[get_all_stocks] 错误堆栈: {traceback.format_exc()}")
                
                fetch_thread = threading.Thread(target=fetch_stocks)
                fetch_thread.daemon = True
                fetch_thread.start()
                fetch_thread.join(timeout=timeout)
                
                if fetch_thread.is_alive():
                    print(f"[get_all_stocks] 获取超时（{timeout}秒），尝试重试...")
                    continue  # 重试
                
                if error[0]:
                    print(f"[get_all_stocks] 获取出错: {error[0]}")
                    if attempt < max_retries - 1:
                        print(f"[get_all_stocks] 等待 2 秒后重试...")
                        import time
                        time.sleep(2)
                        continue  # 重试
                    else:
                        raise error[0]
                
                if result[0] is not None and len(result[0]) > 0:
                    stock_info = result[0]
                    self.stock_list = stock_info
                    print(f"[get_all_stocks] ✅ 成功获取 {len(stock_info)} 只A股股票")
                    return stock_info
                else:
                    print(f"[get_all_stocks] ⚠️ 返回结果为空")
                    if attempt < max_retries - 1:
                        print(f"[get_all_stocks] 等待 2 秒后重试...")
                        import time
                        time.sleep(2)
                        continue  # 重试
                    else:
                        print(f"[get_all_stocks] ❌ 所有重试都失败，返回 None")
                        return None
                        
            except Exception as e:
                import traceback
                error_detail = traceback.format_exc()
                print(f"[get_all_stocks] ❌ 获取股票列表失败（第 {attempt + 1} 次尝试）: {e}")
                print(f"[get_all_stocks] 错误详情: {error_detail}")
                
                if attempt < max_retries - 1:
                    print(f"[get_all_stocks] 等待 2 秒后重试...")
                    import time
                    time.sleep(2)
                    continue  # 重试
                else:
                    print(f"[get_all_stocks] ❌ 所有重试都失败")
                    return None
        
        print(f"[get_all_stocks] ❌ 所有重试都失败，返回 None")
        return None
    
    def get_market_cap(self, stock_code, timeout=5):
        """
        获取股票总市值（单位：亿元）
        :param stock_code: 股票代码（如 '000001'）
        :param timeout: 超时时间（秒），默认5秒
        :return: 总市值（亿元），如果获取失败返回None
        """
        try:
            import threading
            import time
            
            # 使用缓存，避免重复获取全部股票数据
            if self._market_cap_cache is None:
                # 使用实时行情接口（批量获取）- 这个操作可能很慢，使用超时保护
                result = [None]
                error = [None]
                
                def fetch_all_stocks():
                    try:
                        result[0] = ak.stock_zh_a_spot_em()
                    except Exception as e:
                        error[0] = e
                
                # 如果缓存为空，需要获取全部股票数据（可能很慢）
                fetch_thread = threading.Thread(target=fetch_all_stocks)
                fetch_thread.daemon = True
                fetch_thread.start()
                fetch_thread.join(timeout=timeout)
                
                if fetch_thread.is_alive():
                    # 超时了，返回None，不阻塞
                    return None
                
                if error[0]:
                    return None
                
                df = result[0]
                if df is not None and not df.empty:
                    self._market_cap_cache = df
                else:
                    return None
            else:
                df = self._market_cap_cache
            
            if df is not None and not df.empty:
                # 查找对应股票（代码列是字符串类型）
                # 确保stock_code是字符串格式
                stock_code_str = str(stock_code)
                stock_row = df[df['代码'] == stock_code_str]
                
                if not stock_row.empty:
                    if '总市值' in stock_row.columns:
                        market_cap = stock_row.iloc[0]['总市值']
                        if pd.notna(market_cap):
                            try:
                                market_cap = float(market_cap)
                                # 总市值单位是元，转换为亿元
                                return market_cap / 100000000
                            except (ValueError, TypeError):
                                pass
            
            return None
        except Exception as e:
            # 静默失败，返回None（可以取消注释下面的行来调试）
            # print(f"获取市值失败 {stock_code}: {e}")
            return None
    
    def get_daily_kline(self, stock_code, period="1y"):
        """
        获取日K线数据
        :param stock_code: 股票代码（如 '000001'）
        :param period: 时间周期，'1y'表示1年
        :return: DataFrame，包含日期、开盘、收盘、最高、最低、成交量等
        """
        try:
            # 计算开始日期（2年前，确保有足够历史数据）
            # 结束日期使用今天，确保获取最新数据
            end_date = datetime.now().strftime('%Y%m%d')
            start_date = (datetime.now() - timedelta(days=365 * 2)).strftime('%Y%m%d')
            
            # 获取日K线数据
            df = ak.stock_zh_a_hist(symbol=stock_code, period="daily", 
                                    start_date=start_date, end_date=end_date, adjust="qfq")
            
            if df is None or df.empty:
                return None
            
            # akshare返回的DataFrame列名通常是中文，直接使用位置索引更可靠
            # 标准列顺序：日期、开盘、收盘、最高、最低、成交量、成交额、振幅、涨跌幅、涨跌额、换手率
            # 但实际返回的列数可能不同，使用位置索引访问
            
            # 先尝试使用列名（如果akshare返回的是标准列名）
            # 注意：即使列数不足6，也要尝试重命名
            if len(df.columns) >= 5:  # 至少需要5列：日期、开盘、收盘、最高、最低
                # 使用位置索引重命名关键列
                # 根据2025-12-31的正确数据核对：
                # 正确：开盘=4.66, 收盘=4.65, 最高=4.68, 最低=4.62
                # akshare实际返回的顺序可能是：日期、开盘、收盘、最高、最低、成交量
                # 或者：日期、其他、开盘、收盘、最高、最低
                # 需要根据列名或数据逻辑判断
                rename_dict = {}
                if len(df.columns) > 0:
                    rename_dict[df.columns[0]] = '日期'
                
                # 尝试根据列名判断
                col_names = [str(col).lower() for col in df.columns]
                
                # 查找包含"开盘"、"收盘"、"最高"、"最低"的列
                open_idx = None
                close_idx = None
                high_idx = None
                low_idx = None
                
                for i, col_name in enumerate(col_names):
                    if '开盘' in col_name or 'open' in col_name:
                        open_idx = i
                    elif '收盘' in col_name or 'close' in col_name:
                        close_idx = i
                    elif '最高' in col_name or 'high' in col_name:
                        high_idx = i
                    elif '最低' in col_name or 'low' in col_name:
                        low_idx = i
                
                # 如果找到了列名，使用列名映射
                if open_idx and close_idx and high_idx and low_idx:
                    rename_dict[df.columns[open_idx]] = '开盘'
                    rename_dict[df.columns[close_idx]] = '收盘'
                    rename_dict[df.columns[high_idx]] = '最高'
                    rename_dict[df.columns[low_idx]] = '最低'
                else:
                    # 如果没找到列名，根据2025-12-31的正确数据推断：
                    # 正确：开盘=4.66, 收盘=4.65, 最高=4.68, 最低=4.62
                    # 之前错误显示：列1=2.00, 列2=4.66, 列3=4.65, 列4=4.68
                    # 所以列顺序是：日期、其他、开盘、收盘、最高、最低
                    # 列1可能是涨跌幅或其他数据，跳过
                    if len(df.columns) > 2:
                        rename_dict[df.columns[2]] = '开盘'  # 列2是开盘
                    if len(df.columns) > 3:
                        rename_dict[df.columns[3]] = '收盘'  # 列3是收盘
                    if len(df.columns) > 4:
                        rename_dict[df.columns[4]] = '最高'  # 列4是最高
                    if len(df.columns) > 5:
                        rename_dict[df.columns[5]] = '最低'  # 列5是最低
                    
                    # 如果列1存在但不是开盘，保留原列名（可能是涨跌幅等）
                    if len(df.columns) > 1 and df.columns[1] not in rename_dict:
                        # 不重命名列1，保持原样
                        pass
                    
                    if len(df.columns) > 6:
                        rename_dict[df.columns[6]] = '成交量'  # 列6是成交量
                
                # 执行重命名
                if rename_dict:
                    df = df.rename(columns=rename_dict)
                    print(f"[调试] 列重命名完成，新列名: {list(df.columns)}")
                else:
                    print(f"[警告] 未执行列重命名，原始列名: {list(df.columns)}")
            
            # 确保日期列存在且可转换
            if '日期' in df.columns:
                df['日期'] = pd.to_datetime(df['日期'], errors='coerce')
            else:
                print(f"[错误] 未找到'日期'列，可用列: {list(df.columns)}")
                return None
            
            # 验证必要的列是否存在，如果不存在则使用位置索引创建
            required_cols = ['开盘', '收盘', '最高', '最低']
            missing_cols = [col for col in required_cols if col not in df.columns]
            if missing_cols:
                # print(f"[警告] 缺少必要的列: {missing_cols}")
                # print(f"[调试] 当前列名: {list(df.columns)}")
                # print(f"[调试] 列数: {len(df.columns)}")
                # 如果列数足够，尝试使用位置索引创建新列
                # 根据2025-12-31的正确数据：列顺序是 日期、其他、开盘、收盘、最高、最低
                if len(df.columns) >= 6:
                    # print(f"[调试] 使用位置索引创建缺失的列...")
                    if '开盘' not in df.columns and len(df.columns) > 2:
                        df['开盘'] = df.iloc[:, 2]
                    if '收盘' not in df.columns and len(df.columns) > 3:
                        df['收盘'] = df.iloc[:, 3]
                    if '最高' not in df.columns and len(df.columns) > 4:
                        df['最高'] = df.iloc[:, 4]
                    if '最低' not in df.columns and len(df.columns) > 5:
                        df['最低'] = df.iloc[:, 5]
                    # print(f"[调试] 创建后的列名: {list(df.columns)}")
            
            # 删除日期为空的记录
            df = df.dropna(subset=['日期'])
            
            if df.empty:
                return None
            
            df = df.sort_values('日期').reset_index(drop=True)
            
            return df
        except Exception as e:
            print(f"获取 {stock_code} 日K线数据失败: {e}")
            return None
    
    def get_weekly_kline(self, stock_code, period="1y"):
        """
        获取周K线数据（包含周成交量）
        :param stock_code: 股票代码（如 '000001'）
        :param period: 时间周期，'1y'表示1年
        :return: DataFrame，包含周日期、开盘、收盘、最高、最低、周成交量等
        """
        try:
            print(f"开始获取 {stock_code} 的周K线数据...")
            # 方法1: 尝试直接使用akshare的周K线接口
            try:
                end_date = datetime.now().strftime('%Y%m%d')
                start_date = (datetime.now() - timedelta(days=365 * 2)).strftime('%Y%m%d')
                
                print(f"尝试直接获取周K线: {stock_code}, {start_date} - {end_date}")
                df = ak.stock_zh_a_hist(symbol=stock_code, period="weekly", 
                                        start_date=start_date, end_date=end_date, adjust="qfq")
                print(f"直接获取周K线结果: {df is not None}, {len(df) if df is not None else 0} 条")
                
                if df is not None and not df.empty:
                    # 重命名列
                    if len(df.columns) >= 6:
                        rename_dict = {}
                        if len(df.columns) > 0:
                            rename_dict[df.columns[0]] = '日期'
                        # 根据2025-12-31的正确数据推断：
                        # 正确：开盘=4.66, 收盘=4.65, 最高=4.68, 最低=4.62
                        # 之前错误显示：列1=2.00, 列2=4.66, 列3=4.65, 列4=4.68
                        # 所以列顺序是：日期、其他（列1，可能是涨跌幅）、开盘（列2）、收盘（列3）、最高（列4）、最低（列5）
                        # 列1跳过（可能是涨跌幅或其他数据）
                        if len(df.columns) > 2:
                            rename_dict[df.columns[2]] = '开盘'  # 列2是开盘
                        if len(df.columns) > 3:
                            rename_dict[df.columns[3]] = '收盘'  # 列3是收盘
                        if len(df.columns) > 4:
                            rename_dict[df.columns[4]] = '最高'  # 列4是最高
                        if len(df.columns) > 5:
                            rename_dict[df.columns[5]] = '最低'  # 列5是最低
                        if len(df.columns) > 6:
                            rename_dict[df.columns[6]] = '成交量'  # 列6是成交量
                        
                        df = df.rename(columns=rename_dict)
                    
                    # 确保日期列存在且可转换
                    if '日期' in df.columns:
                        df['日期'] = pd.to_datetime(df['日期'], errors='coerce')
                        df = df.dropna(subset=['日期'])
                        df = df.sort_values('日期').reset_index(drop=True)
                        # 重命名成交量为周成交量
                        if '成交量' in df.columns:
                            df = df.rename(columns={'成交量': '周成交量'})
                        return df
            except Exception as e1:
                print(f"直接获取周K线失败: {e1}，尝试从日K线聚合...")
                # 如果直接获取失败，使用聚合方式
            
            # 方法2: 从日K线聚合为周K线
            print(f"开始从日K线聚合周K线: {stock_code}")
            daily_df = self.get_daily_kline(stock_code, period)
            if daily_df is None or daily_df.empty:
                print(f"无法获取 {stock_code} 的日K线数据")
                return None
            print(f"获取到 {len(daily_df)} 条日K线数据，开始聚合...")
            
            # 确保必要的列存在
            required_cols = ['日期', '开盘', '收盘', '最高', '最低', '成交量']
            missing_cols = [col for col in required_cols if col not in daily_df.columns]
            if missing_cols:
                print(f"警告：缺少必要的列 {missing_cols}")
                return None
            
            # 转换为周K线
            weekly_df = daily_df.copy()
            
            # 使用ISO周（周一开始）
            weekly_df['年周'] = weekly_df['日期'].dt.to_period('W-SUN')  # 周日结束的周
            
            # 按周聚合
            def agg_week(group):
                return pd.Series({
                    '开盘': group['开盘'].iloc[0],
                    '收盘': group['收盘'].iloc[-1],
                    '最高': group['最高'].max(),
                    '最低': group['最低'].min(),
                    '周成交量': group['成交量'].sum()  # 周成交量 = 该周所有交易日的成交量之和
                })
            
            weekly_kline = weekly_df.groupby('年周').apply(agg_week).reset_index()
            
            # 如果成交额列存在，也聚合
            if '成交额' in weekly_df.columns:
                weekly_kline['周成交额'] = weekly_df.groupby('年周')['成交额'].sum().values
            
            # 将周期转换为日期（使用该周的最后一天）
            weekly_kline['日期'] = weekly_kline['年周'].dt.to_timestamp() + pd.Timedelta(days=6)
            weekly_kline = weekly_kline.sort_values('日期').reset_index(drop=True)
            
            # 计算周涨跌幅
            weekly_kline['涨跌幅'] = weekly_kline['收盘'].pct_change() * 100
            weekly_kline['涨跌幅'] = weekly_kline['涨跌幅'].fillna(0)
            
            return weekly_kline
        except Exception as e:
            import traceback
            print(f"获取 {stock_code} 周K线数据失败: {e}")
            print(f"错误详情: {traceback.format_exc()}")
            return None
    
    def get_monthly_kline(self, stock_code, period="1y"):
        """
        获取月K线数据
        :param stock_code: 股票代码
        :param period: 时间周期
        :return: DataFrame，月K线数据
        """
        try:
            # 先获取日K线，然后转换为月K线
            daily_df = self.get_daily_kline(stock_code, period)
            if daily_df is None or daily_df.empty:
                return None
            
            # 转换为月K线
            monthly_df = daily_df.copy()
            
            # 确保必要的列存在
            required_cols = ['日期', '开盘', '收盘', '最高', '最低', '成交量']
            missing_cols = [col for col in required_cols if col not in monthly_df.columns]
            if missing_cols:
                print(f"警告：缺少必要的列 {missing_cols}")
                return None
            
            monthly_df['年月'] = monthly_df['日期'].dt.to_period('M')
            
            # 按月聚合（使用apply方式，更兼容）
            def agg_month(group):
                return pd.Series({
                    '开盘': group['开盘'].iloc[0],
                    '收盘': group['收盘'].iloc[-1],
                    '最高': group['最高'].max(),
                    '最低': group['最低'].min(),
                    '成交量': group['成交量'].sum()
                })
            
            monthly_kline = monthly_df.groupby('年月').apply(agg_month).reset_index()
            
            # 如果成交额列存在，也聚合
            if '成交额' in monthly_df.columns:
                monthly_kline['成交额'] = monthly_df.groupby('年月')['成交额'].sum().values
            
            monthly_kline['日期'] = monthly_kline['年月'].dt.to_timestamp()
            monthly_kline = monthly_kline.sort_values('日期').reset_index(drop=True)
            
            # 计算月涨跌幅
            monthly_kline['涨跌幅'] = monthly_kline['收盘'].pct_change() * 100
            monthly_kline['涨跌幅'] = monthly_kline['涨跌幅'].fillna(0)
            
            return monthly_kline
        except Exception as e:
            import traceback
            print(f"获取 {stock_code} 月K线数据失败: {e}")
            print(f"错误详情: {traceback.format_exc()}")
            return None
    
    def get_limit_up_info(self, stock_code, days=10):
        """
        获取最近N个交易日的涨停信息
        :param stock_code: 股票代码
        :param days: 查询天数
        :return: 是否有涨停（True/False），涨停日期列表
        """
        try:
            # 获取最近N天的日K线数据
            end_date = datetime.now().strftime('%Y%m%d')
            start_date = (datetime.now() - timedelta(days=days*2)).strftime('%Y%m%d')  # 多取一些，排除非交易日
            
            df = ak.stock_zh_a_hist(symbol=stock_code, period="daily", 
                                    start_date=start_date, end_date=end_date, adjust="qfq")
            
            if df is None or df.empty:
                return False, []
            
            # 使用位置索引访问数据，避免列名问题
            if len(df.columns) < 9:
                return False, []
            
            # 直接使用位置索引
            df.iloc[:, 0] = pd.to_datetime(df.iloc[:, 0], errors='coerce')
            df = df.dropna(subset=[df.columns[0]])
            if df.empty:
                return False, []
            
            # 按日期排序
            df = df.sort_values(by=df.columns[0]).reset_index(drop=True)
            
            # 取最近days个交易日
            recent_df = df.tail(days)
            
            # 判断是否有涨停（涨跌幅 >= 9.5%，考虑ST股是5%）
            # 涨跌幅通常在第8列（索引8）
            pct_chg_col = df.columns[8] if len(df.columns) > 8 else None
            if pct_chg_col is None:
                return False, []
            
            limit_up_mask = recent_df[pct_chg_col] >= 9.5
            date_col = df.columns[0]
            limit_up_days = recent_df[limit_up_mask][date_col].tolist()
            has_limit_up = len(limit_up_days) > 0
            
            return has_limit_up, limit_up_days
        except Exception as e:
            print(f"获取 {stock_code} 涨停信息失败: {e}")
            return False, []

