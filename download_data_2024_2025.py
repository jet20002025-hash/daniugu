#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
离线下载 2024-2025 全市场数据（日K + 周K）到本地 cache/ 目录。

输出：
  cache/daily_kline/{code}.csv
  cache/weekly_kline/{code}.csv
并带 .meta.json 记录保存时间与区间。

特点：
  - 断点续跑：已存在且覆盖范围正确的文件会跳过
  - 失败重试：依赖 DataFetcher 内部重试 + 本脚本外层容错
  - 默认单线程（最稳）；可 --max-workers 2/3 但可能更容易被断连/限流
"""

import os
# 避免系统/环境代理影响数据拉取
for k in ["http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY", "all_proxy", "ALL_PROXY", "no_proxy", "NO_PROXY"]:
    os.environ.pop(k, None)
os.environ["NO_PROXY"] = "*"
os.environ["no_proxy"] = "*"

import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

import pandas as pd

from data_fetcher import DataFetcher


def ensure_dir(p: str):
    os.makedirs(p, exist_ok=True)


def save_csv_with_meta(df: pd.DataFrame, csv_path: str, meta_path: str, meta: dict):
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)


def already_ok(meta_path: str, start_ymd: str, end_ymd: str) -> bool:
    if not os.path.exists(meta_path):
        return False
    try:
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
        return meta.get("start") == start_ymd and meta.get("end") == end_ymd
    except Exception:
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="20240101", help="YYYYMMDD")
    ap.add_argument("--end", default="20251231", help="YYYYMMDD")
    ap.add_argument("--cache-dir", default="/Users/zwj/股票分析/cache", help="本地缓存目录")
    ap.add_argument("--max-workers", type=int, default=1, help="并发线程数（建议 1~2）")
    ap.add_argument("--limit", type=int, default=None, help="只下载前 N 只股票（用于小规模测试）")
    ap.add_argument("--per-stock-timeout", type=int, default=25, help="单只股票最大下载时间（秒），超时则记为失败继续")
    args = ap.parse_args()

    start_ymd = args.start
    end_ymd = args.end
    cache_dir = args.cache_dir

    fetcher = DataFetcher()
    os.environ["LOCAL_CACHE_DIR"] = cache_dir

    paths = fetcher._local_cache_paths()
    daily_dir = paths["daily_dir"]
    weekly_dir = paths["weekly_dir"]
    ensure_dir(daily_dir)
    ensure_dir(weekly_dir)

    stocks = fetcher.get_all_stocks()
    if stocks is None or len(stocks) == 0:
        raise RuntimeError("无法获取股票列表")

    # 推断代码列
    code_col = None
    for col in stocks.columns:
        if "代码" in str(col) or "code" in str(col).lower():
            code_col = col
            break
    if code_col is None:
        code_col = stocks.columns[0]

    codes = [str(x) for x in stocks[code_col].tolist()]
    if args.limit:
        codes = codes[: args.limit]

    total = len(codes)
    stats = {
        "total": total,
        "done": 0,
        "daily_ok": 0,
        "weekly_ok": 0,
        "skipped": 0,
        "fail": 0,
        "start": start_ymd,
        "end": end_ymd,
    }

    start_ts = time.time()

    def work(code: str):
        daily_csv = os.path.join(daily_dir, f"{code}.csv")
        daily_meta = os.path.join(daily_dir, f"{code}.meta.json")
        weekly_csv = os.path.join(weekly_dir, f"{code}.csv")
        weekly_meta = os.path.join(weekly_dir, f"{code}.meta.json")

        if already_ok(daily_meta, start_ymd, end_ymd) and already_ok(weekly_meta, start_ymd, end_ymd):
            return code, "skipped", True, True

        # 通过线程+join 实现超时，避免 akshare 卡死导致整体不动
        import threading
        daily_df = None
        weekly_df = None
        errs = []

        def fetch_daily():
            nonlocal daily_df
            daily_df = fetcher.get_daily_kline_range(code, start_ymd, end_ymd)

        def fetch_weekly():
            nonlocal weekly_df
            weekly_df = fetcher.get_weekly_kline_range(code, start_ymd, end_ymd)

        t1 = threading.Thread(target=fetch_daily, daemon=True)
        t2 = threading.Thread(target=fetch_weekly, daemon=True)
        t1.start()
        t2.start()
        t1.join(timeout=max(1, int(args.per_stock_timeout)))
        t2.join(timeout=max(1, int(args.per_stock_timeout)))
        if t1.is_alive() or t2.is_alive():
            return code, "fail", False, False

        saved_daily = False
        saved_weekly = False

        now = datetime.now(timezone.utc).timestamp()

        if daily_df is not None and len(daily_df) > 0:
            save_csv_with_meta(
                daily_df,
                daily_csv,
                daily_meta,
                {"saved_at": now, "start": start_ymd, "end": end_ymd},
            )
            saved_daily = True

        if weekly_df is not None and len(weekly_df) > 0:
            save_csv_with_meta(
                weekly_df,
                weekly_csv,
                weekly_meta,
                {"saved_at": now, "start": start_ymd, "end": end_ymd},
            )
            saved_weekly = True

        if not saved_daily and not saved_weekly:
            return code, "fail", False, False
        return code, "ok", saved_daily, saved_weekly

    print("=" * 100)
    print(f"[download] start={start_ymd} end={end_ymd} total={total} cache_dir={cache_dir} workers={args.max_workers}")
    print("=" * 100)

    with ThreadPoolExecutor(max_workers=max(1, args.max_workers)) as ex:
        futs = {ex.submit(work, c): c for c in codes}
        for i, fut in enumerate(as_completed(futs), start=1):
            code = futs[fut]
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

            # 更频繁输出，便于观察是否在跑
            if i % 10 == 0 or i == total:
                elapsed = time.time() - start_ts
                speed = stats["done"] / elapsed if elapsed > 0 else 0
                print(
                    f"[download] {stats['done']}/{total} "
                    f"daily_ok={stats['daily_ok']} weekly_ok={stats['weekly_ok']} "
                    f"skipped={stats['skipped']} fail={stats['fail']} speed={speed:.2f}/s"
                )

    # 写汇总
    summary_path = os.path.join(cache_dir, "download_2024_2025_summary.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
    print("=" * 100)
    print("[download] DONE ->", summary_path)


if __name__ == "__main__":
    main()

