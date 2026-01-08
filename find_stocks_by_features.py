"""
根据涨幅最大区间起点的特征，查找符合条件的股票
"""
from surge_stock_analyzer import SurgeStockAnalyzer
from data_fetcher import DataFetcher
from technical_analysis import TechnicalAnalysis
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys

def find_max_gain_start_point(stock_code, stock_name, days=20):
    """
    找到股票涨幅最大区间的起点
    :param stock_code: 股票代码
    :param stock_name: 股票名称
    :param days: 区间天数（默认20个交易日）
    :return: 起点信息
    """
    print(f"\n正在查找 {stock_code} {stock_name} 的涨幅最大区间起点...")
    
    fetcher = DataFetcher()
    daily_df = fetcher.get_daily_kline(stock_code)
    
    if daily_df is None or len(daily_df) == 0:
        print(f"❌ 无法获取 {stock_code} 的数据")
        return None
    
    if len(daily_df) < days:
        print(f"❌ 数据不足，需要至少 {days} 天数据")
        return None
    
    # 找到涨幅最大的区间（在指定天数内）
    max_gain = 0
    max_gain_start_idx = None
    max_gain_end_idx = None
    max_gain_start_price = None
    max_gain_end_price = None
    max_gain_start_date = None
    max_gain_end_date = None
    
    # 遍历所有可能的起点
    for start_idx in range(len(daily_df) - days + 1):
        start_price = daily_df.iloc[start_idx]['收盘']
        start_date = daily_df.iloc[start_idx]['日期']
        
        # 在起点后的days个交易日内，找到最高价格
        end_idx = min(start_idx + days, len(daily_df))
        window_df = daily_df.iloc[start_idx:end_idx]
        
        # 找到窗口内的最高价格和对应日期
        max_price_idx = window_df['收盘'].idxmax()
        max_price = window_df.loc[max_price_idx, '收盘']
        max_price_date = window_df.loc[max_price_idx, '日期']
        
        # 计算涨幅
        gain = (max_price - start_price) / start_price * 100
        
        if gain > max_gain:
            max_gain = gain
            max_gain_start_idx = start_idx
            max_gain_end_idx = window_df.index.get_loc(max_price_idx) + start_idx
            max_gain_start_price = start_price
            max_gain_end_price = max_price
            max_gain_start_date = start_date
            max_gain_end_date = max_price_date
    
    if max_gain_start_idx is not None:
        print(f"✅ 找到涨幅最大区间:")
        print(f"   起点日期: {max_gain_start_date}")
        print(f"   起点价格: {max_gain_start_price:.2f} 元")
        print(f"   终点日期: {max_gain_end_date}")
        print(f"   终点价格: {max_gain_end_price:.2f} 元")
        print(f"   涨幅: {max_gain:.2f}% (翻{max_gain/100:.2f}倍)")
        
        return {
            '股票代码': stock_code,
            '股票名称': stock_name,
            '起点日期': max_gain_start_date,
            '起点价格': max_gain_start_price,
            '起点索引': max_gain_start_idx,
            '终点日期': max_gain_end_date,
            '终点价格': max_gain_end_price,
            '涨幅': max_gain,
            'daily_df': daily_df  # 返回数据用于后续分析
        }
    else:
        print(f"❌ 未找到涨幅区间")
        return None


