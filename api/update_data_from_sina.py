#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
午盘/尾盘后从新浪更新 K 线数据的 Vercel Serverless Function
支持分批处理（适配 10 秒限制）
"""
import os
import sys
import json

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timezone, timedelta

# 注意：这个文件会被 Flask 路由调用，也会被 Vercel Serverless Function 直接调用
# 因此需要同时支持 Flask request 和 Vercel request 对象

def get_beijing_time():
    """获取北京时间（UTC+8）"""
    utc_now = datetime.now(timezone.utc)
    beijing_tz = timezone(timedelta(hours=8))
    beijing_now = utc_now.astimezone(beijing_tz)
    return beijing_now

def is_after_noon_or_close(beijing_now):
    """判断是否在午盘后（11:30-12:00）或尾盘后（15:00-15:30）"""
    current_hour = beijing_now.hour
    current_minute = beijing_now.minute
    
    # 午盘后：11:30-12:00
    if current_hour == 11 and current_minute >= 30:
        return True, 'noon'
    if current_hour == 12:
        return True, 'noon'
    
    # 尾盘后：15:00-15:30
    if current_hour == 15 and current_minute >= 0:
        return True, 'close'
    if current_hour == 15 and current_minute <= 30:
        return True, 'close'
    
    return False, None

def handler(request_obj):
    """处理函数（支持 Flask request 和 Vercel request）"""
    try:
        from flask import jsonify
        
        beijing_now = get_beijing_time()
        current_time_str = beijing_now.strftime('%Y-%m-%d %H:%M:%S')
        
        # 检查是否在允许的时间段
        is_allowed, time_type = is_after_noon_or_close(beijing_now)
        
        # 支持 Flask request 和 Vercel request
        if hasattr(request_obj, 'args'):
            # Flask request 对象
            force = request_obj.args.get('force', '').lower() == 'true'
            batch_num = int(request_obj.args.get('batch', 0))
            batch_size = int(request_obj.args.get('batch_size', 50))
        else:
            # Vercel request 对象（字典格式）
            query = request_obj.get('query', {}) if isinstance(request_obj, dict) else {}
            force = query.get('force', '').lower() == 'true'
            batch_num = int(query.get('batch', 0))
            batch_size = int(query.get('batch_size', 50))
        
        if not is_allowed and not force:
            return jsonify({
                'success': False,
                'message': f'当前时间不在允许的执行时间（当前时间: {current_time_str}）\n\n允许的时间：\n- 11:30-12:00（午盘后）\n- 15:00-15:30（尾盘后）\n\n如需强制执行，请使用 ?force=true 参数',
                'current_time': current_time_str
            }), 200
        
        
        print(f"[update_data_from_sina] 开始从新浪更新数据 - 时间: {current_time_str}, 批次: {batch_num}, 每批: {batch_size}")
        
        # 导入更新脚本
        try:
            import sys
            # 设置 today_only 模式（通过修改 sys.argv，因为 process_single_stock 从 sys.argv 读取）
            original_argv = sys.argv.copy()
            sys.argv = ['update_data_sina.py', '--today-only']  # 设置 today_only 模式
            
            from update_data_sina import get_stock_list, process_single_stock
            import pandas as pd
            from concurrent.futures import ThreadPoolExecutor, as_completed
            import time as time_module
        except ImportError as e:
            # 恢复 sys.argv
            if 'original_argv' in locals():
                sys.argv = original_argv
            return jsonify({
                'success': False,
                'message': f'导入更新模块失败: {str(e)}',
                'current_time': current_time_str
            }), 500
        
        # 获取股票列表
        stock_list = get_stock_list()
        if not stock_list:
            return jsonify({
                'success': False,
                'message': '无法获取股票列表',
                'current_time': current_time_str
            }), 500
        
        # 转换为统一格式
        valid_stocks = []
        for stock in stock_list:
            code = stock.get('code', stock.get('股票代码', ''))
            name = stock.get('name', stock.get('股票名称', ''))
            if code:
                valid_stocks.append({'code': str(code).strip(), 'name': name or ''})
        
        total_stocks = len(valid_stocks)
        start_idx = batch_num * batch_size
        end_idx = min(start_idx + batch_size, total_stocks)
        batch_stocks = valid_stocks[start_idx:end_idx]
        
        if len(batch_stocks) == 0:
            return jsonify({
                'success': True,
                'message': '所有批次已处理完成',
                'current_time': current_time_str,
                'total_stocks': total_stocks,
                'batch_num': batch_num,
                'batch_size': batch_size,
                'processed': total_stocks,
                'completed': True
            }), 200
        
        print(f"[update_data_from_sina] 处理批次 {batch_num}: {start_idx}-{end_idx}/{total_stocks} 只股票")
        
        # 目标日期（今天）
        target_date = beijing_now.strftime('%Y-%m-%d')
        
        # 处理当前批次（today-only 模式，只更新今天这一根日K）
        daily_updated = 0
        weekly_updated = 0
        errors = 0
        start_time = time_module.time()
        
        # 使用较小的并发数，避免超时
        max_workers = min(5, len(batch_stocks))
        
        # 注意：process_single_stock 内部会检查 today_only 参数（从 sys.argv 读取）
        # 我们需要确保它使用 today-only 模式（只更新今天这一根日K）
        # 由于 process_single_stock 从 sys.argv 读取参数，我们需要设置环境变量或修改调用方式
        # 但为了简化，我们直接调用，process_single_stock 会检查目标日期是否为今天
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(process_single_stock, s['code'], s['name'], target_date): s
                for s in batch_stocks
            }
            
            for future in as_completed(futures):
                stock = futures[future]
                try:
                    result = future.result(timeout=8)  # 单只股票最多 8 秒
                    if result:
                        daily_updated += result.get('daily_updated', 0)
                        weekly_updated += result.get('weekly_updated', 0)
                        if result.get('error'):
                            errors += 1
                except Exception as e:
                    errors += 1
                    print(f"[update_data_from_sina] {stock['code']} 处理失败: {e}")
        
        elapsed = time_module.time() - start_time
        
        # 检查是否还有下一批
        has_next = end_idx < total_stocks
        next_batch = batch_num + 1 if has_next else None
        
        # 恢复原始 sys.argv
        sys.argv = original_argv
        
        return jsonify({
            'success': True,
            'message': f'批次 {batch_num} 处理完成（{len(batch_stocks)} 只股票，耗时 {elapsed:.1f}秒）',
            'current_time': current_time_str,
            'total_stocks': total_stocks,
            'batch_num': batch_num,
            'batch_size': batch_size,
            'processed': end_idx,
            'daily_updated': daily_updated,
            'weekly_updated': weekly_updated,
            'errors': errors,
            'has_next': has_next,
            'next_batch': next_batch,
            'next_batch_url': f'/api/update_data_from_sina?batch={next_batch}&batch_size={batch_size}' if has_next else None,
            'completed': not has_next
        }), 200
        
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"[update_data_from_sina] ❌ 错误: {error_detail}")
        # 确保恢复 sys.argv
        if 'original_argv' in locals():
            sys.argv = original_argv
        return jsonify({
            'success': False,
            'message': f'更新数据失败: {str(e)}',
            'error_detail': error_detail[:500] if len(error_detail) > 500 else error_detail
        }), 500
