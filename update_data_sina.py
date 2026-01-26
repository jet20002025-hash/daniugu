#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
使用新浪财经API增量更新本地K线数据到最新日期
"""
import os
import sys
import json
import time
import requests
import pandas as pd
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

# 配置
CACHE_DIR = 'cache'
DAILY_DIR = os.path.join(CACHE_DIR, 'daily_kline')
WEEKLY_DIR = os.path.join(CACHE_DIR, 'weekly_kline')
MAX_WORKERS = 10  # 并发数（新浪API相对宽松）
RETRY_TIMES = 3  # 重试次数

# 创建全局session
session = requests.Session()
session.trust_env = False  # 不使用系统代理
session.headers.update({'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'})


def get_stock_list():
    """获取股票列表"""
    stock_list_path = os.path.join(CACHE_DIR, 'stock_list_all.json')
    if os.path.exists(stock_list_path):
        with open(stock_list_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None


def get_sina_daily_kline(code, datalen=60):
    """
    通过新浪财经获取日K线数据
    :param code: 股票代码
    :param datalen: 获取数据条数
    """
    # 转换代码格式
    if code.startswith('6'):
        symbol = f'sh{code}'
    else:
        symbol = f'sz{code}'
    
    url = f'https://quotes.sina.cn/cn/api/jsonp_v2.php/data/CN_MarketDataService.getKLineData?symbol={symbol}&scale=240&datalen={datalen}'
    
    for attempt in range(RETRY_TIMES):
        try:
            resp = session.get(url, timeout=10)
            if resp.status_code == 200:
                text = resp.text
                if 'data(' in text:
                    json_str = text.split('data(')[1].rsplit(')', 1)[0]
                    data = json.loads(json_str)
                    if data:
                        df = pd.DataFrame(data)
                        df = df.rename(columns={
                            'day': '日期',
                            'open': '开盘',
                            'close': '收盘',
                            'high': '最高',
                            'low': '最低',
                            'volume': '成交量'
                        })
                        df = df[['日期', '开盘', '收盘', '最高', '最低', '成交量']]
                        df['开盘'] = df['开盘'].astype(float)
                        df['收盘'] = df['收盘'].astype(float)
                        df['最高'] = df['最高'].astype(float)
                        df['最低'] = df['最低'].astype(float)
                        df['成交量'] = df['成交量'].astype(int)
                        return df
        except Exception as e:
            if attempt < RETRY_TIMES - 1:
                time.sleep(0.3 * (attempt + 1))
    return None


def get_sina_weekly_kline(code, datalen=30):
    """
    通过新浪财经获取周K线数据
    :param code: 股票代码
    :param datalen: 获取数据条数
    """
    # 转换代码格式
    if code.startswith('6'):
        symbol = f'sh{code}'
    else:
        symbol = f'sz{code}'
    
    # scale=1200 是周K线
    url = f'https://quotes.sina.cn/cn/api/jsonp_v2.php/data/CN_MarketDataService.getKLineData?symbol={symbol}&scale=1200&datalen={datalen}'
    
    for attempt in range(RETRY_TIMES):
        try:
            resp = session.get(url, timeout=10)
            if resp.status_code == 200:
                text = resp.text
                if 'data(' in text:
                    json_str = text.split('data(')[1].rsplit(')', 1)[0]
                    data = json.loads(json_str)
                    if data:
                        df = pd.DataFrame(data)
                        df = df.rename(columns={
                            'day': '日期',
                            'open': '开盘',
                            'close': '收盘',
                            'high': '最高',
                            'low': '最低',
                            'volume': '周成交量'
                        })
                        df = df[['日期', '开盘', '收盘', '最高', '最低', '周成交量']]
                        df['开盘'] = df['开盘'].astype(float)
                        df['收盘'] = df['收盘'].astype(float)
                        df['最高'] = df['最高'].astype(float)
                        df['最低'] = df['最低'].astype(float)
                        df['周成交量'] = df['周成交量'].astype(int)
                        return df
        except Exception as e:
            if attempt < RETRY_TIMES - 1:
                time.sleep(0.3 * (attempt + 1))
    return None


def process_single_stock(code, name, target_date):
    """处理单只股票的数据更新"""
    result = {'code': code, 'name': name, 'daily_updated': 0, 'weekly_updated': 0, 'error': None}
    
    try:
        # 更新日K线
        daily_path = os.path.join(DAILY_DIR, f'{code}.csv')
        if os.path.exists(daily_path):
            existing_daily = pd.read_csv(daily_path)
            last_date = existing_daily['日期'].iloc[-1] if len(existing_daily) > 0 else '2000-01-01'
            
            # 如果数据已经是最新的，跳过
            if last_date >= target_date:
                pass
            else:
                # 获取最近的数据
                new_daily = get_sina_daily_kline(code, datalen=30)
                if new_daily is not None and len(new_daily) > 0:
                    # 只保留比现有数据新的记录
                    new_daily = new_daily[new_daily['日期'] > last_date]
                    if len(new_daily) > 0:
                        # 合并数据
                        combined = pd.concat([existing_daily, new_daily], ignore_index=True)
                        combined = combined.drop_duplicates(subset=['日期'], keep='last')
                        combined = combined.sort_values('日期').reset_index(drop=True)
                        combined.to_csv(daily_path, index=False, encoding='utf-8')
                        result['daily_updated'] = len(new_daily)
        
        # 更新周K线
        weekly_path = os.path.join(WEEKLY_DIR, f'{code}.csv')
        if os.path.exists(weekly_path):
            existing_weekly = pd.read_csv(weekly_path)
            last_date = existing_weekly['日期'].iloc[-1] if len(existing_weekly) > 0 else '2000-01-01'
            
            # 获取最近的周K线数据
            new_weekly = get_sina_weekly_kline(code, datalen=10)
            if new_weekly is not None and len(new_weekly) > 0:
                # 只保留比现有数据新的记录（周K线用日期做比较，取最后一周）
                new_weekly = new_weekly[new_weekly['日期'] > last_date]
                if len(new_weekly) > 0:
                    # 合并数据
                    combined = pd.concat([existing_weekly, new_weekly], ignore_index=True)
                    combined = combined.drop_duplicates(subset=['日期'], keep='last')
                    combined = combined.sort_values('日期').reset_index(drop=True)
                    combined.to_csv(weekly_path, index=False, encoding='utf-8')
                    result['weekly_updated'] = len(new_weekly)
        
    except Exception as e:
        result['error'] = str(e)
    
    return result


def main():
    print("=" * 60)
    print("📊 增量更新本地K线数据（使用新浪财经API）")
    print("=" * 60)
    print(flush=True)
    
    # 获取股票列表
    stock_list = get_stock_list()
    if not stock_list:
        print("❌ 无法获取股票列表")
        return
    
    # 目标日期（今天）
    target_date = datetime.now().strftime('%Y-%m-%d')
    
    print(f"📅 目标日期: {target_date}")
    print(f"📈 股票总数: {len(stock_list)}")
    print(flush=True)
    
    # 不过滤：ST、北交所等全部参与追加更新
    valid_stocks = []
    for stock in stock_list:
        code = stock.get('code', stock.get('股票代码', ''))
        name = stock.get('name', stock.get('股票名称', ''))
        if code:
            valid_stocks.append({'code': str(code).strip(), 'name': name or ''})
    
    print(f"📊 参与更新股票数: {len(valid_stocks)}（全部）")
    print()
    print(flush=True)
    
    # 并行更新
    total = len(valid_stocks)
    completed = 0
    daily_total = 0
    weekly_total = 0
    errors = 0
    
    start_time = time.time()
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(process_single_stock, s['code'], s['name'], target_date): s
            for s in valid_stocks
        }
        
        for future in as_completed(futures):
            completed += 1
            result = future.result()
            
            if result['error']:
                errors += 1
            else:
                daily_total += result['daily_updated']
                weekly_total += result['weekly_updated']
            
            # 每200只股票显示一次进度
            if completed % 200 == 0 or completed == total:
                elapsed = time.time() - start_time
                speed = completed / elapsed if elapsed > 0 else 0
                eta = (total - completed) / speed if speed > 0 else 0
                print(f"进度: {completed}/{total} ({completed/total*100:.1f}%) | "
                      f"日K新增: {daily_total} | 周K新增: {weekly_total} | "
                      f"错误: {errors} | 速度: {speed:.1f}只/秒 | 预计剩余: {eta:.0f}秒", flush=True)
    
    elapsed = time.time() - start_time
    print()
    print("=" * 60)
    print(f"✅ 更新完成!")
    print(f"   耗时: {elapsed:.1f}秒")
    print(f"   日K线新增记录: {daily_total}")
    print(f"   周K线新增记录: {weekly_total}")
    print(f"   错误数: {errors}")
    print("=" * 60)
    print(flush=True)


if __name__ == '__main__':
    main()