def extract_features_at_start_point(daily_df, start_idx):
    """
    提取起点前一年的特征
    :param daily_df: 日K线数据
    :param start_idx: 起点在数据中的索引
    :return: 特征字典
    """
    tech_analysis = TechnicalAnalysis()
    
    # 获取起点前一年的数据（约250个交易日）
    lookback_days = min(250, start_idx)
    if lookback_days < 60:
        print(f"⚠️ 数据不足，只有 {lookback_days} 天，建议至少60天")
    
    before_start_df = daily_df.iloc[start_idx - lookback_days:start_idx]
    current_price = daily_df.iloc[start_idx]['收盘']
    current_date = daily_df.iloc[start_idx]['日期']
    
    if len(before_start_df) == 0:
        return None
    
    features = {}
    
    # 1. 价格特征
    if isinstance(current_price, pd.Series):
        current_price = current_price.iloc[0] if len(current_price) > 0 else 0
    current_price = float(current_price) if pd.notna(current_price) else 0
    features['当前价格'] = current_price
    
    # 2. 均线特征
    if len(before_start_df) >= 5:
        ma5 = before_start_df['收盘'].tail(5).mean()
        if isinstance(ma5, pd.Series):
            ma5 = ma5.iloc[0] if len(ma5) > 0 else 0
        ma5 = float(ma5) if pd.notna(ma5) and ma5 > 0 else 0
        features['价格相对MA5'] = float((current_price - ma5) / ma5 * 100) if ma5 > 0 else 0
    
    if len(before_start_df) >= 10:
        ma10 = before_start_df['收盘'].tail(10).mean()
        if isinstance(ma10, pd.Series):
            ma10 = ma10.iloc[0] if len(ma10) > 0 else 0
        ma10 = float(ma10) if pd.notna(ma10) and ma10 > 0 else 0
        features['价格相对MA10'] = float((current_price - ma10) / ma10 * 100) if ma10 > 0 else 0
    
    if len(before_start_df) >= 20:
        ma20 = before_start_df['收盘'].tail(20).mean()
        if isinstance(ma20, pd.Series):
            ma20 = ma20.iloc[0] if len(ma20) > 0 else 0
        ma20 = float(ma20) if pd.notna(ma20) and ma20 > 0 else 0
        features['价格相对MA20'] = float((current_price - ma20) / ma20 * 100) if ma20 > 0 else 0
    
    if len(before_start_df) >= 60:
        ma60 = before_start_df['收盘'].tail(60).mean()
        if isinstance(ma60, pd.Series):
            ma60 = ma60.iloc[0] if len(ma60) > 0 else 0
        ma60 = float(ma60) if pd.notna(ma60) and ma60 > 0 else 0
        features['价格相对MA60'] = float((current_price - ma60) / ma60 * 100) if ma60 > 0 else 0
    
    # 3. 成交量特征
    if len(before_start_df) >= 20:
        avg_volume = before_start_df['成交量'].tail(20).mean()
        current_volume = daily_df.iloc[start_idx]['成交量']
        # 确保是标量值
        if isinstance(avg_volume, pd.Series):
            avg_volume = avg_volume.iloc[0] if len(avg_volume) > 0 else 0
        if isinstance(current_volume, pd.Series):
            current_volume = current_volume.iloc[0] if len(current_volume) > 0 else 0
        avg_volume = float(avg_volume) if pd.notna(avg_volume) else 0
        current_volume = float(current_volume) if pd.notna(current_volume) else 0
        features['成交量放大倍数'] = float(current_volume / avg_volume) if avg_volume > 0 else 1.0
    
    # 4. 价格变化率（最近30天）
    if len(before_start_df) >= 30:
        price_30_days_ago = before_start_df.iloc[-30]['收盘']
        if isinstance(price_30_days_ago, pd.Series):
            price_30_days_ago = price_30_days_ago.iloc[0] if len(price_30_days_ago) > 0 else 0
        price_30_days_ago = float(price_30_days_ago) if pd.notna(price_30_days_ago) and price_30_days_ago > 0 else 0
        features['价格变化率'] = float((current_price - price_30_days_ago) / price_30_days_ago * 100) if price_30_days_ago > 0 else 0
    
    # 5. 波动率
    if len(before_start_df) >= 20:
        volatility = before_start_df['收盘'].pct_change().std() * 100
        if isinstance(volatility, pd.Series):
            volatility = volatility.iloc[0] if len(volatility) > 0 else 0
        features['波动率'] = float(volatility) if pd.notna(volatility) else 0
    
    # 6. 连续上涨/下跌天数
    price_changes = before_start_df['收盘'].pct_change().dropna()
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
    if '涨跌幅' in before_start_df.columns:
        limit_up_count = (before_start_df['涨跌幅'] >= 9.9).sum()
        if isinstance(limit_up_count, pd.Series):
            limit_up_count = limit_up_count.iloc[0] if len(limit_up_count) > 0 else 0
        features['涨停次数'] = int(limit_up_count) if pd.notna(limit_up_count) else 0
    
    # 8. 量价关系
    if len(before_start_df) >= 10:
        volume_trend = before_start_df['成交量'].tail(5).mean() / before_start_df['成交量'].head(5).mean()
        price_trend = before_start_df['收盘'].tail(5).mean() / before_start_df['收盘'].head(5).mean()
        # 确保是标量值
        if isinstance(volume_trend, pd.Series):
            volume_trend = volume_trend.iloc[0] if len(volume_trend) > 0 else 1
        if isinstance(price_trend, pd.Series):
            price_trend = price_trend.iloc[0] if len(price_trend) > 0 else 1
        volume_trend = float(volume_trend) if pd.notna(volume_trend) else 1
        price_trend = float(price_trend) if pd.notna(price_trend) else 1
        features['量价配合度'] = 1 if (volume_trend > 1 and price_trend > 1) or (volume_trend < 1 and price_trend < 1) else 0
    
    # 9. 均线多头排列
    if len(before_start_df) >= 60:
        ma5 = before_start_df['收盘'].tail(5).mean()
        ma10 = before_start_df['收盘'].tail(10).mean()
        ma20 = before_start_df['收盘'].tail(20).mean()
        ma60 = before_start_df['收盘'].tail(60).mean()
        # 确保是标量值
        for ma in [ma5, ma10, ma20, ma60]:
            if isinstance(ma, pd.Series):
                ma = ma.iloc[0] if len(ma) > 0 else 0
        ma5 = float(ma5) if pd.notna(ma5) else 0
        ma10 = float(ma10) if pd.notna(ma10) else 0
        ma20 = float(ma20) if pd.notna(ma20) else 0
        ma60 = float(ma60) if pd.notna(ma60) else 0
        features['均线多头排列'] = 1 if ma5 > ma10 > ma20 > ma60 else 0
    
    # 10. 距离最低点/最高点
    low_30 = before_start_df['最低'].min()
    high_30 = before_start_df['最高'].max()
    if isinstance(low_30, pd.Series):
        low_30 = low_30.iloc[0] if len(low_30) > 0 else 0
    if isinstance(high_30, pd.Series):
        high_30 = high_30.iloc[0] if len(high_30) > 0 else 0
    low_30 = float(low_30) if pd.notna(low_30) else 0
    high_30 = float(high_30) if pd.notna(high_30) else 0
    features['距离最低点'] = float((current_price - low_30) / current_price * 100) if current_price > 0 else 0
    features['距离最高点'] = float((high_30 - current_price) / current_price * 100) if current_price > 0 else 0
    
    return features


