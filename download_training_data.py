#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
训练前下载完整数据到本地缓存。

- 从 train_model_to_match_1.ALL_BULL_STOCKS 等来源收集训练股列表
- 若本地 cache 无对应日 K / 周 K，则从网络下载并写入 cache
- 训练时仅从本地读取，不再访问网络

用法:
  python3 download_training_data.py
  python3 download_training_data.py --start 20150101 --end 20261231
"""
from __future__ import annotations

import os
import sys
import json
import time
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta

for k in ["http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY", "all_proxy", "ALL_PROXY", "no_proxy", "NO_PROXY"]:
    os.environ.pop(k, None)
os.environ["NO_PROXY"] = "*"
os.environ["no_proxy"] = "*"

import pandas as pd

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)


def get_training_stock_codes() -> list[str]:
    """收集所有训练用股票代码"""
    codes = set()
    try:
        from train_model_to_match_1 import ALL_BULL_STOCKS
        for c in ALL_BULL_STOCKS:
            codes.add(str(c))
    except Exception:
        pass
    try:
        model_path = os.path.join(PROJECT_ROOT, "trained_model.json")
        if os.path.exists(model_path):
            with open(model_path, "r", encoding="utf-8") as f:
                m = json.load(f)
            for s in m.get("bull_stocks", []) or []:
                c = s.get("code") or s.get("股票代码")
                if c:
                    codes.add(str(c))
    except Exception:
        pass
    try:
        mp = os.path.join(PROJECT_ROOT, "model有效模型0124.json")
        if os.path.exists(mp):
            with open(mp, "r", encoding="utf-8") as f:
                m = json.load(f)
            for s in m.get("bull_stocks", []) or []:
                c = s.get("code") or s.get("股票代码")
                if c:
                    codes.add(str(c))
    except Exception:
        pass
    return sorted(codes)


def _ensure_dirs(fetcher):
    paths = fetcher._local_cache_paths()
    for d in (paths["daily_dir"], paths["weekly_dir"]):
        os.makedirs(d, exist_ok=True)


def _save_csv_with_meta(df: pd.DataFrame, csv_path: str, meta_path: str, meta: dict) -> None:
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)


def _already_ok(meta_path: str, start_ymd: str, end_ymd: str) -> bool:
    if not os.path.exists(meta_path):
        return False
    try:
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
        return meta.get("start") == start_ymd and meta.get("end") == end_ymd
    except Exception:
        return False


def _work(
    code: str,
    fetcher,
    daily_dir: str,
    weekly_dir: str,
    start_ymd: str,
    end_ymd: str,
    per_stock_timeout: int,
) -> tuple[str, str, bool, bool]:
    """下载单只股票的日 K、周 K；可跳过已存在的完整缓存。"""
    daily_csv = os.path.join(daily_dir, f"{code}.csv")
    daily_meta = os.path.join(daily_dir, f"{code}.meta.json")
    weekly_csv = os.path.join(weekly_dir, f"{code}.csv")
    weekly_meta = os.path.join(weekly_dir, f"{code}.meta.json")

    if _already_ok(daily_meta, start_ymd, end_ymd) and _already_ok(weekly_meta, start_ymd, end_ymd):
        return code, "skipped", True, True

    import threading
    daily_df = None
    weekly_df = None

    def fetch_daily():
        nonlocal daily_df
        daily_df = fetcher.get_daily_kline_range(code, start_ymd, end_ymd, use_cache=False, local_only=False)

    def fetch_weekly():
        nonlocal weekly_df
        weekly_df = fetcher.get_weekly_kline_range(code, start_ymd, end_ymd)

    t1 = threading.Thread(target=fetch_daily, daemon=True)
    t2 = threading.Thread(target=fetch_weekly, daemon=True)
    t1.start()
    t2.start()
    t1.join(timeout=max(1, per_stock_timeout))
    t2.join(timeout=max(1, per_stock_timeout))
    if t1.is_alive() or t2.is_alive():
        return code, "fail", False, False

    saved_daily = False
    saved_weekly = False
    now_ts = datetime.now(timezone.utc).timestamp()
    meta = {"saved_at": now_ts, "start": start_ymd, "end": end_ymd}

    if daily_df is not None and len(daily_df) > 0:
        _save_csv_with_meta(daily_df, daily_csv, daily_meta, meta)
        saved_daily = True
    if weekly_df is not None and len(weekly_df) > 0:
        _save_csv_with_meta(weekly_df, weekly_csv, weekly_meta, meta)
        saved_weekly = True

    if not saved_daily and not saved_weekly:
        return code, "fail", False, False
    return code, "ok", saved_daily, saved_weekly


def ensure_training_data_local(
    start_ymd: str | None = None,
    end_ymd: str | None = None,
    max_workers: int = 2,
    per_stock_timeout: int = 25,
    cache_dir: str | None = None,
    limit: int | None = None,
) -> dict:
    """
    确保训练股日 K、周 K 已下载到本地。缺失则从网络拉取并写入 cache。
    :return: 统计 {'total', 'daily_ok', 'weekly_ok', 'skipped', 'fail', 'done'}
    """
    if cache_dir:
        os.environ["LOCAL_CACHE_DIR"] = cache_dir

    from data_fetcher import DataFetcher
    fetcher = DataFetcher()
    paths = fetcher._local_cache_paths()
    daily_dir = paths["daily_dir"]
    weekly_dir = paths["weekly_dir"]
    _ensure_dirs(fetcher)

    codes = get_training_stock_codes()
    if not codes:
        return {"total": 0, "daily_ok": 0, "weekly_ok": 0, "skipped": 0, "fail": 0, "done": 0}
    if limit is not None and limit > 0:
        codes = codes[: limit]

    end = end_ymd or datetime.now().strftime("%Y%m%d")
    start = start_ymd or (datetime.now() - timedelta(days=365 * 11)).strftime("%Y%m%d")

    stats = {"total": len(codes), "done": 0, "daily_ok": 0, "weekly_ok": 0, "skipped": 0, "fail": 0, "start": start, "end": end}
    start_ts = time.time()

    with ThreadPoolExecutor(max_workers=max(1, max_workers)) as ex:
        futs = {
            ex.submit(_work, c, fetcher, daily_dir, weekly_dir, start, end, per_stock_timeout): c
            for c in codes
        }
        for fut in as_completed(futs):
            c = futs[fut]
            try:
                code, status, d_ok, w_ok = fut.result()
                if status == "skipped":
                    stats["skipped"] += 1
                elif status == "ok":
                    if d_ok:
                        stats["daily_ok"] += 1
                    if w_ok:
                        stats["weekly_ok"] += 1
                else:
                    stats["fail"] += 1
            except Exception:
                stats["fail"] += 1
            stats["done"] += 1
            if stats["done"] % 5 == 0 or stats["done"] == stats["total"]:
                el = time.time() - start_ts
                speed = stats["done"] / el if el > 0 else 0
                print(
                    f"[download_training_data] {stats['done']}/{stats['total']} "
                    f"daily_ok={stats['daily_ok']} weekly_ok={stats['weekly_ok']} "
                    f"skipped={stats['skipped']} fail={stats['fail']} speed={speed:.2f}/s"
                )

    return stats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default=None, help="YYYYMMDD，默认约 11 年前")
    ap.add_argument("--end", default=None, help="YYYYMMDD，默认今天")
    ap.add_argument("--cache-dir", default=None)
    ap.add_argument("--max-workers", type=int, default=2)
    ap.add_argument("--per-stock-timeout", type=int, default=25)
    ap.add_argument("--limit", type=int, default=None, help="仅处理前 N 只（测试用）")
    args = ap.parse_args()

    print("=" * 80)
    print("📥 训练数据本地下载：缺失则从网络拉取完整日 K / 周 K")
    print("=" * 80)
    codes = get_training_stock_codes()
    print(f"训练股数量: {len(codes)}")
    if codes:
        print(f"示例: {codes[:10]}")
    print()

    stats = ensure_training_data_local(
        start_ymd=args.start,
        end_ymd=args.end,
        max_workers=args.max_workers,
        per_stock_timeout=args.per_stock_timeout,
        cache_dir=args.cache_dir,
        limit=args.limit,
    )
    print()
    print("=" * 80)
    print(f"✅ 完成: {stats}")
    print("=" * 80)


if __name__ == "__main__":
    main()
