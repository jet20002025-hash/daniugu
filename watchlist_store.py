#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
关注列表和价格预警存储模块
使用 Upstash Redis 或 Vercel KV 存储用户关注列表和价格预警
"""
import json
import os
from datetime import datetime
from typing import Dict, List, Optional, Any

# 复用 scan_progress_store 的存储后端
from scan_progress_store import _upstash_redis_get, _upstash_redis_set, _storage_type

# 内存存储（如果Redis不可用）
_memory_watchlist = {}
_memory_alerts = {}


def save_watchlist(username: str, watchlist: List[Dict]) -> bool:
    """
    保存用户关注列表
    :param username: 用户名
    :param watchlist: 关注列表（最多50只股票）
    :return: 是否保存成功
    """
    try:
        # 限制最多50只股票
        if len(watchlist) > 50:
            watchlist = watchlist[:50]
        
        key = f'watchlist:{username}'
        
        if _storage_type == 'upstash_redis':
            # 保存到 Redis，TTL 90天
            return _upstash_redis_set(key, watchlist, ttl=7776000)
        elif _storage_type == 'vercel_kv':
            from vercel_kv import kv
            kv.set(key, json.dumps(watchlist, default=str, ensure_ascii=False), ex=7776000)
            return True
        else:
            # 内存存储
            _memory_watchlist[username] = watchlist
            return True
    except Exception as e:
        print(f"保存关注列表失败: {e}")
        import traceback
        print(traceback.format_exc())
        return False


def get_watchlist(username: str) -> List[Dict]:
    """
    获取用户关注列表
    :param username: 用户名
    :return: 关注列表
    """
    try:
        key = f'watchlist:{username}'
        
        if _storage_type == 'upstash_redis':
            data = _upstash_redis_get(key)
            if data:
                return data if isinstance(data, list) else []
            return []
        elif _storage_type == 'vercel_kv':
            from vercel_kv import kv
            value = kv.get(key)
            if value:
                return json.loads(value) if isinstance(value, str) else value
            return []
        else:
            # 内存存储
            return _memory_watchlist.get(username, [])
    except Exception as e:
        print(f"获取关注列表失败: {e}")
        return []


def add_to_watchlist(username: str, stock_info: Dict) -> bool:
    """
    添加到关注列表
    :param username: 用户名
    :param stock_info: 股票信息（包含股票代码、名称、买点价格等）
    :return: 是否添加成功
    """
    try:
        watchlist = get_watchlist(username)
        
        # 检查是否已存在
        stock_code = stock_info.get('stock_code') or stock_info.get('code') or stock_info.get('股票代码')
        if stock_code:
            # 检查是否已在关注列表中
            for item in watchlist:
                if item.get('stock_code') == stock_code or item.get('code') == stock_code or item.get('股票代码') == stock_code:
                    return False  # 已存在
        
        # 限制最多50只股票
        if len(watchlist) >= 50:
            return False  # 已达到上限
        
        # 添加时间戳
        stock_info['added_at'] = datetime.now().isoformat()
        
        # 规范化股票信息
        normalized_info = {
            'stock_code': stock_code or stock_info.get('code') or stock_info.get('股票代码'),
            'stock_name': stock_info.get('stock_name') or stock_info.get('name') or stock_info.get('股票名称'),
            'buy_price': stock_info.get('buy_price') or stock_info.get('最佳买点价格'),
            'buy_date': stock_info.get('buy_date') or stock_info.get('最佳买点日期'),
            'match_score': stock_info.get('match_score') or stock_info.get('匹配度'),
            'current_price': stock_info.get('current_price') or stock_info.get('当前价格'),
            'market_cap': stock_info.get('market_cap') or stock_info.get('市值'),
            'added_at': stock_info.get('added_at')
        }
        
        watchlist.append(normalized_info)
        return save_watchlist(username, watchlist)
    except Exception as e:
        print(f"添加到关注列表失败: {e}")
        import traceback
        print(traceback.format_exc())
        return False


def remove_from_watchlist(username: str, stock_code: str) -> bool:
    """
    从关注列表删除
    :param username: 用户名
    :param stock_code: 股票代码
    :return: 是否删除成功
    """
    try:
        watchlist = get_watchlist(username)
        
        # 过滤掉指定的股票
        watchlist = [
            item for item in watchlist
            if item.get('stock_code') != stock_code and item.get('code') != stock_code and item.get('股票代码') != stock_code
        ]
        
        return save_watchlist(username, watchlist)
    except Exception as e:
        print(f"从关注列表删除失败: {e}")
        return False


def save_price_alert(username: str, alert_info: Dict) -> bool:
    """
    保存价格预警
    :param username: 用户名
    :param alert_info: 预警信息（包含股票代码、价格上限/下限等）
    :return: 是否保存成功
    """
    try:
        key = f'price_alert:{username}'
        
        # 获取现有预警列表
        alerts = get_price_alerts(username)
        
        # 检查是否已存在该股票的预警
        stock_code = alert_info.get('stock_code')
        if stock_code:
            alerts = [a for a in alerts if a.get('stock_code') != stock_code]
        
        # 添加预警信息
        alert_info['created_at'] = datetime.now().isoformat()
        alert_info['triggered'] = False
        alert_info['triggered_at'] = None
        alerts.append(alert_info)
        
        if _storage_type == 'upstash_redis':
            # 保存到 Redis，TTL 90天
            return _upstash_redis_set(key, alerts, ttl=7776000)
        elif _storage_type == 'vercel_kv':
            from vercel_kv import kv
            kv.set(key, json.dumps(alerts, default=str, ensure_ascii=False), ex=7776000)
            return True
        else:
            # 内存存储
            _memory_alerts[username] = alerts
            return True
    except Exception as e:
        print(f"保存价格预警失败: {e}")
        import traceback
        print(traceback.format_exc())
        return False


def get_price_alerts(username: str) -> List[Dict]:
    """
    获取用户价格预警列表
    :param username: 用户名
    :return: 价格预警列表
    """
    try:
        key = f'price_alert:{username}'
        
        if _storage_type == 'upstash_redis':
            data = _upstash_redis_get(key)
            if data:
                return data if isinstance(data, list) else []
            return []
        elif _storage_type == 'vercel_kv':
            from vercel_kv import kv
            value = kv.get(key)
            if value:
                return json.loads(value) if isinstance(value, str) else value
            return []
        else:
            # 内存存储
            return _memory_alerts.get(username, [])
    except Exception as e:
        print(f"获取价格预警失败: {e}")
        return []


def remove_price_alert(username: str, stock_code: str) -> bool:
    """
    删除价格预警
    :param username: 用户名
    :param stock_code: 股票代码
    :return: 是否删除成功
    """
    try:
        key = f'price_alert:{username}'
        alerts = get_price_alerts(username)
        
        # 过滤掉指定的预警
        alerts = [a for a in alerts if a.get('stock_code') != stock_code]
        
        if _storage_type == 'upstash_redis':
            return _upstash_redis_set(key, alerts, ttl=7776000)
        elif _storage_type == 'vercel_kv':
            from vercel_kv import kv
            kv.set(key, json.dumps(alerts, default=str, ensure_ascii=False), ex=7776000)
            return True
        else:
            # 内存存储
            _memory_alerts[username] = alerts
            return True
    except Exception as e:
        print(f"删除价格预警失败: {e}")
        return False


def update_price_alert_triggered(username: str, stock_code: str, current_price: float) -> bool:
    """
    更新价格预警触发状态
    :param username: 用户名
    :param stock_code: 股票代码
    :param current_price: 当前价格
    :return: 是否更新成功
    """
    try:
        alerts = get_price_alerts(username)
        updated = False
        
        for alert in alerts:
            if alert.get('stock_code') == stock_code and not alert.get('triggered'):
                price_high = alert.get('price_high')
                price_low = alert.get('price_low')
                
                # 检查是否触发预警
                triggered = False
                if price_high and current_price >= price_high:
                    triggered = True
                    alert['trigger_type'] = 'high'
                    alert['trigger_price'] = current_price
                elif price_low and current_price <= price_low:
                    triggered = True
                    alert['trigger_type'] = 'low'
                    alert['trigger_price'] = current_price
                
                if triggered:
                    alert['triggered'] = True
                    alert['triggered_at'] = datetime.now().isoformat()
                    updated = True
        
        if updated:
            key = f'price_alert:{username}'
            if _storage_type == 'upstash_redis':
                return _upstash_redis_set(key, alerts, ttl=7776000)
            elif _storage_type == 'vercel_kv':
                from vercel_kv import kv
                kv.set(key, json.dumps(alerts, default=str, ensure_ascii=False), ex=7776000)
                return True
            else:
                _memory_alerts[username] = alerts
                return True
        
        return True
    except Exception as e:
        print(f"更新价格预警触发状态失败: {e}")
        return False

