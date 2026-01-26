#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
下载所有A股从2022年开始的完整数据（日K + 周K）
使用 akshare，支持指定日期范围。

用法:
  python download_all_stocks_2022.py --list-cache
     从 cache/stock_list_all.json 读列表，仅下载缺失 2022+ 数据的股票。
  python download_all_stocks_2022.py --list-cache --force
     强制重新下载全部。
  python download_all_stocks_2022.py --list-cache --limit 100 --workers 1
     仅处理前 100 只，单线程（网络不稳时建议 --workers 1）。

后台运行: nohup python download_all_stocks_2022.py --list-cache > download_2022.log 2>&1 &
"""
import os
import sys
import json
import time
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed

# 禁用代理
for k in ["http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY", "all_proxy", "ALL_PROXY", "no_proxy", "NO_PROXY"]:
    os.environ.pop(k, None)
os.environ["NO_PROXY"] = "*"
os.environ["no_proxy"] = "*"

import pandas as pd
import akshare as ak

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

from data_fetcher import DataFetcher


def _save_csv_with_meta(df: pd.DataFrame, csv_path: str, meta_path: str, meta: dict) -> None:
    """保存CSV和meta文件"""
    if df is None or len(df) == 0:
        return
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)


def download_stock_2022_onwards(code: str, name: str, daily_dir: str, weekly_dir: str, end_ymd: str) -> tuple[str, str, bool, bool, str]:
    """下载单只股票从2022-01-01开始的数据"""
    start_ymd = "20220101"
    
    daily_csv = os.path.join(daily_dir, f"{code}.csv")
    daily_meta = os.path.join(daily_dir, f"{code}.meta.json")
    weekly_csv = os.path.join(weekly_dir, f"{code}.csv")
    weekly_meta = os.path.join(weekly_dir, f"{code}.meta.json")
    
    saved_daily = False
    saved_weekly = False
    error_msg = None
    
    # 下载日K线
    try:
        daily_df = None
        for attempt in range(5):
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
                if attempt < 4:
                    time.sleep(3 * (attempt + 1))
                else:
                    error_msg = f"日K下载失败: {str(e)[:100]}"
        
        if daily_df is not None and len(daily_df) > 0:
            # 标准化列名
            if len(daily_df.columns) > 0:
                daily_df = daily_df.rename(columns={daily_df.columns[0]: "日期"})
            if "日期" in daily_df.columns:
                daily_df["日期"] = pd.to_datetime(daily_df["日期"], errors="coerce")
                daily_df = daily_df.dropna(subset=["日期"]).sort_values("日期").reset_index(drop=True)
            
            # 保存
            now_ts = datetime.now(timezone.utc).timestamp()
            meta = {"saved_at": now_ts, "start": start_ymd, "end": end_ymd, "code": code, "name": name}
            _save_csv_with_meta(daily_df, daily_csv, daily_meta, meta)
            saved_daily = True
    except Exception as e:
        if not error_msg:
            error_msg = f"日K异常: {str(e)[:100]}"
    
    time.sleep(1)
    
    # 下载周K线
    try:
        weekly_df = None
        for attempt in range(5):
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
                if attempt < 4:
                    time.sleep(3 * (attempt + 1))
                else:
                    if error_msg:
                        error_msg += f"; 周K下载失败: {str(e)[:100]}"
                    else:
                        error_msg = f"周K下载失败: {str(e)[:100]}"
        
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
            meta = {"saved_at": now_ts, "start": start_ymd, "end": end_ymd, "code": code, "name": name}
            _save_csv_with_meta(weekly_df, weekly_csv, weekly_meta, meta)
            saved_weekly = True
    except Exception as e:
        if error_msg:
            error_msg += f"; 周K异常: {str(e)[:100]}"
        else:
            error_msg = f"周K异常: {str(e)[:100]}"
    
    status = "ok" if (saved_daily or saved_weekly) else "fail"
    return code, status, saved_daily, saved_weekly, error_msg or ""


def main():
    import argparse
    parser = argparse.ArgumentParser(description='下载所有A股从2022年开始的数据')
    parser.add_argument('--force', action='store_true', help='强制重新下载所有数据')
    parser.add_argument('--list-cache', action='store_true', help='从 cache/stock_list_all.json 读取股票列表（不调用 akshare）')
    parser.add_argument('--limit', type=int, default=0, help='仅处理前 N 只（0=全部）')
    parser.add_argument('--workers', type=int, default=3, help='并发数，网络不稳时可设为 1')
    args = parser.parse_args()
    
    print("=" * 80)
    print("📥 下载所有A股从2022年开始的完整数据")
    if args.force:
        print("⚠️  强制模式：将重新下载所有数据")
    if args.list_cache:
        print("⚠️  使用本地股票列表: cache/stock_list_all.json")
    print("=" * 80)
    print()
    
    codes = []
    names = []
    fetcher = DataFetcher()
    
    if args.list_cache:
        list_path = os.path.join(PROJECT_ROOT, "cache", "stock_list_all.json")
        if not os.path.exists(list_path):
            print(f"❌ 股票列表不存在: {list_path}")
            return
        with open(list_path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        for item in raw:
            code = (item.get("code") or item.get("代码", "")).strip()
            name = item.get("name") or item.get("名称", "") or ""
            if not code or len(code) != 6 or not code.isdigit():
                continue
            if name and ("ST" in name or "退" in name):
                continue
            if code.startswith("9") or code.startswith("2"):
                continue
            codes.append(code)
            names.append(name)
        print(f"📊 从缓存读取股票列表: {len(codes)} 只")
    else:
        print("📊 正在获取所有A股列表...")
        stock_df = fetcher.get_all_stocks(timeout=30, max_retries=3)
        if stock_df is None or len(stock_df) == 0:
            print("❌ 无法获取股票列表")
            return
        code_col = None
        name_col = None
        for col in stock_df.columns:
            col_lower = str(col).lower()
            if "code" in col_lower or "代码" in col or col == stock_df.columns[0]:
                code_col = col
            if "name" in col_lower or "名称" in col or (len(stock_df.columns) >= 2 and col == stock_df.columns[1]):
                name_col = col
        if code_col is None:
            code_col = stock_df.columns[0]
        if name_col is None and len(stock_df.columns) >= 2:
            name_col = stock_df.columns[1]
        for _, row in stock_df.iterrows():
            code = str(row[code_col]).strip()
            name = str(row[name_col]).strip() if name_col else ""
            if not code or len(code) != 6 or not code.isdigit():
                continue
            if name and ("ST" in name or "退" in name):
                continue
            if code.startswith("9") or code.startswith("2"):
                continue
            codes.append(code)
            names.append(name)
        print(f"✅ 获取到 {len(codes)} 只A股")
    
    if args.limit > 0:
        codes = codes[: args.limit]
        names = names[: args.limit]
        print(f"⚠️ --limit={args.limit}，仅处理前 {len(codes)} 只")
    
    if not codes:
        print("❌ 无有效股票")
        return
    print()
    
    # 设置目录
    paths = fetcher._local_cache_paths()
    daily_dir = paths["daily_dir"]
    weekly_dir = paths["weekly_dir"]
    os.makedirs(daily_dir, exist_ok=True)
    os.makedirs(weekly_dir, exist_ok=True)
    
    end_ymd = datetime.now().strftime("%Y%m%d")
    start_ymd = "20220101"
    
    workers = args.workers
    print(f"日期范围: {start_ymd} 至 {end_ymd}")
    print(f"并发数: {workers}")
    print(f"预计耗时: 约 {len(codes) * 2 / max(1, workers) / 60:.1f} 分钟")
    print()
    
    stats = {"total": len(codes), "done": 0, "daily_ok": 0, "weekly_ok": 0, "fail": 0, "skip": 0}
    start_ts = time.time()
    last_report_ts = start_ts
    
    # 检查已存在的文件，跳过已有完整数据的股票
    print("🔍 检查已有数据...")
    to_download = []
    for i, (code, name) in enumerate(zip(codes, names)):
        daily_csv = os.path.join(daily_dir, f"{code}.csv")
        weekly_csv = os.path.join(weekly_dir, f"{code}.csv")
        
        # 检查是否已有2022年数据
        has_daily_2022 = False
        has_weekly_2022 = False
        
        if os.path.exists(daily_csv):
            try:
                df = pd.read_csv(daily_csv, encoding='utf-8-sig', nrows=1)
                if '日期' in df.columns:
                    df_full = pd.read_csv(daily_csv, encoding='utf-8-sig')
                    df_full['日期'] = pd.to_datetime(df_full['日期'], errors='coerce')
                    df_2022 = df_full[df_full['日期'] >= datetime(2022, 1, 1)]
                    if len(df_2022) > 0:
                        has_daily_2022 = True
            except:
                pass
        
        if os.path.exists(weekly_csv):
            try:
                df = pd.read_csv(weekly_csv, encoding='utf-8-sig', nrows=1)
                if '日期' in df.columns:
                    df_full = pd.read_csv(weekly_csv, encoding='utf-8-sig')
                    df_full['日期'] = pd.to_datetime(df_full['日期'], errors='coerce')
                    df_2022 = df_full[df_full['日期'] >= datetime(2022, 1, 1)]
                    if len(df_2022) > 0:
                        has_weekly_2022 = True
            except:
                pass
        
        if args.force:
            to_download.append((code, name))
        elif has_daily_2022 and has_weekly_2022:
            stats["skip"] += 1
        else:
            to_download.append((code, name))
    
    print(f"✅ 已有完整数据（跳过）: {stats['skip']} 只")
    print(f"📥 需要下载: {len(to_download)} 只")
    print()
    
    if len(to_download) == 0:
        print("✅ 所有股票数据已完整，无需下载")
        return
    
    # 开始下载
    print("=" * 80)
    print("开始下载...")
    print("=" * 80)
    print()
    
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {
            ex.submit(download_stock_2022_onwards, c, n, daily_dir, weekly_dir, end_ymd): (c, n)
            for c, n in to_download
        }
        
        for fut in as_completed(futs):
            c, n = futs[fut]
            try:
                code, status, d_ok, w_ok, err = fut.result()
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
            
            # 每10秒或每50只股票报告一次进度
            now_ts = time.time()
            if now_ts - last_report_ts >= 10 or stats["done"] % 50 == 0 or stats["done"] == len(to_download):
                el = now_ts - start_ts
                speed = stats["done"] / el if el > 0 else 0
                remaining = (len(to_download) - stats["done"]) / speed if speed > 0 else 0
                print(f"[进度] {stats['done']}/{len(to_download)} "
                      f"daily_ok={stats['daily_ok']} weekly_ok={stats['weekly_ok']} "
                      f"fail={stats['fail']} speed={speed:.2f}/s "
                      f"剩余约{remaining/60:.1f}分钟")
                last_report_ts = now_ts
    
    print()
    print("=" * 80)
    print("✅ 下载完成")
    print("=" * 80)
    print(f"总计: {stats['total']} 只")
    print(f"跳过（已有数据）: {stats['skip']} 只")
    print(f"日K成功: {stats['daily_ok']} 只")
    print(f"周K成功: {stats['weekly_ok']} 只")
    print(f"失败: {stats['fail']} 只")
    print(f"总耗时: {(time.time() - start_ts) / 60:.1f} 分钟")
    print()


if __name__ == "__main__":
    main()
