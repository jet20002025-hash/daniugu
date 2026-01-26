#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
通达信数据导入工具
将通达信的 .day 文件转换为系统可用的 CSV 格式
"""

import os
import struct
import pandas as pd
from datetime import datetime
import json

# 配置
CACHE_DIR = 'cache'
DAILY_DIR = os.path.join(CACHE_DIR, 'daily_kline')
WEEKLY_DIR = os.path.join(CACHE_DIR, 'weekly_kline')

def read_tdx_day_file(file_path):
    """
    读取通达信 .day 文件
    :param file_path: .day 文件路径
    :return: DataFrame，包含日期、开盘、收盘、最高、最低、成交量、成交额
    """
    try:
        with open(file_path, 'rb') as f:
            data = f.read()
        
        if len(data) % 32 != 0:
            print(f"⚠️ 警告：{file_path} 文件大小不是32的倍数，可能损坏")
            return None
        
        records = []
        for i in range(0, len(data), 32):
            # 每32字节一条记录
            record = data[i:i+32]
            if len(record) < 32:
                break
            
            # 解析数据
            # 00~03: 年月日 (YYYYMMDD)
            date_int = struct.unpack('I', record[0:4])[0]
            year = date_int // 10000
            month = (date_int % 10000) // 100
            day = date_int % 100
            date_str = f"{year:04d}-{month:02d}-{day:02d}"
            
            # 04~07: 开盘价 (需除以100)
            open_price = struct.unpack('I', record[4:8])[0] / 100.0
            
            # 08~11: 最高价 (需除以100)
            high_price = struct.unpack('I', record[8:12])[0] / 100.0
            
            # 12~15: 最低价 (需除以100)
            low_price = struct.unpack('I', record[12:16])[0] / 100.0
            
            # 16~19: 收盘价 (需除以100)
            close_price = struct.unpack('I', record[16:20])[0] / 100.0
            
            # 20~23: 成交额 (浮点数，单位：元)
            amount = struct.unpack('f', record[20:24])[0]
            
            # 24~27: 成交量 (需除以100，单位：手)
            volume = struct.unpack('I', record[24:28])[0] / 100.0
            
            records.append({
                '日期': date_str,
                '开盘': open_price,
                '收盘': close_price,
                '最高': high_price,
                '最低': low_price,
                '成交量': int(volume * 100),  # 转换为股数（手 * 100）
                '成交额': amount
            })
        
        if not records:
            return None
        
        df = pd.DataFrame(records)
        df = df.sort_values('日期').reset_index(drop=True)
        return df
    
    except Exception as e:
        print(f"❌ 读取 {file_path} 失败: {e}")
        return None

def convert_tdx_to_csv(tdx_dir, output_dir=None):
    """
    批量转换通达信数据目录中的所有 .day 文件
    :param tdx_dir: 通达信数据目录（如 vipdoc/sh/lday 或 vipdoc/sz/lday）
    :param output_dir: 输出目录（默认使用 cache/daily_kline）
    :return: 转换统计信息
    """
    if output_dir is None:
        output_dir = DAILY_DIR
    
    os.makedirs(output_dir, exist_ok=True)
    
    if not os.path.exists(tdx_dir):
        print(f"❌ 目录不存在: {tdx_dir}")
        return {'success': 0, 'failed': 0, 'skipped': 0}
    
    # 获取所有 .day 文件
    day_files = [f for f in os.listdir(tdx_dir) if f.endswith('.day')]
    
    if not day_files:
        print(f"⚠️ 目录中没有找到 .day 文件: {tdx_dir}")
        return {'success': 0, 'failed': 0, 'skipped': 0}
    
    print(f"📁 找到 {len(day_files)} 个 .day 文件")
    print(f"📂 输出目录: {output_dir}")
    print()
    
    success_count = 0
    failed_count = 0
    skipped_count = 0
    
    # 加载数据标记文件
    markers = load_data_markers()
    
    total_files = len(day_files)
    print(f"📊 总共 {total_files} 个文件需要转换")
    print()
    
    for idx, day_file in enumerate(sorted(day_files), 1):
        # 每100个文件显示一次进度
        if idx % 100 == 0 or idx == total_files:
            print(f"📈 进度: {idx}/{total_files} ({idx*100//total_files}%)")
        # 提取股票代码
        # 格式：sh600000.day 或 sz000001.day
        base_name = day_file.replace('.day', '')
        if base_name.startswith('sh') or base_name.startswith('sz'):
            stock_code = base_name[2:]  # 去掉市场前缀
        else:
            print(f"⚠️ 跳过无法识别的文件: {day_file}")
            skipped_count += 1
            continue
        
        tdx_file_path = os.path.join(tdx_dir, day_file)
        csv_file_path = os.path.join(output_dir, f'{stock_code}.csv')
        
        try:
            # 读取通达信数据
            df = read_tdx_day_file(tdx_file_path)
            
            if df is None or len(df) == 0:
                print(f"⚠️ {stock_code}: 数据为空，跳过")
                skipped_count += 1
                continue
            
            # 如果CSV文件已存在，合并数据（追加新数据）
            if os.path.exists(csv_file_path):
                try:
                    existing_df = pd.read_csv(csv_file_path)
                    # 合并数据（去重）
                    combined_df = pd.concat([existing_df, df], ignore_index=True)
                    combined_df = combined_df.drop_duplicates(subset=['日期'], keep='last')
                    combined_df = combined_df.sort_values('日期').reset_index(drop=True)
                    df = combined_df
                except Exception as e:
                    print(f"⚠️ {stock_code}: 合并现有数据失败，覆盖保存: {e}")
            
            # 保存为CSV
            df.to_csv(csv_file_path, index=False, encoding='utf-8')
            
            # 更新数据标记
            latest_date = str(df['日期'].max())[:10]
            update_marker(stock_code, daily_latest_date=latest_date, markers=markers)
            
            print(f"✅ {stock_code}: 转换成功，共 {len(df)} 条数据，最新日期: {latest_date}")
            success_count += 1
            
        except Exception as e:
            print(f"❌ {stock_code}: 转换失败: {e}")
            failed_count += 1
    
    # 保存标记文件
    save_data_markers(markers)
    
    print()
    print("=" * 60)
    print(f"转换完成！成功: {success_count}, 失败: {failed_count}, 跳过: {skipped_count}")
    print("=" * 60)
    
    return {
        'success': success_count,
        'failed': failed_count,
        'skipped': skipped_count
    }

def generate_weekly_kline_from_daily():
    """
    从日K线数据生成周K线数据
    """
    os.makedirs(WEEKLY_DIR, exist_ok=True)
    
    daily_files = [f for f in os.listdir(DAILY_DIR) if f.endswith('.csv')]
    
    print(f"📊 从 {len(daily_files)} 个日K线文件生成周K线数据...")
    
    markers = load_data_markers()
    success_count = 0
    
    for daily_file in sorted(daily_files):
        stock_code = daily_file.replace('.csv', '')
        daily_path = os.path.join(DAILY_DIR, daily_file)
        weekly_path = os.path.join(WEEKLY_DIR, daily_file)
        
        try:
            daily_df = pd.read_csv(daily_path)
            if len(daily_df) == 0:
                continue
            
            # 转换日期格式
            daily_df['日期'] = pd.to_datetime(daily_df['日期'])
            
            # 按周分组
            daily_df['年周'] = daily_df['日期'].dt.to_period('W')
            
            # 计算周K线数据
            weekly_data = []
            for week, group in daily_df.groupby('年周'):
                weekly_data.append({
                    '日期': group['日期'].max().strftime('%Y-%m-%d'),  # 使用该周最后一个交易日
                    '开盘': group.iloc[0]['开盘'],
                    '收盘': group.iloc[-1]['收盘'],
                    '最高': group['最高'].max(),
                    '最低': group['最低'].min(),
                    '周成交量': int(group['成交量'].sum())
                })
            
            if weekly_data:
                weekly_df = pd.DataFrame(weekly_data)
                weekly_df = weekly_df.sort_values('日期').reset_index(drop=True)
                weekly_df.to_csv(weekly_path, index=False, encoding='utf-8')
                
                # 更新标记
                latest_date = str(weekly_df['日期'].max())[:10]
                update_marker(stock_code, weekly_latest_date=latest_date, markers=markers)
                
                success_count += 1
                if success_count % 100 == 0:
                    print(f"  已处理 {success_count} 只股票...")
        
        except Exception as e:
            print(f"⚠️ {stock_code}: 生成周K线失败: {e}")
    
    save_data_markers(markers)
    print(f"✅ 周K线生成完成，共 {success_count} 只股票")

def load_data_markers():
    """加载数据标记文件"""
    marker_file = os.path.join(CACHE_DIR, 'data_markers.json')
    if os.path.exists(marker_file):
        try:
            with open(marker_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_data_markers(markers):
    """保存数据标记文件"""
    marker_file = os.path.join(CACHE_DIR, 'data_markers.json')
    with open(marker_file, 'w', encoding='utf-8') as f:
        json.dump(markers, f, ensure_ascii=False, indent=2)

def update_marker(code, daily_latest_date=None, weekly_latest_date=None, markers=None):
    """更新股票的数据标记"""
    if markers is None:
        markers = load_data_markers()
    if code not in markers:
        markers[code] = {}
    if daily_latest_date:
        markers[code]['daily_latest_date'] = daily_latest_date
    if weekly_latest_date:
        markers[code]['weekly_latest_date'] = weekly_latest_date

def main():
    print("=" * 60)
    print("📊 通达信数据导入工具")
    print("=" * 60)
    print()
    
    # 提示用户输入通达信数据目录
    print("请提供通达信数据目录路径：")
    print("  示例（Windows）: C:\\new_tdx\\vipdoc\\sh\\lday")
    print("  示例（Windows）: C:\\new_tdx\\vipdoc\\sz\\lday")
    print("  示例（Mac）: /Users/用户名/通达信/vipdoc/sh/lday")
    print()
    
    # 可以手动指定目录，或者让用户输入
    import sys
    if len(sys.argv) > 1:
        tdx_dir = sys.argv[1]
    else:
        tdx_dir = input("请输入通达信数据目录路径（直接回车跳过）: ").strip()
        if not tdx_dir:
            print("⚠️ 未提供目录，退出")
            return
    
    if not os.path.exists(tdx_dir):
        print(f"❌ 目录不存在: {tdx_dir}")
        return
    
    # 转换日K线数据
    print()
    print("=" * 60)
    print("步骤1: 转换日K线数据")
    print("=" * 60)
    result = convert_tdx_to_csv(tdx_dir)
    
    # 生成周K线数据
    print()
    print("=" * 60)
    print("步骤2: 生成周K线数据")
    print("=" * 60)
    generate_weekly_kline_from_daily()
    
    print()
    print("=" * 60)
    print("✅ 导入完成！")
    print("=" * 60)
    print()
    print("数据已保存到:")
    print(f"  - 日K线: {DAILY_DIR}")
    print(f"  - 周K线: {WEEKLY_DIR}")
    print()
    print("现在可以在系统中使用这些数据了！")

if __name__ == '__main__':
    main()
