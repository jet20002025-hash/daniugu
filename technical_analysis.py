"""
技术指标计算模块
计算各种技术指标和量价分析
"""
import pandas as pd
import numpy as np


class TechnicalAnalysis:
    """技术分析类"""
    
    @staticmethod
    def calculate_ma(df, period=250):
        """
        计算移动平均线
        :param df: K线数据DataFrame
        :param period: 周期（如250为年线）
        :return: Series，移动平均线数据
        """
        if df is None or df.empty or len(df) < period:
            return None
        return df['收盘'].rolling(window=period).mean()
    
    @staticmethod
    def calculate_monthly_ma(monthly_df, period=20):
        """
        计算月线移动平均线
        :param monthly_df: 月K线数据DataFrame
        :param period: 周期（如20为20月均线）
        :return: Series，移动平均线数据
        """
        if monthly_df is None or monthly_df.empty or len(monthly_df) < period:
            return None
        return monthly_df['收盘'].rolling(window=period).mean()
    
    @staticmethod
    def find_max_volume_date(df, days=365):
        """
        找出过去N天内的最大成交量日期
        :param df: 日K线数据
        :param days: 查询天数
        :return: (最大成交量, 最大成交量日期, 最大成交量当天的收盘价)
        """
        if df is None or df.empty:
            return None, None, None
        
        # 取最近days天的数据
        recent_df = df.tail(days) if len(df) > days else df
        
        max_volume_idx = recent_df['成交量'].idxmax()
        max_volume = recent_df.loc[max_volume_idx, '成交量']
        max_volume_date = recent_df.loc[max_volume_idx, '日期']
        max_volume_price = recent_df.loc[max_volume_idx, '收盘']
        
        return max_volume, max_volume_date, max_volume_price
    
    @staticmethod
    def check_price_above_ma(df, ma_series):
        """
        检查股价是否在均线之上
        :param df: K线数据
        :param ma_series: 均线数据
        :return: 当前是否在均线之上, 最近N天是否都在均线之上
        """
        if df is None or df.empty or ma_series is None:
            return False, False
        
        # 合并数据
        check_df = pd.DataFrame({
            '收盘': df['收盘'].values,
            '均线': ma_series.values
        }, index=df.index)
        
        # 当前是否在均线之上
        current_above = check_df.iloc[-1]['收盘'] > check_df.iloc[-1]['均线']
        
        # 最近30天是否都在均线之上（重心稳步上移的判断）
        recent_above = (check_df.tail(30)['收盘'] > check_df.tail(30)['均线']).all()
        
        return current_above, recent_above
    
    @staticmethod
    def check_center_rising(df, ma_series, days=30):
        """
        检查重心是否稳步上移
        :param df: K线数据
        :param ma_series: 均线数据
        :param days: 检查天数
        :return: 是否重心稳步上移
        """
        if df is None or df.empty or ma_series is None or len(df) < days:
            return False
        
        recent_df = df.tail(days)
        recent_ma = ma_series.tail(days)
        
        # 计算低点是否逐步抬升
        lows = recent_df['最低'].values
        ma_values = recent_ma.values
        
        # 检查低点是否在均线之上且逐步抬升
        if len(lows) < 3:
            return False
        
        # 简单判断：最近的低点是否高于之前的低点
        recent_lows = lows[-10:] if len(lows) >= 10 else lows
        if len(recent_lows) < 3:
            return False
        
        # 检查低点是否逐步抬升（允许小幅波动）
        min_low = np.min(recent_lows[:-1])
        current_low = recent_lows[-1]
        
        return current_low >= min_low * 0.98  # 允许2%的波动
    
    @staticmethod
    def find_startup_price(monthly_df, ma20_monthly):
        """
        识别启动价
        条件：
        1. 连续下跌不超过2个月
        2. 下跌期间不跌破20月均线
        3. 由小阴线（跌幅-2%以内）变成小阳线（涨幅1%-10%）或大阳线（涨幅≥20%）
        
        :param monthly_df: 月K线数据
        :param ma20_monthly: 20月均线数据
        :return: (是否找到启动价, 启动价, 反转日期, 反转日最低价, 反转日收盘价)
        """
        if monthly_df is None or monthly_df.empty or len(monthly_df) < 3:
            return False, None, None, None, None
        
        if ma20_monthly is None or len(ma20_monthly) < 3:
            return False, None, None, None, None
        
        # 合并数据
        check_df = pd.DataFrame({
            '日期': monthly_df['日期'].values,
            '收盘': monthly_df['收盘'].values,
            '最低': monthly_df['最低'].values,
            '涨跌幅': monthly_df['涨跌幅'].values,
            '20月均线': ma20_monthly.values
        })
        
        # 从后往前查找反转点
        for i in range(len(check_df) - 1, 1, -1):
            current_month = check_df.iloc[i]
            prev_month = check_df.iloc[i-1]
            prev2_month = check_df.iloc[i-2] if i >= 2 else None
            
            # 检查当前月是否是阳线
            if current_month['涨跌幅'] < 1:  # 不是小阳线或大阳线
                continue
            
            # 检查前一个月是否是阴线（跌幅-2%以内）
            if prev_month['涨跌幅'] > -2 or prev_month['涨跌幅'] >= 0:
                continue
            
            # 检查连续下跌不超过2个月
            decline_months = 0
            if prev_month['涨跌幅'] < 0:
                decline_months = 1
                if prev2_month is not None and prev2_month['涨跌幅'] < 0:
                    decline_months = 2
            
            if decline_months > 2:
                continue
            
            # 检查下跌期间是否跌破20月均线（需要检查所有下跌月份）
            if decline_months >= 1:
                # 检查前一个月是否跌破20月均线
                if prev_month['最低'] < prev_month['20月均线']:
                    continue
                # 如果有连续2个月下跌，检查前两个月是否跌破20月均线
                if decline_months == 2 and prev2_month is not None:
                    if prev2_month['最低'] < prev2_month['20月均线']:
                        continue
            
            # 检查当前月是否是小阳线（1%-10%）或大阳线（≥20%）
            is_small_positive = 1 <= current_month['涨跌幅'] <= 10
            is_large_positive = current_month['涨跌幅'] >= 20
            
            if is_small_positive or is_large_positive:
                # 找到启动价
                startup_price = current_month['收盘']  # 反转当天的收盘价
                reversal_date = current_month['日期']
                reversal_low = current_month['最低']
                reversal_close = current_month['收盘']
                
                return True, startup_price, reversal_date, reversal_low, reversal_close
        
        return False, None, None, None, None
    
    @staticmethod
    def check_near_startup_price(current_price, startup_price, reversal_low, threshold=0.03):
        """
        检查当前价是否在启动价附近
        :param current_price: 当前价格
        :param startup_price: 启动价
        :param reversal_low: 反转日最低价
        :param threshold: 阈值（默认3%）
        :return: 是否满足条件
        """
        if startup_price is None or current_price is None:
            return False
        
        # 不能跌破反转日最低价
        if current_price < reversal_low:
            return False
        
        # 在启动价±3%范围内
        price_diff = abs(current_price - startup_price) / startup_price
        return price_diff <= threshold
    
    @staticmethod
    def check_large_volume_recent(df, multiplier=2.0):
        """
        检查最近一个交易日是否有大量成交
        :param df: 日K线数据
        :param multiplier: 倍数（默认2倍）
        :return: 是否满足条件
        """
        if df is None or df.empty or len(df) < 2:
            return False
        
        recent_volume = df.iloc[-1]['成交量']
        prev_volume = df.iloc[-2]['成交量']
        
        return recent_volume >= prev_volume * multiplier
    
    @staticmethod
    def find_max_monthly_volume(monthly_df, months=12):
        """
        找出过去N个月内的最大月成交量
        :param monthly_df: 月K线数据
        :param months: 查询月数
        :return: (最大月成交量, 最大月成交量日期)
        """
        if monthly_df is None or monthly_df.empty:
            return None, None
        
        recent_df = monthly_df.tail(months) if len(monthly_df) > months else monthly_df
        
        max_volume_idx = recent_df['成交量'].idxmax()
        max_volume = recent_df.loc[max_volume_idx, '成交量']
        max_volume_date = recent_df.loc[max_volume_idx, '日期']
        
        return max_volume, max_volume_date
    
    @staticmethod
    def check_monthly_trend_rising(monthly_df, months=6):
        """
        检查月线是否稳步上升
        :param monthly_df: 月K线数据
        :param months: 检查月数
        :return: 是否稳步上升
        """
        if monthly_df is None or monthly_df.empty or len(monthly_df) < months:
            return False
        
        recent_df = monthly_df.tail(months)
        closes = recent_df['收盘'].values
        
        # 简单判断：最近几个月的收盘价是否逐步上升
        if len(closes) < 3:
            return False
        
        # 计算趋势（使用线性回归的斜率）
        x = np.arange(len(closes))
        slope = np.polyfit(x, closes, 1)[0]
        
        return slope > 0  # 斜率为正表示上升趋势

