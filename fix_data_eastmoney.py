#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
使用东方财富API修复过期数据
"""

import os
import json
import time
import requests
import pandas as pd
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cache')
WEEKLY_DIR = os.path.join(CACHE_DIR, 'weekly_kline')

session = requests.Session()
session.trust_env = False
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
})

def get_eastmoney_weekly(code):
    """从东方财富获取周K线"""
    try:
        # 转换代码格式
        if code.startswith('6'):
            secid = f'1.{code}'
        else:
            secid = f'0.{code}'
        
        url = 'https://push2his.eastmoney.com/api/qt/stock/kline/get'
        params = {
            'secid': secid,
            'fields1': 'f1,f2,f3,f4,f5,f6',
            'fields2': 'f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61',
            'klt': '102',  # 102=周K线
            'fqt': '1',    # 前复权
            'end': '20500101',
            'lmt': '120'   # 120周
        }
        
        resp = session.get(url, params=params, timeout=10)
        if resp.status_code != 200:
            return None
        
        data = resp.json()
        if not data.get('data') or not data['data'].get('klines'):
            return None
        
        klines = data['data']['klines']
        records = []
        for line in klines:
            parts = line.split(',')
            if len(parts) >= 7:
                records.append({
                    '日期': parts[0],
                    '开盘': float(parts[1]),
                    '收盘': float(parts[2]),
                    '最高': float(parts[3]),
                    '最低': float(parts[4]),
                    '周成交量': float(parts[5]),
                    '成交额': float(parts[6]),
                    '股票代码': code
                })
        
        if not records:
            return None
        
        df = pd.DataFrame(records)
        return df
    except Exception as e:
        return None

def update_single(code, path):
    """更新单只股票"""
    try:
        df = get_eastmoney_weekly(code)
        if df is not None and len(df) > 0:
            df.to_csv(path, index=False, encoding='utf-8')
            return True
    except:
        pass
    return False

def main():
    print("=" * 60)
    print("使用东方财富API修复过期数据")
    print("=" * 60)
    
    # 找出过期文件
    outdated = []
    for f in os.listdir(WEEKLY_DIR):
        if f.endswith('.csv'):
            code = f.replace('.csv', '')
            path = os.path.join(WEEKLY_DIR, f)
            try:
                df = pd.read_csv(path)
                if '日期' in df.columns and len(df) > 0:
                    max_date = str(df['日期'].max())[:10]
                    if max_date < '2026-01-17':
                        outdated.append((code, path))
            except:
                outdated.append((code, path))
    
    print(f"发现 {len(outdated)} 只股票数据过期")
    
    if not outdated:
        print("所有数据已是最新！")
        return
    
    updated = 0
    failed = 0
    start_time = time.time()
    
    print(f"\n开始更新（5线程并发）...")
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(update_single, code, path): code for code, path in outdated}
        
        completed = 0
        for future in as_completed(futures):
            completed += 1
            code = futures[future]
            
            try:
                if future.result():
                    updated += 1
                else:
                    failed += 1
            except:
                failed += 1
            
            if completed % 50 == 0 or completed == len(outdated):
                elapsed = time.time() - start_time
                speed = completed / elapsed if elapsed > 0 else 0
                print(f"进度: {completed}/{len(outdated)} ({completed/len(outdated)*100:.1f}%) "
                      f"| 成功: {updated} | 失败: {failed} | 速度: {speed:.1f}/秒")
            
            time.sleep(0.1)  # 避免请求过快
    
    elapsed = time.time() - start_time
    print("\n" + "=" * 60)
    print(f"更新完成！耗时: {elapsed:.1f}秒")
    print(f"成功: {updated} | 失败: {failed}")
    print("=" * 60)

if __name__ == '__main__':
    main()
