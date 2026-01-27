#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
在下载数据后，从K线文件列表自动生成 stock_list_all.json
"""
import os
import json
import pandas as pd
from pathlib import Path
from datetime import datetime, timezone

def generate_stock_list_from_kline_files():
    """从K线文件列表生成股票列表"""
    cache_dir = os.environ.get('LOCAL_CACHE_DIR') or 'cache'
    weekly_dir = os.path.join(cache_dir, 'weekly_kline')
    daily_dir = os.path.join(cache_dir, 'daily_kline')
    stock_list_path = os.path.join(cache_dir, 'stock_list_all.json')
    meta_path = os.path.join(cache_dir, 'stock_list_all.meta.json')
    
    print("=" * 60)
    print("📋 从K线文件列表生成股票列表")
    print("=" * 60)
    
    # 收集所有股票代码
    stock_codes = set()
    
    # 从周K线目录收集
    if os.path.exists(weekly_dir):
        print(f"\n📂 扫描周K线目录: {weekly_dir}")
        for file in os.listdir(weekly_dir):
            if file.endswith('.csv'):
                code = file.replace('.csv', '')
                stock_codes.add(code)
        print(f"   找到 {len(stock_codes)} 只股票（从周K线）")
    
    # 从日K线目录收集（补充）
    if os.path.exists(daily_dir):
        print(f"\n📂 扫描日K线目录: {daily_dir}")
        daily_count = 0
        for file in os.listdir(daily_dir):
            if file.endswith('.csv'):
                code = file.replace('.csv', '')
                if code not in stock_codes:
                    stock_codes.add(code)
                    daily_count += 1
        print(f"   新增 {daily_count} 只股票（从日K线）")
    
    if not stock_codes:
        print("\n⚠️  未找到任何K线文件，无法生成股票列表")
        return False
    
    print(f"\n✅ 共找到 {len(stock_codes)} 只股票")
    
        # 尝试从K线文件中获取股票名称
        stock_list = []
        name_count = 0
        
        print("\n📝 正在获取股票名称...")
        for code in sorted(stock_codes):
            stock_info = {
                'code': code,
                'name': code  # 默认使用代码作为名称
            }
            
            # 尝试从周K线文件读取名称
            weekly_file = os.path.join(weekly_dir, f'{code}.csv')
            if os.path.exists(weekly_file):
                try:
                    df = pd.read_csv(weekly_file, nrows=1)
                    if '股票名称' in df.columns:
                        stock_info['name'] = str(df['股票名称'].iloc[0]).strip()
                        name_count += 1
                    elif '名称' in df.columns:
                        stock_info['name'] = str(df['名称'].iloc[0]).strip()
                        name_count += 1
                except Exception as e:
                    pass
            
            # 如果周K线没有名称，尝试从日K线读取
            if stock_info['name'] == code:
                daily_file = os.path.join(daily_dir, f'{code}.csv')
                if os.path.exists(daily_file):
                    try:
                        df = pd.read_csv(daily_file, nrows=1)
                        if '股票名称' in df.columns:
                            stock_info['name'] = str(df['股票名称'].iloc[0]).strip()
                            name_count += 1
                        elif '名称' in df.columns:
                            stock_info['name'] = str(df['名称'].iloc[0]).strip()
                            name_count += 1
                    except Exception as e:
                        pass
            
            # 如果还是没有名称，尝试使用 akshare 获取（可选）
            if stock_info['name'] == code:
                try:
                    import akshare as ak
                    # 尝试获取股票基本信息
                    stock_info_df = ak.stock_individual_info_em(symbol=code)
                    if stock_info_df is not None and len(stock_info_df) > 0:
                        # 查找名称字段
                        for idx, row in stock_info_df.iterrows():
                            if '股票简称' in str(row.iloc[0]) or '名称' in str(row.iloc[0]):
                                stock_info['name'] = str(row.iloc[1]).strip()
                                name_count += 1
                                break
                except Exception as e:
                    # akshare 获取失败，使用代码作为名称
                    pass
            
            stock_list.append(stock_info)
    
    print(f"   成功获取 {name_count} 只股票的名称")
    
    # 保存股票列表
    try:
        os.makedirs(cache_dir, exist_ok=True)
        with open(stock_list_path, 'w', encoding='utf-8') as f:
            json.dump(stock_list, f, ensure_ascii=False, indent=2)
        
        # 保存元数据
        with open(meta_path, 'w', encoding='utf-8') as f:
            json.dump({
                'saved_at': datetime.now(timezone.utc).timestamp(),
                'ttl': 86400,
                'generated_from': 'kline_files',
                'stock_count': len(stock_list)
            }, f, ensure_ascii=False, indent=2)
        
        print(f"\n✅ 股票列表已生成: {stock_list_path}")
        print(f"   股票数: {len(stock_list)} 只")
        print(f"   文件大小: {os.path.getsize(stock_list_path) / 1024:.2f} KB")
        return True
    except Exception as e:
        print(f"\n❌ 保存股票列表失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    generate_stock_list_from_kline_files()
