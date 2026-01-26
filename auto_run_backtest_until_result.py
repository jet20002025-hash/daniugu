#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
全自动运行 model有效模型0124 回测，直到生成结果文件为止。
若单次运行无结果则重试（可调低匹配度阈值）。
"""
import os
import sys
import subprocess
import glob
import time

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
BACKTEST_SCRIPT = os.path.join(PROJECT_ROOT, 'backtest_model有效模型0124.py')
LOG_FILE = os.path.join(PROJECT_ROOT, 'backtest_model0124.log')
CSV_PREFIX = os.path.join(PROJECT_ROOT, 'backtest_model有效模型0124_')


def has_valid_result():
    """检查是否存在有效的回测结果 CSV（至少一行数据）。"""
    for p in glob.glob(CSV_PREFIX + '*.csv'):
        try:
            with open(p, 'r', encoding='utf-8-sig') as f:
                lines = [ln for ln in f.readlines() if ln.strip()]
            if len(lines) > 1:  # 表头 + 至少一行数据
                return True, p
        except Exception:
            pass
    return False, None


def run_once(min_match_score=None):
    """执行一次回测。可通过环境变量传递 min_match_score。"""
    env = os.environ.copy()
    if min_match_score is not None:
        env['BACKTEST_MIN_MATCH_SCORE'] = str(min_match_score)
    with open(LOG_FILE, 'a', encoding='utf-8') as log:
        log.write(f"\n\n{'='*80}\n[auto_run] 开始新一轮回测 min_match_score={min_match_score}\n{'='*80}\n\n")
    proc = subprocess.Popen(
        [sys.executable, BACKTEST_SCRIPT],
        cwd=PROJECT_ROOT,
        stdout=open(LOG_FILE, 'a', encoding='utf-8'),
        stderr=subprocess.STDOUT,
        env=env,
    )
    return proc.wait()


def main():
    os.chdir(PROJECT_ROOT)
    # 若已有有效结果，可直接退出
    ok, path = has_valid_result()
    if ok:
        print(f"✅ 已存在有效结果: {path}")
        return 0

    retries = 0
    max_retries = 20
    # 首次 0.85，之后逐步放宽
    scores = [0.85, 0.82, 0.80, 0.78, 0.75, 0.72, 0.70] + [0.65] * (max_retries - 7)

    while retries < max_retries:
        ms = scores[retries] if retries < len(scores) else 0.60
        print(f"[auto_run] 第 {retries + 1}/{max_retries} 次回测 (min_match_score={ms}) ...", flush=True)
        code = run_once(min_match_score=ms)
        ok, path = has_valid_result()
        if ok:
            print(f"✅ 回测完成，结果已保存: {path}", flush=True)
            return 0
        print(f"   本轮无有效结果 (exit={code})，30 秒后重试...", flush=True)
        time.sleep(30)
        retries += 1

    print("❌ 已达最大重试次数，未得到有效结果。请查看 backtest_model0124.log")
    return 1


if __name__ == '__main__':
    sys.exit(main())
