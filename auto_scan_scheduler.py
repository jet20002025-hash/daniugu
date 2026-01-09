#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自动扫描调度器
用于定时自动扫描股票
"""
import os
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional, List


def get_beijing_time() -> datetime:
    """获取北京时间（UTC+8）"""
    utc_now = datetime.now(timezone.utc)
    beijing_tz = timezone(timedelta(hours=8))
    beijing_now = utc_now.astimezone(beijing_tz)
    return beijing_now


def should_run_auto_scan_for_free_users() -> bool:
    """
    检查是否应该为免费用户运行自动扫描
    免费用户：每天3:00（15:00）自动扫描
    """
    beijing_now = get_beijing_time()
    current_hour = beijing_now.hour
    current_minute = beijing_now.minute
    
    # 每天3:00（15:00）执行，允许5分钟的执行窗口
    if current_hour == 15 and 0 <= current_minute < 5:
        return True
    return False


def should_run_auto_scan_for_vip_users() -> bool:
    """
    检查是否应该为VIP用户运行自动扫描
    VIP用户：每天11:30自动扫描
    """
    beijing_now = get_beijing_time()
    current_hour = beijing_now.hour
    current_minute = beijing_now.minute
    
    # 每天11:30执行，允许5分钟的执行窗口
    if current_hour == 11 and 30 <= current_minute < 35:
        return True
    return False


def get_users_by_tier(tier: str, is_vercel: bool = False) -> List[Dict]:
    """
    根据用户等级获取用户列表
    :param tier: 用户等级 ('free', 'premium', 'super')
    :param is_vercel: 是否在Vercel环境
    :return: 用户列表
    """
    try:
        if is_vercel:
            from user_auth_vercel import load_users
        else:
            from user_auth import load_users
        
        users = load_users()
        result = []
        
        for username, user_data in users.items():
            is_vip = user_data.get('is_vip', False) or user_data.get('is_premium', False)
            is_super = user_data.get('is_super', False) or user_data.get('is_admin', False)
            username_lower = username.lower()
            admin_users = ['admin', 'super', 'root']
            is_super = is_super or username_lower in admin_users
            
            user_tier = 'super' if is_super else ('premium' if is_vip else 'free')
            
            if user_tier == tier:
                result.append({
                    'username': username,
                    'email': user_data.get('email', ''),
                    'tier': user_tier
                })
        
        return result
    except Exception as e:
        print(f"[get_users_by_tier] 获取用户列表失败: {e}")
        return []


def check_if_auto_scan_done_today(username: str, tier: str, is_vercel: bool = False) -> bool:
    """
    检查今天是否已经执行过自动扫描
    :param username: 用户名
    :param tier: 用户等级
    :param is_vercel: 是否在Vercel环境
    :return: 是否已执行
    """
    beijing_now = get_beijing_time()
    today_str = beijing_now.strftime('%Y-%m-%d')
    scan_key = f'auto_scan_{tier}_{username}_{today_str}'
    
    try:
        if is_vercel:
            try:
                import scan_progress_store
                if hasattr(scan_progress_store, '_upstash_redis_get'):
                    result = scan_progress_store._upstash_redis_get(scan_key)
                    return result is not None and result != ''
            except Exception as e:
                print(f"[check_if_auto_scan_done_today] 从 Redis 读取失败: {e}")
        else:
            import json
            import os
            auto_scan_file = 'auto_scan_log.json'
            if os.path.exists(auto_scan_file):
                with open(auto_scan_file, 'r', encoding='utf-8') as f:
                    auto_scan_log = json.load(f)
                    return scan_key in auto_scan_log
        return False
    except Exception as e:
        print(f"[check_if_auto_scan_done_today] 检查自动扫描状态失败: {e}")
        return False


def mark_auto_scan_done(username: str, tier: str, scan_id: str, is_vercel: bool = False):
    """
    标记自动扫描已完成
    :param username: 用户名
    :param tier: 用户等级
    :param scan_id: 扫描任务ID
    :param is_vercel: 是否在Vercel环境
    """
    beijing_now = get_beijing_time()
    today_str = beijing_now.strftime('%Y-%m-%d')
    scan_key = f'auto_scan_{tier}_{username}_{today_str}'
    
    try:
        if is_vercel:
            try:
                import scan_progress_store
                if hasattr(scan_progress_store, '_upstash_redis_set'):
                    # 保存扫描ID，TTL设置为25小时
                    scan_progress_store._upstash_redis_set(scan_key, scan_id, ttl=90000)
            except Exception as e:
                print(f"[mark_auto_scan_done] 保存到 Redis 失败: {e}")
        else:
            import json
            import os
            auto_scan_file = 'auto_scan_log.json'
            if os.path.exists(auto_scan_file):
                with open(auto_scan_file, 'r', encoding='utf-8') as f:
                    auto_scan_log = json.load(f)
            else:
                auto_scan_log = {}
            
            auto_scan_log[scan_key] = {
                'scan_id': scan_id,
                'timestamp': beijing_now.isoformat(),
                'tier': tier,
                'username': username
            }
            
            # 清理7天前的记录
            seven_days_ago = (beijing_now - timedelta(days=7)).strftime('%Y-%m-%d')
            keys_to_remove = [k for k in auto_scan_log.keys() if k.endswith(seven_days_ago)]
            for k in keys_to_remove:
                del auto_scan_log[k]
            
            with open(auto_scan_file, 'w', encoding='utf-8') as f:
                json.dump(auto_scan_log, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[mark_auto_scan_done] 标记自动扫描完成失败: {e}")