def match_features(target_features, stock_features, tolerance=0.3):
    """
    匹配特征，计算匹配度
    :param target_features: 目标特征（参考股票的特征）
    :param stock_features: 待匹配股票的特征
    :param tolerance: 容差（30%）
    :return: 匹配度（0-1）
    """
    if not target_features or not stock_features:
        return 0
    
    scores = []
    matched_count = 0
    
    for key, target_value in target_features.items():
        if key in stock_features:
            stock_value = stock_features[key]
            
            # 跳过非数值特征
            if not isinstance(target_value, (int, float)) or not isinstance(stock_value, (int, float)):
                continue
            
            # 对于某些特征，使用更宽松的匹配
            # 对于百分比类特征（如价格相对MA），使用相对误差
            # 对于计数类特征（如涨停次数），使用绝对误差
            if '相对' in key or '变化率' in key or '距离' in key:
                # 百分比类特征，使用相对误差
                if abs(target_value) > 0.01:
                    error = abs(stock_value - target_value) / abs(target_value)
                else:
                    error = abs(stock_value - target_value) / 1.0  # 避免除零
            else:
                # 计数类或其他特征，使用绝对误差，归一化
                max_val = max(abs(target_value), abs(stock_value), 1)
                error = abs(stock_value - target_value) / max_val
            
            # 如果误差在容差范围内，得分为1，否则按比例扣分
            if error <= tolerance:
                score = 1.0
                matched_count += 1
            else:
                # 即使超出容差，也给予部分分数
                score = max(0, 1 - (error - tolerance) / (tolerance * 2))
            
            scores.append(score)
    
    # 返回平均匹配度
    return np.mean(scores) if len(scores) > 0 else 0


