#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
刷新股票列表缓存的 Cron Job 端点
在交易时间段（9:30-11:30, 13:00-15:00）每5分钟刷新一次
盘后（15:05）刷新一次
"""
import os
import sys

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import jsonify, request
from datetime import datetime, timezone, timedelta
from data_fetcher import DataFetcher
from bull_stock_analyzer import BullStockAnalyzer

def get_beijing_time():
    """获取北京时间（UTC+8）"""
    utc_now = datetime.now(timezone.utc)
    beijing_tz = timezone(timedelta(hours=8))
    beijing_now = utc_now.astimezone(beijing_tz)
    return beijing_now

def is_trading_time(beijing_now):
    """判断是否在交易时间段（9:30-11:30, 13:00-15:00）或盘后时间（15:05）"""
    current_hour = beijing_now.hour
    current_minute = beijing_now.minute
    
    # 上午交易时间：9:30-11:30
    # 9:30-9:59, 10:00-10:59, 11:00-11:30
    if current_hour == 9 and current_minute >= 30:
        return True
    if current_hour == 10:
        return True
    if current_hour == 11 and current_minute <= 30:
        return True
    
    # 下午交易时间：13:00-15:00
    # 13:00-13:59, 14:00-14:59, 15:00
    if current_hour == 13:
        return True
    if current_hour == 14:
        return True
    if current_hour == 15 and current_minute <= 0:  # 15:00
        return True
    
    # 盘后时间：15:05（15:05执行一次）
    if current_hour == 15 and current_minute == 5:
        return True
    
    return False

def handler(request):
    """Vercel Serverless Function 处理函数"""
    try:
        beijing_now = get_beijing_time()
        current_time_str = beijing_now.strftime('%Y-%m-%d %H:%M:%S')
        
        # 检查是否在交易时间或盘后时间
        if not is_trading_time(beijing_now):
            return jsonify({
                'success': False,
                'message': f'当前时间不在交易时间段或盘后时间（当前时间: {current_time_str}）',
                'current_time': current_time_str,
                'trading_hours': '9:30-11:30, 13:00-15:00（每5分钟刷新），15:05（盘后刷新）'
            }), 200
        
        print(f"[refresh_stock_cache] 开始刷新股票列表缓存 - 时间: {current_time_str}")
        
        # 创建 DataFetcher 实例
        fetcher = DataFetcher()
        
        # 从 akshare API 获取股票列表（不超时，因为这是后台任务）
        print("[refresh_stock_cache] 从 akshare API 获取股票列表...")
        stock_list = fetcher.get_all_stocks(timeout=30, max_retries=3)  # 后台任务可以使用更长的超时
        
        if stock_list is None or len(stock_list) == 0:
            return jsonify({
                'success': False,
                'message': '无法获取股票列表，缓存刷新失败',
                'current_time': current_time_str
            }), 500
        
        # 保存到缓存（get_all_stocks 内部会自动保存到缓存）
        print(f"[refresh_stock_cache] ✅ 成功刷新股票列表缓存，股票数: {len(stock_list)}")
        
        return jsonify({
            'success': True,
            'message': f'股票列表缓存已刷新（{len(stock_list)} 只股票）',
            'stock_count': len(stock_list),
            'current_time': current_time_str,
            'cache_ttl': '24小时'
        }), 200
            
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"[refresh_stock_cache] ❌ 错误: {error_detail}")
        return jsonify({
            'success': False,
            'message': f'刷新股票列表缓存失败: {str(e)}',
            'error': error_detail,
            'current_time': get_beijing_time().strftime('%Y-%m-%d %H:%M:%S')
        }), 500

