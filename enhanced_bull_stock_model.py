#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
增强版大牛股模型 - 基于全网量价关系研究成果
特征体系：
1. OBV能量潮 - 累积资金流向
2. 筹码集中度 - 价格区间集中度
3. 均线粘合度 - 变盘前兆
4. MACD信号 - 趋势确认
5. 量价背离/同向 - 趋势强度
6. 突破信号 - 形态识别
"""
import os
import sys
import json
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


class EnhancedFeatureExtractor:
    """增强版特征提取器"""
    
    @staticmethod
    def calculate_obv(df: pd.DataFrame, volume_col: str = '周成交量') -> pd.Series:
        """
        计算OBV能量潮
        逻辑：价格上涨加成交量，价格下跌减成交量
        """
        obv = [0]
        for i in range(1, len(df)):
            if df['收盘'].iloc[i] > df['收盘'].iloc[i-1]:
                obv.append(obv[-1] + df[volume_col].iloc[i])
            elif df['收盘'].iloc[i] < df['收盘'].iloc[i-1]:
                obv.append(obv[-1] - df[volume_col].iloc[i])
            else:
                obv.append(obv[-1])
        return pd.Series(obv, index=df.index)
    
    @staticmethod
    def calculate_ad_line(df: pd.DataFrame, volume_col: str = '周成交量') -> pd.Series:
        """
        计算A/D累积派发线
        考虑收盘价在当日高低区间的位置
        """
        clv = ((df['收盘'] - df['最低']) - (df['最高'] - df['收盘'])) / (df['最高'] - df['最低'] + 0.0001)
        ad = (clv * df[volume_col]).cumsum()
        return ad
    
    @staticmethod
    def calculate_macd(prices: pd.Series, fast=12, slow=26, signal=9):
        """计算MACD指标"""
        ema_fast = prices.ewm(span=fast, adjust=False).mean()
        ema_slow = prices.ewm(span=slow, adjust=False).mean()
        dif = ema_fast - ema_slow
        dea = dif.ewm(span=signal, adjust=False).mean()
        macd = (dif - dea) * 2
        return dif, dea, macd
    
    @staticmethod
    def calculate_rsi(prices: pd.Series, period=14):
        """计算RSI指标"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / (loss + 0.0001)
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    @staticmethod
    def calculate_bollinger_bands(prices: pd.Series, period=20, num_std=2):
        """计算布林带"""
        ma = prices.rolling(window=period).mean()
        std = prices.rolling(window=period).std()
        upper = ma + num_std * std
        lower = ma - num_std * std
        return ma, upper, lower
    
    @staticmethod
    def calculate_ma_convergence(df: pd.DataFrame, idx: int) -> float:
        """
        计算均线粘合度
        均线越粘合，值越小，预示变盘
        """
        if idx < 20:
            return 100.0
        
        prices = df['收盘'].iloc[:idx+1]
        ma5 = prices.rolling(5).mean().iloc[-1]
        ma10 = prices.rolling(10).mean().iloc[-1]
        ma20 = prices.rolling(20).mean().iloc[-1]
        
        # 计算均线之间的离散度
        avg_ma = (ma5 + ma10 + ma20) / 3
        if avg_ma > 0:
            dispersion = (abs(ma5-avg_ma) + abs(ma10-avg_ma) + abs(ma20-avg_ma)) / avg_ma * 100
            return round(dispersion, 2)
        return 100.0
    
    @staticmethod
    def calculate_chip_concentration(df: pd.DataFrame, idx: int, lookback=20) -> Dict:
        """
        计算筹码集中度（简化版）
        使用价格区间代替真实筹码分布
        """
        if idx < lookback:
            return {'chip_concentration': 0, 'cost_center': 0}
        
        recent_df = df.iloc[idx-lookback:idx+1]
        
        # 加权平均成本（用成交量加权）
        volume_col = '周成交量' if '周成交量' in df.columns else '成交量'
        total_volume = recent_df[volume_col].sum()
        if total_volume > 0:
            weighted_price = (recent_df['收盘'] * recent_df[volume_col]).sum() / total_volume
        else:
            weighted_price = recent_df['收盘'].mean()
        
        # 90%筹码的价格区间
        price_range = recent_df['最高'].max() - recent_df['最低'].min()
        
        # 当前价格相对成本中心
        current_price = df['收盘'].iloc[idx]
        cost_deviation = (current_price - weighted_price) / weighted_price * 100 if weighted_price > 0 else 0
        
        # 筹码集中度 = 成交量加权标准差
        if total_volume > 0:
            price_std = np.sqrt(((recent_df['收盘'] - weighted_price) ** 2 * recent_df[volume_col]).sum() / total_volume)
            concentration = price_std / weighted_price * 100 if weighted_price > 0 else 0
        else:
            concentration = 0
        
        return {
            'chip_concentration': round(concentration, 2),  # 越小越集中
            'cost_center': round(weighted_price, 2),
            'cost_deviation': round(cost_deviation, 2)  # 正值=价格在成本上方
        }
    
    def extract_enhanced_features(self, df: pd.DataFrame, idx: int, volume_col: str = '周成交量') -> Optional[Dict]:
        """
        提取增强版特征
        """
        if idx < 40 or len(df) < 40:
            return None
        
        try:
            features = {}
            current_price = df['收盘'].iloc[idx]
            current_volume = df[volume_col].iloc[idx]
            
            # ========== 1. OBV能量潮特征 ==========
            obv = self.calculate_obv(df.iloc[:idx+1], volume_col)
            
            # OBV趋势（近10周OBV斜率）
            if len(obv) >= 10:
                obv_recent = obv.tail(10)
                obv_slope = (obv_recent.iloc[-1] - obv_recent.iloc[0]) / (obv_recent.iloc[0] + 1) * 100
                features['OBV趋势'] = round(obv_slope, 2)
            
            # OBV是否创新高（相对前20周）
            if len(obv) >= 20:
                obv_high_20 = obv.tail(20).max()
                features['OBV创新高'] = 1 if obv.iloc[-1] >= obv_high_20 * 0.95 else 0
            
            # OBV与价格背离
            if len(obv) >= 10:
                price_trend = (df['收盘'].iloc[idx] - df['收盘'].iloc[idx-10]) / df['收盘'].iloc[idx-10]
                obv_trend = (obv.iloc[-1] - obv.iloc[-10]) / (abs(obv.iloc[-10]) + 1)
                # 正背离：价格跌OBV涨（买入信号）
                features['OBV正背离'] = 1 if (price_trend < -0.05 and obv_trend > 0.1) else 0
            
            # ========== 2. A/D累积派发特征 ==========
            ad = self.calculate_ad_line(df.iloc[:idx+1], volume_col)
            if len(ad) >= 10:
                ad_trend = (ad.iloc[-1] - ad.iloc[-10]) / (abs(ad.iloc[-10]) + 1) * 100
                features['AD趋势'] = round(ad_trend, 2)
            
            # ========== 3. MACD特征 ==========
            prices = df['收盘'].iloc[:idx+1]
            dif, dea, macd = self.calculate_macd(prices)
            
            features['MACD_DIF'] = round(dif.iloc[-1], 3)
            features['MACD_DEA'] = round(dea.iloc[-1], 3)
            features['MACD柱'] = round(macd.iloc[-1], 3)
            
            # MACD金叉/死叉
            if len(dif) >= 2:
                prev_diff = dif.iloc[-2] - dea.iloc[-2]
                curr_diff = dif.iloc[-1] - dea.iloc[-1]
                features['MACD金叉'] = 1 if (prev_diff < 0 and curr_diff >= 0) else 0
                features['MACD零轴上方'] = 1 if dif.iloc[-1] > 0 else 0
            
            # ========== 4. RSI特征 ==========
            rsi = self.calculate_rsi(prices, 14)
            if len(rsi) > 0 and not pd.isna(rsi.iloc[-1]):
                features['RSI'] = round(rsi.iloc[-1], 2)
                features['RSI超卖'] = 1 if rsi.iloc[-1] < 30 else 0
                features['RSI强势区'] = 1 if 50 < rsi.iloc[-1] < 70 else 0
            
            # ========== 5. 布林带特征 ==========
            ma, upper, lower = self.calculate_bollinger_bands(prices, 20, 2)
            if not pd.isna(upper.iloc[-1]) and not pd.isna(lower.iloc[-1]):
                bb_width = (upper.iloc[-1] - lower.iloc[-1]) / ma.iloc[-1] * 100
                features['布林带宽度'] = round(bb_width, 2)
                
                # 价格在布林带中的位置
                bb_position = (current_price - lower.iloc[-1]) / (upper.iloc[-1] - lower.iloc[-1] + 0.01) * 100
                features['布林带位置'] = round(bb_position, 2)
                
                # 布林带收窄（变盘信号）
                if len(ma) >= 10:
                    bb_width_10 = ((upper.iloc[-10] - lower.iloc[-10]) / ma.iloc[-10] * 100) if ma.iloc[-10] > 0 else bb_width
                    features['布林带收窄'] = 1 if bb_width < bb_width_10 * 0.8 else 0
            
            # ========== 6. 均线粘合度 ==========
            features['均线粘合度'] = self.calculate_ma_convergence(df, idx)
            
            # 均线多头排列
            if idx >= 20:
                ma5 = df['收盘'].iloc[idx-4:idx+1].mean()
                ma10 = df['收盘'].iloc[idx-9:idx+1].mean()
                ma20 = df['收盘'].iloc[idx-19:idx+1].mean()
                features['均线多头'] = 1 if (ma5 > ma10 > ma20) else 0
                features['价格在MA20上方'] = 1 if current_price > ma20 else 0
            
            # ========== 7. 筹码集中度 ==========
            chip_info = self.calculate_chip_concentration(df, idx, 20)
            features['筹码集中度'] = chip_info['chip_concentration']
            features['成本偏离度'] = chip_info['cost_deviation']
            
            # ========== 8. 量比特征 ==========
            # 量比 = 当前成交量 / 过去N周平均成交量
            avg_vol_5 = df[volume_col].iloc[idx-5:idx].mean()
            avg_vol_10 = df[volume_col].iloc[idx-10:idx].mean()
            avg_vol_20 = df[volume_col].iloc[idx-20:idx].mean()
            
            features['量比5周'] = round(current_volume / avg_vol_5, 2) if avg_vol_5 > 0 else 1
            features['量比10周'] = round(current_volume / avg_vol_10, 2) if avg_vol_10 > 0 else 1
            features['量比20周'] = round(current_volume / avg_vol_20, 2) if avg_vol_20 > 0 else 1
            
            # 地量信号（成交量极度萎缩）
            min_vol_20 = df[volume_col].iloc[idx-20:idx].min()
            features['地量信号'] = 1 if current_volume <= min_vol_20 * 1.2 else 0
            
            # ========== 9. 突破信号 ==========
            high_20 = df['最高'].iloc[idx-20:idx].max()
            high_40 = df['最高'].iloc[idx-40:idx].max()
            
            features['突破20周高点'] = 1 if current_price > high_20 else 0
            features['突破40周高点'] = 1 if current_price > high_40 else 0
            features['接近20周高点'] = 1 if current_price > high_20 * 0.95 else 0
            
            # ========== 10. 价格形态 ==========
            # 近期涨跌幅
            if idx >= 4:
                ret_4w = (current_price - df['收盘'].iloc[idx-4]) / df['收盘'].iloc[idx-4] * 100
                features['近4周涨跌幅'] = round(ret_4w, 2)
            
            if idx >= 8:
                ret_8w = (current_price - df['收盘'].iloc[idx-8]) / df['收盘'].iloc[idx-8] * 100
                features['近8周涨跌幅'] = round(ret_8w, 2)
            
            # 价格波动率
            if idx >= 20:
                returns = df['收盘'].iloc[idx-20:idx+1].pct_change().dropna()
                volatility = returns.std() * np.sqrt(52) * 100  # 年化波动率
                features['波动率'] = round(volatility, 2)
            
            # ========== 11. 量价配合 ==========
            # 量价同向性
            if idx >= 10:
                price_changes = df['收盘'].iloc[idx-10:idx+1].pct_change().dropna()
                vol_changes = df[volume_col].iloc[idx-10:idx+1].pct_change().dropna()
                
                if len(price_changes) > 0 and len(vol_changes) > 0:
                    correlation = price_changes.corr(vol_changes)
                    if not pd.isna(correlation):
                        features['量价相关性'] = round(correlation, 3)
            
            # 价涨量增得分
            up_vol_score = 0
            for i in range(max(0, idx-10), idx+1):
                if i > 0:
                    if df['收盘'].iloc[i] > df['收盘'].iloc[i-1] and df[volume_col].iloc[i] > df[volume_col].iloc[i-1]:
                        up_vol_score += 1
            features['价涨量增得分'] = up_vol_score
            
            # ========== 12. 底部形态特征 ==========
            # 价格相对40周低点
            low_40 = df['最低'].iloc[idx-40:idx].min()
            features['相对40周低点'] = round((current_price - low_40) / low_40 * 100, 2) if low_40 > 0 else 0
            
            # 横盘整理天数（价格波动小于10%的周数）
            sideways_weeks = 0
            for i in range(idx-20, idx):
                if i >= 0:
                    range_pct = (df['最高'].iloc[i] - df['最低'].iloc[i]) / df['最低'].iloc[i] * 100
                    if range_pct < 10:
                        sideways_weeks += 1
            features['横盘周数'] = sideways_weeks
            
            return features
            
        except Exception as e:
            print(f"特征提取错误: {e}")
            return None