def scan_all_stocks_by_features(target_features, limit=None, min_match_score=0.6, max_market_cap=60.0):
    """
    根据目标特征扫描所有股票
    :param target_features: 目标特征
    :param limit: 限制扫描数量
    :param min_match_score: 最小匹配度阈值
    :param max_market_cap: 最大市值（亿元），默认60亿
    :return: 符合条件的股票列表
    """
    print(f"\n开始扫描所有股票，查找符合特征的股票...")
    print(f"目标特征: {len(target_features)} 个")
    print(f"最小匹配度: {min_match_score:.1%}")
    print(f"市值约束: ≤ {max_market_cap} 亿元")
    
    fetcher = DataFetcher()
    tech_analysis = TechnicalAnalysis()
    
    # 获取所有股票
    stock_list = fetcher.get_all_stocks()
    if stock_list is None or len(stock_list) == 0:
        print("❌ 无法获取股票列表")
        return []
    
    if limit:
        stock_list = stock_list.head(limit)
    
    candidates = []
    total = len(stock_list)
    
    # 进度条显示
    import sys
    import time
    from datetime import datetime, timedelta
    start_time = time.time()
    
    def print_progress(current, total, found, bar_length=40):
        """打印进度条"""
        percent = current / total if total > 0 else 0
        filled = int(bar_length * percent)
        bar = '█' * filled + '░' * (bar_length - filled)
        
        # 计算已用时间和预估剩余时间
        elapsed = time.time() - start_time
        if current > 0:
            avg_time = elapsed / current
            remaining = (total - current) * avg_time
            elapsed_str = f"{int(elapsed//60)}分{int(elapsed%60)}秒"
            remaining_str = f"{int(remaining//60)}分{int(remaining%60)}秒"
            # 计算预计完成时间
            estimated_end = datetime.now() + timedelta(seconds=remaining)
            end_time_str = estimated_end.strftime("%H:%M:%S")
        else:
            elapsed_str = "0秒"
            remaining_str = "计算中..."
            end_time_str = "--:--:--"
        
        # 当前时间
        current_time_str = datetime.now().strftime("%H:%M:%S")
        
        progress_text = f'📊 扫描进度: [{bar}] {percent*100:.1f}% | {current}/{total} 只 | ✅ 已找到: {found} 只 | ⏱️ 已用: {elapsed_str} | ⏳ 剩余: {remaining_str} | 🕐 当前: {current_time_str} | 🎯 预计完成: {end_time_str}'
        sys.stdout.write('\r' + progress_text)
        sys.stdout.flush()
    
    print(f"\n开始扫描 {total} 只股票...")
    print_progress(0, total, 0)
    
    for idx, row in enumerate(stock_list.itertuples(), 1):
        stock_code = row.code
        stock_name = row.name
        
        # 每只股票都更新进度条（实时显示）
        print_progress(idx, total, len(candidates))
        
        try:
            # 先检查市值约束（提前过滤，节省时间）
            market_cap = fetcher.get_market_cap(stock_code)
            if market_cap is not None and market_cap > max_market_cap:
                continue  # 市值超过限制，跳过
            
            # 获取股票数据
            daily_df = fetcher.get_daily_kline(stock_code)
            if daily_df is None or len(daily_df) < 60:
                continue
            
            # 提取当前时点的特征（使用最新数据）
            current_idx = len(daily_df) - 1
            stock_features = extract_features_at_start_point(daily_df, current_idx)
            
            if stock_features:
                # 计算匹配度
                match_score = match_features(target_features, stock_features)
                
                if match_score >= min_match_score:
                    candidate = {
                        '股票代码': stock_code,
                        '股票名称': stock_name,
                        '匹配度': match_score,
                        '当前价格': daily_df.iloc[-1]['收盘'],
                        '当前日期': str(daily_df.iloc[-1]['日期']),
                        '特征': stock_features
                    }
                    # 添加市值信息
                    if market_cap is not None:
                        candidate['总市值'] = market_cap
                    else:
                        candidate['总市值'] = None  # 无法获取市值
                    
                    candidates.append(candidate)
        except Exception as e:
            continue
    
    # 完成进度条
    print_progress(total, total, len(candidates))
    sys.stdout.write('\n')  # 换行
    sys.stdout.flush()
    
    # 按匹配度排序
    candidates.sort(key=lambda x: x['匹配度'], reverse=True)
    
    print(f"\n✅ 扫描完成，找到 {len(candidates)} 只符合条件的股票")
    return candidates


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("使用方法: python3 find_stocks_by_features.py <股票代码> <股票名称> [扫描数量]")
        print("例如: python3 find_stocks_by_features.py 001331 胜通能源 100")
        sys.exit(1)
    
    stock_code = sys.argv[1]
    stock_name = sys.argv[2]
    if len(sys.argv) > 3:
        try:
            limit = int(sys.argv[3])
        except:
            limit = None
    else:
        limit = None
    
    # 1. 找到涨幅最大区间的起点
    start_point = find_max_gain_start_point(stock_code, stock_name, days=20)
    
    if not start_point:
        print("❌ 未找到起点，退出")
        sys.exit(1)
    
    # 2. 提取起点前的特征
    print(f"\n正在提取起点前的特征...")
    target_features = extract_features_at_start_point(
        start_point['daily_df'], 
        start_point['起点索引']
    )
    
    if not target_features:
        print("❌ 无法提取特征，退出")
        sys.exit(1)
    
    print(f"\n✅ 提取到 {len(target_features)} 个特征:")
    for key, value in target_features.items():
        if isinstance(value, float):
            print(f"   {key}: {value:.2f}")
        else:
            print(f"   {key}: {value}")
    
    # 3. 扫描所有股票
    candidates = scan_all_stocks_by_features(target_features, limit=limit, min_match_score=0.7)
    
    # 4. 显示结果
    print("\n" + "=" * 80)
    print("符合条件的股票（按匹配度排序）:")
    print("=" * 80)
    
    if len(candidates) == 0:
        print("\n未找到符合条件的股票")
        print("建议：")
        print("1. 降低匹配度阈值（当前70%）")
        print("2. 检查特征是否过于严格")
    else:
        for i, candidate in enumerate(candidates[:50], 1):  # 显示前50个
            print(f"\n{i}. {candidate['股票名称']} ({candidate['股票代码']})")
            print(f"   匹配度: {candidate['匹配度']:.1%}")
            print(f"   当前价格: {candidate['当前价格']:.2f} 元")
            print(f"   当前日期: {candidate['当前日期']}")
            
            # 显示关键特征对比
            if '特征' in candidate:
                stock_features = candidate['特征']
                print(f"   关键特征:")
                key_features = ['价格相对MA20', '成交量放大倍数', '价格变化率', '涨停次数', '连续上涨天数']
                for key in key_features:
                    if key in target_features and key in stock_features:
                        target_val = target_features[key]
                        stock_val = stock_features[key]
                        if isinstance(target_val, float):
                            print(f"     {key}: 目标={target_val:.2f}, 实际={stock_val:.2f}")
                        else:
                            print(f"     {key}: 目标={target_val}, 实际={stock_val}")
        
        if len(candidates) > 50:
            print(f"\n... 还有 {len(candidates) - 50} 只股票未显示")
        
        print(f"\n总共找到 {len(candidates)} 只符合条件的股票")
        
        # 保存结果到文件
        import json
        output_file = f"符合条件的股票_{stock_code}_{stock_name}.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            # 转换numpy类型
            candidates_json = []
            for c in candidates:
                c_json = {}
                for k, v in c.items():
                    if k == '特征':
                        c_json[k] = {k2: float(v2) if isinstance(v2, (int, float, np.number)) else v2 
                                   for k2, v2 in v.items()}
                    elif isinstance(v, (np.integer, np.int64)):
                        c_json[k] = int(v)
                    elif isinstance(v, (np.floating, np.float64)):
                        c_json[k] = float(v)
                    else:
                        c_json[k] = v
                candidates_json.append(c_json)
            
            json.dump({
                '参考股票': f"{stock_name}({stock_code})",
                '起点日期': str(start_point['起点日期']),
                '起点价格': start_point['起点价格'],
                '目标特征': {k: float(v) if isinstance(v, (int, float, np.number)) else v 
                          for k, v in target_features.items()},
                '符合条件的股票': candidates_json
            }, f, ensure_ascii=False, indent=2)
        
        print(f"\n✅ 结果已保存到: {output_file}")

