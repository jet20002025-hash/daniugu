#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
使用本地缓存数据重新训练模型（添加新特征）
"""
import os
import sys
import json
import pandas as pd
import numpy as np
from datetime import datetime

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
            print(f"  ❌ 加载 {code} CSV失败: {e}")
    
    if os.path.exists(json_path):
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            df = pd.DataFrame(data)
            if '日期' in df.columns:
                df['日期'] = pd.to_datetime(df['日期'], errors='coerce')
                df = df.dropna(subset=['日期']).sort_values('日期').reset_index(drop=True)
            return df
        except Exception as e:
            print(f"  ❌ 加载 {code} JSON失败: {e}")
    
    return None


def extract_features_with_new_indicators(weekly_df, start_idx, lookback_weeks=40):
    """
    提取特征（包含新增的技术指标）
    """
    if start_idx >= len(weekly_df) or start_idx < lookback_weeks:
        return None
    
    # 获取起点前的数据
    before_start_df = weekly_df.iloc[start_idx - lookback_weeks:start_idx].copy()
    
    volume_col = '周成交量' if '周成交量' in weekly_df.columns else '成交量'
    if volume_col not in weekly_df.columns:
        return None
    
    start_price = float(weekly_df.iloc[start_idx]['收盘'])
    start_volume = float(weekly_df.iloc[start_idx][volume_col])
    
    features = {}
    
    # ========== 1. 原有成交量特征 ==========
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
    
    # ========== 2. 原有价格特征 ==========
    if len(before_start_df) >= 20:
        max_price_20 = float(before_start_df['最高'].tail(20).max())
        min_price_20 = float(before_start_df['最低'].tail(20).min())
        if max_price_20 > min_price_20:
            features['价格相对位置'] = round((start_price - min_price_20) / (max_price_20 - min_price_20) * 100, 2)
            features['相对高点跌幅'] = round((max_price_20 - start_price) / max_price_20 * 100, 2)
        features['起点前20周最高价'] = round(max_price_20, 2)
        features['起点前20周最低价'] = round(min_price_20, 2)
        features['起点前20周波动幅度'] = round((max_price_20 - min_price_20) / min_price_20 * 100, 2)
    
    if len(before_start_df) >= 40:
        features['起点前40周最高价'] = round(float(before_start_df['最高'].tail(40).max()), 2)
        features['起点前40周最低价'] = round(float(before_start_df['最低'].tail(40).min()), 2)
    
    # ========== 3. 原有均线特征 ==========
    if len(before_start_df) >= 5:
        ma5 = float(before_start_df['收盘'].tail(5).mean())
        features['价格相对MA5'] = round((start_price - ma5) / ma5 * 100, 2) if ma5 > 0 else 0
        features['MA5值'] = round(ma5, 2)
    
    if len(before_start_df) >= 10:
        ma10 = float(before_start_df['收盘'].tail(10).mean())
        features['价格相对MA10'] = round((start_price - ma10) / ma10 * 100, 2) if ma10 > 0 else 0
        features['MA10值'] = round(ma10, 2)
    
    if len(before_start_df) >= 20:
        ma20 = float(before_start_df['收盘'].tail(20).mean())
        features['价格相对MA20'] = round((start_price - ma20) / ma20 * 100, 2) if ma20 > 0 else 0
        features['MA20值'] = round(ma20, 2)
        ma20_recent = float(before_start_df['收盘'].tail(5).mean())
        ma20_earlier = float(before_start_df['收盘'].iloc[-20:-15].mean())
        if ma20_earlier > 0:
            features['MA20斜率'] = round((ma20_recent - ma20_earlier) / ma20_earlier * 100, 2)
    
    if len(before_start_df) >= 40:
        ma40 = float(before_start_df['收盘'].tail(40).mean())
        features['价格相对MA40'] = round((start_price - ma40) / ma40 * 100, 2) if ma40 > 0 else 0
        features['MA40值'] = round(ma40, 2)
    
    # ========== 4. 原有量价配合特征 ==========
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
    
    # ========== 5. 原有波动率特征 ==========
    if len(before_start_df) >= 10:
        recent_prices = before_start_df['收盘'].tail(10)
        features['起点前10周波动率'] = round(float((recent_prices.max() - recent_prices.min()) / recent_prices.min() * 100), 2)
    
    if len(before_start_df) >= 20:
        recent_prices = before_start_df['收盘'].tail(20)
        features['起点前20周波动率'] = round(float((recent_prices.max() - recent_prices.min()) / recent_prices.min() * 100), 2)
    
    features['起点价格'] = round(start_price, 2)
    
    # ========== 6. 新增：MACD指标 ==========
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
    
    # ========== 7. 新增：RSI指标 ==========
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
    
    # ========== 8. 新增：KDJ指标 ==========
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
    
    # ========== 9. 新增：OBV能量潮 ==========
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
    
    # ========== 10. 新增：均线粘合度 ==========
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
    
    # ========== 11. 新增：布林带特征 ==========
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
            
            if len(ma20) >= 10 and ma20.iloc[-10] > 0:
                bb_width_10 = (upper.iloc[-10] - lower.iloc[-10]) / ma20.iloc[-10] * 100
                features['布林带收窄'] = 1 if bb_width < bb_width_10 * 0.8 else 0
        except Exception:
            pass
    
    # ========== 12. 新增：筹码集中度 ==========
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
    
    # ========== 13. 新增：突破特征 ==========
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
    
    # ========== 14. 新增：平台整理时间 ==========
    if len(before_start_df) >= 20:
        try:
            sideways_weeks = 0
            for i in range(len(before_start_df) - 20, len(before_start_df)):
                if i >= 0:
                    range_pct = (before_start_df['最高'].iloc[i] - before_start_df['最低'].iloc[i]) / before_start_df['最低'].iloc[i] * 100
                    if range_pct < 10:
                        sideways_weeks += 1
            features['平台整理周数'] = sideways_weeks
        except Exception:
            pass
    
    return features


def main():
    print("=" * 60)
    print("🚀 使用本地数据重新训练模型（添加新特征）")
    print("=" * 60)
    
    # 加载当前模型
    with open('trained_model.json', 'r', encoding='utf-8') as f:
        old_model = json.load(f)
    
    sample_stocks = old_model['buy_features']['sample_stocks']
    analysis_results = old_model.get('analysis_results', {})
    
    print(f"样本股票: {sample_stocks}")
    print(f"旧特征数量: {len(old_model['buy_features']['common_features'])}")
    print()
    
    # 提取所有样本的特征
    all_features = []
    
    for code in sample_stocks:
        print(f"处理 {code}...")
        
        if code not in analysis_results:
            print(f"  ⚠️ {code} 无分析结果，跳过")
            continue
        
        interval = analysis_results[code].get('interval', {})
        start_date = interval.get('起点日期', '')
        
        if not start_date:
            print(f"  ⚠️ {code} 无起点日期，跳过")
            continue
        
        # 加载周K线数据
        weekly_df = load_weekly_kline_from_cache(code)
        if weekly_df is None or len(weekly_df) < 50:
            print(f"  ⚠️ {code} 数据不足，跳过")
            continue
        
        # 找到起点索引
        start_ts = pd.to_datetime(start_date)
        start_idx = None
        for i, row in weekly_df.iterrows():
            if row['日期'] <= start_ts:
                start_idx = i
        
        if start_idx is None or start_idx < 40:
            print(f"  ⚠️ {code} 找不到起点或数据不足，跳过")
            continue
        
        # 提取特征
        features = extract_features_with_new_indicators(weekly_df, start_idx)
        if features:
            features['股票代码'] = code
            all_features.append(features)
            print(f"  ✅ {code} 特征提取成功，共 {len(features)} 个特征")
        else:
            print(f"  ⚠️ {code} 特征提取失败")
    
    if not all_features:
        print("❌ 没有提取到任何特征")
        return
    
    print(f"\n成功提取 {len(all_features)} 只股票的特征")
    
    # 计算共同特征统计值
    feature_df = pd.DataFrame(all_features)
    numeric_cols = feature_df.select_dtypes(include=[np.number]).columns
    
    common_features = {}
    for col in numeric_cols:
        values = feature_df[col].dropna()
        if len(values) > 0:
            common_features[col] = {
                '均值': round(float(values.mean()), 4),
                '中位数': round(float(values.median()), 4),
                '标准差': round(float(values.std()), 4),
                '最小值': round(float(values.min()), 4),
                '最大值': round(float(values.max()), 4),
                '样本数': len(values)
            }
    
    print(f"\n新特征数量: {len(common_features)}")
    
    # 显示新增特征
    old_features = set(old_model['buy_features']['common_features'].keys())
    new_features = set(common_features.keys()) - old_features
    print(f"\n新增的 {len(new_features)} 个特征:")
    for name in sorted(new_features):
        print(f"  + {name}")
    
    # 更新模型
    old_model['buy_features']['common_features'] = common_features
    old_model['trained_at'] = datetime.now().isoformat()
    
    # 保存模型
    with open('trained_model.json', 'w', encoding='utf-8') as f:
        json.dump(old_model, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ 模型已保存到 trained_model.json")
    print(f"   特征总数: {len(common_features)}")


if __name__ == '__main__':
    main()
