#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
纯分析：志特新材 vs 畅联股份 特征差异
不调整模型，仅精确找出导致两者匹配度差异的参数
"""
import sys
sys.path.insert(0, '.')
from bull_stock_analyzer import BullStockAnalyzer
import pandas as pd
import math

analyzer = BullStockAnalyzer(auto_load_default_stocks=False, auto_analyze_and_train=False)
analyzer.load_model('trained_model.json')
common_features = analyzer._get_common_features()

stock1_code = '300986'  # 志特新材（大牛股）
stock2_code = '603648'  # 畅联股份（一般）
scan_date = '2026-01-04'

# 获取数据
weekly_df1 = analyzer.fetcher.get_weekly_kline(stock1_code, period='2y', use_cache=True, local_only=True)
weekly_df2 = analyzer.fetcher.get_weekly_kline(stock2_code, period='2y', use_cache=True, local_only=True)
if weekly_df1 is None or len(weekly_df1) < 40 or weekly_df2 is None or len(weekly_df2) < 40:
    print('数据不足')
    sys.exit(1)

scan_ts = pd.to_datetime(scan_date)
weekly_df1['日期'] = pd.to_datetime(weekly_df1['日期'], errors='coerce')
weekly_df2['日期'] = pd.to_datetime(weekly_df2['日期'], errors='coerce')
weekly_df1 = weekly_df1[weekly_df1['日期'] <= scan_ts].sort_values('日期').reset_index(drop=True)
weekly_df2 = weekly_df2[weekly_df2['日期'] <= scan_ts].sort_values('日期').reset_index(drop=True)
idx1, idx2 = len(weekly_df1) - 1, len(weekly_df2) - 1

features1 = analyzer.extract_features_at_start_point(stock1_code, idx1, lookback_weeks=40, weekly_df=weekly_df1)
features2 = analyzer.extract_features_at_start_point(stock2_code, idx2, lookback_weeks=40, weekly_df=weekly_df2)
if features1 is None or features2 is None:
    print('特征提取失败')
    sys.exit(1)

match1 = analyzer._calculate_match_score(features1, common_features, tolerance=0.3)
match2 = analyzer._calculate_match_score(features2, common_features, tolerance=0.3)

core_features = [
    '起点当周量比', '价格相对位置', '成交量萎缩程度', '价格相对MA20',
    '起点前20周波动率', '是否跌破最大量最低价', '均线多头排列', 'MACD零轴上方',
    'RSI', '均线粘合度', '布林带宽度', 'OBV趋势', '买点前两月内曾涨停',
]

print('=' * 100)
print('志特新材 vs 畅联股份 特征分析（2026-01-04 买点）')
print('=' * 100)
print()
print(f'志特新材总匹配度: {match1["总匹配度"]:.4f}')
print(f'畅联股份总匹配度: {match2["总匹配度"]:.4f}')
print(f'差距（志特 - 畅联）: {(match1["总匹配度"] - match2["总匹配度"])*100:.2f}%')
print()

# 1. 核心特征逐项对比
print('=' * 100)
print('一、核心特征逐项对比（目标中位、志特值、畅联值、志匹配、畅匹配、单特征差距）')
print('=' * 100)
print()
print(f'{"特征名称":<28} {"目标中位":>10} {"志特值":>10} {"畅联值":>10} {"志匹配":>8} {"畅匹配":>8} {"差距":>8} {"在[min,max]":>12}')
print('-' * 100)

rows = []
for fn in core_features:
    if fn not in common_features or fn not in features1 or fn not in features2:
        continue
    stats = common_features[fn]
    median = stats.get('中位数', stats.get('均值', 0))
    std = stats.get('标准差', 0)
    mn, mx = stats.get('最小值', 0), stats.get('最大值', 0)
    v1, v2 = features1[fn], features2[fn]
    s1 = match1.get('核心特征匹配', {}).get(fn, 0)
    s2 = match2.get('核心特征匹配', {}).get(fn, 0)
    d = s1 - s2
    in1 = '是' if mn <= v1 <= mx else '否'
    in2 = '是' if mn <= v2 <= mx else '否'
    in_range = f'志{in1}/畅{in2}'
    rows.append({
        'feature': fn, 'median': median, 'std': std, 'min': mn, 'max': mx,
        'v1': v1, 'v2': v2, 's1': s1, 's2': s2, 'diff': d, 'in_range': in_range
    })
    print(f'{fn:<28} {median:>10.2f} {v1:>10.2f} {v2:>10.2f} {s1:>8.3f} {s2:>8.3f} {d:>8.3f} {in_range:>12}')

# 2. 单特征对总匹配度的贡献（核心特征权重 3.0）
total_weight = len([r for r in rows]) * 3.0   # 仅核心
# 实际算法是 core*3 + normal*1，这里简化只看核心
print()
print('=' * 100)
print('二、单特征对总匹配度的加权贡献（核心特征权重=3）')
print('=' * 100)
print()
print(f'{"特征名称":<28} {"志贡献":>10} {"畅贡献":>10} {"贡献差":>10} {"说明":<30}')
print('-' * 100)

for r in rows:
    c1, c2 = r['s1'] * 3.0, r['s2'] * 3.0
    cd = c1 - c2
    note = '志特优' if cd > 0.1 else ('畅联优' if cd < -0.1 else '接近')
    print(f'{r["feature"]:<28} {c1:>10.3f} {c2:>10.3f} {cd:>10.3f} {note:<30}')

# 3. 精确找出“拉高畅联、拉低志特”的特征
print()
print('=' * 100)
print('三、导致匹配度差异的关键参数归纳')
print('=' * 100)
print()

positive = [r for r in rows if r['diff'] > 0.05]   # 志特明显优于畅联
negative = [r for r in rows if r['diff'] < -0.05]  # 畅联明显优于志特

print('【志特新材明显优于畅联股份】的特征（志匹配 > 畅匹配，且差距>0.05）：')
for r in sorted(positive, key=lambda x: -x['diff']):
    print(f"  • {r['feature']}")
    print(f"    目标中位={r['median']:.2f}, 志特={r['v1']:.2f}, 畅联={r['v2']:.2f}")
    print(f"    志匹配={r['s1']:.3f}, 畅匹配={r['s2']:.3f}, 差距={r['diff']:.3f}")
    print()

print('【畅联股份明显优于志特新材】的特征（畅匹配 > 志匹配，且差距>0.05）：')
for r in sorted(negative, key=lambda x: x['diff']):
    print(f"  • {r['feature']}")
    print(f"    目标中位={r['median']:.2f}, 志特={r['v1']:.2f}, 畅联={r['v2']:.2f}")
    print(f"    志匹配={r['s1']:.3f}, 畅匹配={r['s2']:.3f}, 差距={r['diff']:.3f}")
    print()

# 4. 汇总：哪几个参数导致两者总匹配度差异
print('=' * 100)
print('四、结论：导致两者匹配度差异的主要参数')
print('=' * 100)
print()
sum_pos = sum(r['diff'] for r in positive)
sum_neg = sum(r['diff'] for r in negative)
print(f'志特优特征贡献合计: {sum_pos:.3f}')
print(f'畅联优特征贡献合计: {sum_neg:.3f}')
print(f'净效果（志-畅）: {sum_pos + sum_neg:.3f}')
print()
print('因此，导致「畅联匹配度高于志特」的主要是【畅联优于志特】的这几项：')
for r in sorted(negative, key=lambda x: x['diff']):
    print(f"  - {r['feature']}（差距 {r['diff']:.3f}）")
print()
print('若希望志特匹配度提高、畅联降低，应针对上述参数做温和微调（例如中位数略向志特靠拢），')
print('而不是激进改动。')
print()

# 5. 精确复现总匹配度计算（含所有特征 + 核心/非核心权重）
print('=' * 100)
print('五、总匹配度精确复现（含核心+非核心特征）')
print('=' * 100)
print()

def calc_one_score(val, median, std, mn, mx, range_val):
    if std > 0:
        z = abs(val - median) / std
        base = math.exp(-0.4 * z * z)
        if mn <= val <= mx:
            return max(base, 0.6)
        if val < mn:
            out = (mn - val) / (range_val + 0.01)
        else:
            out = (val - mx) / (range_val + 0.01)
        return base * math.exp(-out * 3) * 0.8
    if mn <= val <= mx:
        if range_val > 0:
            rel = abs(val - median) / range_val
            return max(0.6, 1.0 - rel * 0.4)
        return 1.0 if abs(val - median) < 0.01 else 0.7
    if val < mn:
        out = (mn - val) / (range_val + 0.01)
    else:
        out = (val - mx) / (range_val + 0.01)
    return max(0, 0.5 * math.exp(-out * 2))

all_rows = []
for fn, stats in common_features.items():
    if fn not in features1 or fn not in features2:
        continue
    median = stats.get('中位数', stats.get('均值', 0))
    std = stats.get('标准差', 0)
    mn, mx = stats.get('最小值', 0), stats.get('最大值', 0)
    rng = mx - mn if mx > mn else (abs(median) * 0.2 if median else 1)
    v1, v2 = features1[fn], features2[fn]
    s1 = calc_one_score(v1, median, std, mn, mx, rng)
    s2 = calc_one_score(v2, median, std, mn, mx, rng)
    w = 3.0 if fn in core_features else 1.0
    c1, c2 = s1 * w, s2 * w
    all_rows.append({
        'feature': fn, 'core': fn in core_features, 'w': w,
        'v1': v1, 'v2': v2, 's1': s1, 's2': s2, 'c1': c1, 'c2': c2, 'diff': c1 - c2
    })

total_c1 = sum(r['c1'] for r in all_rows)
total_c2 = sum(r['c2'] for r in all_rows)
tw = sum(r['w'] for r in all_rows)
implied1 = total_c1 / tw
implied2 = total_c2 / tw

print(f'志特 total_score={total_c1:.4f}, total_weight={tw:.2f}, 总匹配度={implied1:.4f}')
print(f'畅联 total_score={total_c2:.4f}, total_weight={tw:.2f}, 总匹配度={implied2:.4f}')
print(f'（与 analyzer 输出 志特={match1["总匹配度"]:.4f} 畅联={match2["总匹配度"]:.4f} 对比，含均线粘合度奖励等）')
print()

# 按 |贡献差| 排序，找出对总匹配度差异影响最大的特征
all_rows.sort(key=lambda x: abs(x['diff']), reverse=True)
print('对所有特征按 |贡献差| 排序，影响总匹配度差异最大的前 15 个：')
print(f'{"特征":<28} {"核心":>4} {"权":>4} {"志贡献":>8} {"畅贡献":>8} {"贡献差":>8}')
print('-' * 70)
for r in all_rows[:15]:
    core = 'Y' if r['core'] else 'N'
    print(f'{r["feature"]:<28} {core:>4} {r["w"]:>4.1f} {r["c1"]:>8.3f} {r["c2"]:>8.3f} {r["diff"]:>8.3f}')
print()
print('综上：导致两者总匹配度差异的，主要是上述若干参数的贡献差；')
print('其中【畅联优于志特】的项（贡献差为负）拉高了畅联、拉低了志特。')
print()

# 6. 最终归纳：哪几个参数导致差异
print('=' * 100)
print('六、最终归纳：导致两者匹配度差异的几项参数')
print('=' * 100)
print()
print('（一）志特新材优于畅联股份的特征（拉高志特、拉低畅联）')
print('  • 是否跌破最大量最低价：志特=1、畅联=0，贡献差 +1.20')
print('  • 布林带宽度：志特=35.22、畅联=16.63，贡献差 +1.19')
print('  • 起点前20周波动率：志特=33.56、畅联=17.83，贡献差 +0.74')
print('  • 成交量萎缩程度：志特=0.87、畅联=0.80，贡献差 +0.31')
print('  • 平台整理周数、起点前20周波动幅度等（非核心）也有正向贡献。')
print()
print('（二）畅联股份优于志特新材的特征（拉高畅联、拉低志特）')
print('  • KDJ 相关（超卖、K、D、J）：畅联更接近目标，志特偏离大，贡献差约 -0.93、-0.46、-0.38、-0.34')
print('  • 价格相对MA40：畅联更接近目标，贡献差 -0.76')
print('  • MACD_DEA、MACD_DIF：畅联更接近目标，贡献差约 -0.40、-0.40')
print('  • 价格相对位置：志特=26.93、畅联=38.53，贡献差 -0.31')
print('  • OBV趋势：志特=23.42、畅联=-9.97（畅联更近目标-14.08），贡献差 -0.30')
print()
print('（三）结论')
print('  畅联总匹配度高于志特，主要是因为：')
print('  1. 非核心特征里 KDJ、价格相对MA40、MACD 等多项，畅联更贴近模型目标，志特偏离较大；')
print('  2. 核心特征里 价格相对位置、OBV趋势 畅联优于志特。')
print('  这些「畅联优」项的负向贡献差，足以抵消志特在「是否跌破、布林带、波动率、量萎缩」等上的优势。')
print()
print('  若后续做温和微调，应优先考虑：')
print('  - 核心：价格相对位置、OBV趋势、RSI、价格相对MA20（略向志特靠拢）；')
print('  - 非核心：KDJ 系列、价格相对MA40、MACD 等（视是否希望区分大牛与一般股而定）。')
