#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
再次训练：用 11 只大牛股训练买点、新模型全部特征，
匹配度逻辑改为 [min,max] 内即 1.0，目标 11 只买点匹配度全为 1.0。
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bull_stock_analyzer import BullStockAnalyzer

def main():
    analyzer = BullStockAnalyzer(auto_load_default_stocks=False, auto_analyze_and_train=False)
    if not analyzer.load_model('trained_model.json', skip_network=True):
        print('❌ 加载 trained_model.json 失败')
        return

    if not getattr(analyzer, 'analysis_results', None) or len(analyzer.analysis_results) == 0:
        print('❌ 模型无 analysis_results，请先分析大牛股')
        return

    print('=' * 72)
    print('再次训练：11 只大牛股 · 买点特征 · 全部特征 · 目标匹配度全 1.0')
    print('=' * 72)

    result = analyzer.train_features()
    if not result.get('success'):
        print('❌ 训练失败:', result.get('message', '未知'))
        return

    if not analyzer.save_model('trained_model.json'):
        print('❌ 保存模型失败')
        return

    print()
    print('✅ 已保存到 trained_model.json')
    print()
    print('验证 11 只买点匹配度...')
    print()

    # 运行评测脚本逻辑（内联，避免子进程）
    import pandas as pd
    common = analyzer._get_common_features()
    ar = getattr(analyzer, 'analysis_results', None) or {}
    analyzer._scan_quiet = True

    out = []
    for code, res in ar.items():
        iv = res.get('interval', {})
        start_date = iv.get('起点日期')
        start_price = iv.get('起点价格')
        if not start_date:
            continue
        name = next((s.get('名称', code) for s in analyzer.bull_stocks if s.get('代码') == code), code)

        w = analyzer.fetcher.get_weekly_kline(code, period='10y', use_cache=True, local_only=True)
        if w is None or len(w) < 40:
            out.append((code, name, start_date, start_price, None, '周线不足'))
            continue

        w = w.copy()
        w['日期'] = pd.to_datetime(w['日期'], errors='coerce')
        w = w.dropna(subset=['日期']).sort_values('日期').reset_index(drop=True)
        td = str(start_date)[:10]
        buy_bar = None
        for i, row in w.iterrows():
            ds = row['日期'].strftime('%Y-%m-%d') if hasattr(row['日期'], 'strftime') else str(row['日期'])[:10]
            if ds == td:
                buy_bar = int(i)
                break
        if buy_bar is None or buy_bar < 20:
            out.append((code, name, start_date, start_price, None, '无买点周'))
            continue

        vs = analyzer.find_volume_surge_point(code, buy_bar, weekly_df=w, min_volume_ratio=3.0, lookback_weeks=52)
        vs = vs if vs is not None else max(0, buy_bar - 20)
        if vs < 20:
            out.append((code, name, start_date, start_price, None, '量突增前不足20周'))
            continue

        f = analyzer.extract_features_at_start_point(code, vs, lookback_weeks=40, weekly_df=w)
        if f is None:
            out.append((code, name, start_date, start_price, None, '特征失败'))
            continue

        ms = analyzer._calculate_match_score(f, common, tolerance=0.3)
        m = ms.get('总匹配度')
        out.append((code, name, start_date, start_price, round(float(m), 3) if m is not None else None, None))

    analyzer._scan_quiet = False

    print('-' * 72)
    for i, (code, name, dt, pr, match, note) in enumerate(out, 1):
        s = f"{match:.3f}" if match is not None else f"({note})"
        print(f"  {i:2}. {code} {name:8}  买点 {dt}  价格 {pr}  匹配度 {s}")
    print('-' * 72)
    valid = [x for x in out if x[4] is not None]
    if valid:
        avg = sum(x[4] for x in valid) / len(valid)
        all_one = all(x[4] >= 0.999 for x in valid)
        print(f"  有效 {len(valid)} 只，平均 {avg:.3f}，全部≥1.0: {'✅ 是' if all_one else '❌ 否'}")
    print('=' * 72)

if __name__ == '__main__':
    main()
