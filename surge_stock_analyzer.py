"""
暴涨股票特征学习分析器
分析暴涨股票在暴涨前的共同特征，并识别最佳买点
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from data_fetcher import DataFetcher
from technical_analysis import TechnicalAnalysis
import warnings
warnings.filterwarnings('ignore')


class SurgeStockAnalyzer:
    """暴涨股票特征分析器"""
    
    def __init__(self):
        self.data_fetcher = DataFetcher()
        self.tech_analysis = TechnicalAnalysis()
        self.surge_stocks = []  # 存储暴涨股票数据
        self.common_features = {}  # 存储共同特征
        
    def add_surge_stock(self, stock_code, stock_name, surge_date=None):
        """
        添加暴涨股票进行分析
        :param stock_code: 股票代码
        :param stock_name: 股票名称
        :param surge_date: 暴涨开始日期（如果为None，则使用最近一个月）
        """
        print(f"正在分析暴涨股票: {stock_code} {stock_name}")
        
        # 处理日期参数
        if surge_date is None:
            end_date = datetime.now()
        elif isinstance(surge_date, str):
            # 如果是字符串，转换为datetime对象
            try:
                end_date = pd.to_datetime(surge_date)
                if isinstance(end_date, pd.Timestamp):
                    end_date = end_date.to_pydatetime()
            except:
                print(f"日期格式错误: {surge_date}，使用当前日期")
                end_date = datetime.now()
        else:
            end_date = surge_date
        
        # 获取历史数据（暴涨前至少3个月的数据）
        start_date = end_date - timedelta(days=180)  # 获取6个月的数据
        
        daily_df = self.data_fetcher.get_daily_kline(stock_code)
        # 使用len()而不是.empty来避免Series布尔判断错误
        if daily_df is None or len(daily_df) == 0:
            print(f"无法获取 {stock_code} 的数据")
            return None
        
        # 计算暴涨日期（如果未指定，则查找最近一个月内涨幅翻倍（≥100%）的日期）
        if surge_date is None:
            # 计算每日涨跌幅
            daily_df['涨跌幅'] = daily_df['收盘'].pct_change() * 100
            
            # 计算每个日期相对于20个交易日前的累计涨幅（约一个月）
            # 需要确保有足够的数据
            if len(daily_df) < 20:
                print(f"❌ {stock_code} {stock_name} 数据不足，无法计算30日涨幅（需要至少20天数据）")
                return None
            
            # 计算每个日期相对于20个交易日前的涨幅（约一个月）
            daily_df['30日累计涨幅'] = daily_df['收盘'].pct_change(periods=20) * 100
            
            # 同时计算任意20个交易日区间的最大涨幅
            # 这样可以找到任意20个交易日内涨幅≥100%的区间
            max_gain = 0
            max_gain_end_idx = None
            max_gain_start_idx = None
            
            # 搜索最近90天的数据（扩大搜索范围）
            search_range = min(90, len(daily_df) - 20)
            if search_range <= 0:
                print(f"❌ {stock_code} {stock_name} 数据不足，无法搜索暴涨日期")
                return None
            
            # 遍历所有可能的20个交易日区间
            for end_idx in range(len(daily_df) - search_range, len(daily_df)):
                if end_idx >= 20:
                    start_idx = end_idx - 20
                    start_price = daily_df.iloc[start_idx]['收盘']
                    end_price = daily_df.iloc[end_idx]['收盘']
                    gain = (end_price - start_price) / start_price * 100
                    
                    if gain > max_gain:
                        max_gain = gain
                        max_gain_end_idx = end_idx
                        max_gain_start_idx = start_idx
            
            # 检查是否找到涨幅≥100%的区间
            if max_gain >= 100:
                surge_date = daily_df.iloc[max_gain_end_idx]['日期']
                start_date = daily_df.iloc[max_gain_start_idx]['日期']
                print(f"✅ 找到暴涨区间: {start_date} 到 {surge_date}")
                print(f"   起始价格: {daily_df.iloc[max_gain_start_idx]['收盘']:.2f}")
                print(f"   结束价格: {daily_df.iloc[max_gain_end_idx]['收盘']:.2f}")
                print(f"   涨幅: {max_gain:.2f}% (翻{max_gain/100:.1f}倍)")
            else:
                print(f"❌ {stock_code} {stock_name} 最近{search_range}天内任意20个交易日的最大涨幅仅为 {max_gain:.2f}%，未达到翻倍（100%）要求，不符合暴涨条件")
                return None  # 不符合暴涨条件，返回None
        
        # 找到暴涨日期在数据中的位置
        surge_idx = None
        # 确保surge_date是datetime对象
        if isinstance(surge_date, str):
            surge_date_dt = pd.to_datetime(surge_date)
        else:
            surge_date_dt = pd.to_datetime(surge_date)
        
        # 确保是单个值，不是Series
        if isinstance(surge_date_dt, pd.Series):
            surge_date_dt = surge_date_dt.iloc[0]
        if isinstance(surge_date_dt, pd.Timestamp):
            surge_date_dt = surge_date_dt.to_pydatetime()
        
        for idx, row in daily_df.iterrows():
            row_date = pd.to_datetime(row['日期'])
            # 确保是单个值
            if isinstance(row_date, pd.Series):
                row_date = row_date.iloc[0]
            if isinstance(row_date, pd.Timestamp):
                row_date = row_date.to_pydatetime()
            
            # 现在可以安全比较
            if row_date >= surge_date_dt:
                surge_idx = idx
                break
        
        if surge_idx is None:
            print(f"❌ 无法找到 {stock_code} {stock_name} 的暴涨日期在数据中的位置")
            return None
        
        # 提取暴涨前30天的特征
        before_surge_df = daily_df.iloc[:surge_idx].tail(30)
        # 使用len()而不是.empty来避免Series布尔判断错误
        if len(before_surge_df) == 0 or len(before_surge_df) < 10:
            print(f"❌ {stock_code} {stock_name} 暴涨前的数据不足（只有{len(before_surge_df)}天），需要至少10天数据来提取特征")
            return None
        
        # 提取特征
        features = self._extract_features(before_surge_df, daily_df, surge_idx)
        features['股票代码'] = stock_code
        features['股票名称'] = stock_name
        # 保存日期为字符串格式
        # 从daily_df中获取暴涨日期
        if surge_idx is not None and surge_idx < len(daily_df):
            surge_date_from_df = daily_df.iloc[surge_idx]['日期']
            if isinstance(surge_date_from_df, (pd.Timestamp, datetime)):
                if isinstance(surge_date_from_df, pd.Timestamp):
                    features['暴涨日期'] = surge_date_from_df.strftime('%Y-%m-%d')
                else:
                    features['暴涨日期'] = surge_date_from_df.strftime('%Y-%m-%d')
            else:
                features['暴涨日期'] = str(surge_date_from_df)
        else:
            features['暴涨日期'] = 'N/A'
        
        self.surge_stocks.append(features)
        print(f"✅ 已添加 {stock_code} {stock_name} 的特征分析")
        
        return features
    
    def _extract_features(self, before_surge_df, full_df, surge_idx):
        """提取股票特征"""
        features = {}
        
        # 1. 价格特征
        current_price = before_surge_df.iloc[-1]['收盘']
        price_30_days_ago = before_surge_df.iloc[0]['收盘'] if len(before_surge_df) >= 30 else before_surge_df.iloc[0]['收盘']
        # 确保是标量值
        if isinstance(current_price, pd.Series):
            current_price = current_price.iloc[0] if len(current_price) > 0 else 0
        if isinstance(price_30_days_ago, pd.Series):
            price_30_days_ago = price_30_days_ago.iloc[0] if len(price_30_days_ago) > 0 else 0
        # 转换为Python原生类型
        current_price = float(current_price) if pd.notna(current_price) else 0
        price_30_days_ago = float(price_30_days_ago) if pd.notna(price_30_days_ago) else 0
        features['价格变化率'] = (current_price - price_30_days_ago) / price_30_days_ago * 100 if price_30_days_ago > 0 else 0
        
        # 2. 成交量特征
        avg_volume_30 = before_surge_df['成交量'].mean()
        recent_volume_5 = before_surge_df.tail(5)['成交量'].mean()
        # 确保是标量值，不是Series
        if isinstance(avg_volume_30, pd.Series):
            avg_volume_30 = avg_volume_30.iloc[0] if len(avg_volume_30) > 0 else 0
        if isinstance(recent_volume_5, pd.Series):
            recent_volume_5 = recent_volume_5.iloc[0] if len(recent_volume_5) > 0 else 0
        # 转换为Python原生类型
        avg_volume_30 = float(avg_volume_30) if pd.notna(avg_volume_30) else 0
        recent_volume_5 = float(recent_volume_5) if pd.notna(recent_volume_5) else 0
        features['成交量放大倍数'] = recent_volume_5 / avg_volume_30 if avg_volume_30 > 0 else 0
        
        # 3. 技术指标
        # MA5, MA10, MA20, MA60
        ma5 = self.tech_analysis.calculate_ma(full_df.iloc[:surge_idx], period=5)
        ma10 = self.tech_analysis.calculate_ma(full_df.iloc[:surge_idx], period=10)
        ma20 = self.tech_analysis.calculate_ma(full_df.iloc[:surge_idx], period=20)
        ma60 = self.tech_analysis.calculate_ma(full_df.iloc[:surge_idx], period=60)
        
        if ma5 is not None and len(ma5) > 0:
            ma5_val = ma5.iloc[-1]
            if isinstance(ma5_val, pd.Series):
                ma5_val = ma5_val.iloc[0] if len(ma5_val) > 0 else 0
            ma5_val = float(ma5_val) if pd.notna(ma5_val) and ma5_val > 0 else 0
            features['价格相对MA5'] = (current_price - ma5_val) / ma5_val * 100 if ma5_val > 0 else 0
        if ma10 is not None and len(ma10) > 0:
            ma10_val = ma10.iloc[-1]
            if isinstance(ma10_val, pd.Series):
                ma10_val = ma10_val.iloc[0] if len(ma10_val) > 0 else 0
            ma10_val = float(ma10_val) if pd.notna(ma10_val) and ma10_val > 0 else 0
            features['价格相对MA10'] = (current_price - ma10_val) / ma10_val * 100 if ma10_val > 0 else 0
        if ma20 is not None and len(ma20) > 0:
            ma20_val = ma20.iloc[-1]
            if isinstance(ma20_val, pd.Series):
                ma20_val = ma20_val.iloc[0] if len(ma20_val) > 0 else 0
            ma20_val = float(ma20_val) if pd.notna(ma20_val) and ma20_val > 0 else 0
            features['价格相对MA20'] = (current_price - ma20_val) / ma20_val * 100 if ma20_val > 0 else 0
        if ma60 is not None and len(ma60) > 0:
            ma60_val = ma60.iloc[-1]
            if isinstance(ma60_val, pd.Series):
                ma60_val = ma60_val.iloc[0] if len(ma60_val) > 0 else 0
            ma60_val = float(ma60_val) if pd.notna(ma60_val) and ma60_val > 0 else 0
            features['价格相对MA60'] = (current_price - ma60_val) / ma60_val * 100 if ma60_val > 0 else 0
        
        # 4. 均线排列
        if ma5 is not None and ma10 is not None and ma20 is not None:
            if len(ma5) > 0 and len(ma10) > 0 and len(ma20) > 0:
                ma5_val = ma5.iloc[-1]
                ma10_val = ma10.iloc[-1]
                ma20_val = ma20.iloc[-1]
                # 确保是标量值
                if isinstance(ma5_val, pd.Series):
                    ma5_val = ma5_val.iloc[0] if len(ma5_val) > 0 else 0
                if isinstance(ma10_val, pd.Series):
                    ma10_val = ma10_val.iloc[0] if len(ma10_val) > 0 else 0
                if isinstance(ma20_val, pd.Series):
                    ma20_val = ma20_val.iloc[0] if len(ma20_val) > 0 else 0
                # 转换为float
                ma5_val = float(ma5_val) if pd.notna(ma5_val) else 0
                ma10_val = float(ma10_val) if pd.notna(ma10_val) else 0
                ma20_val = float(ma20_val) if pd.notna(ma20_val) else 0
                features['均线多头排列'] = 1 if (ma5_val > ma10_val > ma20_val) else 0
        
        # 5. 波动率
        volatility = before_surge_df['收盘'].pct_change().std() * 100
        # 确保是标量值
        if isinstance(volatility, pd.Series):
            volatility = volatility.iloc[0] if len(volatility) > 0 else 0
        features['波动率'] = float(volatility) if pd.notna(volatility) else 0
        
        # 6. 连续上涨/下跌天数
        price_changes = before_surge_df['收盘'].pct_change().dropna()
        consecutive_up = 0
        consecutive_down = 0
        for change in price_changes[::-1]:
            if change > 0:
                consecutive_up += 1
                consecutive_down = 0
            elif change < 0:
                consecutive_down += 1
                consecutive_up = 0
            else:
                break
        features['连续上涨天数'] = consecutive_up
        features['连续下跌天数'] = consecutive_down
        
        # 7. 涨停次数（最近30天）
        if '涨跌幅' in before_surge_df.columns:
            limit_up_count = (before_surge_df['涨跌幅'] >= 9.9).sum()
            features['涨停次数'] = limit_up_count
        
        # 8. 量价关系
        if len(before_surge_df) >= 10:
            volume_trend = before_surge_df['成交量'].tail(5).mean() / before_surge_df['成交量'].head(5).mean()
            price_trend = before_surge_df['收盘'].tail(5).mean() / before_surge_df['收盘'].head(5).mean()
            # 确保是标量值
            if isinstance(volume_trend, pd.Series):
                volume_trend = volume_trend.iloc[0] if len(volume_trend) > 0 else 1
            if isinstance(price_trend, pd.Series):
                price_trend = price_trend.iloc[0] if len(price_trend) > 0 else 1
            volume_trend = float(volume_trend) if pd.notna(volume_trend) else 1
            price_trend = float(price_trend) if pd.notna(price_trend) else 1
        else:
            volume_trend = 1
            price_trend = 1
        features['量价配合度'] = 1 if (volume_trend > 1 and price_trend > 1) or (volume_trend < 1 and price_trend < 1) else 0
        
        # 9. 相对强度（与大盘对比，这里简化处理）
        features['相对强度'] = features['价格变化率']  # 简化处理，实际应该与指数对比
        
        # 10. 支撑位和阻力位
        high_30 = before_surge_df['最高'].max()
        low_30 = before_surge_df['最低'].min()
        features['距离最高点'] = (high_30 - current_price) / current_price * 100
        features['距离最低点'] = (current_price - low_30) / current_price * 100
        
        return features
    
    def analyze_common_features(self):
        """分析所有暴涨股票的共同特征"""
        if len(self.surge_stocks) == 0:
            print("没有暴涨股票数据，请先添加股票")
            return None
        
        print(f"\n开始分析 {len(self.surge_stocks)} 只暴涨股票的共同特征...")
        
        # 转换为DataFrame
        df = pd.DataFrame(self.surge_stocks)
        
        # 排除非数值列
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        numeric_cols = [col for col in numeric_cols if col not in ['股票代码', '暴涨日期']]
        
        # 计算统计特征
        common_features = {}
        for col in numeric_cols:
            values = df[col].dropna()
            if len(values) > 0:
                common_features[col] = {
                    '平均值': values.mean(),
                    '中位数': values.median(),
                    '最小值': values.min(),
                    '最大值': values.max(),
                    '标准差': values.std(),
                    '25%分位数': values.quantile(0.25),
                    '75%分位数': values.quantile(0.75)
                }
        
        self.common_features = common_features
        
        print("\n✅ 共同特征分析完成！")
        print("\n主要特征统计：")
        for col, stats in common_features.items():
            print(f"\n{col}:")
            print(f"  平均值: {stats['平均值']:.2f}")
            print(f"  中位数: {stats['中位数']:.2f}")
            print(f"  范围: [{stats['最小值']:.2f}, {stats['最大值']:.2f}]")
        
        return common_features
    
    def find_best_buy_points(self, stock_code, stock_name):
        """
        根据学习到的特征，找到最佳买点
        :param stock_code: 股票代码
        :param stock_name: 股票名称
        :return: 买点信息，包含买入后的表现验证
        """
        if len(self.common_features) == 0:
            print("请先分析暴涨股票的共同特征")
            return None
        
        print(f"\n正在分析 {stock_code} {stock_name} 的买点...")
        
        # 获取股票数据
        daily_df = self.data_fetcher.get_daily_kline(stock_code)
        # 使用len()而不是.empty来避免Series布尔判断错误
        if daily_df is None or len(daily_df) == 0:
            print(f"无法获取 {stock_code} 的数据")
            return None
        
        buy_points = []
        
        # 滑动窗口分析（每次分析30天窗口）
        window_size = 30
        for i in range(window_size, len(daily_df)):
            window_df = daily_df.iloc[i-window_size:i]
            current_date = daily_df.iloc[i]['日期']
            current_price = daily_df.iloc[i]['收盘']
            
            # 提取特征
            features = self._extract_features(window_df, daily_df.iloc[:i+1], i)
            
            # 计算匹配度
            match_score = self._calculate_match_score(features)
            
            if match_score > 0.7:  # 匹配度阈值
                # 计算买入后的表现（验证买点是否正确）
                # 查看买入后20个交易日（约一个月）的表现
                performance = self._calculate_buy_performance(daily_df, i)
                
                if performance is not None:
                    # 只有买入后20日内翻倍（涨幅≥100%）的才算最佳买点
                    is_best_buy_point = performance.get('是否翻倍', False)
                    
                    buy_points.append({
                        '日期': current_date,
                        '价格': current_price,
                        '匹配度': match_score,
                        '特征': features,
                        '买入后表现': performance,
                        '是否最佳买点': is_best_buy_point  # 标记是否为最佳买点（买入后一个月内翻倍）
                    })
                else:
                    # 如果无法计算表现（数据不足），也添加，但标记为非最佳买点
                    buy_points.append({
                        '日期': current_date,
                        '价格': current_price,
                        '匹配度': match_score,
                        '特征': features,
                        '买入后表现': {},
                        '是否最佳买点': False
                    })
        
        # 优先按是否最佳买点排序，然后按匹配度排序
        # 最佳买点（翻倍的）排在前面
        buy_points.sort(key=lambda x: (x.get('是否最佳买点', False), x['匹配度']), reverse=True)
        
        print(f"\n✅ 找到 {len(buy_points)} 个潜在买点")
        if len(buy_points) > 0:
            print("\n最佳买点（前5个）：")
            for i, point in enumerate(buy_points[:5], 1):
                perf = point.get('买入后表现', {})
                print(f"{i}. 日期: {point['日期']}, 价格: {point['价格']:.2f}, 匹配度: {point['匹配度']:.2%}")
                if perf:
                    print(f"   买入后20日涨幅: {perf.get('20日涨幅', 0):.2f}%, 最高涨幅: {perf.get('最高涨幅', 0):.2f}%")
        
        return buy_points
    
    def _calculate_buy_performance(self, daily_df, buy_idx):
        """
        计算买入后的表现，用于验证买点是否正确
        :param daily_df: 日K线数据
        :param buy_idx: 买入日期在数据中的索引
        :return: 表现信息字典
        """
        if buy_idx >= len(daily_df) - 1:
            return None
        
        buy_price = daily_df.iloc[buy_idx]['收盘']
        buy_date = daily_df.iloc[buy_idx]['日期']
        
        # 计算买入后20个交易日的表现
        look_forward_days = 20
        end_idx = min(buy_idx + look_forward_days, len(daily_df) - 1)
        
        if end_idx <= buy_idx:
            return None
        
        # 买入后的价格数据
        after_buy_df = daily_df.iloc[buy_idx+1:end_idx+1]
        
        if len(after_buy_df) == 0:
            return None
        
        # 计算各种表现指标
        performance = {}
        
        # 20日后的价格
        price_20_days_later = after_buy_df.iloc[-1]['收盘']
        performance['20日涨幅'] = (price_20_days_later - buy_price) / buy_price * 100
        
        # 最高价格和最高涨幅
        max_price = after_buy_df['最高'].max()
        performance['最高价格'] = float(max_price) if pd.notna(max_price) else buy_price
        performance['最高涨幅'] = (max_price - buy_price) / buy_price * 100
        
        # 最低价格和最大回撤
        min_price = after_buy_df['最低'].min()
        performance['最低价格'] = float(min_price) if pd.notna(min_price) else buy_price
        performance['最大回撤'] = (min_price - buy_price) / buy_price * 100
        
        # 20日后的日期
        performance['20日后日期'] = after_buy_df.iloc[-1]['日期']
        
        # 是否盈利（确保是Python原生bool类型）
        performance['是否盈利'] = bool(performance['20日涨幅'] > 0)
        
        # 是否翻倍（买入后20日内涨幅≥100%，确保是Python原生bool类型）
        performance['是否翻倍'] = bool(performance['20日涨幅'] >= 100)
        
        return performance
    
    def _calculate_match_score(self, features):
        """计算特征匹配度"""
        if len(self.common_features) == 0:
            return 0
        
        scores = []
        
        for col, stats in self.common_features.items():
            if col in features and pd.notna(features[col]):
                value = features[col]
                avg = stats['平均值']
                std = stats['标准差']
                
                # 计算值是否在合理范围内（平均值±1.5倍标准差）
                if std > 0:
                    z_score = abs((value - avg) / std)
                    # z_score越小，匹配度越高
                    score = max(0, 1 - z_score / 2)  # 归一化到0-1
                else:
                    # 标准差为0，完全匹配得1分
                    score = 1 if abs(value - avg) < 0.01 else 0
                
                scores.append(score)
        
        # 返回平均匹配度
        return np.mean(scores) if len(scores) > 0 else 0
    
    def scan_all_stocks(self, limit=None):
        """
        扫描所有股票，找到符合暴涨特征的股票
        :param limit: 限制扫描数量
        :return: 符合条件的股票列表
        """
        if len(self.common_features) == 0:
            print("请先分析暴涨股票的共同特征")
            return []
        
        print(f"\n开始扫描所有股票，寻找符合暴涨特征的股票...")
        
        # 获取所有股票
        stock_list = self.data_fetcher.get_all_stocks()
        # 使用len()而不是.empty来避免Series布尔判断错误
        if stock_list is None or len(stock_list) == 0:
            print("无法获取股票列表")
            return []
        
        if limit:
            stock_list = stock_list.head(limit)
        
        candidates = []
        
        for idx, row in stock_list.iterrows():
            stock_code = row['code']
            stock_name = row['name']
            
            try:
                buy_points = self.find_best_buy_points(stock_code, stock_name)
                if buy_points and len(buy_points) > 0:
                    best_point = buy_points[0]
                    if best_point['匹配度'] > 0.75:  # 高匹配度阈值
                        candidates.append({
                            '股票代码': stock_code,
                            '股票名称': stock_name,
                            '最佳买点日期': best_point['日期'],
                            '最佳买点价格': best_point['价格'],
                            '匹配度': best_point['匹配度'],
                            '特征': best_point['特征']
                        })
            except Exception as e:
                print(f"分析 {stock_code} 时出错: {e}")
                continue
        
        # 按匹配度排序
        candidates.sort(key=lambda x: x['匹配度'], reverse=True)
        
        print(f"\n✅ 扫描完成，找到 {len(candidates)} 只符合条件的股票")
        
        return candidates


if __name__ == "__main__":
    analyzer = SurgeStockAnalyzer()
    
    # 示例：添加暴涨股票
    # analyzer.add_surge_stock("000001", "平安银行")
    # analyzer.add_surge_stock("000002", "万科A")
    
    # 分析共同特征
    # analyzer.analyze_common_features()
    
    # 寻找买点
    # buy_points = analyzer.find_best_buy_points("000001", "平安银行")
    
    print("暴涨股票特征学习分析器已就绪！")
    print("请使用 add_surge_stock() 方法添加暴涨股票进行分析")

