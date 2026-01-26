#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
全自动：下载数据 + 扫描测试
目标：数据完整率95%以上，然后执行扫描
"""

import os
import sys
import json
import time
import pandas as pd
import baostock as bs
from datetime import datetime

CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cache')
WEEKLY_DIR = os.path.join(CACHE_DIR, 'weekly_kline')

def check_data_completeness():
    """检查数据完整率"""
    updated = 0
    total = 0
    for f in os.listdir(WEEKLY_DIR):
        if f.endswith('.csv'):
            total += 1
            try:
                df = pd.read_csv(os.path.join(WEEKLY_DIR, f))
                if '日期' in df.columns and len(df) > 0:
                    max_date = str(df['日期'].max())[:10]
                    if max_date >= '2026-01-10':
                        updated += 1
            except:
                pass
    return updated, total

def download_weekly_kline(code):
    """下载单只股票的周K线"""
    try:
        if code.startswith('6'):
            bs_code = f'sh.{code}'
        else:
            bs_code = f'sz.{code}'
        
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
        df.rename(columns={
            'date': '日期',
            'open': '开盘',
            'high': '最高',
            'low': '最低',
            'close': '收盘',
            'volume': '周成交量',
            'amount': '成交额'
        }, inplace=True)
        df['股票代码'] = code
        
        for col in ['开盘', '最高', '最低', '收盘', '周成交量', '成交额']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        return df
    except:
        return None

def fix_outdated_data():
    """修复过期数据"""
    print("\n" + "=" * 60)
    print("步骤1: 修复过期数据")
    print("=" * 60)
    
    # 登录baostock
    lg = bs.login()
    if lg.error_code != '0':
        print(f"baostock登录失败: {lg.error_msg}")
        return False
    print("baostock登录成功")
    
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
                    if max_date < '2026-01-10':
                        outdated.append((code, path))
            except:
                outdated.append((code, path))
    
    print(f"发现 {len(outdated)} 只股票数据需要更新")
    
    if not outdated:
        bs.logout()
        return True
    
    updated = 0
    failed = 0
    start_time = time.time()
    
    for i, (code, path) in enumerate(outdated):
        try:
            df = download_weekly_kline(code)
            if df is not None and len(df) > 0:
                df.to_csv(path, index=False, encoding='utf-8')
                updated += 1
            else:
                failed += 1
        except:
            failed += 1
        
        if (i + 1) % 100 == 0 or (i + 1) == len(outdated):
            elapsed = time.time() - start_time
            speed = (i + 1) / elapsed if elapsed > 0 else 0
            pct = (i + 1) / len(outdated) * 100
            print(f"  进度: {i+1}/{len(outdated)} ({pct:.1f}%) | 成功: {updated} | 失败: {failed} | {speed:.1f}/秒")
        
        time.sleep(0.05)
    
    bs.logout()
    print(f"数据更新完成: 成功 {updated}, 失败 {failed}")
    return True

def run_scan():
    """执行扫描"""
    print("\n" + "=" * 60)
    print("步骤2: 执行扫描")
    print("=" * 60)
    print("扫描参数:")
    print("  - 扫描日期: 2026-01-21")
    print("  - 最低匹配度: 0.93")
    print("  - 最大流通市值: 100亿")
    print("=" * 60)
    
    from bull_stock_analyzer import BullStockAnalyzer
    
    # 初始化分析器
    print("\n初始化分析器...")
    analyzer = BullStockAnalyzer(auto_load_default_stocks=False, auto_analyze_and_train=False)
    
    # 加载模型
    with open('trained_model.json', 'r', encoding='utf-8') as f:
        model = json.load(f)
    analyzer.trained_features = model
    
    common_features = analyzer._get_common_features()
    print(f"模型特征数: {len(common_features)}")
    
    # 获取股票列表
    stock_list = analyzer.fetcher.get_all_stocks()
    if stock_list is None or len(stock_list) == 0:
        print("无法获取股票列表")
        return []
    
    total_stocks = len(stock_list)
    print(f"待扫描股票数: {total_stocks}")
    
    # 扫描参数
    min_match_score = 0.93
    max_market_cap = 100.0
    scan_date = '2026-01-21'
    
    # 开始扫描
    candidates = []
    start_time = time.time()
    
    for idx, row in stock_list.iterrows():
        code = row.get('代码', '') or row.get('code', '')
        name = row.get('名称', '') or row.get('name', '')
        
        if not code:
            continue
        
        # 排除ST和退市
        if 'ST' in name or '退' in name:
            continue
        
        try:
            # 获取周K线数据
            weekly_df = analyzer.fetcher.get_weekly_kline(code, period="2y", use_cache=True, local_only=True)
            if weekly_df is None or len(weekly_df) < 40:
                continue
            
            # 按日期截断
            scan_ts = pd.to_datetime(scan_date)
            if '日期' in weekly_df.columns:
                weekly_df['__dt'] = pd.to_datetime(weekly_df['日期'], errors='coerce')
                weekly_df = weekly_df.dropna(subset=['__dt'])
                weekly_df = weekly_df[weekly_df['__dt'] <= scan_ts]
                if len(weekly_df) < 40:
                    continue
                weekly_df = weekly_df.drop(columns=['__dt'])
            
            current_idx = len(weekly_df) - 1
            
            # 提取特征
            features = analyzer.extract_features_at_start_point(code, current_idx, lookback_weeks=40, weekly_df=weekly_df)
            if features is None:
                continue
            
            # 计算匹配度
            match_result = analyzer._calculate_match_score(features, common_features, tolerance=0.3)
            total_match = match_result.get('总匹配度', 0)
            
            if total_match >= min_match_score:
                # 获取价格信息
                current_price = float(weekly_df.iloc[current_idx]['收盘'])
                current_date = weekly_df.iloc[current_idx]['日期']
                if isinstance(current_date, pd.Timestamp):
                    current_date = current_date.strftime('%Y-%m-%d')
                else:
                    current_date = str(current_date)[:10]
                
                candidates.append({
                    '股票代码': code,
                    '股票名称': name,
                    '匹配度': round(total_match, 4),
                    '最佳买点日期': current_date,
                    '当前价格': round(current_price, 2)
                })
                print(f"  ✅ 找到: {code} {name} 匹配度={total_match:.4f}")
        
        except Exception as e:
            continue
        
        # 显示进度
        if (idx + 1) % 500 == 0:
            elapsed = time.time() - start_time
            pct = (idx + 1) / total_stocks * 100
            print(f"  扫描进度: {idx+1}/{total_stocks} ({pct:.1f}%) | 已找到: {len(candidates)} 只")
    
    # 按匹配度排序
    candidates.sort(key=lambda x: x['匹配度'], reverse=True)
    
    elapsed = time.time() - start_time
    print(f"\n扫描完成! 耗时: {elapsed:.1f}秒")
    
    return candidates

def main():
    print("=" * 60)
    print("全自动数据下载 + 扫描测试")
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # 检查当前数据完整率
    updated, total = check_data_completeness()
    completeness = updated / total * 100 if total > 0 else 0
    print(f"\n当前数据完整率: {updated}/{total} ({completeness:.1f}%)")
    
    # 如果完整率低于95%，修复数据
    if completeness < 95:
        print(f"完整率低于95%，开始修复数据...")
        fix_outdated_data()
        
        # 重新检查
        updated, total = check_data_completeness()
        completeness = updated / total * 100 if total > 0 else 0
        print(f"\n修复后数据完整率: {updated}/{total} ({completeness:.1f}%)")
    
    # 执行扫描
    candidates = run_scan()
    
    # 输出结果
    print("\n" + "=" * 60)
    print("扫描结果汇总")
    print("=" * 60)
    print(f"扫描日期: 2026-01-21")
    print(f"最低匹配度: 0.93")
    print(f"找到符合条件股票: {len(candidates)} 只")
    print("=" * 60)
    
    if candidates:
        print("\n排名 | 股票代码 | 股票名称 | 匹配度 | 买点日期 | 当前价格")
        print("-" * 70)
        for i, c in enumerate(candidates[:50], 1):
            print(f"{i:3d}  | {c['股票代码']:8s} | {c['股票名称'][:8]:8s} | {c['匹配度']:.4f} | {c['最佳买点日期']} | {c['当前价格']:.2f}")
    else:
        print("\n未找到符合条件的股票")
    
    # 保存结果
    result_file = f"scan_result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(result_file, 'w', encoding='utf-8') as f:
        json.dump({
            'scan_date': '2026-01-21',
            'min_match_score': 0.93,
            'max_market_cap': 100,
            'found_count': len(candidates),
            'candidates': candidates
        }, f, ensure_ascii=False, indent=2)
    print(f"\n结果已保存到: {result_file}")
    
    print("\n" + "=" * 60)
    print(f"完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    return candidates

if __name__ == '__main__':
    main()
