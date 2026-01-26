#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""列出 11 只大牛股在当前 trained_model.json 下的最新匹配度"""
import json
import pandas as pd
from train_to_098 import load_weekly_kline_from_cache, extract_all_features, calculate_match_score


def main():
    with open('trained_model.json', 'r', encoding='utf-8') as f:
        model = json.load(f)
    sample_stocks = model['buy_features']['sample_stocks']
    analysis_results = model.get('analysis_results', {})
    common = model['buy_features']['common_features']
    name_by_code = {s['代码']: s['名称'] for s in model.get('bull_stocks', [])}
    trained_at = model.get('trained_at', model.get('buy_features', {}).get('trained_at', '-'))

    rows = []
    for code in sample_stocks:
        name = name_by_code.get(code, code)
        if code not in analysis_results:
            rows.append((code, name, None))
            continue
        interval = analysis_results[code].get('interval', {})
        start_date = interval.get('起点日期', '')
        if not start_date:
            rows.append((code, name, None))
            continue
        weekly_df = load_weekly_kline_from_cache(code)
        if weekly_df is None or len(weekly_df) < 50:
            rows.append((code, name, None))
            continue
        start_ts = pd.to_datetime(start_date)
        start_idx = None
        for i, r in weekly_df.iterrows():
            if r['日期'] <= start_ts:
                start_idx = i
        if start_idx is None or start_idx < 20:
            rows.append((code, name, None))
            continue
        features = extract_all_features(weekly_df, start_idx, stock_code=code)
        if not features:
            rows.append((code, name, None))
            continue
        score = calculate_match_score(features, common)
        rows.append((code, name, score))

    print("=" * 60)
    print("📋 11只大牛股 · 最新匹配度（当前 trained_model.json）")
    print("=" * 60)
    print(f"模型时间: {trained_at}")
    print("-" * 60)
    print(f"{'代码':<10} {'名称':<12} {'匹配度':<12}")
    print("-" * 60)
    for code, name, s in rows:
        v = f"{s:.4f}" if s is not None else "-"
        print(f"{code:<10} {name:<12} {v:<12}")
    print("=" * 60)


if __name__ == '__main__':
    main()
