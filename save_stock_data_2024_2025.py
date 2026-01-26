#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
保存2024-2025年所有A股数据到本地
支持多种存储格式：CSV、Parquet、SQLite
"""
import os
import pandas as pd
from datetime import datetime, date
from data_fetcher import DataFetcher
import time
import json

class StockDataSaver:
    """股票数据保存类"""
    
    def __init__(self, base_dir='stock_data'):
        """
        初始化
        :param base_dir: 数据存储根目录
        """
        self.base_dir = base_dir
        self.fetcher = DataFetcher()
        
        # 创建目录结构
        self.daily_dir = os.path.join(base_dir, 'daily_kline')
        self.weekly_dir = os.path.join(base_dir, 'weekly_kline')
        self.parquet_dir = os.path.join(base_dir, 'parquet')
        self.db_path = os.path.join(base_dir, 'stock_data.db')
        
        os.makedirs(self.daily_dir, exist_ok=True)
        os.makedirs(self.weekly_dir, exist_ok=True)
        os.makedirs(self.parquet_dir, exist_ok=True)
        
        # 数据范围
        self.start_date = '2024-01-01'
        self.end_date = '2025-12-31'
        
    def get_all_stocks(self):
        """获取所有A股股票列表"""
        print("正在获取股票列表...")
        stock_list = self.fetcher.get_all_stocks()
        if stock_list is None or len(stock_list) == 0:
            print("❌ 无法获取股票列表")
            return []
        print(f"✅ 获取到 {len(stock_list)} 只股票")
        return stock_list
    
    def save_daily_kline(self, stock_code, stock_name, format='csv'):
        """
        保存单只股票的日K线数据
        :param stock_code: 股票代码
        :param stock_name: 股票名称
        :param format: 存储格式 ('csv', 'parquet', 'both')
        :return: 是否成功
        """
        try:
            # 获取日K线数据
            df = self.fetcher.get_daily_kline(stock_code, period="2y")
            
            if df is None or len(df) == 0:
                return False
            
            # 过滤日期范围
            if '日期' in df.columns:
                df['日期'] = pd.to_datetime(df['日期'])
                df = df[(df['日期'] >= self.start_date) & (df['日期'] <= self.end_date)]
            
            if len(df) == 0:
                return False
            
            # 添加股票代码和名称
            df['股票代码'] = stock_code
            df['股票名称'] = stock_name
            
            # 保存CSV
            if format in ['csv', 'both']:
                csv_file = os.path.join(self.daily_dir, f'{stock_code}.csv')
                df.to_csv(csv_file, index=False, encoding='utf-8-sig')
            
            # 保存Parquet
            if format in ['parquet', 'both']:
                parquet_file = os.path.join(self.parquet_dir, 'daily_kline', f'{stock_code}.parquet')
                os.makedirs(os.path.dirname(parquet_file), exist_ok=True)
                df.to_parquet(parquet_file, index=False, compression='snappy')
            
            return True
            
        except Exception as e:
            print(f"  ⚠️ {stock_code} 日K线保存失败: {e}")
            return False
    
    def save_weekly_kline(self, stock_code, stock_name, format='csv'):
        """
        保存单只股票的周K线数据
        :param stock_code: 股票代码
        :param stock_name: 股票名称
        :param format: 存储格式 ('csv', 'parquet', 'both')
        :return: 是否成功
        """
        try:
            # 获取周K线数据
            df = self.fetcher.get_weekly_kline(stock_code, period="2y")
            
            if df is None or len(df) == 0:
                return False
            
            # 过滤日期范围
            if '日期' in df.columns:
                df['日期'] = pd.to_datetime(df['日期'])
                df = df[(df['日期'] >= self.start_date) & (df['日期'] <= self.end_date)]
            
            if len(df) == 0:
                return False
            
            # 添加股票代码和名称
            df['股票代码'] = stock_code
            df['股票名称'] = stock_name
            
            # 保存CSV
            if format in ['csv', 'both']:
                csv_file = os.path.join(self.weekly_dir, f'{stock_code}.csv')
                df.to_csv(csv_file, index=False, encoding='utf-8-sig')
            
            # 保存Parquet
            if format in ['parquet', 'both']:
                parquet_file = os.path.join(self.parquet_dir, 'weekly_kline', f'{stock_code}.parquet')
                os.makedirs(os.path.dirname(parquet_file), exist_ok=True)
                df.to_parquet(parquet_file, index=False, compression='snappy')
            
            return True
            
        except Exception as e:
            print(f"  ⚠️ {stock_code} 周K线保存失败: {e}")
            return False
    
    def save_all_stocks(self, data_type='both', format='both', limit=None, delay=0.1):
        """
        保存所有股票数据
        :param data_type: 数据类型 ('daily', 'weekly', 'both')
        :param format: 存储格式 ('csv', 'parquet', 'both')
        :param limit: 限制股票数量（None表示全部）
        :param delay: 每次请求之间的延迟（秒）
        :return: 统计信息
        """
        stock_list = self.get_all_stocks()
        
        if len(stock_list) == 0:
            return
        
        if limit:
            stock_list = stock_list[:limit]
        
        total = len(stock_list)
        stats = {
            'total': total,
            'daily_success': 0,
            'daily_failed': 0,
            'weekly_success': 0,
            'weekly_failed': 0,
            'start_time': time.time()
        }
        
        print(f"\n开始保存 {total} 只股票的数据...")
        print(f"数据范围: {self.start_date} 至 {self.end_date}")
        print(f"存储格式: {format}")
        print(f"数据类型: {data_type}")
        print("=" * 80)
        
        for idx, stock in enumerate(stock_list.iterrows(), 1):
            stock_code = stock[1]['代码'] if '代码' in stock[1] else stock[1].iloc[0]
            stock_name = stock[1]['名称'] if '名称' in stock[1] else stock[1].iloc[1]
            
            print(f"[{idx}/{total}] {stock_code} {stock_name}")
            
            # 保存日K线
            if data_type in ['daily', 'both']:
                if self.save_daily_kline(stock_code, stock_name, format):
                    stats['daily_success'] += 1
                else:
                    stats['daily_failed'] += 1
                time.sleep(delay)
            
            # 保存周K线
            if data_type in ['weekly', 'both']:
                if self.save_weekly_kline(stock_code, stock_name, format):
                    stats['weekly_success'] += 1
                else:
                    stats['weekly_failed'] += 1
                time.sleep(delay)
            
            # 每100只股票显示一次进度
            if idx % 100 == 0:
                elapsed = time.time() - stats['start_time']
                speed = idx / elapsed if elapsed > 0 else 0
                remaining = (total - idx) / speed if speed > 0 else 0
                print(f"\n进度: {idx}/{total} ({idx/total*100:.1f}%)")
                print(f"速度: {speed:.1f} 只/秒, 预计剩余时间: {remaining/60:.1f} 分钟")
                print(f"日K线: 成功 {stats['daily_success']}, 失败 {stats['daily_failed']}")
                print(f"周K线: 成功 {stats['weekly_success']}, 失败 {stats['weekly_failed']}")
                print("-" * 80)
        
        # 最终统计
        elapsed = time.time() - stats['start_time']
        stats['elapsed_time'] = elapsed
        
        print("\n" + "=" * 80)
        print("✅ 数据保存完成！")
        print("=" * 80)
        print(f"总耗时: {elapsed/60:.1f} 分钟")
        print(f"日K线: 成功 {stats['daily_success']}, 失败 {stats['daily_failed']}")
        print(f"周K线: 成功 {stats['weekly_success']}, 失败 {stats['weekly_failed']}")
        print(f"数据存储位置: {os.path.abspath(self.base_dir)}")
        
        # 计算文件大小
        self._calculate_size()
        
        return stats
    
    def _calculate_size(self):
        """计算存储文件大小"""
        total_size = 0
        file_count = 0
        
        for root, dirs, files in os.walk(self.base_dir):
            for file in files:
                file_path = os.path.join(root, file)
                if os.path.exists(file_path):
                    size = os.path.getsize(file_path)
                    total_size += size
                    file_count += 1
        
        print(f"\n存储统计:")
        print(f"  文件数量: {file_count}")
        print(f"  总大小: {total_size / 1024 / 1024:.2f} MB ({total_size / 1024 / 1024 / 1024:.2f} GB)")
    
    def create_sqlite_database(self):
        """
        创建SQLite数据库（可选，用于复杂查询）
        注意：这需要读取所有已保存的CSV文件，可能需要较长时间
        """
        try:
            import sqlite3
        except ImportError:
            print("❌ 需要 sqlite3 库")
            return
        
        print("\n正在创建SQLite数据库...")
        print("⚠️ 这可能需要较长时间，请耐心等待...")
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 创建日K线表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS daily_kline (
                股票代码 TEXT,
                股票名称 TEXT,
                日期 DATE,
                开盘 REAL,
                收盘 REAL,
                最高 REAL,
                最低 REAL,
                成交量 REAL,
                成交额 REAL,
                振幅 REAL,
                涨跌幅 REAL,
                涨跌额 REAL,
                换手率 REAL,
                PRIMARY KEY (股票代码, 日期)
            )
        ''')
        
        # 创建周K线表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS weekly_kline (
                股票代码 TEXT,
                股票名称 TEXT,
                日期 DATE,
                开盘 REAL,
                收盘 REAL,
                最高 REAL,
                最低 REAL,
                成交量 REAL,
                成交额 REAL,
                振幅 REAL,
                涨跌幅 REAL,
                涨跌额 REAL,
                换手率 REAL,
                PRIMARY KEY (股票代码, 日期)
            )
        ''')
        
        # 创建索引
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_daily_code ON daily_kline(股票代码)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_daily_date ON daily_kline(日期)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_weekly_code ON weekly_kline(股票代码)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_weekly_date ON weekly_kline(日期)')
        
        # 读取CSV文件并插入数据库
        csv_files = []
        for file in os.listdir(self.daily_dir):
            if file.endswith('.csv'):
                csv_files.append(('daily', os.path.join(self.daily_dir, file)))
        
        for file in os.listdir(self.weekly_dir):
            if file.endswith('.csv'):
                csv_files.append(('weekly', os.path.join(self.weekly_dir, file)))
        
        print(f"找到 {len(csv_files)} 个CSV文件，开始导入数据库...")
        
        for idx, (table_type, csv_file) in enumerate(csv_files, 1):
            try:
                df = pd.read_csv(csv_file, encoding='utf-8-sig')
                table_name = f'{table_type}_kline'
                df.to_sql(table_name, conn, if_exists='append', index=False)
                
                if idx % 100 == 0:
                    print(f"  进度: {idx}/{len(csv_files)}")
            except Exception as e:
                print(f"  ⚠️ {csv_file} 导入失败: {e}")
        
        conn.commit()
        conn.close()
        
        print(f"✅ SQLite数据库创建完成: {self.db_path}")


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='保存2024-2025年A股数据到本地')
    parser.add_argument('--type', choices=['daily', 'weekly', 'both'], default='both',
                       help='数据类型：daily=日K线, weekly=周K线, both=两者')
    parser.add_argument('--format', choices=['csv', 'parquet', 'both'], default='both',
                       help='存储格式：csv=CSV, parquet=Parquet, both=两者')
    parser.add_argument('--limit', type=int, default=None,
                       help='限制股票数量（用于测试）')
    parser.add_argument('--delay', type=float, default=0.1,
                       help='每次请求之间的延迟（秒）')
    parser.add_argument('--create-db', action='store_true',
                       help='创建SQLite数据库（需要先保存CSV）')
    
    args = parser.parse_args()
    
    saver = StockDataSaver()
    
    if args.create_db:
        saver.create_sqlite_database()
    else:
        saver.save_all_stocks(
            data_type=args.type,
            format=args.format,
            limit=args.limit,
            delay=args.delay
        )


if __name__ == '__main__':
    main()
