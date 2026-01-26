#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据融合：根据 cache/daily_kline 和 cache/weekly_kline 重建 data_markers.json
在批量下载（update_data_sina / update_local_data）之后运行，使「最新日期」与本地缓存一致。
"""
import os
import json
import pandas as pd
from datetime import datetime

CACHE_DIR = 'cache'
DAILY_DIR = os.path.join(CACHE_DIR, 'daily_kline')
WEEKLY_DIR = os.path.join(CACHE_DIR, 'weekly_kline')
MARKERS_PATH = os.path.join(CACHE_DIR, 'data_markers.json')


def _norm_date(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    s = str(pd.Timestamp(v))[:10]
    return s if s and s != 'NaT' else None


def _latest_from_csv(path):
    try:
        df = pd.read_csv(path, usecols=['日期'], encoding='utf-8')
        if df is None or len(df) == 0:
            return None
        df['日期'] = pd.to_datetime(df['日期'], errors='coerce')
        df = df.dropna(subset=['日期'])
        if len(df) == 0:
            return None
        return _norm_date(df['日期'].max())
    except Exception:
        return None


def _latest_from_json(path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if not isinstance(data, list) or len(data) == 0:
            return None
        dates = []
        for row in data:
            d = row.get('日期') if isinstance(row, dict) else None
            if d is not None:
                t = pd.to_datetime(d, errors='coerce')
                if pd.notna(t):
                    dates.append(t)
        if not dates:
            return None
        return _norm_date(max(dates))
    except Exception:
        return None


def main():
    print('=' * 60)
    print('📊 数据融合：从 cache 重建 data_markers.json')
    print('=' * 60)

    # 加载已有 markers（保留未涉及的字段）
    if os.path.exists(MARKERS_PATH):
        try:
            with open(MARKERS_PATH, 'r', encoding='utf-8') as f:
                markers = json.load(f)
        except Exception:
            markers = {}
    else:
        markers = {}

    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    daily_count = 0
    weekly_count = 0
    max_daily = None
    max_weekly = None

    # 日 K：遍历 daily_kline/*.csv
    if os.path.isdir(DAILY_DIR):
        files = [f for f in os.listdir(DAILY_DIR) if f.endswith('.csv')]
        for i, f in enumerate(files):
            if (i + 1) % 2000 == 0:
                print(f'  [日K] {i+1}/{len(files)} ...')
            code = f[:-4]
            path = os.path.join(DAILY_DIR, f)
            latest = _latest_from_csv(path)
            if latest:
                if code not in markers:
                    markers[code] = {}
                markers[code]['daily_latest_date'] = latest
                markers[code]['last_update_timestamp'] = now_str
                daily_count += 1
                if max_daily is None or latest > max_daily:
                    max_daily = latest

    # 周 K：遍历 weekly_kline/*.csv 与 *.json（csv 优先，同 code 则 csv 覆盖）
    if os.path.isdir(WEEKLY_DIR):
        wfiles = [f for f in os.listdir(WEEKLY_DIR) if f.endswith('.csv') or (f.endswith('.json') and not f.endswith('.meta.json'))]
        for i, f in enumerate(wfiles):
            if (i + 1) % 2000 == 0:
                print(f'  [周K] {i+1}/{len(wfiles)} ...')
            code = None
            latest = None
            if f.endswith('.csv'):
                code = f[:-4]
                latest = _latest_from_csv(os.path.join(WEEKLY_DIR, f))
            elif f.endswith('.json') and not f.endswith('.meta.json'):
                code = f[:-5]
                latest = _latest_from_json(os.path.join(WEEKLY_DIR, f))
            if code and latest:
                if code not in markers:
                    markers[code] = {}
                markers[code]['weekly_latest_date'] = latest
                markers[code]['last_update_timestamp'] = now_str
                weekly_count += 1
                if max_weekly is None or latest > max_weekly:
                    max_weekly = latest

    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(MARKERS_PATH, 'w', encoding='utf-8') as f:
        json.dump(markers, f, ensure_ascii=False, indent=2)

    print(f'  日 K: 更新 {daily_count} 只，最新日期: {max_daily or "-"}')
    print(f'  周 K: 更新 {weekly_count} 只，最新日期: {max_weekly or "-"}')
    print(f'  data_markers 总条数: {len(markers)}')
    print('=' * 60)
    print('✅ 融合完成，可直接用最近数据做扫描/回测。')
    print('=' * 60)


if __name__ == '__main__':
    main()