class EnhancedBullStockModel:
    """增强版大牛股模型"""
    
    def __init__(self):
        self.feature_extractor = EnhancedFeatureExtractor()
        self.model = None
        self.feature_stats = {}
        self.sample_stocks = []
    
    def train(self, sample_data: List[Dict]) -> Dict:
        """
        训练模型
        sample_data: [{'code': '000592', 'weekly_df': pd.DataFrame, 'start_idx': 92}, ...]
        """
        all_features = []
        
        for sample in sample_data:
            df = sample['weekly_df']
            idx = sample['start_idx']
            code = sample['code']
            
            volume_col = '周成交量' if '周成交量' in df.columns else '成交量'
            features = self.feature_extractor.extract_enhanced_features(df, idx, volume_col)
            
            if features:
                features['股票代码'] = code
                all_features.append(features)
                self.sample_stocks.append(code)
                print(f"✅ {code} 特征提取成功，共 {len(features)} 个特征")
        
        if not all_features:
            return {}
        
        # 计算特征统计值
        feature_df = pd.DataFrame(all_features)
        numeric_cols = feature_df.select_dtypes(include=[np.number]).columns
        
        for col in numeric_cols:
            values = feature_df[col].dropna()
            if len(values) > 0:
                self.feature_stats[col] = {
                    '均值': round(float(values.mean()), 4),
                    '中位数': round(float(values.median()), 4),
                    '标准差': round(float(values.std()), 4),
                    '最小值': round(float(values.min()), 4),
                    '最大值': round(float(values.max()), 4),
                    '样本数': len(values)
                }
        
        self.model = {
            'feature_stats': self.feature_stats,
            'sample_stocks': self.sample_stocks,
            'sample_count': len(all_features),
            'trained_at': datetime.now().isoformat(),
            'model_type': 'enhanced_volume_price_model'
        }
        
        print(f"\n✅ 模型训练完成")
        print(f"   样本数: {len(all_features)}")
        print(f"   特征数: {len(self.feature_stats)}")
        
        return self.model
    
    def calculate_match_score(self, features: Dict) -> float:
        """计算匹配度"""
        if not self.feature_stats:
            return 0
        
        # 定义核心特征及其权重
        core_features = {
            'OBV趋势': 3.0,
            'OBV创新高': 2.0,
            'MACD金叉': 2.0,
            'MACD零轴上方': 1.5,
            '均线粘合度': 2.0,
            '均线多头': 2.0,
            '量比5周': 2.0,
            '地量信号': 1.5,
            '突破20周高点': 2.0,
            '筹码集中度': 1.5,
            '布林带收窄': 1.5,
            '价涨量增得分': 1.5,
            'RSI强势区': 1.0,
        }
        
        total_score = 0
        total_weight = 0
        
        for feature_name, stats in self.feature_stats.items():
            if feature_name not in features:
                continue
            
            target_value = features[feature_name]
            min_val = stats['最小值']
            max_val = stats['最大值']
            median_val = stats['中位数']
            std_val = stats['标准差']
            
            # 计算匹配分数
            if min_val <= target_value <= max_val:
                # 在范围内，根据到中位数的距离评分
                if std_val > 0:
                    z_score = abs(target_value - median_val) / std_val
                    import math
                    score = math.exp(-0.1 * z_score * z_score)
                else:
                    score = 1.0
            else:
                # 范围外
                if max_val > min_val:
                    range_size = max_val - min_val
                    if target_value < min_val:
                        distance = (min_val - target_value) / range_size
                    else:
                        distance = (target_value - max_val) / range_size
                    score = max(0, 1.0 - distance * 0.5)
                else:
                    score = 0.5
            
            # 应用权重
            weight = core_features.get(feature_name, 1.0)
            total_score += score * weight
            total_weight += weight
        
        if total_weight > 0:
            return round(total_score / total_weight, 3)
        return 0
    
    def save_model(self, filepath: str):
        """保存模型"""
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.model, f, ensure_ascii=False, indent=2)
        print(f"✅ 模型已保存到: {filepath}")
    
    def load_model(self, filepath: str):
        """加载模型"""
        with open(filepath, 'r', encoding='utf-8') as f:
            self.model = json.load(f)
        self.feature_stats = self.model.get('feature_stats', {})
        self.sample_stocks = self.model.get('sample_stocks', [])
        print(f"✅ 模型已加载: {filepath}")


