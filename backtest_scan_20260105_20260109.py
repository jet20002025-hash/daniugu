import os
import json
import datetime as dt
import pandas as pd

from bull_stock_analyzer import BullStockAnalyzer

OUT_DIR = os.path.join(os.getcwd(), "backtest_daily_scans_20260105_20260109")
os.makedirs(OUT_DIR, exist_ok=True)

DATES = ["2026-01-05", "2026-01-06", "2026-01-07", "2026-01-08", "2026-01-09"]

MIN_MATCH = 0.90
MAX_CAP = 100.0
USE_PARALLEL = True
MAX_WORKERS = 8

analyzer = BullStockAnalyzer()
# 尽量复用已训练模型
try:
    analyzer.load_models()
except Exception:
    pass

summary_rows = []

for d in DATES:
    print("=" * 100)
    print(f"[backtest] scan_date={d} min_match={MIN_MATCH} max_cap={MAX_CAP} workers={MAX_WORKERS}")

    start = dt.datetime.now()
    result = analyzer.scan_all_stocks(
        min_match_score=MIN_MATCH,
        max_market_cap=MAX_CAP,
        limit=None,
        use_parallel=USE_PARALLEL,
        max_workers=MAX_WORKERS,
        scan_date=d,
        scan_session="close",
        force_refresh=True,
    )
    elapsed = (dt.datetime.now() - start).total_seconds()

    candidates = result.get("candidates") or []
    # 统一字段
    norm = []
    for c in candidates:
        norm.append({
            "scan_date": d,
            "code": c.get("股票代码") or c.get("code"),
            "name": c.get("股票名称") or c.get("name"),
            "match_score": c.get("匹配度") or c.get("match_score"),
            "buy_date": c.get("最佳买点日期") or c.get("buy_date"),
            "buy_price": c.get("最佳买点价格") or c.get("buy_price"),
            "current_price": c.get("当前价格") or c.get("current_price"),
            "market_cap": c.get("市值") or c.get("market_cap"),
            "scan_session": c.get("时间段") or c.get("scan_session") or "close",
        })

    df = pd.DataFrame(norm)
    if not df.empty:
        df["match_score"] = pd.to_numeric(df["match_score"], errors="coerce")
        df = df.sort_values(["match_score"], ascending=False)

    out_csv = os.path.join(OUT_DIR, f"scan_{d}_min0.90_cap100.csv")
    df.to_csv(out_csv, index=False, encoding="utf-8-sig")

    out_json = os.path.join(OUT_DIR, f"scan_{d}_min0.90_cap100.json")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump({
            "scan_date": d,
            "min_match_score": MIN_MATCH,
            "max_market_cap": MAX_CAP,
            "elapsed_seconds": elapsed,
            "found_count": int(result.get("found_count") or len(candidates)),
            "total_scanned": int(result.get("total_scanned") or 0),
            "candidates": norm,
        }, f, ensure_ascii=False, indent=2)

    summary_rows.append({
        "scan_date": d,
        "found_count": int(result.get("found_count") or len(candidates)),
        "total_scanned": int(result.get("total_scanned") or 0),
        "elapsed_seconds": round(elapsed, 2),
        "top_code": (df.iloc[0]["code"] if not df.empty else ""),
        "top_name": (df.iloc[0]["name"] if not df.empty else ""),
        "top_match": (float(df.iloc[0]["match_score"]) if not df.empty and pd.notna(df.iloc[0]["match_score"]) else None),
    })

    print(f"[backtest] {d} done: found={summary_rows[-1]['found_count']} scanned={summary_rows[-1]['total_scanned']} elapsed={elapsed:.1f}s -> {out_csv}")

summary_df = pd.DataFrame(summary_rows)
summary_path = os.path.join(OUT_DIR, "summary.csv")
summary_df.to_csv(summary_path, index=False, encoding="utf-8-sig")
print("=" * 100)
print("[backtest] ALL DONE ->", summary_path)
