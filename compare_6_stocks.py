#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按用户分类对比 6 只股票特征，支持温和微调"""

import sys
sys.path.insert(0, '.')
from bull_stock_analyzer import BullStockAnalyzer
import pandas as pd
import numpy as np

# 用户明确分类：表现好 vs 表现不好
GOOD = [('300986', '志特新材'), ('002254', '泰和新材'), ('300599', '雄塑科技')]
BAD = [('300205', '*ST天喻'), ('603648', '畅联股份'), ('002599', '盛通股份')]

scan_ts = pd.to_datetime('2026-01-04')
analyzer = BullStockAnalyzer(auto_load_default_stocks=False, auto_analyze_and_train=False)
analyzer.load_model('trained_model.json')
common = analyzer._get_common_features()

print('=' * 60)
print('表现好: 志特、泰和、雄塑  |  表现不好: *ST天喻、畅联、盛通')
print('=' * 60)

results = []
for code, name in GOOD + BAD:
    w = analyzer.fetcher.get_weekly_kline(code, period='2y', use_cache=True, local_only=True)
    w['日期'] = pd.to_datetime(w['日期'], errors='coerce')
    w = w[w['日期'] <= scan_ts].sort_values('日期').reset_index(drop=True)
    if len(w) < 40:
        print(f'{name} 数据不足')
        continue
    f = analyzer.extract_features_at_start_point(code, len(w) - 1, lookback_weeks=40, weekly_df=w)
    if not f:
        continue
    m = analyzer._calculate_match_score(f, common, tolerance=0.3)
    label = '✅' if (code, name) in GOOD else '❌'
    results.append({'code': code, 'name': name, 'good': (code, name) in GOOD, 'score': m['总匹配度'], 'features': f})
    print(f'{label} {name} ({code}): 匹配度 {m["总匹配度"]:.4f}  |  价格相对MA20={f.get("价格相对MA20")}  均线粘合度={f.get("均线粘合度")}  均线平滑度={f.get("均线平滑度")}')

good_scores = [r['score'] for r in results if r['good']]
bad_scores = [r['score'] for r in results if not r['good']]
print('-' * 60)
print(f'表现好 平均: {np.mean(good_scores):.4f}  表现不好 平均: {np.mean(bad_scores):.4f}  差异: {np.mean(good_scores) - np.mean(bad_scores):.4f}')

# 均线相关特征汇总
for feat in ['价格相对MA20', '均线粘合度', '均线平滑度']:
    gv = [r['features'].get(feat) for r in results if r['good'] and r['features'].get(feat) is not None]
    bv = [r['features'].get(feat) for r in results if not r['good'] and r['features'].get(feat) is not None]
    if gv and bv:
        print(f'  {feat}: 好 中位数={np.median(gv):.2f}  不好 中位数={np.median(bv):.2f}')
