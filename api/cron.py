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
from auto_scan_cron import trigger_auto_scan, get_beijing_time

def handler(request):
    """Vercel Serverless Function 处理函数"""
    try:
        # 从请求中获取用户等级（默认为 free）
        user_tier = request.args.get('tier', 'free')
        
        if user_tier not in ['free', 'premium']:
            return jsonify({
                'success': False,
                'message': f'无效的用户等级: {user_tier}'
            }), 400
        
        beijing_now = get_beijing_time()
        print(f"[cron] 触发自动扫描 - 用户等级: {user_tier}, 时间: {beijing_now.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # 触发自动扫描
        success = trigger_auto_scan(user_tier)
        
        if success:
            return jsonify({
                'success': True,
                'message': f'{user_tier} 用户自动扫描任务已启动',
                'time': beijing_now.strftime('%Y-%m-%d %H:%M:%S')
            }), 200
        else:
            return jsonify({
                'success': False,
                'message': f'{user_tier} 用户自动扫描任务启动失败',
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

