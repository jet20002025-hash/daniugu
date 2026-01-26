#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修复过期的K线数据
直接遍历缓存目录，找出过期的文件并更新
"""

import os
import json
import time
import requests
import pandas as pd
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# 配置
CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cache')
DAILY_DIR = os.path.join(CACHE_DIR, 'daily_kline')
WEEKLY_DIR = os.path.join(CACHE_DIR, 'weekly_kline')

# 创建session
session = requests.Session()
session.trust_env = False
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
    'Referer': 'https://finance.sina.com.cn/'
})

def get_sina_kline(code, kline_type='weekly', datalen=120):
    """从新浪获取K线数据"""
    if code.startswith('6'):
        symbol = f'sh{code}'
    else:
        symbol = f'sz{code}'
    
    scale = '240' if kline_type == 'daily' else '1680'
    url = f'https://quotes.sina.cn/cn/api/jsonp_v2.php/var%20_{symbol}_{scale}/CN_MarketDataService.getKLineData'
    params = {
        'symbol': symbol,
        'scale': scale,
        'ma': 'no',
        'datalen': datalen
    }
    
    try:
        resp = session.get(url, params=params, timeout=10)
        if resp.status_code != 200:
            return None
        
        text = resp.text
        start = text.find('(')
        end = text.rfind(')')
        if start == -1 or end == -1:
            return None
        
        json_str = text[start+1:end]
        data = json.loads(json_str)
        
        if not data:
            return None
        
        df = pd.DataFrame(data)
        df.rename(columns={
            'day': '日期',
            'open': '开盘',
            'high': '最高',
            'low': '最低',
            'close': '收盘',
            'volume': '周成交量' if kline_type == 'weekly' else '成交量'
        }, inplace=True)
        
        df['股票代码'] = code
        
        for col in ['开盘', '最高', '最低', '收盘']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        vol_col = '周成交量' if kline_type == 'weekly' else '成交量'
        df[vol_col] = pd.to_numeric(df[vol_col], errors='coerce')
        
        return df
    except Exception as e:
        return None

def update_single_file(code, file_path, kline_type):
    """更新单个文件"""
    try:
        df = get_sina_kline(code, kline_type)
        if df is not None and len(df) > 0:
            df.to_csv(file_path, index=False, encoding='utf-8')
            return True
        return False
    except Exception as e:
        return False

def main():
    print("=" * 60)
    print("修复过期的K线数据")
    print("=" * 60)
    
    # 找出所有过期的周K线文件
    outdated_weekly = []
    for f in os.listdir(WEEKLY_DIR):
        if f.endswith('.csv'):
            code = f.replace('.csv', '')
            path = os.path.join(WEEKLY_DIR, f)
            try:
                df = pd.read_csv(path)
                if '日期' in df.columns and len(df) > 0:
                    max_date = str(df['日期'].max())[:10]
                    if max_date < '2026-01-17':
                        outdated_weekly.append((code, path))
            except:
                outdated_weekly.append((code, path))
    
    print(f"发现 {len(outdated_weekly)} 只股票周K线数据过期")
    
    if len(outdated_weekly) == 0:
        print("所有数据已是最新！")
        return
    
    # 多线程更新
    updated = 0
    failed = 0
    start_time = time.time()
    
    print(f"\n开始更新（10线程并发）...")
    
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {}
        for code, path in outdated_weekly:
            future = executor.submit(update_single_file, code, path, 'weekly')
            futures[future] = code
        
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
            
            if completed % 100 == 0 or completed == len(outdated_weekly):
                elapsed = time.time() - start_time
                speed = completed / elapsed if elapsed > 0 else 0
                print(f"进度: {completed}/{len(outdated_weekly)} ({completed/len(outdated_weekly)*100:.1f}%) "
                      f"| 更新成功: {updated} | 失败: {failed} | 速度: {speed:.1f} 只/秒")
            
            time.sleep(0.02)  # 短暂延迟
    
    elapsed = time.time() - start_time
    print("\n" + "=" * 60)
    print(f"更新完成！")
    print(f"  总耗时: {elapsed:.1f} 秒")
    print(f"  更新成功: {updated} 只")
    print(f"  更新失败: {failed} 只")
    print("=" * 60)

if __name__ == '__main__':
    main()
