#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
增量更新本地K线数据到最新日期
"""
import os
import sys
import json
import time
import pandas as pd
import akshare as ak
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

# 配置
CACHE_DIR = 'cache'
DAILY_DIR = os.path.join(CACHE_DIR, 'daily_kline')
WEEKLY_DIR = os.path.join(CACHE_DIR, 'weekly_kline')
MAX_WORKERS = 5  # 并发数
RETRY_TIMES = 3  # 重试次数


def get_stock_list():
    """获取股票列表"""
    stock_list_path = os.path.join(CACHE_DIR, 'stock_list_all.json')
    if os.path.exists(stock_list_path):
        with open(stock_list_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None


def update_daily_kline(code, start_date, end_date):
    """更新日K线数据"""
    for attempt in range(RETRY_TIMES):
        try:
            df = ak.stock_zh_a_hist(
                symbol=code,
                period="daily",
                start_date=start_date,
                end_date=end_date,
                adjust="qfq"
            )
            if df is not None and not df.empty:
                # 重命名列
                df = df.rename(columns={
                    df.columns[0]: '日期',
                    df.columns[1]: '开盘',
                    df.columns[2]: '收盘',
                    df.columns[3]: '最高',
                    df.columns[4]: '最低',
                    df.columns[5]: '成交量',
                })
                df['日期'] = pd.to_datetime(df['日期'])
                return df
            return None
        except Exception as e:
            if attempt < RETRY_TIMES - 1:
                time.sleep(0.5 * (attempt + 1))
            continue
    return None


def update_weekly_kline(code, start_date, end_date):
    """更新周K线数据"""
    for attempt in range(RETRY_TIMES):
        try:
            df = ak.stock_zh_a_hist(
                symbol=code,
                period="weekly",
                start_date=start_date,
                end_date=end_date,
                adjust="qfq"
            )
            if df is not None and not df.empty:
                # 重命名列
                if len(df.columns) >= 6:
                    df = df.rename(columns={
                        df.columns[0]: '日期',
                        df.columns[1]: '开盘',
                        df.columns[2]: '收盘',
                        df.columns[3]: '最高',
                        df.columns[4]: '最低',
                        df.columns[5]: '周成交量',
                    })
                df['日期'] = pd.to_datetime(df['日期'])
                return df
            return None
        except Exception as e:
            if attempt < RETRY_TIMES - 1:
                time.sleep(0.5 * (attempt + 1))
            continue
    return None


def process_single_stock(code, name, start_date, end_date):
    """处理单只股票的数据更新"""
    result = {'code': code, 'name': name, 'daily_updated': 0, 'weekly_updated': 0, 'error': None}
    
    try:
        # 更新日K线
        daily_path = os.path.join(DAILY_DIR, f'{code}.csv')
        if os.path.exists(daily_path):
            existing_daily = pd.read_csv(daily_path)
            existing_daily['日期'] = pd.to_datetime(existing_daily['日期'])
            
            # 获取增量数据
            new_daily = update_daily_kline(code, start_date, end_date)
            if new_daily is not None and len(new_daily) > 0:
                # 合并数据，去重
                combined = pd.concat([existing_daily, new_daily], ignore_index=True)
                combined = combined.drop_duplicates(subset=['日期'], keep='last')
                combined = combined.sort_values('日期').reset_index(drop=True)
                combined['日期'] = combined['日期'].dt.strftime('%Y-%m-%d')
                combined.to_csv(daily_path, index=False, encoding='utf-8')
                result['daily_updated'] = len(new_daily)
        
        # 更新周K线
        weekly_path = os.path.join(WEEKLY_DIR, f'{code}.csv')
        if os.path.exists(weekly_path):
            existing_weekly = pd.read_csv(weekly_path)
            existing_weekly['日期'] = pd.to_datetime(existing_weekly['日期'])
            
            # 获取增量数据
            new_weekly = update_weekly_kline(code, start_date, end_date)
            if new_weekly is not None and len(new_weekly) > 0:
                # 合并数据，去重
                combined = pd.concat([existing_weekly, new_weekly], ignore_index=True)
                combined = combined.drop_duplicates(subset=['日期'], keep='last')
                combined = combined.sort_values('日期').reset_index(drop=True)
                combined['日期'] = combined['日期'].dt.strftime('%Y-%m-%d')
                combined.to_csv(weekly_path, index=False, encoding='utf-8')
                result['weekly_updated'] = len(new_weekly)
        
        time.sleep(0.1)  # 避免请求过快
        
    except Exception as e:
        result['error'] = str(e)
    
    return result


def main():
    print("=" * 60)
    print("📊 增量更新本地K线数据")
    print("=" * 60)
    
    # 获取股票列表
    stock_list = get_stock_list()
    if not stock_list:
        print("❌ 无法获取股票列表")
        return
    
    # 设置更新日期范围（从2026年1月1日到今天）
    start_date = '20260101'
    end_date = datetime.now().strftime('%Y%m%d')
    
    print(f"📅 更新日期范围: {start_date} ~ {end_date}")
    print(f"📈 股票总数: {len(stock_list)}")
    print()
    
    # 不过滤：ST、北交所等全部参与追加更新
    valid_stocks = []
    for stock in stock_list:
        code = stock.get('code', stock.get('股票代码', ''))
        name = stock.get('name', stock.get('股票名称', ''))
        if code:
            valid_stocks.append({'code': str(code).strip(), 'name': name or ''})
    
    print(f"📊 参与更新股票数: {len(valid_stocks)}（全部）")
    print()
    
    # 并行更新
    total = len(valid_stocks)
    completed = 0
    daily_total = 0
    weekly_total = 0
    errors = 0
    
    start_time = time.time()
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(process_single_stock, s['code'], s['name'], start_date, end_date): s
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
            
            # 每100只股票显示一次进度
            if completed % 100 == 0 or completed == total:
                elapsed = time.time() - start_time
                speed = completed / elapsed if elapsed > 0 else 0
                eta = (total - completed) / speed if speed > 0 else 0
                print(f"进度: {completed}/{total} ({completed/total*100:.1f}%) | "
                      f"日K新增: {daily_total} | 周K新增: {weekly_total} | "
                      f"错误: {errors} | 速度: {speed:.1f}只/秒 | 预计剩余: {eta:.0f}秒")
    
    elapsed = time.time() - start_time
    print()
    print("=" * 60)
    print(f"✅ 更新完成!")
    print(f"   耗时: {elapsed:.1f}秒")
    print(f"   日K线新增记录: {daily_total}")
    print(f"   周K线新增记录: {weekly_total}")
    print(f"   错误数: {errors}")
    print("=" * 60)


if __name__ == '__main__':
    main()
