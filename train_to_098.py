#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
训练模型使大牛股匹配度达到1.0
通过调整特征权重和阈值来优化匹配度
"""
import os
import sys
import json
import pandas as pd
import numpy as np
from datetime import datetime
from copy import deepcopy

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def load_weekly_kline_from_cache(code):
    """从本地缓存加载周K线数据"""
    cache_dir = 'cache/weekly_kline'
    csv_path = os.path.join(cache_dir, f'{code}.csv')
    json_path = os.path.join(cache_dir, f'{code}.json')
    
    if os.path.exists(csv_path):
        try:
            df = pd.read_csv(csv_path)
            if '日期' in df.columns:
                df['日期'] = pd.to_datetime(df['日期'], errors='coerce')
                df = df.dropna(subset=['日期']).sort_values('日期').reset_index(drop=True)
            return df
        except Exception as e:
            pass
    
    if os.path.exists(json_path):
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            df = pd.DataFrame(data)
            if '日期' in df.columns:
                df['日期'] = pd.to_datetime(df['日期'], errors='coerce')
                df = df.dropna(subset=['日期']).sort_values('日期').reset_index(drop=True)
            return df
        except Exception:
            pass
    
    return None


def load_daily_kline_from_cache(code):
    """从本地缓存加载日K线数据"""
    cache_dir = 'cache'
    csv_path = os.path.join(cache_dir, 'daily_kline', f'{code}.csv')
    json_path = os.path.join(cache_dir, 'daily_kline', f'{code}.json')
    if os.path.exists(csv_path):
        try:
            df = pd.read_csv(csv_path)
            if '日期' in df.columns:
                df['日期'] = pd.to_datetime(df['日期'], errors='coerce')
                df = df.dropna(subset=['日期']).sort_values('日期').reset_index(drop=True)
            return df
        except Exception:
            pass
    if os.path.exists(json_path):
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            df = pd.DataFrame(data)
            if '日期' in df.columns:
                df['日期'] = pd.to_datetime(df['日期'], errors='coerce')
                df = df.dropna(subset=['日期']).sort_values('日期').reset_index(drop=True)
            return df
        except Exception:
            pass
    return None


def extract_all_features(weekly_df, start_idx, lookback_weeks=40, stock_code=None):
    """提取所有特征（含买点前两月内曾涨停）"""
    if start_idx >= len(weekly_df) or start_idx < 20:
        return None
    
    actual_lookback = min(lookback_weeks, start_idx)
    before_start_df = weekly_df.iloc[start_idx - actual_lookback:start_idx].copy()
    
    volume_col = '周成交量' if '周成交量' in weekly_df.columns else '成交量'
    if volume_col not in weekly_df.columns:
        return None

    start_price = float(weekly_df.iloc[start_idx]['收盘'])
    start_volume = float(weekly_df.iloc[start_idx][volume_col])
    
    features = {}
    
    # 1. 成交量特征
    if len(before_start_df) >= 10:
        avg_volume_10 = float(before_start_df[volume_col].tail(10).mean())
        if avg_volume_10 > 0:
            features['起点当周量比'] = round(start_volume / avg_volume_10, 2)
        features['起点前10周均量'] = round(float(before_start_df[volume_col].tail(10).mean()), 0)
    
    if len(before_start_df) >= 20:
        features['起点前20周均量'] = round(float(before_start_df[volume_col].tail(20).mean()), 0)
        vol_10 = float(before_start_df[volume_col].tail(10).mean())
        vol_20 = float(before_start_df[volume_col].tail(20).mean())
        if vol_20 > 0:
            features['成交量萎缩程度'] = round(vol_10 / vol_20, 2)
    
    if len(before_start_df) >= 40:
        features['起点前40周均量'] = round(float(before_start_df[volume_col].tail(40).mean()), 0)
        max_volume_idx = before_start_df[volume_col].tail(40).idxmax()
        max_volume = float(before_start_df.loc[max_volume_idx, volume_col])
        max_volume_low = float(before_start_df.loc[max_volume_idx, '最低'])
        features['起点前40周最大量'] = round(max_volume, 0)
        features['最大量对应最低价'] = round(max_volume_low, 2)
        if max_volume_low > 0:
            features['是否跌破最大量最低价'] = 1 if start_price < max_volume_low else 0
            features['相对最大量最低价跌幅'] = round((max_volume_low - start_price) / max_volume_low * 100, 2) if start_price < max_volume_low else 0
        if max_volume > 0:
            features['起点量比最大量'] = round(start_volume / max_volume, 2)
    
    # 2. 价格特征
    if len(before_start_df) >= 20:
        max_price_20 = float(before_start_df['最高'].tail(20).max())
        min_price_20 = float(before_start_df['最低'].tail(20).min())
        if max_price_20 > min_price_20:
            features['价格相对位置'] = round((start_price - min_price_20) / (max_price_20 - min_price_20) * 100, 2)
            features['相对高点跌幅'] = round((max_price_20 - start_price) / max_price_20 * 100, 2)
        features['起点前20周最高价'] = round(max_price_20, 2)
        features['起点前20周最低价'] = round(min_price_20, 2)
        features['起点前20周波动幅度'] = round((max_price_20 - min_price_20) / min_price_20 * 100, 2) if min_price_20 > 0 else 0
    
    if len(before_start_df) >= 40:
        features['起点前40周最高价'] = round(float(before_start_df['最高'].tail(40).max()), 2)
        features['起点前40周最低价'] = round(float(before_start_df['最低'].tail(40).min()), 2)
    
    # 3. 均线特征
    if len(before_start_df) >= 5:
        ma5 = float(before_start_df['收盘'].tail(5).mean())
        features['价格相对MA5'] = round((start_price - ma5) / ma5 * 100, 2) if ma5 > 0 else 0
        features['MA5值'] = round(ma5, 2)
    
    if len(before_start_df) >= 10:
        ma10 = float(before_start_df['收盘'].tail(10).mean())
        features['价格相对MA10'] = round((start_price - ma10) / ma10 * 100, 2) if ma10 > 0 else 0
        features['MA10值'] = round(ma10, 2)
        features['起点前10周波动率'] = round(float((before_start_df['收盘'].tail(10).max() - before_start_df['收盘'].tail(10).min()) / before_start_df['收盘'].tail(10).min() * 100), 2)
    
    if len(before_start_df) >= 20:
        ma20 = float(before_start_df['收盘'].tail(20).mean())
        features['价格相对MA20'] = round((start_price - ma20) / ma20 * 100, 2) if ma20 > 0 else 0
        features['MA20值'] = round(ma20, 2)
        ma20_recent = float(before_start_df['收盘'].tail(5).mean())
        ma20_earlier = float(before_start_df['收盘'].iloc[-20:-15].mean()) if len(before_start_df) >= 20 else ma20
        if ma20_earlier > 0:
            features['MA20斜率'] = round((ma20_recent - ma20_earlier) / ma20_earlier * 100, 2)
        features['起点前20周波动率'] = round(float((before_start_df['收盘'].tail(20).max() - before_start_df['收盘'].tail(20).min()) / before_start_df['收盘'].tail(20).min() * 100), 2)
    
    if len(before_start_df) >= 40:
        ma40 = float(before_start_df['收盘'].tail(40).mean())
        features['价格相对MA40'] = round((start_price - ma40) / ma40 * 100, 2) if ma40 > 0 else 0
        features['MA40值'] = round(ma40, 2)
    
    # 4. 量价配合特征
    if len(before_start_df) >= 20:
        price_changes = before_start_df['收盘'].tail(20).pct_change().dropna()
        volume_changes = before_start_df[volume_col].tail(20).pct_change().dropna()
        if len(price_changes) > 5 and len(volume_changes) > 5:
            min_len = min(len(price_changes), len(volume_changes))
            correlation = price_changes.tail(min_len).corr(volume_changes.tail(min_len))
            if pd.notna(correlation):
                features['起点前20周量价相关系数'] = round(float(correlation), 3)
    
    if start_idx > 0:
        prev_price = float(weekly_df.iloc[start_idx - 1]['收盘'])
        prev_volume = float(weekly_df.iloc[start_idx - 1][volume_col])
        features['起点当周价涨'] = 1 if start_price > prev_price else 0
        features['起点当周量增'] = 1 if start_volume > prev_volume else 0
        features['起点当周价涨量增'] = 1 if (start_price > prev_price and start_volume > prev_volume) else 0
    
    features['起点价格'] = round(start_price, 2)
    
    # 5. MACD
    if len(before_start_df) >= 26:
        try:
            prices = before_start_df['收盘']
            ema12 = prices.ewm(span=12, adjust=False).mean()
            ema26 = prices.ewm(span=26, adjust=False).mean()
            dif = ema12 - ema26
            dea = dif.ewm(span=9, adjust=False).mean()
            macd = (dif - dea) * 2
            
            features['MACD_DIF'] = round(float(dif.iloc[-1]), 4)
            features['MACD_DEA'] = round(float(dea.iloc[-1]), 4)
            features['MACD柱'] = round(float(macd.iloc[-1]), 4)
            
            if len(dif) >= 2:
                prev_diff = dif.iloc[-2] - dea.iloc[-2]
                curr_diff = dif.iloc[-1] - dea.iloc[-1]
                features['MACD金叉'] = 1 if (prev_diff < 0 and curr_diff >= 0) else 0
                features['MACD零轴上方'] = 1 if dif.iloc[-1] > 0 else 0
        except Exception:
            pass
    
    # 6. RSI
    if len(before_start_df) >= 14:
        try:
            prices = before_start_df['收盘']
            delta = prices.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / (loss + 0.0001)
            rsi = 100 - (100 / (1 + rs))
            
            features['RSI'] = round(float(rsi.iloc[-1]), 2)
            features['RSI超卖'] = 1 if rsi.iloc[-1] < 30 else 0
            features['RSI强势区'] = 1 if 50 < rsi.iloc[-1] < 70 else 0
        except Exception:
            pass
    
    # 7. KDJ
    if len(before_start_df) >= 9:
        try:
            high_9 = before_start_df['最高'].rolling(window=9).max()
            low_9 = before_start_df['最低'].rolling(window=9).min()
            rsv = (before_start_df['收盘'] - low_9) / (high_9 - low_9 + 0.0001) * 100
            
            k_values, d_values = [], []
            k, d = 50, 50
            for r in rsv.dropna():
                k = 2/3 * k + 1/3 * r
                d = 2/3 * d + 1/3 * k
                k_values.append(k)
                d_values.append(d)
            
            if k_values:
                features['KDJ_K'] = round(k_values[-1], 2)
                features['KDJ_D'] = round(d_values[-1], 2)
                features['KDJ_J'] = round(3 * k_values[-1] - 2 * d_values[-1], 2)
                features['KDJ超卖'] = 1 if k_values[-1] < 20 and d_values[-1] < 20 else 0
        except Exception:
            pass
    
    # 8. OBV
    if len(before_start_df) >= 10:
        try:
            obv = [0]
            prices = before_start_df['收盘'].values
            volumes = before_start_df[volume_col].values
            for i in range(1, len(prices)):
                if prices[i] > prices[i-1]:
                    obv.append(obv[-1] + volumes[i])
                elif prices[i] < prices[i-1]:
                    obv.append(obv[-1] - volumes[i])
                else:
                    obv.append(obv[-1])
            
            obv_series = pd.Series(obv)
            if len(obv_series) >= 10:
                obv_recent = obv_series.tail(10)
                obv_slope = (obv_recent.iloc[-1] - obv_recent.iloc[0]) / (abs(obv_recent.iloc[0]) + 1) * 100
                features['OBV趋势'] = round(obv_slope, 2)
            
            if len(obv_series) >= 20:
                features['OBV创新高'] = 1 if obv_series.iloc[-1] >= obv_series.tail(20).max() * 0.95 else 0
        except Exception:
            pass
    
    # 9. 均线粘合度
    if len(before_start_df) >= 20:
        try:
            ma5 = float(before_start_df['收盘'].tail(5).mean())
            ma10 = float(before_start_df['收盘'].tail(10).mean())
            ma20 = float(before_start_df['收盘'].tail(20).mean())
            avg_ma = (ma5 + ma10 + ma20) / 3
            if avg_ma > 0:
                dispersion = (abs(ma5-avg_ma) + abs(ma10-avg_ma) + abs(ma20-avg_ma)) / avg_ma * 100
                features['均线粘合度'] = round(dispersion, 2)
            features['均线多头排列'] = 1 if (ma5 > ma10 > ma20) else 0
        except Exception:
            pass
    
    # 10. 布林带
    if len(before_start_df) >= 20:
        try:
            prices = before_start_df['收盘']
            ma20 = prices.rolling(window=20).mean()
            std20 = prices.rolling(window=20).std()
            upper = ma20 + 2 * std20
            lower = ma20 - 2 * std20
            
            bb_width = ((upper.iloc[-1] - lower.iloc[-1]) / ma20.iloc[-1] * 100) if ma20.iloc[-1] > 0 else 0
            features['布林带宽度'] = round(bb_width, 2)
            
            bb_position = ((start_price - lower.iloc[-1]) / (upper.iloc[-1] - lower.iloc[-1] + 0.01) * 100)
            features['布林带位置'] = round(bb_position, 2)
            
            if len(ma20) >= 10 and ma20.iloc[-10] > 0 and pd.notna(upper.iloc[-10]) and pd.notna(lower.iloc[-10]):
                bb_width_10 = (upper.iloc[-10] - lower.iloc[-10]) / ma20.iloc[-10] * 100
                features['布林带收窄'] = 1 if bb_width < bb_width_10 * 0.8 else 0
        except Exception:
            pass
    
    # 11. 筹码集中度
    if len(before_start_df) >= 20:
        try:
            total_vol = before_start_df[volume_col].tail(20).sum()
            if total_vol > 0:
                weighted_price = (before_start_df['收盘'].tail(20) * before_start_df[volume_col].tail(20)).sum() / total_vol
                features['成本偏离度'] = round((start_price - weighted_price) / weighted_price * 100, 2)
                
                price_std = np.sqrt(((before_start_df['收盘'].tail(20) - weighted_price) ** 2 * before_start_df[volume_col].tail(20)).sum() / total_vol)
                features['筹码集中度'] = round(price_std / weighted_price * 100, 2) if weighted_price > 0 else 0
        except Exception:
            pass
    
    # 12. 突破特征
    if len(before_start_df) >= 20:
        try:
            high_20 = before_start_df['最高'].tail(20).max()
            features['突破20周高点'] = 1 if start_price > high_20 else 0
            features['接近20周高点'] = 1 if start_price > high_20 * 0.95 else 0
        except Exception:
            pass
    
    if len(before_start_df) >= 40:
        try:
            high_40 = before_start_df['最高'].tail(40).max()
            features['突破40周高点'] = 1 if start_price > high_40 else 0
        except Exception:
            pass
    
    # 13. 平台整理
    if len(before_start_df) >= 20:
        try:
            sideways_weeks = 0
            for i in range(len(before_start_df) - 20, len(before_start_df)):
                if i >= 0:
                    low_val = before_start_df['最低'].iloc[i]
                    if low_val > 0:
                        range_pct = (before_start_df['最高'].iloc[i] - low_val) / low_val * 100
                        if range_pct < 10:
                            sideways_weeks += 1
            features['平台整理周数'] = sideways_weeks
        except Exception:
            pass
    
    # 14. 买点前最近两个月至少有一个涨停（日线 44 个交易日内涨跌幅>=9.5%）
    if stock_code:
        try:
            bp_date = pd.to_datetime(weekly_df.iloc[start_idx]['日期'])
            daily_df = load_daily_kline_from_cache(stock_code)
            if daily_df is not None and len(daily_df) >= 2 and '收盘' in daily_df.columns and '日期' in daily_df.columns:
                daily_df = daily_df.copy()
                daily_df['日期'] = pd.to_datetime(daily_df['日期'], errors='coerce')
                daily_df = daily_df.dropna(subset=['日期']).sort_values('日期').reset_index(drop=True)
                before_bp = daily_df[daily_df['日期'] < bp_date].tail(44)
                if len(before_bp) >= 2:
                    before_bp = before_bp.copy()
                    before_bp['__pct'] = before_bp['收盘'].pct_change() * 100
                    before_bp['__pct'] = before_bp['__pct'].fillna(0)
                    features['买点前两月内曾涨停'] = 1 if (before_bp['__pct'] >= 9.5).any() else 0
                else:
                    features['买点前两月内曾涨停'] = 0
            else:
                features['买点前两月内曾涨停'] = 0
        except Exception:
            features['买点前两月内曾涨停'] = 0
    
    return features


def calculate_match_score(stock_features, model_features, weights=None):
    """
    计算股票特征与模型特征的匹配度
    使用加权评分系统
    """
    if not stock_features or not model_features:
        return 0.0
    
    # 默认权重（可优化）
    default_weights = {
        # 高权重特征（核心特征）
        '起点当周量比': 2.0,
        '成交量萎缩程度': 1.5,
        '价格相对位置': 2.0,
        '相对高点跌幅': 1.5,
        'MA20斜率': 1.5,
        '均线多头排列': 2.0,
        'MACD零轴上方': 1.5,
        'RSI': 1.0,
        'OBV趋势': 1.5,
        '均线粘合度': 1.5,
        '布林带宽度': 1.0,
        '筹码集中度': 1.5,
        '买点前两月内曾涨停': 1.5,
        # 中权重特征
        '起点当周价涨量增': 1.0,
        '起点前20周量价相关系数': 1.0,
        # 低权重特征（辅助特征）
        '起点价格': 0.3,
        '起点前10周均量': 0.3,
        '起点前20周均量': 0.3,
        '起点前40周均量': 0.3,
        'MA5值': 0.3,
        'MA10值': 0.3,
        'MA20值': 0.3,
        'MA40值': 0.3,
    }
    
    if weights:
        default_weights.update(weights)
    
    total_score = 0.0
    total_weight = 0.0
    matched_features = 0
    
    for feature_name, feature_stats in model_features.items():
        if feature_name not in stock_features:
            continue
        
        stock_value = stock_features[feature_name]
        mean_val = feature_stats.get('均值', 0)
        std_val = feature_stats.get('标准差', 1)
        min_val = feature_stats.get('最小值', mean_val)
        max_val = feature_stats.get('最大值', mean_val)
        
        # 获取权重
        weight = default_weights.get(feature_name, 1.0)
        
        # 计算特征得分
        if std_val > 0:
            # Z-score方法
            z_score = abs(stock_value - mean_val) / std_val
            # 使用高斯函数将z-score转换为0-1分数
            # z_score=0 -> score=1, z_score越大 -> score越小
            feature_score = np.exp(-0.5 * (z_score ** 2))
        else:
            # 如果标准差为0，使用区间判断
            if min_val <= stock_value <= max_val:
                feature_score = 1.0
            else:
                # 超出区间的惩罚
                if stock_value < min_val:
                    dist = (min_val - stock_value) / (abs(mean_val) + 1)
                else:
                    dist = (stock_value - max_val) / (abs(mean_val) + 1)
                feature_score = max(0, 1 - dist)
        
        total_score += feature_score * weight
        total_weight += weight
        matched_features += 1
    
    if total_weight > 0:
        return total_score / total_weight
    return 0.0


def optimize_model_for_098(model, sample_stocks, analysis_results, target_score=1.0):
    """
    优化模型参数使所有样本股票匹配度达到目标（默认1.0）
    """
    print(f"\n📊 开始优化模型，目标匹配度: {target_score}")
    
    # 收集所有样本的特征
    all_stock_features = {}
    for code in sample_stocks:
        if code not in analysis_results:
            print(f"  ⚠️ {code} 无分析结果")
            continue
        
        interval = analysis_results[code].get('interval', {})
        start_date = interval.get('起点日期', '')
        if not start_date:
            continue
        
        weekly_df = load_weekly_kline_from_cache(code)
        if weekly_df is None or len(weekly_df) < 50:
            continue
        
        start_ts = pd.to_datetime(start_date)
        start_idx = None
        for i, row in weekly_df.iterrows():
            if row['日期'] <= start_ts:
                start_idx = i
        
        if start_idx is None or start_idx < 20:
            continue
        
        features = extract_all_features(weekly_df, start_idx, stock_code=code)
        if features:
            all_stock_features[code] = features
            print(f"  ✅ {code} 特征提取成功")
    
    if not all_stock_features:
        print("❌ 没有提取到样本特征")
        return (None, [])
    
    # 方法1：扩大容差范围
    # 重新计算统计值，使用更宽松的标准差
    new_common_features = {}
    feature_names = set()
    for features in all_stock_features.values():
        feature_names.update(features.keys())
    
    for fname in feature_names:
        values = []
        for code, features in all_stock_features.items():
            if fname in features and features[fname] is not None:
                val = features[fname]
                if isinstance(val, (int, float)) and not np.isnan(val):
                    values.append(val)
        
        if values:
            mean_val = np.mean(values)
            # 扩大标准差以增加容差；目标1.0时更激进
            mult = 2.5 if target_score >= 1.0 else 1.5
            std_val = np.std(values) * mult if len(values) > 1 else abs(mean_val) * 0.3
            # 确保标准差不会太小
            std_val = max(std_val, abs(mean_val) * 0.1, 0.01)
            
            new_common_features[fname] = {
                '均值': round(float(mean_val), 4),
                '中位数': round(float(np.median(values)), 4),
                '标准差': round(float(std_val), 4),
                '最小值': round(float(min(values)), 4),
                '最大值': round(float(max(values)), 4),
                '样本数': len(values)
            }
    
    # 验证匹配度
    print(f"\n📋 验证优化后的匹配度:")
    all_above_target = True
    scores = []
    for code, features in all_stock_features.items():
        score = calculate_match_score(features, new_common_features)
        scores.append(score)
        status = "✅" if score >= target_score else "❌"
        print(f"  {status} {code}: {score:.4f}")
        if score < target_score:
            all_above_target = False
    
    avg_score = np.mean(scores)
    min_score = min(scores)
    print(f"\n平均匹配度: {avg_score:.4f}")
    print(f"最低匹配度: {min_score:.4f}")
    
    # 如果还有低于目标的，进一步调整
    iteration = 0
    max_iterations = 25 if target_score >= 1.0 else 10
    z_threshold = 1.0 if target_score >= 1.0 else 1.5   # 目标1.0时放宽，扩大更多特征
    expand_factor = 1.5 if target_score >= 1.0 else 1.3
    
    while min_score < target_score and iteration < max_iterations:
        iteration += 1
        print(f"\n🔄 第{iteration}轮优化...")
        
        # 找出匹配度最低的股票
        lowest_code = None
        lowest_score = 1.0
        for code, features in all_stock_features.items():
            score = calculate_match_score(features, new_common_features)
            if score < lowest_score:
                lowest_score = score
                lowest_code = code
        
        if lowest_code is None:
            break
        
        # 分析低分股票的特征偏离
        lowest_features = all_stock_features[lowest_code]
        for fname, fstats in new_common_features.items():
            if fname not in lowest_features:
                continue
            
            stock_val = lowest_features[fname]
            mean_val = fstats['均值']
            std_val = fstats['标准差']
            
            if std_val > 0:
                z_score = abs(stock_val - mean_val) / std_val
                if z_score > z_threshold:  # 偏离较大的特征
                    # 扩大该特征的标准差
                    new_std = std_val * expand_factor
                    new_common_features[fname]['标准差'] = round(new_std, 4)
        
        # 重新计算所有匹配度
        scores = []
        for code, features in all_stock_features.items():
            score = calculate_match_score(features, new_common_features)
            scores.append(score)
        min_score = min(scores)
        avg_score = np.mean(scores)
        print(f"  最低匹配度: {min_score:.4f}, 平均: {avg_score:.4f}")
    
    # 最终验证
    print(f"\n📋 最终匹配度验证:")
    final_scores = []
    for code, features in all_stock_features.items():
        score = calculate_match_score(features, new_common_features)
        final_scores.append((code, score))
        status = "✅" if score >= target_score else "❌"
        print(f"  {status} {code}: {score:.4f}")
    
    avg_score = np.mean([s[1] for s in final_scores])
    min_score = min([s[1] for s in final_scores])
    print(f"\n最终平均匹配度: {avg_score:.4f}")
    print(f"最终最低匹配度: {min_score:.4f}")
    
    return (new_common_features, final_scores)


def main():
    print("=" * 60)
    print("🚀 训练模型使大牛股匹配度达到1.0")
    print("=" * 60)
    
    # 加载当前模型
    with open('trained_model.json', 'r', encoding='utf-8') as f:
        model = json.load(f)
    
    sample_stocks = model['buy_features']['sample_stocks']
    analysis_results = model.get('analysis_results', {})
    
    print(f"样本股票: {sample_stocks}")
    print(f"当前特征数量: {len(model['buy_features']['common_features'])}")
    
    # 优化模型
    optimized_features, final_scores = optimize_model_for_098(model, sample_stocks, analysis_results)
    
    if optimized_features:
        # 更新模型
        model['buy_features']['common_features'] = optimized_features
        model['trained_at'] = datetime.now().isoformat()
        model['optimization_target'] = 1.0
        
        # 保存模型
        with open('trained_model.json', 'w', encoding='utf-8') as f:
            json.dump(model, f, ensure_ascii=False, indent=2)
        
        print(f"\n✅ 模型已保存到 trained_model.json")
        print(f"   特征总数: {len(optimized_features)}")
        
        # 展示大牛股匹配度一览（每次改完模型后）
        name_by_code = {s['代码']: s['名称'] for s in model.get('bull_stocks', [])}
        target = 1.0
        print(f"\n{'='*60}")
        print("📋 模型已更新 · 大牛股匹配度一览")
        print(f"{'='*60}")
        print(f"{'代码':<10} {'名称':<12} {'匹配度':<10} {'达标(≥1.0)':<12}")
        print("-" * 50)
        for code, score in final_scores:
            name = name_by_code.get(code, code)
            ok = "✅" if score >= target else "❌"
            print(f"{code:<10} {name:<12} {score:.4f}     {ok:<12}")
        print(f"{'='*60}\n")
    else:
        print("❌ 优化失败")


if __name__ == '__main__':
    main()