def train_enhanced_model():
    """训练增强版模型"""
    print("=" * 80)
    print("🚀 训练增强版大牛股模型")
    print("=" * 80)
    
    # 加载原始模型获取样本股票
    with open('trained_model.json', 'r', encoding='utf-8') as f:
        old_model = json.load(f)
    
    sample_stocks = old_model['buy_features']['sample_stocks']
    analysis_results = old_model.get('analysis_results', {})
    
    print(f"📊 样本股票: {len(sample_stocks)} 只")
    
    # 准备训练数据
    cache_dir = 'cache/weekly_kline'
    sample_data = []
    
    for code in sample_stocks:
        if code not in analysis_results:
            continue
        
        interval = analysis_results[code].get('interval', {})
        start_date = interval.get('起点日期', '')
        
        # 加载周K线
        csv_path = os.path.join(cache_dir, f'{code}.csv')
        json_path = os.path.join(cache_dir, f'{code}.json')
        
        weekly_df = None
        if os.path.exists(csv_path):
            weekly_df = pd.read_csv(csv_path)
        elif os.path.exists(json_path):
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            weekly_df = pd.DataFrame(data)
        
        if weekly_df is None or len(weekly_df) < 40:
            print(f"⚠️ {code} 数据不足")
            continue
        
        # 找到起点索引
        start_ts = pd.to_datetime(start_date)
        weekly_df['__dt'] = pd.to_datetime(weekly_df['日期'], errors='coerce')
        weekly_df = weekly_df.dropna(subset=['__dt'])
        weekly_df = weekly_df.sort_values('__dt').reset_index(drop=True)
        
        start_idx = None
        for i, row in weekly_df.iterrows():
            if row['__dt'] <= start_ts:
                start_idx = i
        
        if start_idx is None or start_idx < 40:
            print(f"⚠️ {code} 找不到起点或数据不足")
            continue
        
        sample_data.append({
            'code': code,
            'weekly_df': weekly_df.drop(columns=['__dt']),
            'start_idx': start_idx
        })
    
    # 训练模型
    model = EnhancedBullStockModel()
    result = model.train(sample_data)
    
    # 保存模型
    model.save_model('enhanced_model.json')
    
    # 验证匹配度
    print("\n" + "=" * 80)
    print("📊 验证训练样本匹配度")
    print("=" * 80)
    
    for sample in sample_data:
        df = sample['weekly_df']
        idx = sample['start_idx']
        code = sample['code']
        
        volume_col = '周成交量' if '周成交量' in df.columns else '成交量'
        features = model.feature_extractor.extract_enhanced_features(df, idx, volume_col)
        
        if features:
            score = model.calculate_match_score(features)
            status = '✅' if score >= 0.95 else '⚠️'
            print(f"{status} {code}: 匹配度 {score:.3f}")
    
    return model


