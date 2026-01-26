#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
下载训练股票从2022年开始的完整数据（日K + 周K）
使用 akshare，支持指定日期范围
"""
import os
import sys
import json
import time
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed

for k in ["http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY", "all_proxy", "ALL_PROXY", "no_proxy", "NO_PROXY"]:
    os.environ.pop(k, None)
os.environ["NO_PROXY"] = "*"
os.environ["no_proxy"] = "*"

import pandas as pd
import akshare as ak

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

from download_training_data import get_training_stock_codes
from data_fetcher import DataFetcher


def _save_csv_with_meta(df: pd.DataFrame, csv_path: str, meta_path: str, meta: dict) -> None:
    """保存CSV和meta文件"""
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)


def download_stock_2022_onwards(code: str, fetcher, daily_dir: str, weekly_dir: str, end_ymd: str) -> tuple[str, str, bool, bool]:
    """下载单只股票从2022-01-01开始的数据"""
    start_ymd = "20220101"
    
    daily_csv = os.path.join(daily_dir, f"{code}.csv")
    daily_meta = os.path.join(daily_dir, f"{code}.meta.json")
    weekly_csv = os.path.join(weekly_dir, f"{code}.csv")
    weekly_meta = os.path.join(weekly_dir, f"{code}.meta.json")
    
    saved_daily = False
    saved_weekly = False
    
    # 下载日K线
    try:
        print(f"  [{code}] 下载日K线 ({start_ymd} - {end_ymd})...", end='', flush=True)
        daily_df = None
        for attempt in range(3):
            try:
                daily_df = ak.stock_zh_a_hist(
                    symbol=str(code),
                    period="daily",
                    start_date=start_ymd,
                    end_date=end_ymd,
                    adjust="qfq",
                )
                break
            except Exception as e:
                if attempt < 2:
                    time.sleep(1 * (attempt + 1))
                else:
                    print(f" ❌ 失败: {e}")
        
        if daily_df is not None and len(daily_df) > 0:
            # 标准化列名
            if len(daily_df.columns) > 0:
                daily_df = daily_df.rename(columns={daily_df.columns[0]: "日期"})
            if "日期" in daily_df.columns:
                daily_df["日期"] = pd.to_datetime(daily_df["日期"], errors="coerce")
                daily_df = daily_df.dropna(subset=["日期"]).sort_values("日期").reset_index(drop=True)
            
            # 保存
            now_ts = datetime.now(timezone.utc).timestamp()
            meta = {"saved_at": now_ts, "start": start_ymd, "end": end_ymd}
            _save_csv_with_meta(daily_df, daily_csv, daily_meta, meta)
            saved_daily = True
            print(f" ✅ ({len(daily_df)} 条)")
        else:
            print(" ❌ 无数据")
    except Exception as e:
        print(f" ❌ 异常: {e}")
    
    # 下载周K线
    try:
        print(f"  [{code}] 下载周K线 ({start_ymd} - {end_ymd})...", end='', flush=True)
        weekly_df = None
        for attempt in range(3):
            try:
                weekly_df = ak.stock_zh_a_hist(
                    symbol=str(code),
                    period="weekly",
                    start_date=start_ymd,
                    end_date=end_ymd,
                    adjust="qfq",
                )
                break
            except Exception as e:
                if attempt < 2:
                    time.sleep(1 * (attempt + 1))
                else:
                    print(f" ❌ 失败: {e}")
        
        if weekly_df is not None and len(weekly_df) > 0:
            # 标准化列名
            if len(weekly_df.columns) > 0:
                weekly_df = weekly_df.rename(columns={weekly_df.columns[0]: "日期"})
            if "日期" in weekly_df.columns:
                weekly_df["日期"] = pd.to_datetime(weekly_df["日期"], errors="coerce")
                weekly_df = weekly_df.dropna(subset=["日期"]).sort_values("日期").reset_index(drop=True)
            if "成交量" in weekly_df.columns and "周成交量" not in weekly_df.columns:
                weekly_df = weekly_df.rename(columns={"成交量": "周成交量"})
            
            # 保存
            now_ts = datetime.now(timezone.utc).timestamp()
            meta = {"saved_at": now_ts, "start": start_ymd, "end": end_ymd}
            _save_csv_with_meta(weekly_df, weekly_csv, weekly_meta, meta)
            saved_weekly = True
            print(f" ✅ ({len(weekly_df)} 条)")
        else:
            print(" ❌ 无数据")
    except Exception as e:
        print(f" ❌ 异常: {e}")
    
    status = "ok" if (saved_daily or saved_weekly) else "fail"
    return code, status, saved_daily, saved_weekly


def main():
    print("=" * 80)
    print("📥 下载训练股票从2022年开始的完整数据")
    print("=" * 80)
    print()
    
    codes = get_training_stock_codes()
    if not codes:
        print("❌ 未找到训练股票列表")
        return
    
    print(f"训练股票数量: {len(codes)}")
    print(f"股票列表: {codes}")
    print()
    
    fetcher = DataFetcher()
    paths = fetcher._local_cache_paths()
    daily_dir = paths["daily_dir"]
    weekly_dir = paths["weekly_dir"]
    os.makedirs(daily_dir, exist_ok=True)
    os.makedirs(weekly_dir, exist_ok=True)
    
    end_ymd = datetime.now().strftime("%Y%m%d")
    start_ymd = "20220101"
    
    print(f"日期范围: {start_ymd} 至 {end_ymd}")
    print(f"并发数: 2（避免网络限流）")
    print()
    
    stats = {"total": len(codes), "done": 0, "daily_ok": 0, "weekly_ok": 0, "fail": 0}
    start_ts = time.time()
    
    with ThreadPoolExecutor(max_workers=2) as ex:
        futs = {
            ex.submit(download_stock_2022_onwards, c, fetcher, daily_dir, weekly_dir, end_ymd): c
            for c in codes
        }
        for fut in as_completed(futs):
            c = futs[fut]
            try:
                code, status, d_ok, w_ok = fut.result()
                if status == "ok":
                    if d_ok:
                        stats["daily_ok"] += 1
                    if w_ok:
                        stats["weekly_ok"] += 1
                else:
                    stats["fail"] += 1
            except Exception as e:
                print(f"  [{c}] ❌ 异常: {e}")
                stats["fail"] += 1
            stats["done"] += 1
            
            if stats["done"] % 2 == 0 or stats["done"] == stats["total"]:
                el = time.time() - start_ts
                speed = stats["done"] / el if el > 0 else 0
                print()
                print(f"[进度] {stats['done']}/{stats['total']} "
                      f"daily_ok={stats['daily_ok']} weekly_ok={stats['weekly_ok']} "
                      f"fail={stats['fail']} speed={speed:.2f}/s")
                print()
    
    print()
    print("=" * 80)
    print("✅ 下载完成")
    print("=" * 80)
    print(f"总计: {stats['total']} 只")
    print(f"日K成功: {stats['daily_ok']} 只")
    print(f"周K成功: {stats['weekly_ok']} 只")
    print(f"失败: {stats['fail']} 只")
    print()


if __name__ == "__main__":
    main()
