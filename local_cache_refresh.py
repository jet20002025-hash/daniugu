#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
本地缓存预下载/预热脚本（建议每天 11:30 与 15:00 各运行一次）

做什么：
- 刷新股票列表到本地缓存（cache/stock_list_all.json）
- 可选：预热周K线到本地缓存（cache/weekly_kline/{code}.json）

用法示例：
  python3 local_cache_refresh.py --mode stock_list
  python3 local_cache_refresh.py --mode weekly --max-workers 8
  python3 local_cache_refresh.py --mode stock_list,weekly --max-workers 8

注意：
- 预热全市场周K会较慢（几千只股票），建议先跑 stock_list，扫描时按需缓存周K；
  如果你希望“扫描几乎不碰网络”，再开启 weekly 预热并逐步调大并发。
"""

import os

# 很多本地环境会配置代理，requests/akshare 可能在 import 时就读取代理配置；
# 因此在最顶部先清除代理环境变量，保证后续所有网络请求走直连（更稳定）。
for k in ["http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY", "all_proxy", "ALL_PROXY", "no_proxy", "NO_PROXY"]:
    os.environ.pop(k, None)
# 强制对所有地址不走代理（即使系统层面配置了代理）
os.environ["NO_PROXY"] = "*"
os.environ["no_proxy"] = "*"

import argparse
import datetime as dt
from concurrent.futures import ThreadPoolExecutor, as_completed

from data_fetcher import DataFetcher


def refresh_stock_list(fetcher: DataFetcher) -> int:
    import akshare as ak
    stock_list = ak.stock_info_a_code_name()
    ok = fetcher._save_stock_list_to_cache(stock_list)
    if not ok:
        raise RuntimeError("保存股票列表到本地缓存失败")
    return len(stock_list)


def warm_weekly_kline(fetcher: DataFetcher, max_workers: int = 8, force: bool = False) -> dict:
    stocks = fetcher.get_all_stocks()
    if stocks is None or len(stocks) == 0:
        raise RuntimeError("无法获取股票列表（用于周K预热）")

    # 尝试推断代码列
    code_col = None
    for col in stocks.columns:
        if "代码" in str(col) or "code" in str(col).lower():
            code_col = col
            break
    if code_col is None:
        code_col = stocks.columns[0]

    codes = [str(x) for x in stocks[code_col].tolist()]

    stats = {"total": len(codes), "ok": 0, "fail": 0}
    start = dt.datetime.now()

    def work(code: str) -> bool:
        # force=True：强制重新拉取周K并覆盖本地缓存
        if force:
            df = fetcher.get_weekly_kline(code, period="2y", use_cache=False)
            if df is not None and len(df) > 0:
                # 显式保存到本地文件缓存（不依赖 get_weekly_kline 的 use_cache=True 才保存的逻辑）
                fetcher._save_weekly_kline_to_cache(code, df, ttl=86400)
                return True
            return False
        # 默认：优先使用本地/云端缓存，缺失时才拉取并写入缓存
        df = fetcher.get_weekly_kline(code, period="2y", use_cache=True)
        return df is not None and len(df) > 0

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futs = {ex.submit(work, c): c for c in codes}
        for i, fut in enumerate(as_completed(futs), start=1):
            code = futs[fut]
            try:
                ok = fut.result()
                if ok:
                    stats["ok"] += 1
                else:
                    stats["fail"] += 1
            except Exception:
                stats["fail"] += 1

            if i % 200 == 0 or i == stats["total"]:
                elapsed = (dt.datetime.now() - start).total_seconds()
                speed = i / elapsed if elapsed > 0 else 0
                print(f"[weekly] {i}/{stats['total']} ok={stats['ok']} fail={stats['fail']} speed={speed:.1f}/s force={force}")

    return stats


def _acquire_lock(lock_path: str) -> bool:
    """简单锁：防止两次定时任务重叠运行。"""
    try:
        if os.path.exists(lock_path):
            try:
                with open(lock_path, "r", encoding="utf-8") as f:
                    pid = int((f.read() or "").strip() or "0")
                if pid > 0:
                    # 检查进程是否仍存在
                    try:
                        os.kill(pid, 0)
                        print(f"[lock] detected running pid={pid}, skip this run")
                        return False
                    except Exception:
                        pass
            except Exception:
                pass
        os.makedirs(os.path.dirname(lock_path), exist_ok=True)
        with open(lock_path, "w", encoding="utf-8") as f:
            f.write(str(os.getpid()))
        return True
    except Exception:
        # 锁失败时也继续（不阻塞），但尽量提示
        print("[lock] failed to acquire lock (continue anyway)")
        return True


def _release_lock(lock_path: str) -> None:
    try:
        if os.path.exists(lock_path):
            os.remove(lock_path)
    except Exception:
        pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default="stock_list", help="stock_list, weekly 或 stock_list,weekly")
    # 默认并发调低一些，避免数据源限流/断连（需要更快可手动调大）
    ap.add_argument("--max-workers", type=int, default=2, help="weekly 预热并发线程数")
    ap.add_argument("--force-weekly", action="store_true", help="强制刷新周K（跳过缓存，覆盖本地文件）")
    ap.add_argument("--cache-dir", default=None, help="覆盖本地缓存目录（也可用环境变量 LOCAL_CACHE_DIR）")
    args = ap.parse_args()

    if args.cache_dir:
        os.environ["LOCAL_CACHE_DIR"] = args.cache_dir

    fetcher = DataFetcher()
    lock_path = os.path.join(fetcher._local_cache_dir(), "local_cache_refresh.lock")
    if not _acquire_lock(lock_path):
        return

    modes = [m.strip() for m in args.mode.split(",") if m.strip()]
    print("=" * 80)
    print(f"[cache_refresh] start {dt.datetime.now().strftime('%F %T')} modes={modes} cache_dir={fetcher._local_cache_dir()}")
    print("=" * 80)

    try:
        if "stock_list" in modes:
            n = refresh_stock_list(fetcher)
            print(f"[stock_list] refreshed: {n} stocks")

        if "weekly" in modes:
            stats = warm_weekly_kline(fetcher, max_workers=max(1, args.max_workers), force=bool(args.force_weekly))
            print(f"[weekly] done: {stats}")
    finally:
        _release_lock(lock_path)

    print("=" * 80)
    print(f"[cache_refresh] done {dt.datetime.now().strftime('%F %T')}")


if __name__ == "__main__":
    main()

