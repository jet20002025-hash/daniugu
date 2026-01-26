#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
下载从2022年开始的所有A股个股数据（日K + 周K）
使用新浪财经API，datalen 拉足覆盖 2022 至今，只保留 2022-01-01 及之后的数据。

若遇「拒绝访问 / IP 封禁」，可等 5–60 分钟或换网络/VPN 后再试。
推荐优先用 download_all_stocks_2022.py（akshare），支持 --list-cache。
"""
import os
import sys
import json
import time
import requests
import pandas as pd
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

# 配置
CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache")
DAILY_DIR = os.path.join(CACHE_DIR, "daily_kline")
WEEKLY_DIR = os.path.join(CACHE_DIR, "weekly_kline")
STOCK_LIST_PATH = os.path.join(CACHE_DIR, "stock_list_all.json")

# 2022-01-01 至今约 1000 个交易日、约 210 周，多拉一些
DAILY_DATALEN = 1500
WEEKLY_DATALEN = 300

MAX_WORKERS = 10
RETRY_TIMES = 3
CUTOFF_DATE = "2022-01-01"

session = requests.Session()
session.trust_env = False
session.headers.update({"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"})


def get_sina_daily_kline(code: str, datalen: int = DAILY_DATALEN) -> Optional[pd.DataFrame]:
    symbol = f"sh{code}" if code.startswith("6") else f"sz{code}"
    url = f"https://quotes.sina.cn/cn/api/jsonp_v2.php/data/CN_MarketDataService.getKLineData?symbol={symbol}&scale=240&datalen={datalen}"
    for attempt in range(RETRY_TIMES):
        try:
            resp = session.get(url, timeout=15)
            if resp.status_code != 200:
                continue
            text = resp.text
            if "data(" not in text:
                continue
            json_str = text.split("data(")[1].rsplit(")", 1)[0]
            data = json.loads(json_str)
            if not data:
                return None
            df = pd.DataFrame(data)
            df = df.rename(columns={
                "day": "日期", "open": "开盘", "close": "收盘",
                "high": "最高", "low": "最低", "volume": "成交量",
            })
            df = df[["日期", "开盘", "收盘", "最高", "最低", "成交量"]]
            df["开盘"] = pd.to_numeric(df["开盘"], errors="coerce")
            df["收盘"] = pd.to_numeric(df["收盘"], errors="coerce")
            df["最高"] = pd.to_numeric(df["最高"], errors="coerce")
            df["最低"] = pd.to_numeric(df["最低"], errors="coerce")
            df["成交量"] = pd.to_numeric(df["成交量"], errors="coerce").fillna(0).astype(int)
            return df
        except Exception:
            if attempt < RETRY_TIMES - 1:
                time.sleep(0.3 * (attempt + 1))
    return None


def get_sina_weekly_kline(code: str, datalen: int = WEEKLY_DATALEN) -> Optional[pd.DataFrame]:
    symbol = f"sh{code}" if code.startswith("6") else f"sz{code}"
    url = f"https://quotes.sina.cn/cn/api/jsonp_v2.php/data/CN_MarketDataService.getKLineData?symbol={symbol}&scale=1200&datalen={datalen}"
    for attempt in range(RETRY_TIMES):
        try:
            resp = session.get(url, timeout=15)
            if resp.status_code != 200:
                continue
            text = resp.text
            if "data(" not in text:
                continue
            json_str = text.split("data(")[1].rsplit(")", 1)[0]
            data = json.loads(json_str)
            if not data:
                return None
            df = pd.DataFrame(data)
            df = df.rename(columns={
                "day": "日期", "open": "开盘", "close": "收盘",
                "high": "最高", "low": "最低", "volume": "周成交量",
            })
            df = df[["日期", "开盘", "收盘", "最高", "最低", "周成交量"]]
            df["开盘"] = pd.to_numeric(df["开盘"], errors="coerce")
            df["收盘"] = pd.to_numeric(df["收盘"], errors="coerce")
            df["最高"] = pd.to_numeric(df["最高"], errors="coerce")
            df["最低"] = pd.to_numeric(df["最低"], errors="coerce")
            df["周成交量"] = pd.to_numeric(df["周成交量"], errors="coerce").fillna(0).astype(int)
            return df
        except Exception:
            if attempt < RETRY_TIMES - 1:
                time.sleep(0.3 * (attempt + 1))
    return None


def _filter_2022_onwards(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or len(df) == 0:
        return df
    df = df.copy()
    df["日期"] = pd.to_datetime(df["日期"], errors="coerce")
    df = df.dropna(subset=["日期"])
    df = df[df["日期"] >= CUTOFF_DATE].sort_values("日期").reset_index(drop=True)
    return df


def process_one(code: str, name: str, force: bool, dry_run: bool = False) -> dict:
    res = {"code": code, "name": name, "daily_ok": False, "weekly_ok": False, "skip": False, "error": None}
    daily_path = os.path.join(DAILY_DIR, f"{code}.csv")
    weekly_path = os.path.join(WEEKLY_DIR, f"{code}.csv")

    def has_2022(path: str) -> bool:
        if not os.path.exists(path):
            return False
        try:
            d = pd.read_csv(path, encoding="utf-8-sig", nrows=5000)
            if "日期" not in d.columns or len(d) == 0:
                return False
            d["日期"] = pd.to_datetime(d["日期"], errors="coerce")
            d = d.dropna(subset=["日期"])
            return (d["日期"] >= CUTOFF_DATE).any()
        except Exception:
            return False

    if not force and has_2022(daily_path) and has_2022(weekly_path):
        res["skip"] = True
        return res

    try:
        daily = get_sina_daily_kline(code)
        daily = _filter_2022_onwards(daily)
        if daily is not None and len(daily) > 0:
            if not dry_run:
                daily.to_csv(daily_path, index=False, encoding="utf-8-sig")
            res["daily_ok"] = True
        time.sleep(0.02)

        weekly = get_sina_weekly_kline(code)
        weekly = _filter_2022_onwards(weekly)
        if weekly is not None and len(weekly) > 0:
            if not dry_run:
                weekly.to_csv(weekly_path, index=False, encoding="utf-8-sig")
            res["weekly_ok"] = True
    except Exception as e:
        res["error"] = str(e)[:80]
    return res


def main():
    import argparse
    ap = argparse.ArgumentParser(description="下载从2022年开始的所有A股日K/周K（新浪API）")
    ap.add_argument("--force", action="store_true", help="强制覆盖已有2022+数据")
    ap.add_argument("--workers", type=int, default=MAX_WORKERS, help=f"并发数，默认{MAX_WORKERS}")
    ap.add_argument("--limit", type=int, default=0, help="仅处理前 N 只（0=全部）")
    ap.add_argument("--dry-run", action="store_true", help="仅试跑前3只，打印调试信息")
    args = ap.parse_args()

    os.makedirs(DAILY_DIR, exist_ok=True)
    os.makedirs(WEEKLY_DIR, exist_ok=True)

    if not os.path.exists(STOCK_LIST_PATH):
        print(f"❌ 股票列表不存在: {STOCK_LIST_PATH}")
        print("请先运行本地/Web 刷新股票列表，或使用 data_fetcher 拉取并保存。")
        sys.exit(1)

    with open(STOCK_LIST_PATH, "r", encoding="utf-8") as f:
        raw = json.load(f)

    stocks = []
    for item in raw:
        code = item.get("code") or item.get("代码", "")
        name = item.get("name") or item.get("名称", "")
        if not code:
            continue
        code = str(code).strip()
        if len(code) != 6 or not code.isdigit():
            continue
        stocks.append({"code": code, "name": name or ""})

    if args.limit > 0:
        stocks = stocks[: args.limit]
        print(f"⚠️ --limit={args.limit}，仅处理前 {len(stocks)} 只")
    if args.dry_run:
        stocks = stocks[:3]
        args.force = True  # 强制抓取，否则会因已有数据而跳过
        print("⚠️ --dry-run：仅试跑前 3 只，不写入文件")
    total = len(stocks)
    print("=" * 70)
    print("📥 下载从2022年开始的所有A股个股数据（新浪API）")
    print("=" * 70)
    print(f"股票数: {total}")
    print(f"日期: >= {CUTOFF_DATE}")
    print(f"并发: {args.workers}")
    print(f"强制覆盖: {args.force}")
    print()

    start = time.time()
    done = 0
    daily_ok = 0
    weekly_ok = 0
    skip = 0
    err = 0
    last_report = start

    dry_run = getattr(args, "dry_run", False)
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        f2s = {ex.submit(process_one, s["code"], s["name"], args.force, dry_run): s for s in stocks}
        for fut in as_completed(f2s):
            s = f2s[fut]
            try:
                r = fut.result()
                if r["skip"]:
                    skip += 1
                else:
                    if r["daily_ok"]:
                        daily_ok += 1
                    if r["weekly_ok"]:
                        weekly_ok += 1
                    if r["error"]:
                        err += 1
            except Exception as e:
                err += 1
            done += 1

            now = time.time()
            if done % 200 == 0 or done == total or (now - last_report) >= 10:
                el = now - start
                speed = done / el if el > 0 else 0
                eta = (total - done) / speed if speed > 0 else 0
                print(f"进度: {done}/{total} ({100*done/total:.1f}%) | "
                      f"日K: {daily_ok} 周K: {weekly_ok} 跳过: {skip} 错误: {err} | "
                      f"{speed:.1f}只/s 剩余约{eta/60:.1f}min", flush=True)
                last_report = now

    el = time.time() - start
    print()
    print("=" * 70)
    print("✅ 完成")
    print("=" * 70)
    print(f"耗时: {el/60:.1f} 分钟")
    print(f"日K成功: {daily_ok} | 周K成功: {weekly_ok} | 跳过: {skip} | 错误: {err}")
    print()


if __name__ == "__main__":
    main()