def backtest_enhanced_model():
    """使用增强版模型回测"""
    print("\n" + "=" * 80)
    print("🚀 增强版模型回测 - 2025年12月")
    print("=" * 80)
    
    # 加载模型
    model = EnhancedBullStockModel()
    model.load_model('enhanced_model.json')
    
    # 加载股票列表
    with open('cache/stock_list_all.json', 'r', encoding='utf-8') as f:
        stock_list = json.load(f)
    
    weeks = ['2025-12-05', '2025-12-12', '2025-12-19', '2025-12-26', '2025-12-31']
    cache_dir = 'cache/weekly_kline'
    
    all_results = []
    
    for week_date in weeks:
        print(f"\n📅 扫描日期: {week_date}")
        print("-" * 60)
        
        candidates = []
        scan_ts = pd.to_datetime(week_date)
        
        for stock_info in stock_list:
            code = stock_info.get('code', '')
            name = stock_info.get('name', '')
            
            # 排除ST和北交所
            if 'ST' in name.upper() or code.startswith('8') or code.startswith('9'):
                continue
            
            # 加载数据
            csv_path = os.path.join(cache_dir, f'{code}.csv')
            json_path = os.path.join(cache_dir, f'{code}.json')
            
            weekly_df = None
            if os.path.exists(csv_path):
                weekly_df = pd.read_csv(csv_path)
            elif os.path.exists(json_path):
                with open(json_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                weekly_df = pd.DataFrame(data)
            
            if weekly_df is None or len(weekly_df) < 50:
                continue
            
            # 按日期筛选
            weekly_df['__dt'] = pd.to_datetime(weekly_df['日期'], errors='coerce')
            weekly_df = weekly_df.dropna(subset=['__dt'])
            weekly_df = weekly_df[weekly_df['__dt'] <= scan_ts]
            weekly_df = weekly_df.sort_values('__dt').reset_index(drop=True)
            
            if len(weekly_df) < 50:
                continue
            
            idx = len(weekly_df) - 1
            volume_col = '周成交量' if '周成交量' in weekly_df.columns else '成交量'
            
            # 提取特征并计算匹配度
            features = model.feature_extractor.extract_enhanced_features(
                weekly_df.drop(columns=['__dt']), idx, volume_col
            )
            
            if features:
                score = model.calculate_match_score(features)
                if score >= 0.95:
                    candidates.append({
                        '股票代码': code,
                        '股票名称': name,
                        '匹配度': score,
                        '价格': round(weekly_df['收盘'].iloc[idx], 2),
                        'OBV趋势': features.get('OBV趋势', 0),
                        'MACD金叉': features.get('MACD金叉', 0),
                        '均线多头': features.get('均线多头', 0),
                        '量比5周': features.get('量比5周', 0),
                    })
        
        # 排序并取前5
        candidates.sort(key=lambda x: x['匹配度'], reverse=True)
        top5 = candidates[:5]
        
        print(f"找到 {len(candidates)} 只候选，前5名:")
        for i, c in enumerate(top5, 1):
            print(f"  {i}. {c['股票代码']} {c['股票名称']}: {c['匹配度']:.3f} | "
                  f"OBV={c['OBV趋势']:.1f} MACD金叉={c['MACD金叉']} 均线多头={c['均线多头']}")
        
        for c in top5:
            c['扫描周'] = week_date
            all_results.append(c)
    
    # 保存结果
    if all_results:
        df = pd.DataFrame(all_results)
        output_file = f'backtest_enhanced_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        df.to_csv(output_file, index=False, encoding='utf-8-sig')
        print(f"\n✅ 结果已保存到: {output_file}")
    
    return all_results


if __name__ == '__main__':
    # 训练模型
    model = train_enhanced_model()
    
    # 回测
    results = backtest_enhanced_model()
