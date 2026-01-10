#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Vercel Cron Job 端点
用于触发自动扫描任务
"""
import os
import sys

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import jsonify
from auto_scan_cron import trigger_auto_scan_by_type, get_beijing_time

def handler(request):
    """Vercel Serverless Function 处理函数（根据当前时间自动判断扫描类型）"""
    try:
        beijing_now = get_beijing_time()
        current_hour = beijing_now.hour
        current_minute = beijing_now.minute
        
        # 根据当前时间自动判断扫描类型
        scan_type = None
        if current_hour == 11 and current_minute == 30:
            scan_type = 'noon'
        elif current_hour == 15 and current_minute == 0:
            scan_type = 'afternoon'
        else:
            # 如果不在预期的扫描时间，尝试从参数获取（向后兼容）
            scan_type = request.args.get('scan_type', '')
            if scan_type not in ['noon', 'afternoon']:
                return jsonify({
                    'success': False,
                    'message': f'当前时间不是自动扫描时间点（当前时间: {beijing_now.strftime("%H:%M")}，扫描时间: 11:30 (noon), 15:00 (afternoon)）',
                    'current_time': beijing_now.strftime('%Y-%m-%d %H:%M:%S'),
                    'expected_times': ['11:30 (noon)', '15:00 (afternoon)']
                }), 400
        
        scan_time = '11:30' if scan_type == 'noon' else '15:00'
        print(f"[cron] 触发自动扫描 - 类型: {scan_type}, 当前时间: {beijing_now.strftime('%Y-%m-%d %H:%M:%S')} (预计完成时间: {scan_time})")
        
        # 触发自动扫描
        success = trigger_auto_scan_by_type(scan_type)
        
        if success:
            return jsonify({
                'success': True,
                'message': f'{scan_type} 自动扫描任务已启动',
                'scan_type': scan_type,
                'scan_time': scan_time,
                'time': beijing_now.strftime('%Y-%m-%d %H:%M:%S')
            }), 200
        else:
            return jsonify({
                'success': False,
                'message': f'{scan_type} 自动扫描任务启动失败',
                'scan_type': scan_type,
                'scan_time': scan_time,
                'time': beijing_now.strftime('%Y-%m-%d %H:%M:%S')
            }), 500
            
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"[cron] 错误: {error_detail}")
        return jsonify({
            'success': False,
            'message': f'自动扫描任务失败: {str(e)}',
            'error': error_detail
        }), 500



