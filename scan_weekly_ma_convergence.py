#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
周线均线粘合扫描脚本

功能：
- 从本地缓存的周 K 线中，找出「5 / 10 / 20 / 30 周均线」彼此非常接近的个股
- 默认判定条件：4 条均线之间的最大差值不超过 2%（相对于均线平均值）

使用示例：

  python3 scan_weekly_ma_convergence.py                 # 使用默认阈值 2%，扫描全部股票
  python3 scan_weekly_ma_convergence.py --threshold 1.5 # 使用 1.5% 作为阈值
  python3 scan_weekly_ma_convergence.py --max 500       # 仅扫描前 500 只（按代码列表顺序）

说明：
- 周 K、日 K 缓存路径与 `scan_near_new_high.py`、`data_fetcher.py` 保持一致，假定为前复权(qfq)。
- 本脚本只做「周线均线是否粘合」判断，不限制价格位置、趋势、市值等，可按需要再叠加其它条件。
"""

import os
import sys
import json
import argparse
from typing import Optional, Tuple, List

import pandas as pd

# 确保可以导入同目录下模块
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from technical_analysis import TechnicalAnalysis  # noqa: E402
from scan_near_new_high import load_weekly_kline_from_cache  # noqa: E402


STOCK_LIST_PATH = os.path.join(BASE_DIR, "cache", "stock_list_all.json")


def load_stock_list(limit: Optional[int] = None) -> List[Tuple[str, str]]:
    """
    从 cache/stock_list_all.json 加载股票代码和名称。
    返回 [(code, name), ...]
    """
    stocks: List[Tuple[str, str]] = []
    if not os.path.exists(STOCK_LIST_PATH):
        print(f"⚠️ 未找到股票列表文件: {STOCK_LIST_PATH}，将不会扫描任何股票。")
        return stocks
    try:
        with open(STOCK_LIST_PATH, "r", encoding="utf-8") as f:
            raw = json.load(f)
        items = []
        if isinstance(raw, list):
            items = raw
        elif isinstance(raw, dict) and "data" in raw:
            items = raw["data"]
        for s in items:
            code = str(s.get("code") or s.get("代码") or "").strip()
            name = str(s.get("name") or s.get("名称") or code).strip()
            if code and len(code) == 6 and code.isdigit():
                stocks.append((code, name))
        if limit is not None and limit > 0:
            stocks = stocks[:limit]
    except Exception as e:  # pragma: no cover - 仅日志
        print(f"⚠️ 加载股票列表失败: {e}")
    return stocks


def calc_weekly_ma_convergence(weekly_df: pd.DataFrame) -> Optional[Tuple[float, List[float]]]:
    """
    计算最新一周的 5/10/20/30 周均线粘合度。

    返回:
        (diff_pct, [ma5, ma10, ma20, ma30])
        其中 diff_pct 为均线之间最大差值 / 均值 * 100（百分比）。
        如果数据不足或无法计算，返回 None。
    """
    if weekly_df is None or weekly_df.empty:
        return None
    # 至少需要 30 周数据
    if len(weekly_df) < 30:
        return None
    if "收盘" not in weekly_df.columns:
        return None

    # 统一按日期排序
    df = weekly_df.copy()
    if "日期" in df.columns:
        df["日期"] = pd.to_datetime(df["日期"], errors="coerce")
        df = df.dropna(subset=["日期"]).sort_values("日期").reset_index(drop=True)

    n = len(df)
    last_idx = n - 1

    ma5 = TechnicalAnalysis.calculate_ma(df, period=5)
    ma10 = TechnicalAnalysis.calculate_ma(df, period=10)
    ma20 = TechnicalAnalysis.calculate_ma(df, period=20)
    ma30 = TechnicalAnalysis.calculate_ma(df, period=30)
    if any(x is None for x in (ma5, ma10, ma20, ma30)):
        return None
    try:
        vals = [
            float(ma5.iloc[last_idx]),
            float(ma10.iloc[last_idx]),
            float(ma20.iloc[last_idx]),
            float(ma30.iloc[last_idx]),
        ]
    except Exception:
        return None
    # 检查 NaN 或非正值
    if any(pd.isna(v) or v <= 0 for v in vals):
        return None

    ma_avg = sum(vals) / len(vals)
    if ma_avg <= 0:
        return None
    diff = max(vals) - min(vals)
    diff_pct = diff / ma_avg * 100.0
    return diff_pct, vals


def scan_all_stocks(threshold_pct: float = 2.0, limit: Optional[int] = None):
    """
    扫描所有股票，找出周线 5/10/20/30 均线差值在 threshold_pct% 以内的个股。
    """
    stocks = load_stock_list(limit=limit)
    if not stocks:
        print("⚠️ 没有股票列表可供扫描。")
        return

    print(f"开始扫描 {len(stocks)} 只股票，阈值 = {threshold_pct:.2f}% ...")
    results = []
    for idx, (code, name) in enumerate(stocks, start=1):
        if idx % 200 == 0 or idx == 1:
            print(f"  进度: {idx}/{len(stocks)} ({idx/len(stocks)*100:.1f}%)")
        weekly_df = load_weekly_kline_from_cache(code)
        if weekly_df is None:
            continue
        res = calc_weekly_ma_convergence(weekly_df)
        if res is None:
            continue
        diff_pct, ma_vals = res
        if diff_pct <= threshold_pct:
            last_row = weekly_df.iloc[-1]
            date_str = str(last_row.get("日期", ""))[:10]
            close = float(last_row.get("收盘", 0) or 0)
            results.append(
                {
                    "code": code,
                    "name": name,
                    "date": date_str,
                    "close": round(close, 2),
                    "ma5": round(ma_vals[0], 2),
                    "ma10": round(ma_vals[1], 2),
                    "ma20": round(ma_vals[2], 2),
                    "ma30": round(ma_vals[3], 2),
                    "diff_pct": round(diff_pct, 2),
                }
            )

    if not results:
        print("扫描完成，没有找到符合条件的股票。")
        return

    # 按粘合度从小到大排序
    results.sort(key=lambda x: x["diff_pct"])

    print(f"\n✅ 扫描完成，共找到 {len(results)} 只均线粘合个股（阈值 {threshold_pct:.2f}%）：\n")
    print("代码    名称        日期        收盘价   MA5    MA10   MA20   MA30   差值%")
    print("-" * 80)
    for r in results:
        print(
            f"{r['code']}  {r['name']:<8}  {r['date']}  "
            f"{r['close']:>6.2f}  {r['ma5']:>6.2f}  {r['ma10']:>6.2f}  "
            f"{r['ma20']:>6.2f}  {r['ma30']:>6.2f}  {r['diff_pct']:>6.2f}"
        )

    # 同时输出到 CSV，方便后续筛选
    out_path = os.path.join(BASE_DIR, f"weekly_ma_convergence_{int(threshold_pct*1000)}_{len(results)}.csv")
    try:
        pd.DataFrame(results).to_csv(out_path, index=False, encoding="utf-8-sig")
        print(f"\n结果已保存到: {out_path}")
    except Exception as e:  # pragma: no cover - 仅日志
        print(f"⚠️ 保存 CSV 失败: {e}")


def main():
    parser = argparse.ArgumentParser(description="扫描 5/10/20/30 周均线粘合个股")
    parser.add_argument(
        "--threshold",
        type=float,
        default=2.0,
        help="均线最大差值占均值的百分比阈值，例如 2 表示 2%%（默认 2）",
    )
    parser.add_argument(
        "--max",
        type=int,
        default=None,
        help="最多扫描多少只股票（按 stock_list_all.json 顺序，默认全部）",
    )
    args = parser.parse_args()
    scan_all_stocks(threshold_pct=args.threshold, limit=args.max)


if __name__ == "__main__":
    main()

