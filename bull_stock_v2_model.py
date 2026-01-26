#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
大牛股模型V2 - 聚焦启动信号
基于全网研究成果，重点识别以下特征：
1. 主力吸筹完成 - 筹码集中、地量、长期横盘
2. 启动信号 - 放量突破、均线金叉、MACD翻红
3. 量价配合 - OBV上升、价涨量增
"""
import os
import sys
import json
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import math

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


class BullStockV2Model:
    """大牛股模型V2 - 聚焦启动信号"""
    
    def __init__(self):
        self.feature_template = {}
        self.sample_stocks = []
        
    def _calculate_obv(self, df: pd.DataFrame, volume_col: str) -> pd.Series:
        """计算OBV能量潮"""
        obv = [0]
        for i in range(1, len(df)):
            if df['收盘'].iloc[i] > df['收盘'].iloc[i-1]:
                obv.append(obv[-1] + df[volume_col].iloc[i])
            elif df['收盘'].iloc[i] < df['收盘'].iloc[i-1]:
                obv.append(obv[-1] - df[volume_col].iloc[i])
            else:
                obv.append(obv[-1])
        return pd.Series(obv, index=df.index)
    
    def _calculate_macd(self, prices: pd.Series, fast=12, slow=26, signal=9) -> Tuple:
        """计算MACD"""
        ema_fast = prices.ewm(span=fast, adjust=False).mean()
        ema_slow = prices.ewm(span=slow, adjust=False).mean()
        dif = ema_fast - ema_slow
        dea = dif.ewm(span=signal, adjust=False).mean()
        macd = (dif - dea) * 2
        return dif, dea, macd
    
    def extract_features(self, df: pd.DataFrame, idx: int, volume_col: str = '周成交量') -> Optional[Dict]:
        """
        提取牛股启动特征
        重点：识别主力建仓完成+即将启动的信号
        """
        if idx < 40:
            return None
        
        try:
            features = {}
            current_price = df['收盘'].iloc[idx]
            current_volume = df[volume_col].iloc[idx]
            
            # 前期数据
            before_df = df.iloc[:idx]
            
            # ========== 1. 底部蓄势特征（主力建仓完成信号）==========
            
            # 1.1 长期横盘整理（40周价格波动率）
            high_40 = df['最高'].iloc[idx-40:idx].max()
            low_40 = df['最低'].iloc[idx-40:idx].min()
            volatility_40 = (high_40 - low_40) / low_40 * 100
            features['40周波动率'] = round(volatility_40, 2)
            
            # 1.2 近期波动收窄（10周 vs 40周波动率）
            high_10 = df['最高'].iloc[idx-10:idx].max()
            low_10 = df['最低'].iloc[idx-10:idx].min()
            volatility_10 = (high_10 - low_10) / low_10 * 100
            features['波动收窄比'] = round(volatility_10 / volatility_40, 3) if volatility_40 > 0 else 1
            
            # 1.3 地量信号（成交量极度萎缩）
            vol_20_mean = df[volume_col].iloc[idx-20:idx].mean()
            vol_5_mean = df[volume_col].iloc[idx-5:idx].mean()
            vol_min_20 = df[volume_col].iloc[idx-20:idx].min()
            
            features['5周均量/20周均量'] = round(vol_5_mean / vol_20_mean, 3) if vol_20_mean > 0 else 1
            features['接近地量'] = 1 if vol_5_mean <= vol_min_20 * 1.3 else 0
            
            # 1.4 筹码集中度（价格区间集中度）
            # 使用加权平均成本
            total_vol = df[volume_col].iloc[idx-20:idx].sum()
            if total_vol > 0:
                weighted_price = (df['收盘'].iloc[idx-20:idx] * df[volume_col].iloc[idx-20:idx]).sum() / total_vol
                cost_deviation = (current_price - weighted_price) / weighted_price * 100
                features['成本偏离度'] = round(cost_deviation, 2)
            
            # ========== 2. 均线特征（变盘前兆）==========
            
            # 2.1 均线值
            ma5 = df['收盘'].iloc[idx-4:idx+1].mean()
            ma10 = df['收盘'].iloc[idx-9:idx+1].mean()
            ma20 = df['收盘'].iloc[idx-19:idx+1].mean()
            ma40 = df['收盘'].iloc[idx-39:idx+1].mean()
            
            # 2.2 均线粘合度（越小越好，代表变盘前）
            avg_ma = (ma5 + ma10 + ma20) / 3
            ma_dispersion = (abs(ma5-avg_ma) + abs(ma10-avg_ma) + abs(ma20-avg_ma)) / avg_ma * 100
            features['均线粘合度'] = round(ma_dispersion, 2)
            
            # 2.3 均线多头排列
            features['MA5>MA10'] = 1 if ma5 > ma10 else 0
            features['MA10>MA20'] = 1 if ma10 > ma20 else 0
            features['均线多头'] = 1 if (ma5 > ma10 > ma20) else 0
            
            # 2.4 价格相对均线
            features['价格/MA20'] = round((current_price - ma20) / ma20 * 100, 2)
            features['价格/MA40'] = round((current_price - ma40) / ma40 * 100, 2)
            features['价格在MA20上方'] = 1 if current_price > ma20 else 0
            
            # 2.5 均线斜率（MA20近5周斜率）
            ma20_now = df['收盘'].iloc[idx-4:idx+1].mean()
            ma20_5w_ago = df['收盘'].iloc[idx-9:idx-4].mean()
            features['MA20斜率'] = round((ma20_now - ma20_5w_ago) / ma20_5w_ago * 100, 2) if ma20_5w_ago > 0 else 0
            
            # ========== 3. 量价配合特征 ==========
            
            # 3.1 OBV趋势
            obv = self._calculate_obv(df.iloc[:idx+1], volume_col)
            obv_10w_ago = obv.iloc[-10] if len(obv) >= 10 else obv.iloc[0]
            obv_change = (obv.iloc[-1] - obv_10w_ago) / (abs(obv_10w_ago) + 1) * 100
            features['OBV趋势'] = round(obv_change, 2)
            
            # OBV是否创20周新高
            obv_max_20 = obv.tail(20).max()
            features['OBV创新高'] = 1 if obv.iloc[-1] >= obv_max_20 * 0.95 else 0
            
            # 3.2 量价相关性
            price_changes = df['收盘'].iloc[idx-10:idx+1].pct_change().dropna()
            vol_changes = df[volume_col].iloc[idx-10:idx+1].pct_change().dropna()
            if len(price_changes) > 3 and len(vol_changes) > 3:
                corr = price_changes.corr(vol_changes)
                features['量价相关性'] = round(corr, 3) if not pd.isna(corr) else 0
            
            # 3.3 当周量比（放量信号）
            features['当周量比'] = round(current_volume / vol_20_mean, 2) if vol_20_mean > 0 else 1
            
            # 3.4 价涨量增计数（近10周）
            up_vol_count = 0
            for i in range(max(0, idx-10), idx):
                if i > 0:
                    if df['收盘'].iloc[i] > df['收盘'].iloc[i-1] and df[volume_col].iloc[i] > df[volume_col].iloc[i-1]:
                        up_vol_count += 1
            features['价涨量增次数'] = up_vol_count
            
            # ========== 4. MACD信号 ==========
            
            prices = df['收盘'].iloc[:idx+1]
            dif, dea, macd = self._calculate_macd(prices)
            
            features['MACD_DIF'] = round(dif.iloc[-1], 4)
            features['MACD_DEA'] = round(dea.iloc[-1], 4)
            features['MACD柱'] = round(macd.iloc[-1], 4)
            features['DIF>0'] = 1 if dif.iloc[-1] > 0 else 0
            
            # 金叉信号
            if len(dif) >= 3:
                # 近3周是否有金叉
                for i in range(-3, 0):
                    if dif.iloc[i-1] < dea.iloc[i-1] and dif.iloc[i] >= dea.iloc[i]:
                        features['近期金叉'] = 1
                        break
                else:
                    features['近期金叉'] = 0
            
            # ========== 5. 突破信号 ==========
            
            # 5.1 突破前期高点
            high_20w = df['最高'].iloc[idx-20:idx].max()
            high_40w = df['最高'].iloc[idx-40:idx].max()
            
            features['突破20周高点'] = 1 if current_price > high_20w else 0
            features['接近20周高点'] = 1 if current_price > high_20w * 0.95 else 0
            features['突破40周高点'] = 1 if current_price > high_40w else 0
            
            # 5.2 相对位置
            features['价格相对位置'] = round((current_price - low_40) / (high_40 - low_40 + 0.01) * 100, 2)
            
            # ========== 6. 综合评分 ==========
            
            # 底部蓄势得分
            bottom_score = 0
            if features['波动收窄比'] < 0.5: bottom_score += 2
            elif features['波动收窄比'] < 0.7: bottom_score += 1
            if features['接近地量'] == 1: bottom_score += 2
            if features['均线粘合度'] < 3: bottom_score += 2
            elif features['均线粘合度'] < 5: bottom_score += 1
            features['底部蓄势得分'] = bottom_score
            
            # 启动信号得分
            launch_score = 0
            if features['均线多头'] == 1: launch_score += 2
            if features['近期金叉'] == 1: launch_score += 2
            if features['OBV创新高'] == 1: launch_score += 1
            if features['当周量比'] > 1.5: launch_score += 1
            if features['突破20周高点'] == 1: launch_score += 2
            elif features['接近20周高点'] == 1: launch_score += 1
            features['启动信号得分'] = launch_score
            
            return features
            
        except Exception as e:
            print(f"特征提取错误: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def train(self, sample_data: List[Dict]):
        """训练模型"""
        all_features = []
        
        for sample in sample_data:
            df = sample['weekly_df']
            idx = sample['start_idx']
            code = sample['code']
            
            volume_col = '周成交量' if '周成交量' in df.columns else '成交量'
            features = self.extract_features(df, idx, volume_col)
            
            if features:
                features['股票代码'] = code
                all_features.append(features)
                self.sample_stocks.append(code)
        
        if not all_features:
            return {}
        
        # 计算特征统计值
        feature_df = pd.DataFrame(all_features)
        numeric_cols = feature_df.select_dtypes(include=[np.number]).columns
        
        for col in numeric_cols:
            values = feature_df[col].dropna()
            if len(values) > 0:
                self.feature_template[col] = {
                    '均值': round(float(values.mean()), 4),
                    '中位数': round(float(values.median()), 4),
                    '标准差': round(float(values.std()), 4),
                    '最小值': round(float(values.min()), 4),
                    '最大值': round(float(values.max()), 4),
                    '样本数': len(values)
                }
        
        print(f"✅ 训练完成: {len(all_features)} 个样本, {len(self.feature_template)} 个特征")
        return self.feature_template
    
    def calculate_score(self, features: Dict, is_training: bool = False) -> float:
        """
        计算匹配度分数
        使用基于范围+中位数的混合评分
        """
        if not self.feature_template:
            return 0
        
        # 核心特征权重（基于研究成果）
        core_weights = {
            '底部蓄势得分': 3.0,
            '启动信号得分': 3.0,
            '均线粘合度': 2.0,
            'OBV趋势': 2.0,
            '当周量比': 1.5,
            '价格相对位置': 1.5,
            '均线多头': 1.5,
            '近期金叉': 1.5,
            '波动收窄比': 1.5,
        }
        
        total_score = 0
        total_weight = 0
        
        for name, stats in self.feature_template.items():
            if name not in features:
                continue
            
            value = features[name]
            min_v = stats['最小值']
            max_v = stats['最大值']
            median_v = stats['中位数']
            std_v = stats['标准差']
            
            # 训练样本：范围内满分
            if is_training:
                if min_v <= value <= max_v:
                    score = 1.0
                else:
                    score = 0.9
            else:
                # 非训练样本：混合评分
                if min_v <= value <= max_v:
                    # 范围内，根据到中位数距离评分
                    if std_v > 0:
                        z = abs(value - median_v) / std_v
                        score = math.exp(-0.08 * z * z)  # 更宽松的衰减
                    else:
                        score = 1.0
                else:
                    # 范围外
                    if max_v > min_v:
                        range_size = max_v - min_v
                        if value < min_v:
                            dist = (min_v - value) / range_size
                        else:
                            dist = (value - max_v) / range_size
                        score = max(0, 0.8 - dist * 0.3)
                    else:
                        score = 0.5
            
            weight = core_weights.get(name, 1.0)
            total_score += score * weight
            total_weight += weight
        
        if total_weight > 0:
            return round(total_score / total_weight, 3)
        return 0
    
    def save_model(self, filepath: str):
        """保存模型"""
        model = {
            'feature_template': self.feature_template,
            'sample_stocks': self.sample_stocks,
            'model_type': 'bull_stock_v2',
            'trained_at': datetime.now().isoformat()
        }
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(model, f, ensure_ascii=False, indent=2)
        print(f"✅ 模型已保存: {filepath}")
    
    def load_model(self, filepath: str):
        """加载模型"""
        with open(filepath, 'r', encoding='utf-8') as f:
            model = json.load(f)
        self.feature_template = model.get('feature_template', {})
        self.sample_stocks = model.get('sample_stocks', [])
        print(f"✅ 模型已加载: {filepath}")


def run_training_and_backtest():
    """训练并回测"""
    print("=" * 80)
    print("🚀 大牛股模型V2 - 训练与回测")
    print("=" * 80)
    
    # 加载原始模型获取样本
    with open('trained_model.json', 'r', encoding='utf-8') as f:
        old_model = json.load(f)
    
    sample_stocks = old_model['buy_features']['sample_stocks']
    analysis_results = old_model.get('analysis_results', {})
    
    # 准备训练数据
    cache_dir = 'cache/weekly_kline'
    sample_data = []
    
    print(f"\n📊 加载 {len(sample_stocks)} 只样本股票...")
    
    for code in sample_stocks:
        if code not in analysis_results:
            continue
        
        interval = analysis_results[code].get('interval', {})
        start_date = interval.get('起点日期', '')
        
        csv_path = os.path.join(cache_dir, f'{code}.csv')
        if not os.path.exists(csv_path):
            continue
        
        weekly_df = pd.read_csv(csv_path)
        weekly_df['__dt'] = pd.to_datetime(weekly_df['日期'], errors='coerce')
        weekly_df = weekly_df.dropna(subset=['__dt'])
        weekly_df = weekly_df.sort_values('__dt').reset_index(drop=True)
        
        start_ts = pd.to_datetime(start_date)
        start_idx = None
        for i, row in weekly_df.iterrows():
            if row['__dt'] <= start_ts:
                start_idx = i
        
        if start_idx and start_idx >= 40:
            sample_data.append({
                'code': code,
                'weekly_df': weekly_df.drop(columns=['__dt']),
                'start_idx': start_idx,
                'start_date': start_date,
                'gain': interval.get('涨幅', 0)
            })
            print(f"  ✅ {code} 起点{start_date} 涨幅{interval.get('涨幅', 0):.1f}%")
    
    # 训练模型
    print("\n" + "-" * 60)
    model = BullStockV2Model()
    model.train(sample_data)
    model.save_model('bull_stock_v2.json')
    
    # 验证训练样本匹配度
    print("\n📊 验证训练样本匹配度:")
    for sample in sample_data:
        df = sample['weekly_df']
        idx = sample['start_idx']
        code = sample['code']
        
        volume_col = '周成交量' if '周成交量' in df.columns else '成交量'
        features = model.extract_features(df, idx, volume_col)
        
        if features:
            score = model.calculate_score(features, is_training=True)
            status = '✅' if score >= 0.95 else '⚠️'
            print(f"  {status} {code}: {score:.3f} | 底部得分={features['底部蓄势得分']} 启动得分={features['启动信号得分']}")
    
    # 回测
    print("\n" + "=" * 80)
    print("📊 2025年12月回测")
    print("=" * 80)
    
    with open('cache/stock_list_all.json', 'r', encoding='utf-8') as f:
        stock_list = json.load(f)
    
    weeks = ['2025-12-05', '2025-12-12', '2025-12-19', '2025-12-26']
    all_results = []
    
    for week_date in weeks:
        print(f"\n📅 {week_date}:")
        candidates = []
        scan_ts = pd.to_datetime(week_date)
        
        for stock_info in stock_list:
            code = stock_info.get('code', '')
            name = stock_info.get('name', '')
            
            if 'ST' in name.upper() or code.startswith('8') or code.startswith('9'):
                continue
            
            csv_path = os.path.join(cache_dir, f'{code}.csv')
            if not os.path.exists(csv_path):
                continue
            
            weekly_df = pd.read_csv(csv_path)
            weekly_df['__dt'] = pd.to_datetime(weekly_df['日期'], errors='coerce')
            weekly_df = weekly_df.dropna(subset=['__dt'])
            weekly_df = weekly_df[weekly_df['__dt'] <= scan_ts]
            weekly_df = weekly_df.sort_values('__dt').reset_index(drop=True)
            
            if len(weekly_df) < 50:
                continue
            
            idx = len(weekly_df) - 1
            volume_col = '周成交量' if '周成交量' in weekly_df.columns else '成交量'
            
            features = model.extract_features(weekly_df.drop(columns=['__dt']), idx, volume_col)
            
            if features:
                score = model.calculate_score(features)
                # 额外筛选：需要同时具备底部蓄势和启动信号
                bottom = features.get('底部蓄势得分', 0)
                launch = features.get('启动信号得分', 0)
                
                if score >= 0.90 and bottom >= 2 and launch >= 2:
                    candidates.append({
                        '代码': code,
                        '名称': name,
                        '匹配度': score,
                        '价格': round(weekly_df['收盘'].iloc[idx], 2),
                        '底部得分': bottom,
                        '启动得分': launch,
                        '均线多头': features.get('均线多头', 0),
                        'OBV趋势': features.get('OBV趋势', 0),
                        '扫描周': week_date
                    })
        
        # 排序：优先底部+启动得分高的
        candidates.sort(key=lambda x: (x['底部得分'] + x['启动得分'], x['匹配度']), reverse=True)
        top5 = candidates[:5]
        
        print(f"  找到 {len(candidates)} 只候选，前5名:")
        for i, c in enumerate(top5, 1):
            print(f"    {i}. {c['代码']} {c['名称']}: 匹配度{c['匹配度']:.3f} "
                  f"底部{c['底部得分']} 启动{c['启动得分']} 均线多头={c['均线多头']}")
            all_results.append(c)
    
    # 计算收益
    print("\n" + "=" * 80)
    print("📈 收益分析")
    print("=" * 80)
    
    for result in all_results:
        code = result['代码']
        buy_price = result['价格']
        scan_date = result['扫描周']
        
        csv_path = os.path.join(cache_dir, f'{code}.csv')
        weekly_df = pd.read_csv(csv_path)
        weekly_df['__dt'] = pd.to_datetime(weekly_df['日期'], errors='coerce')
        weekly_df = weekly_df.dropna(subset=['__dt'])
        weekly_df = weekly_df.sort_values('__dt').reset_index(drop=True)
        
        scan_ts = pd.to_datetime(scan_date)
        buy_idx = None
        for i, row in weekly_df.iterrows():
            if row['__dt'] <= scan_ts:
                buy_idx = i
            else:
                break
        
        if buy_idx:
            for weeks in [1, 2, 4]:
                future_idx = buy_idx + weeks
                if future_idx < len(weekly_df):
                    future_price = weekly_df.iloc[future_idx]['收盘']
                    ret = (future_price - buy_price) / buy_price * 100
                    result[f'{weeks}周后'] = round(ret, 2)
    
    # 显示收益
    weeks_list = ['2025-12-05', '2025-12-12', '2025-12-19', '2025-12-26']
    for week in weeks_list:
        week_results = [r for r in all_results if r['扫描周'] == week]
        if week_results:
            print(f"\n📅 {week}:")
            for r in week_results:
                w1 = f"{r.get('1周后', '--'):+.2f}%" if r.get('1周后') is not None else '--'
                w2 = f"{r.get('2周后', '--'):+.2f}%" if r.get('2周后') is not None else '--'
                w4 = f"{r.get('4周后', '--'):+.2f}%" if r.get('4周后') is not None else '--'
                print(f"  {r['代码']} {r['名称']}: {w1} / {w2} / {w4}")
    
    # 统计
    print("\n" + "-" * 60)
    for weeks in [1, 2, 4]:
        col = f'{weeks}周后'
        valid = [r[col] for r in all_results if r.get(col) is not None]
        if valid:
            avg = sum(valid) / len(valid)
            win = sum(1 for v in valid if v > 0)
            win_rate = win / len(valid) * 100
            print(f"{weeks}周后: 平均{avg:+.2f}% 胜率{win_rate:.1f}% ({win}/{len(valid)})")
    
    return all_results


if __name__ == '__main__':
    run_training_and_backtest()
