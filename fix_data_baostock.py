#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
使用baostock批量修复过期的周K线数据
"""

import os
import pandas as pd
import baostock as bs
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import threading

CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cache')
WEEKLY_DIR = os.path.join(CACHE_DIR, 'weekly_kline')

# baostock需要单线程访问，使用锁
bs_lock = threading.Lock()

def download_weekly_kline(code):
    """下载单只股票的周K线"""
    try:
        # 转换代码格式
        if code.startswith('6'):
            bs_code = f'sh.{code}'
        else:
            bs_code = f'sz.{code}'
        
        with bs_lock:
            rs = bs.query_history_k_data_plus(
                bs_code,
                "date,open,high,low,close,volume,amount",
                start_date='2024-01-01',
                end_date='2026-01-21',
                frequency="w",
                adjustflag="2"
            )
        
        if rs.error_code != '0':
            return None
        
        data_list = []
        while rs.next():
            data_list.append(rs.get_row_data())
        
        if not data_list:
            return None
        
        df = pd.DataFrame(data_list, columns=rs.fields)
        
        # 重命名列以匹配现有格式
        df.rename(columns={
            'date': '日期',
            'open': '开盘',
            'high': '最高',
            'low': '最低',
            'close': '收盘',
            'volume': '周成交量',
            'amount': '成交额'
        }, inplace=True)
        
        # 添加股票代码列
        df['股票代码'] = code
        
        # 转换数据类型
        for col in ['开盘', '最高', '最低', '收盘', '周成交量', '成交额']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        return df
    except Exception as e:
        return None

def update_single(code, path):
    """更新单只股票"""
    df = download_weekly_kline(code)
    if df is not None and len(df) > 0:
        df.to_csv(path, index=False, encoding='utf-8')
        return True
    return False

def main():
    print("=" * 60)
    print("使用baostock批量修复过期的周K线数据")
    print("=" * 60)
    
    # 登录baostock
    lg = bs.login()
    if lg.error_code != '0':
        print(f"登录失败: {lg.error_msg}")
        return
    print(f"baostock登录成功")
    
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
                    if max_date < '2026-01-10':  # 需要至少有上周数据
                        outdated.append((code, path))
            except:
                outdated.append((code, path))
    
    print(f"发现 {len(outdated)} 只股票数据过期")
    
    if not outdated:
        print("所有数据已是最新！")
        bs.logout()
        return
    
    updated = 0
    failed = 0
    start_time = time.time()
    
    print(f"\n开始更新（顺序处理，避免API限制）...")
    
    for i, (code, path) in enumerate(outdated):
        try:
            if update_single(code, path):
                updated += 1
            else:
                failed += 1
        except Exception as e:
            failed += 1
        
        # 显示进度
        if (i + 1) % 50 == 0 or (i + 1) == len(outdated):
            elapsed = time.time() - start_time
            speed = (i + 1) / elapsed if elapsed > 0 else 0
            pct = (i + 1) / len(outdated) * 100
            print(f"进度: {i+1}/{len(outdated)} ({pct:.1f}%) "
                  f"| 成功: {updated} | 失败: {failed} | 速度: {speed:.1f}/秒")
        
        # 短暂延迟避免API限制
        time.sleep(0.05)
    
    # 登出
    bs.logout()
    
    elapsed = time.time() - start_time
    print("\n" + "=" * 60)
    print(f"更新完成！")
    print(f"  总耗时: {elapsed:.1f} 秒")
    print(f"  成功: {updated} 只")
    print(f"  失败: {failed} 只")
    print("=" * 60)

if __name__ == '__main__':
    main()
