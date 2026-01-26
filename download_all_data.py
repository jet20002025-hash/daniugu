#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量下载/更新所有股票的K线数据
使用新浪财经API，多线程并发下载
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
STOCK_LIST_FILE = os.path.join(CACHE_DIR, 'stock_list_all.json')

# 确保目录存在
os.makedirs(DAILY_DIR, exist_ok=True)
os.makedirs(WEEKLY_DIR, exist_ok=True)

# 创建session
session = requests.Session()
session.trust_env = False  # 禁用系统代理
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
    'Referer': 'https://finance.sina.com.cn/'
})

def get_sina_kline(code, kline_type='daily', datalen=250):
    """
    从新浪获取K线数据
    kline_type: 'daily' 或 'weekly'
    """
    # 转换股票代码格式
    if code.startswith('6'):
        symbol = f'sh{code}'
    else:
        symbol = f'sz{code}'
    
    # 新浪K线API
    scale = '240' if kline_type == 'daily' else '1680'  # 日K=240分钟，周K=1680分钟(7*240)
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
        # 解析JSONP格式
        start = text.find('(')
        end = text.rfind(')')
        if start == -1 or end == -1:
            return None
        
        json_str = text[start+1:end]
        data = json.loads(json_str)
        
        if not data:
            return None
        
        # 转换为DataFrame
        df = pd.DataFrame(data)
        df.rename(columns={
            'day': '日期',
            'open': '开盘',
            'high': '最高',
            'low': '最低',
            'close': '收盘',
            'volume': '成交量' if kline_type == 'daily' else '周成交量'
        }, inplace=True)
        
        # 添加股票代码列
        df['股票代码'] = code
        
        # 转换数据类型
        for col in ['开盘', '最高', '最低', '收盘']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        vol_col = '成交量' if kline_type == 'daily' else '周成交量'
        df[vol_col] = pd.to_numeric(df[vol_col], errors='coerce')
        
        return df
    except Exception as e:
        return None

def update_stock_data(code, name, target_date):
    """更新单只股票的数据"""
    results = {'code': code, 'name': name, 'daily': False, 'weekly': False, 'error': None}
    
    try:
        # 检查日K线是否需要更新
        daily_path = os.path.join(DAILY_DIR, f'{code}.csv')
        need_daily = True
        if os.path.exists(daily_path):
            try:
                df = pd.read_csv(daily_path)
                if '日期' in df.columns and len(df) > 0:
                    max_date = str(df['日期'].max())[:10]
                    # 今天是周二(2026-01-21)，上个交易日是周一(2026-01-20)
                    if max_date >= '2026-01-20':
                        need_daily = False
            except:
                pass
        
        # 检查周K线是否需要更新
        weekly_path = os.path.join(WEEKLY_DIR, f'{code}.csv')
        need_weekly = True
        if os.path.exists(weekly_path):
            try:
                df = pd.read_csv(weekly_path)
                if '日期' in df.columns and len(df) > 0:
                    max_date = str(df['日期'].max())[:10]
                    # 周K线需要到本周（2026-01-17 是上周五）
                    if max_date >= '2026-01-17':
                        need_weekly = False
            except:
                pass
        
        # 下载日K线
        if need_daily:
            df = get_sina_kline(code, 'daily', 250)
            if df is not None and len(df) > 0:
                df.to_csv(daily_path, index=False, encoding='utf-8')
                results['daily'] = True
            time.sleep(0.02)  # 短暂延迟
        
        # 下载周K线
        if need_weekly:
            df = get_sina_kline(code, 'weekly', 120)
            if df is not None and len(df) > 0:
                df.to_csv(weekly_path, index=False, encoding='utf-8')
                results['weekly'] = True
            time.sleep(0.02)
        
    except Exception as e:
        results['error'] = str(e)
    
    return results

def main():
    print("=" * 60)
    print("批量下载/更新股票K线数据")
    print("=" * 60)
    
    # 加载股票列表
    if not os.path.exists(STOCK_LIST_FILE):
        print(f"错误: 股票列表文件不存在: {STOCK_LIST_FILE}")
        return
    
    with open(STOCK_LIST_FILE, 'r', encoding='utf-8') as f:
        stock_list = json.load(f)
    
    # 过滤有效股票（兼容不同的键名格式）
    valid_stocks = []
    for item in stock_list:
        code = item.get('代码', '') or item.get('code', '')
        name = item.get('名称', '') or item.get('name', '')
        if not code or not name:
            continue
        # 排除ST、退市、B股等
        if 'ST' in name or '退' in name or code.startswith('9') or code.startswith('2'):
            continue
        # 统一格式
        valid_stocks.append({'code': code, 'name': name})
    
    print(f"有效股票数量: {len(valid_stocks)}")
    
    target_date = datetime.now().strftime('%Y-%m-%d')
    print(f"目标日期: {target_date}")
    
    # 统计
    updated_daily = 0
    updated_weekly = 0
    failed = 0
    skipped = 0
    
    start_time = time.time()
    
    # 使用多线程下载
    print(f"\n开始下载（10线程并发）...")
    
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {}
        for item in valid_stocks:
            code = item.get('code', '')
            name = item.get('name', '')
            future = executor.submit(update_stock_data, code, name, target_date)
            futures[future] = (code, name)
        
        completed = 0
        for future in as_completed(futures):
            completed += 1
            code, name = futures[future]
            
            try:
                result = future.result()
                if result['daily']:
                    updated_daily += 1
                if result['weekly']:
                    updated_weekly += 1
                if result['error']:
                    failed += 1
                if not result['daily'] and not result['weekly'] and not result['error']:
                    skipped += 1
            except Exception as e:
                failed += 1
            
            # 显示进度
            if completed % 100 == 0 or completed == len(valid_stocks):
                elapsed = time.time() - start_time
                speed = completed / elapsed if elapsed > 0 else 0
                print(f"进度: {completed}/{len(valid_stocks)} ({completed/len(valid_stocks)*100:.1f}%) "
                      f"| 日K更新: {updated_daily} | 周K更新: {updated_weekly} "
                      f"| 跳过: {skipped} | 失败: {failed} "
                      f"| 速度: {speed:.1f} 只/秒")
    
    elapsed = time.time() - start_time
    print("\n" + "=" * 60)
    print(f"下载完成！")
    print(f"  总耗时: {elapsed:.1f} 秒")
    print(f"  日K线更新: {updated_daily} 只")
    print(f"  周K线更新: {updated_weekly} 只")
    print(f"  跳过（已是最新）: {skipped} 只")
    print(f"  失败: {failed} 只")
    print("=" * 60)

if __name__ == '__main__':
    main()
