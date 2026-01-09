#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
扫描限制辅助函数
用于检查用户扫描权限和时间限制
"""
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional, Tuple


def get_beijing_time() -> datetime:
    """获取北京时间（UTC+8）"""
    # 获取当前UTC时间
    utc_now = datetime.now(timezone.utc)
    # 转换为北京时间（UTC+8）
    beijing_tz = timezone(timedelta(hours=8))
    beijing_now = utc_now.astimezone(beijing_tz)
    return beijing_now


def check_scan_time_limit(user_tier: str, scan_config: Dict) -> Tuple[bool, Optional[str]]:
    """
    检查用户是否可以在当前时间扫描
    :param user_tier: 用户等级 ('free', 'premium', 'super')
    :param scan_config: 扫描配置
    :return: (是否允许, 错误消息)
    """
    if user_tier == 'super':
        # 超级用户：随时可以扫描
        return True, None
    
    beijing_now = get_beijing_time()
    current_hour = beijing_now.hour
    current_minute = beijing_now.minute
    
    if user_tier == 'premium':
        # VIP用户：随时可以扫描（没有时间限制）
        return True, None
    else:
        # 免费用户：只能在下午3点后扫描
        scan_start_hour = scan_config.get('scan_start_hour', 15)
        if current_hour < scan_start_hour:
            return False, f'免费用户只能在下午{scan_start_hour}点后扫描，当前时间：{beijing_now.strftime("%H:%M")}'
        return True, None


def check_daily_scan_limit(username: str, user_tier: str, scan_config: Dict, is_vercel: bool = False) -> Tuple[bool, Optional[str], Optional[int]]:
    """
    检查用户每日扫描次数限制
    :param username: 用户名
    :param user_tier: 用户等级
    :param scan_config: 扫描配置
    :param is_vercel: 是否在Vercel环境
    :return: (是否允许, 错误消息, 今日已扫描次数)
    """
    if user_tier == 'super':
        # 超级用户：无限制
        return True, None, 0
    
    if user_tier == 'premium':
        # VIP用户：无限制
        return True, None, 0
    
    # 免费用户：每天只能扫描一次
    beijing_now = get_beijing_time()
    today_str = beijing_now.strftime('%Y-%m-%d')
    
    # 从存储中获取今日扫描记录
    scan_key = f'scan_count_{username}_{today_str}'
    
    try:
        if is_vercel:
            # Vercel 环境：从 Redis 读取
            try:
                import scan_progress_store
                # 尝试使用 scan_progress_store 的 Redis 功能
                if hasattr(scan_progress_store, '_upstash_redis_get'):
                    scan_count_data = scan_progress_store._upstash_redis_get(scan_key)
                    today_scan_count = int(scan_count_data) if scan_count_data else 0
                else:
                    # 直接使用 Upstash Redis REST API
                    import os
                    import requests
                    redis_url = os.environ.get('UPSTASH_REDIS_REST_URL')
                    redis_token = os.environ.get('UPSTASH_REDIS_REST_TOKEN')
                    if redis_url and redis_token:
                        response = requests.get(
                            f"{redis_url}/get/{scan_key}",
                            headers={"Authorization": f"Bearer {redis_token}"},
                            timeout=5
                        )
                        if response.status_code == 200:
                            result = response.json()
                            scan_count_data = result.get('result')
                            today_scan_count = int(scan_count_data) if scan_count_data else 0
                        else:
                            today_scan_count = 0
                    else:
                        today_scan_count = 0
            except Exception as e:
                print(f"[check_daily_scan_limit] 从 Redis 读取失败: {e}")
                today_scan_count = 0
        else:
            # 本地环境：从文件读取
            import json
            import os
            scan_limit_file = 'scan_limit.json'
            if os.path.exists(scan_limit_file):
                with open(scan_limit_file, 'r', encoding='utf-8') as f:
                    scan_limits = json.load(f)
                    today_scan_count = scan_limits.get(scan_key, 0)
            else:
                today_scan_count = 0
        
        # 免费用户每天只能扫描一次
        if today_scan_count >= 1:
            return False, f'免费用户每天只能扫描一次，今日已扫描 {today_scan_count} 次。请明天再试。', today_scan_count
        
        return True, None, today_scan_count
    except Exception as e:
        print(f"[check_daily_scan_limit] 检查扫描限制失败: {e}")
        # 出错时允许扫描（避免影响用户体验）
        return True, None, 0


def record_scan_count(username: str, is_vercel: bool = False):
    """
    记录用户今日扫描次数
    :param username: 用户名
    :param is_vercel: 是否在Vercel环境
    """
    beijing_now = get_beijing_time()
    today_str = beijing_now.strftime('%Y-%m-%d')
    scan_key = f'scan_count_{username}_{today_str}'
    
    try:
        if is_vercel:
            # Vercel 环境：保存到 Redis
            try:
                import scan_progress_store
                if hasattr(scan_progress_store, '_upstash_redis_get') and hasattr(scan_progress_store, '_upstash_redis_set'):
                    # 获取当前计数
                    current_count = scan_progress_store._upstash_redis_get(scan_key)
                    new_count = int(current_count) + 1 if current_count else 1
                    # 保存到 Redis
                    scan_progress_store._upstash_redis_set(scan_key, str(new_count))
                else:
                    # 直接使用 Upstash Redis REST API
                    import os
                    import requests
                    redis_url = os.environ.get('UPSTASH_REDIS_REST_URL')
                    redis_token = os.environ.get('UPSTASH_REDIS_REST_TOKEN')
                    if redis_url and redis_token:
                        # 获取当前计数
                        response = requests.get(
                            f"{redis_url}/get/{scan_key}",
                            headers={"Authorization": f"Bearer {redis_token}"},
                            timeout=5
                        )
                        current_count = 0
                        if response.status_code == 200:
                            result = response.json()
                            count_data = result.get('result')
                            current_count = int(count_data) if count_data else 0
                        
                        new_count = current_count + 1
                        # 保存到 Redis，TTL 设置为 25 小时（86400 + 3600 秒）
                        requests.post(
                            f"{redis_url}/setex/{scan_key}/90000/{new_count}",
                            headers={
                                "Authorization": f"Bearer {redis_token}",
                                "Content-Type": "application/json"
                            },
                            timeout=5
                        )
            except Exception as e:
                print(f"[record_scan_count] 保存到 Redis 失败: {e}")
        else:
            # 本地环境：保存到文件
            import json
            import os
            scan_limit_file = 'scan_limit.json'
            if os.path.exists(scan_limit_file):
                with open(scan_limit_file, 'r', encoding='utf-8') as f:
                    scan_limits = json.load(f)
            else:
                scan_limits = {}
            
            current_count = scan_limits.get(scan_key, 0)
            scan_limits[scan_key] = current_count + 1
            
            # 清理7天前的记录
            seven_days_ago = (beijing_now - timedelta(days=7)).strftime('%Y-%m-%d')
            keys_to_remove = [k for k in scan_limits.keys() if k.endswith(seven_days_ago)]
            for k in keys_to_remove:
                del scan_limits[k]
            
            with open(scan_limit_file, 'w', encoding='utf-8') as f:
                json.dump(scan_limits, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[record_scan_count] 记录扫描次数失败: {e}")


def check_result_view_time(user_tier: str, scan_config: Dict) -> Tuple[bool, Optional[str]]:
    """
    检查用户是否可以在当前时间查看扫描结果
    :param user_tier: 用户等级
    :param scan_config: 扫描配置
    :return: (是否允许, 错误消息)
    """
    if user_tier == 'super':
        # 超级用户：随时可以查看
        return True, None
    
    beijing_now = get_beijing_time()
    current_hour = beijing_now.hour
    current_minute = beijing_now.minute
    
    if user_tier == 'premium':
        # VIP用户：中午12点后可查看结果（系统11:30自动扫描）
        result_view_hour = scan_config.get('result_view_hour', 12)
        if current_hour < result_view_hour:
            return False, f'VIP用户可在中午{result_view_hour}点后查看结果（系统11:30自动扫描），当前时间：{beijing_now.strftime("%H:%M")}'
        return True, None
    else:
        # 免费用户：下午3:00后可查看结果（系统3:00自动扫描）
        result_view_hour = scan_config.get('result_view_hour', 15)
        result_view_minute = scan_config.get('result_view_minute', 0)
        
        current_time_minutes = current_hour * 60 + current_minute
        view_time_minutes = result_view_hour * 60 + result_view_minute
        
        if current_time_minutes < view_time_minutes:
            return False, f'免费用户可在下午{result_view_hour}:{result_view_minute:02d}后查看结果（系统{result_view_hour}:00自动扫描），当前时间：{beijing_now.strftime("%H:%M")}'
        return True, None

