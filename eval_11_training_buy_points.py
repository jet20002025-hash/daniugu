#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
11只训练大牛股：在训练买点用最新模型评测匹配度（不做训练买点提升）
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
from bull_stock_analyzer import BullStockAnalyzer

def main():
    analyzer = BullStockAnalyzer(auto_load_default_stocks=False, auto_analyze_and_train=False)
    if not analyzer.load_model('trained_model.json', skip_network=True):
        print('加载 trained_model.json 失败')
        return

    common_features = analyzer._get_common_features()
    if not common_features:
        print('模型无 common_features')
        return

    ar = getattr(analyzer, 'analysis_results', None) or {}
    if not ar:
        print('模型无 analysis_results（训练买点）')
        return

    # 静音：避免 find_volume_surge / extract_features 刷屏
    analyzer._scan_quiet = True

    results = []
    for code, res in ar.items():
        iv = res.get('interval', {})
        start_date = iv.get('起点日期')
        start_price = iv.get('起点价格')
        start_idx = iv.get('起点索引')
        if not start_date:
            continue

        name = None
        for s in analyzer.bull_stocks:
            if s.get('代码') == code:
                name = s.get('名称', code)
                break
        if not name:
            name = code

        weekly_df = analyzer.fetcher.get_weekly_kline(code, period='10y', use_cache=True, local_only=True)
        if weekly_df is None or len(weekly_df) < 40:
            results.append({
                'code': code,
                'name': name,
                'buy_date': start_date,
                'buy_price': start_price,
                'match': None,
                'note': '周线不足40周',
            })
            continue

        weekly_df = weekly_df.copy()
        weekly_df['日期'] = pd.to_datetime(weekly_df['日期'], errors='coerce')
        weekly_df = weekly_df.dropna(subset=['日期']).sort_values('日期').reset_index(drop=True)

        # 找到 起点日期 对应的周K索引 i（买点 bar）
        buy_bar_idx = None
        td = str(start_date)[:10]
        for i, row in weekly_df.iterrows():
            d = row['日期']
            ds = d.strftime('%Y-%m-%d') if hasattr(d, 'strftime') else str(d)[:10]
            if ds == td:
                buy_bar_idx = i
                break

        if buy_bar_idx is None:
            results.append({
                'code': code,
                'name': name,
                'buy_date': start_date,
                'buy_price': start_price,
                'match': None,
                'note': f'周线中无{td}',
            })
            continue

        if buy_bar_idx < 20:
            results.append({
                'code': code,
                'name': name,
                'buy_date': start_date,
                'buy_price': start_price,
                'match': None,
                'note': '买点前数据不足20周',
            })
            continue

        try:
            vs_idx = analyzer.find_volume_surge_point(
                code, int(buy_bar_idx), weekly_df=weekly_df,
                min_volume_ratio=3.0, lookback_weeks=52
            )
            if vs_idx is None:
                vs_idx = max(0, int(buy_bar_idx) - 20)
            if vs_idx < 20:
                results.append({
                    'code': code,
                    'name': name,
                    'buy_date': start_date,
                    'buy_price': start_price,
                    'match': None,
                    'note': '量突增点前不足20周',
                })
                continue

            features = analyzer.extract_features_at_start_point(
                code, vs_idx, lookback_weeks=40, weekly_df=weekly_df
            )
            if features is None:
                results.append({
                    'code': code,
                    'name': name,
                    'buy_date': start_date,
                    'buy_price': start_price,
                    'match': None,
                    'note': '特征提取失败',
                })
                continue

            # 用最新模型计算匹配度（不做训练买点提升）
            ms = analyzer._calculate_match_score(features, common_features, tolerance=0.3)
            match = ms.get('总匹配度')
            results.append({
                'code': code,
                'name': name,
                'buy_date': start_date,
                'buy_price': start_price,
                'match': round(float(match), 3) if match is not None else None,
                'note': None,
            })
        except Exception as e:
            results.append({
                'code': code,
                'name': name,
                'buy_date': start_date,
                'buy_price': start_price,
                'match': None,
                'note': str(e)[:80],
            })

    analyzer._scan_quiet = False

    # 输出
    print('=' * 72)
    print('11只训练大牛股 · 训练买点 · 最新模型评测匹配度')
    print('=' * 72)
    print()
    valid = [r for r in results if r['match'] is not None]
    for i, r in enumerate(results, 1):
        m = f"{r['match']:.3f}" if r['match'] is not None else f"({r['note']})"
        print(f"  {i:2}. {r['code']} {r['name']:8}  买点 {r['buy_date']}  价格 {r['buy_price']}  匹配度 {m}")
    print()
    if valid:
        avg = sum(x['match'] for x in valid) / len(valid)
        print(f"  有效 {len(valid)} 只，平均匹配度: {avg:.3f}")
        print(f"  最高: {max(x['match'] for x in valid):.3f}  最低: {min(x['match'] for x in valid):.3f}")
    print('=' * 72)

if __name__ == '__main__':
    main()
