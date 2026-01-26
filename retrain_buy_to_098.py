#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
重新训练买点模型，使 11 只大牛股在「涨幅最大区间起点」的匹配度均 ≥ 0.98
- 起点：涨幅最大区间的起点索引（不用成交量突增点）
- 数据：本地缓存（通达信）
- 仅更新 buy_features.common_features，不改模型结构、不改 sell 等
"""
import os
import sys
import json
import numpy as np
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

BULL_STOCKS = [
    ('000592', '平潭发展'), ('002104', '恒宝股份'), ('002759', '天际股份'),
    ('300436', '广生堂'),   ('301005', '超捷股份'), ('301232', '飞沃科技'),
    ('002788', '鹭燕医药'), ('603778', '国晟科技'), ('603122', '合富中国'),
    ('600343', '航天动力'), ('603216', '梦天家居'),
]
TARGET = 0.98


def main():
    from bull_stock_analyzer import BullStockAnalyzer

    # 强制只走本地缓存
    def _patch(a):
        orig = a.fetcher.get_weekly_kline
        def _go(code, period="1y", use_cache=True, local_only=False):
            return orig(code, period=period, use_cache=True, local_only=True)
        a.fetcher.get_weekly_kline = _go

    analyzer = BullStockAnalyzer(auto_load_default_stocks=False, auto_analyze_and_train=False)
    _patch(analyzer)

    if not analyzer.load_model('trained_model.json', skip_network=True):
        print("❌ 加载模型失败")
        return

    # 1) 收集 11 只在「起点」的特征
    samples = []  # [(code, name, features), ...]
    for code, name in BULL_STOCKS:
        res = analyzer.find_max_gain_interval(code, search_weeks=10, min_gain=0)
        if not res or not res.get('success') or not res.get('interval'):
            print(f"  ⚠️ {code} {name} 未找到涨幅区间，跳过")
            continue
        ival = res['interval']
        start_idx = ival.get('起点索引')
        if start_idx is None or int(start_idx) < 20:
            print(f"  ⚠️ {code} {name} 起点索引无效或<20，跳过")
            continue

        weekly_df = analyzer.fetcher.get_weekly_kline(code, period="2y", use_cache=True, local_only=True)
        if weekly_df is None or len(weekly_df) == 0:
            print(f"  ⚠️ {code} {name} 无周K，跳过")
            continue

        features = analyzer.extract_features_at_start_point(code, int(start_idx), lookback_weeks=40, weekly_df=weekly_df)
        if not features:
            print(f"  ⚠️ {code} {name} 特征提取失败，跳过")
            continue
        # 去掉非数值字段，避免进 common
        features = {k: v for k, v in features.items() if k not in ('股票代码','股票名称','起点日期','最大量对应日期') and isinstance(v, (int, float)) and not (isinstance(v, float) and np.isnan(v))}
        samples.append((code, name, features))
        print(f"  ✅ {code} {name} 起点特征数 {len(features)}")

    if len(samples) < 2:
        print("❌ 有效样本不足 2 只")
        return

    # 2) 特征名并集
    all_names = set()
    for _, _, f in samples:
        all_names.update(f.keys())

    # 3) 迭代放大 标准差，直到 11 只都在起点匹配度 ≥ TARGET
    k = 2.0
    best_cf = None
    best_min = -1.0

    for _ in range(20):
        common = {}
        for fname in all_names:
            vals = []
            for _, _, f in samples:
                if fname in f:
                    v = f[fname]
                    if isinstance(v, (int, float)) and not (isinstance(v, float) and np.isnan(v)):
                        vals.append(float(v))
            if not vals:
                continue
            mean_v = np.mean(vals)
            med_v = np.median(vals)
            std_v = np.std(vals)
            std_v = max(std_v * k, abs(med_v) * 0.05, 0.01)
            common[fname] = {
                '均值': round(float(mean_v), 4),
                '中位数': round(float(med_v), 4),
                '标准差': round(float(std_v), 4),
                '最小值': round(float(np.min(vals)), 4),
                '最大值': round(float(np.max(vals)), 4),
                '样本数': len(vals),
            }

        scores = []
        for code, name, f in samples:
            s = analyzer._calculate_match_score(f, common, tolerance=0.3).get('总匹配度', 0)
            scores.append((code, name, s))
        min_s = min(s[2] for s in scores)
        if min_s >= TARGET:
            best_cf = common
            best_min = min_s
            print(f"\n  k={k:.1f} 时 最低={min_s:.4f} >= {TARGET}，达标")
            break
        if best_cf is None or min_s > best_min:
            best_cf = common
            best_min = min_s
        k += 0.5
        if k > 10:
            print(f"\n  k 已到 10，取当前最佳 最低={best_min:.4f}")
            break

    if not best_cf:
        print("❌ 无法构造 common_features")
        return

    # 4) 最终校验（用 best_cf）
    print("\n--- 最终匹配度 ---")
    for code, name, f in samples:
        s = analyzer._calculate_match_score(f, best_cf, tolerance=0.3).get('总匹配度', 0)
        ok = "✅" if s >= TARGET else "❌"
        print(f"  {ok} {code} {name}: {s:.4f}")
    min_final = min(analyzer._calculate_match_score(f, best_cf, tolerance=0.3).get('总匹配度', 0) for _, _, f in samples)
    print(f"  最低: {min_final:.4f}")

    # 5) 写回 trained_model.json，只改 buy 的 common 与 sample_stocks
    path = os.path.join(os.path.dirname(__file__), 'trained_model.json')
    with open(path, 'r', encoding='utf-8') as f:
        model = json.load(f)
    if 'buy_features' not in model:
        model['buy_features'] = {}
    model['buy_features']['common_features'] = best_cf
    model['buy_features']['sample_stocks'] = [s[0] for s in samples]
    model['trained_at'] = datetime.now().isoformat()
    model['retrain_note'] = f'11只大牛股在起点重训，目标≥{TARGET}，k={k:.1f}'

    with open(path, 'w', encoding='utf-8') as f:
        json.dump(model, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 已保存 trained_model.json（buy common_features 样本数 {len(samples)}，特征数 {len(best_cf)}）")


if __name__ == '__main__':
    main()
