#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""轮询等待回测结果 CSV 出现，然后打印表格。"""
import os
import glob
import time
import sys

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
CSV_PREFIX = os.path.join(PROJECT_ROOT, 'backtest_model有效模型0124_')

def main():
    os.chdir(PROJECT_ROOT)
    interval = 60
    print(f"等待回测结果 (每 {interval} 秒检查一次)，按 Ctrl+C 退出...", flush=True)
    while True:
        for p in sorted(glob.glob(CSV_PREFIX + '*.csv'), reverse=True):
            try:
                with open(p, 'r', encoding='utf-8-sig') as f:
                    lines = [ln for ln in f if ln.strip()]
                if len(lines) <= 1:
                    continue
                print(f"\n✅ 已生成结果: {os.path.basename(p)}\n", flush=True)
                for ln in lines:
                    print(ln.rstrip())
                return 0
            except Exception as e:
                pass
        print(f"  {time.strftime('%H:%M:%S')} 尚未生成有效结果，继续等待...", flush=True)
        time.sleep(interval)

if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n已取消")
        sys.exit(130)
