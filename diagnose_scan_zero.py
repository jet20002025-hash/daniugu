#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
扫描结果为 0 的诊断脚本
在模式、数据未改的情况下，帮助排查为什么一只股票都搜不到。
"""
import os
import sys

def main():
    print("=" * 70)
    print("扫描结果为 0 — 诊断")
    print("=" * 70)

    # 1. 模型
    print("\n【1】模型 trained_model.json")
    model_path = os.path.join(os.path.dirname(__file__), 'trained_model.json')
    if not os.path.exists(model_path):
        print("  ❌ 文件不存在:", model_path)
    else:
        import json
        with open(model_path, 'r', encoding='utf-8') as f:
            model = json.load(f)
        buy = model.get('buy_features', {}) or {}
        common = (buy.get('common_features') or model.get('common_features')) or {}
        n = len(common)
        print(f"  ✅ 文件存在，common_features 数量: {n}")
        if n == 0:
            print("  ❌ common_features 为空，扫描会直接返回 0 只。请检查模型是否损坏或格式是否变化。")
        else:
            print(f"  前 3 个特征名: {list(common.keys())[:3]}")

    # 2. 周K缓存
    print("\n【2】周K线缓存 cache/weekly_kline")
    base = os.path.join(os.path.dirname(__file__), 'cache')
    weekly_dir = os.path.join(base, 'weekly_kline')
    if not os.path.isdir(weekly_dir):
        print("  ❌ 目录不存在:", weekly_dir)
    else:
        import glob
        csvs = glob.glob(os.path.join(weekly_dir, '*.csv'))
        jsons = glob.glob(os.path.join(weekly_dir, '*.json'))
        total = len(csvs) + len(jsons)
        print(f"  ✅ 目录存在，约 {len(csvs)} 个 csv, {len(jsons)} 个 json")
        if total == 0:
            print("  ❌ 没有周K缓存，扫描时所有股票都会因「无数据」被跳过，结果为 0。")
        else:
            # 抽 1 个看行数、列名
            for p in (csvs[:1] + jsons[:1]):
                if not p:
                    continue
                try:
                    import pandas as pd
                    if p.endswith('.csv'):
                        df = pd.read_csv(p)
                    else:
                        with open(p, 'r', encoding='utf-8') as f:
                            df = pd.DataFrame(json.load(f))
                    rows = len(df)
                    cols = list(df.columns)[:6]
                    code = os.path.splitext(os.path.basename(p))[0]
                    print(f"  样例 {code}: 行数={rows}, 列={cols}")
                    if rows < 40:
                        print(f"  ⚠️ 行数<40，该股会被跳过；若多数股都<40，会导致 0 结果。")
                except Exception as e:
                    print(f"  读取样例失败: {e}")

    # 3. 分析器 + 小范围扫描
    print("\n【3】分析器与 50 只股票试扫（min_match=0.80, max_cap=100）")
    try:
        from bull_stock_analyzer import BullStockAnalyzer

        a = BullStockAnalyzer(auto_load_default_stocks=False, auto_analyze_and_train=False)
        ok = a.load_model('trained_model.json', skip_network=True)
        if not ok:
            print("  ❌ load_model 失败")
        else:
            cf = a._get_common_features()
            print(f"  common_features 数量: {len(cf)}")
            if len(cf) == 0:
                print("  ❌ common_features 为空，无法扫描。")
            else:
                res = a.scan_all_stocks(min_match_score=0.80, max_market_cap=100.0, limit=50, use_parallel=True, max_workers=4, scan_date=None, strict_local_only=True)
                cands = (res or {}).get('candidates', [])
                total = (res or {}).get('total_scanned', 0)
                found = (res or {}).get('found_count', len(cands))
                print(f"  试扫 50 只: total_scanned={total}, found_count={found}, candidates={len(cands)}")
                if found == 0 and total > 0:
                    print("  ⚠️ 有扫描数量但 0 命中，可能原因：阈值过高、市值过滤过严、或匹配度普遍低于阈值。")
                if res and res.get('data_warning'):
                    w = res['data_warning']
                    print(f"  数据警告: {w.get('missing_count', 0)} 只缺数据, 共 {w.get('total_stocks', 0)} 只")

    except Exception as e:
        import traceback
        print("  运行试扫失败:", e)
        traceback.print_exc()

    print("\n" + "=" * 70)
    print("建议：若 common_features 为空→检查/重新训练模型；若周K缓存为空或不足→先下载数据；若试扫有 total 但 found=0→可临时把匹配度降到 0.70 或市值调到 200 试一次。")
    print("=" * 70)


if __name__ == '__main__':
    main()
