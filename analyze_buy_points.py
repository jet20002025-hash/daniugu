"""
根据指定的买点日期，分析买点前的特征，然后扫描所有股票
"""
from find_stocks_by_features import extract_features_at_start_point, scan_all_stocks_by_features, match_features
from data_fetcher import DataFetcher
import pandas as pd
import numpy as np
import sys

def find_buy_point_date(daily_df, target_date_str):
    """
    在数据中找到指定日期的索引
    :param daily_df: 日K线数据
    :param target_date_str: 目标日期字符串，如 '2025-12-04'
    :return: 索引位置，如果未找到返回None
    """
    daily_df['日期_str'] = pd.to_datetime(daily_df['日期']).dt.strftime('%Y-%m-%d')
    target_rows = daily_df[daily_df['日期_str'] == target_date_str]
    
    if len(target_rows) > 0:
        return daily_df.index.get_loc(target_rows.index[0])
    else:
        # 找最接近的日期
        daily_df['日期_dt'] = pd.to_datetime(daily_df['日期'])
        target_dt = pd.to_datetime(target_date_str)
        daily_df['日期差'] = abs(daily_df['日期_dt'] - target_dt)
        closest = daily_df.nsmallest(1, '日期差')
        if len(closest) > 0:
            closest_date = closest.iloc[0]['日期_str']
            print(f"⚠️ 未找到 {target_date_str}，使用最接近的日期: {closest_date}")
            return daily_df.index.get_loc(closest.index[0])
        return None


def analyze_stocks_with_buy_points():
    """
    分析指定的股票买点，提取特征，然后扫描所有股票
    """
    # 指定的买点信息
    buy_points = [
        {'股票代码': '001331', '股票名称': '胜通能源', '买点日期': '2025-12-04', '买点价格': 13.70},
        {'股票代码': '002969', '股票名称': '嘉美包装', '买点日期': '2025-12-04', '买点价格': 4.02},
        {'股票代码': '301005', '股票名称': '超捷股份', '买点日期': '2025-12-04', '买点价格': 57.12},
    ]
    
    fetcher = DataFetcher()
    all_features = []
    
    print("=" * 80)
    print("第一步：分析买点前的特征")
    print("=" * 80)
    
    # 1. 为每只股票提取买点前的特征
    for bp in buy_points:
        stock_code = bp['股票代码']
        stock_name = bp['股票名称']
        buy_date = bp['买点日期']
        
        print(f"\n分析 {stock_name} ({stock_code}) 在 {buy_date} 买点前的特征...")
        
        daily_df = fetcher.get_daily_kline(stock_code)
        if daily_df is None or len(daily_df) == 0:
            print(f"❌ 无法获取 {stock_code} 的数据")
            continue
        
        # 找到买点日期在数据中的位置
        buy_idx = find_buy_point_date(daily_df, buy_date)
        if buy_idx is None:
            print(f"❌ 无法找到 {buy_date} 在数据中的位置")
            continue
        
        # 提取买点前的特征
        features = extract_features_at_start_point(daily_df, buy_idx)
        if features:
            features['股票代码'] = stock_code
            features['股票名称'] = stock_name
            features['买点日期'] = buy_date
            features['买点价格'] = bp['买点价格']
            all_features.append(features)
            
            print(f"✅ 提取到 {len(features)} 个特征")
            print(f"   买点日期: {buy_date}")
            print(f"   买点价格: {bp['买点价格']:.2f} 元")
        else:
            print(f"❌ 无法提取特征")
    
    if len(all_features) == 0:
        print("\n❌ 未能提取任何特征，退出")
        return
    
    # 2. 计算共同特征（平均值）
    print("\n" + "=" * 80)
    print("第二步：计算共同特征（多只股票的平均值）")
    print("=" * 80)
    
    # 获取所有特征键
    feature_keys = set()
    for f in all_features:
        feature_keys.update([k for k in f.keys() if k not in ['股票代码', '股票名称', '买点日期', '买点价格']])
    
    common_features = {}
    for key in feature_keys:
        values = []
        for f in all_features:
            if key in f and isinstance(f[key], (int, float)):
                values.append(f[key])
        
        if len(values) > 0:
            common_features[key] = np.mean(values)
            print(f"   {key}: {common_features[key]:.2f} (平均值)")
    
    print(f"\n✅ 计算出 {len(common_features)} 个共同特征")
    
    # 3. 扫描所有股票
    print("\n" + "=" * 80)
    print("第三步：根据共同特征扫描所有股票")
    print("=" * 80)
    
    from datetime import datetime
    start_scan_time = datetime.now()
    print(f"开始扫描时间: {start_scan_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    if len(sys.argv) > 1:
        try:
            limit = int(sys.argv[1])
        except:
            limit = None
    else:
        limit = None
    
    if limit:
        print(f"将扫描前 {limit} 只股票")
    else:
        print("将扫描全部股票（约5000只，需要较长时间）")
    
    print(f"约束条件: 匹配度 ≥ 65%, 总市值 ≤ 60 亿元")
    print("=" * 80)
    
    candidates = scan_all_stocks_by_features(common_features, limit=limit, min_match_score=0.65, max_market_cap=60.0)
    
    end_scan_time = datetime.now()
    scan_duration = (end_scan_time - start_scan_time).total_seconds()
    print(f"\n扫描完成时间: {end_scan_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"总耗时: {int(scan_duration//60)}分{int(scan_duration%60)}秒")
    
    # 4. 显示结果
    print("\n" + "=" * 80)
    print("符合条件的股票（按匹配度排序）:")
    print("=" * 80)
    
    if len(candidates) == 0:
        print("\n未找到符合条件的股票")
    else:
        for i, candidate in enumerate(candidates[:30], 1):  # 显示前30个
            print(f"\n{i}. {candidate['股票名称']} ({candidate['股票代码']})")
            print(f"   匹配度: {candidate['匹配度']:.1%}")
            print(f"   当前价格: {candidate['当前价格']:.2f} 元")
            print(f"   当前日期: {candidate['当前日期']}")
        
        if len(candidates) > 30:
            print(f"\n... 还有 {len(candidates) - 30} 只股票未显示")
        
        print(f"\n总共找到 {len(candidates)} 只符合条件的股票")
        
        # 保存结果
        import json
        output_file = "符合条件的股票_共同特征.json"
        with open(output_file, 'w', encoding='utf-8') as f:
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
                '参考股票': [f"{f['股票名称']}({f['股票代码']}) @ {f['买点日期']}" for f in all_features],
                '共同特征': {k: float(v) if isinstance(v, (int, float, np.number)) else v 
                          for k, v in common_features.items()},
                '符合条件的股票': candidates_json
            }, f, ensure_ascii=False, indent=2)
        
        print(f"\n✅ 结果已保存到: {output_file}")


if __name__ == '__main__':
    analyze_stocks_with_buy_points()

