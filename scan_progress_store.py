#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
扫描进度存储模块 - 使用 Upstash Redis 或 Vercel KV 存储扫描进度
支持在 Vercel serverless 环境中跨请求共享扫描状态
"""
import json
import os
from datetime import datetime
from typing import Dict, Optional, Any

# 存储后端类型
_storage_type = None

# 尝试使用 Upstash Redis（推荐，免费）
try:
    redis_url = os.environ.get('UPSTASH_REDIS_REST_URL')
    redis_token = os.environ.get('UPSTASH_REDIS_REST_TOKEN')
    if redis_url and redis_token:
        import requests
        _storage_type = 'upstash_redis'
        print("✅ 扫描进度存储: 使用 Upstash Redis")
except Exception as e:
    print(f"⚠️ Upstash Redis 不可用: {e}")

# 如果 Upstash Redis 不可用，尝试使用 Vercel KV
if not _storage_type:
    try:
        from vercel_kv import kv
        _storage_type = 'vercel_kv'
        print("✅ 扫描进度存储: 使用 Vercel KV")
    except ImportError:
        pass

# 如果都不可用，使用内存存储（仅用于测试，不推荐生产环境）
if not _storage_type:
    _storage_type = 'memory'
    _memory_storage = {}
    print("⚠️ 扫描进度存储: 使用内存存储（数据不会持久化，重启后会丢失）")


def _upstash_redis_get(key: str) -> Optional[Any]:
    """从 Upstash Redis 获取数据"""
    try:
        redis_url = os.environ.get('UPSTASH_REDIS_REST_URL')
        redis_token = os.environ.get('UPSTASH_REDIS_REST_TOKEN')
        if not redis_url or not redis_token:
            return None
        
        import requests
        # Upstash Redis REST API: GET /get/{key}
        response = requests.get(
            f"{redis_url}/get/{key}",
            headers={"Authorization": f"Bearer {redis_token}"},
            timeout=5
        )
        if response.status_code == 200:
            result = response.json()
            # Upstash 返回格式: {"result": "value"} 或 {"result": null}
            value_str = result.get('result')
            if value_str:
                # 如果 value_str 是字符串，尝试解析为 JSON
                if isinstance(value_str, str):
                    try:
                        return json.loads(value_str)
                    except (json.JSONDecodeError, TypeError):
                        # 如果不是 JSON，直接返回字符串
                        return value_str
                else:
                    # 如果已经是对象，直接返回
                    return value_str
        return None
    except Exception as e:
        print(f"⚠️ Upstash Redis GET 失败: {e}")
        import traceback
        print(traceback.format_exc())
        return None


def _upstash_redis_set(key: str, value: Any, ttl: int = 3600) -> bool:
    """保存数据到 Upstash Redis（TTL 默认1小时）"""
    try:
        redis_url = os.environ.get('UPSTASH_REDIS_REST_URL')
        redis_token = os.environ.get('UPSTASH_REDIS_REST_TOKEN')
        if not redis_url or not redis_token:
            return False
        
        import requests
        # Upstash Redis REST API: POST /setex/{key}/{ttl}
        # 请求体是 JSON 字符串（需要转义）
        value_str = json.dumps(value, default=str, ensure_ascii=False)
        # Upstash REST API 需要将值作为字符串发送
        # 注意：值需要是 JSON 字符串，但整个请求体也是 JSON
        response = requests.post(
            f"{redis_url}/setex/{key}/{ttl}",
            headers={
                "Authorization": f"Bearer {redis_token}",
                "Content-Type": "application/json"
            },
            json=value_str,  # 发送 JSON 字符串
            timeout=5
        )
        # Upstash 返回 200 表示成功
        if response.status_code == 200:
            try:
                result = response.json()
                # Upstash 返回格式: {"result": "OK"} 或 {"result": true}
                return result.get('result') == 'OK' or result.get('result') is True
            except:
                # 如果响应不是 JSON，检查状态码
                return True
        return False
    except Exception as e:
        print(f"⚠️ Upstash Redis SET 失败: {e}")
        import traceback
        print(traceback.format_exc())
        return False


def save_scan_progress(scan_id: str, progress: Dict) -> bool:
    """
    保存扫描进度
    :param scan_id: 扫描任务ID
    :param progress: 进度信息（字典）
    :return: 是否保存成功
    """
    try:
        # 添加保存时间戳
        progress['saved_at'] = datetime.now().isoformat()
        
        if _storage_type == 'upstash_redis':
            return _upstash_redis_set(f'scan_progress:{scan_id}', progress, ttl=86400)  # 24小时TTL（避免长时间扫描时数据过期）
        elif _storage_type == 'vercel_kv':
            from vercel_kv import kv
            kv.set(f'scan_progress:{scan_id}', json.dumps(progress, default=str), ex=7200)
            return True
        else:
            # 内存存储
            _memory_storage[f'scan_progress:{scan_id}'] = progress
            return True
    except Exception as e:
        print(f"保存扫描进度失败: {e}")
        return False


def get_scan_progress(scan_id: str) -> Optional[Dict]:
    """
    获取扫描进度
    :param scan_id: 扫描任务ID
    :return: 进度信息（字典），如果不存在返回None
    """
    try:
        if _storage_type == 'upstash_redis':
            return _upstash_redis_get(f'scan_progress:{scan_id}')
        elif _storage_type == 'vercel_kv':
            from vercel_kv import kv
            value = kv.get(f'scan_progress:{scan_id}')
            if value:
                return json.loads(value)
            return None
        else:
            # 内存存储
            return _memory_storage.get(f'scan_progress:{scan_id}')
    except Exception as e:
        print(f"获取扫描进度失败: {e}")
        return None


def save_scan_results(scan_id: str, results: Dict) -> bool:
    """
    保存扫描结果
    :param scan_id: 扫描任务ID
    :param results: 扫描结果（字典）
    :return: 是否保存成功
    """
    try:
        if _storage_type == 'upstash_redis':
            # 结果可能很大，使用更长的TTL（24小时）
            return _upstash_redis_set(f'scan_results:{scan_id}', results, ttl=86400)
        elif _storage_type == 'vercel_kv':
            from vercel_kv import kv
            kv.set(f'scan_results:{scan_id}', json.dumps(results, default=str), ex=86400)
            return True
        else:
            # 内存存储
            _memory_storage[f'scan_results:{scan_id}'] = results
            return True
    except Exception as e:
        print(f"保存扫描结果失败: {e}")
        return False


def get_scan_results(scan_id: str) -> Optional[Dict]:
    """
    获取扫描结果
    :param scan_id: 扫描任务ID
    :return: 扫描结果（字典），如果不存在返回None
    """
    try:
        if _storage_type == 'upstash_redis':
            return _upstash_redis_get(f'scan_results:{scan_id}')
        elif _storage_type == 'vercel_kv':
            from vercel_kv import kv
            value = kv.get(f'scan_results:{scan_id}')
            if value:
                return json.loads(value)
            return None
        else:
            # 内存存储
            return _memory_storage.get(f'scan_results:{scan_id}')
    except Exception as e:
        print(f"获取扫描结果失败: {e}")
        return None


def delete_scan_data(scan_id: str) -> bool:
    """
    删除扫描数据和结果
    :param scan_id: 扫描任务ID
    :return: 是否删除成功
    """
    try:
        if _storage_type == 'upstash_redis':
            redis_url = os.environ.get('UPSTASH_REDIS_REST_URL')
            redis_token = os.environ.get('UPSTASH_REDIS_REST_TOKEN')
            if not redis_url or not redis_token:
                return False
            
            import requests
            # 删除进度和结果
            for key in [f'scan_progress:{scan_id}', f'scan_results:{scan_id}']:
                requests.delete(
                    f"{redis_url}/del/{key}",
                    headers={"Authorization": f"Bearer {redis_token}"},
                    timeout=3
                )
            return True
        elif _storage_type == 'vercel_kv':
            from vercel_kv import kv
            kv.delete(f'scan_progress:{scan_id}')
            kv.delete(f'scan_results:{scan_id}')
            return True
        else:
            # 内存存储
            _memory_storage.pop(f'scan_progress:{scan_id}', None)
            _memory_storage.pop(f'scan_results:{scan_id}', None)
            return True
    except Exception as e:
        print(f"删除扫描数据失败: {e}")
        return False


def save_global_scan_results(scan_type: str, date_str: str, results: Dict) -> bool:
    """
    保存全局扫描结果（按扫描类型和日期）
    :param scan_type: 扫描类型 ('noon' 或 'afternoon')
    :param date_str: 日期字符串，格式: 'YYYY-MM-DD'
    :param results: 扫描结果（字典）
    :return: 是否保存成功
    """
    try:
        # 添加保存时间戳和扫描类型信息
        results['scan_type'] = scan_type
        results['date'] = date_str
        results['saved_at'] = datetime.now().isoformat()
        
        # 存储键格式: global_scan_results:{scan_type}:{date}
        key = f'global_scan_results:{scan_type}:{date_str}'
        
        if _storage_type == 'upstash_redis':
            # 全局扫描结果保存30天（2592000秒）
            return _upstash_redis_set(key, results, ttl=2592000)
        elif _storage_type == 'vercel_kv':
            from vercel_kv import kv
            kv.set(key, json.dumps(results, default=str, ensure_ascii=False), ex=2592000)
            return True
        else:
            # 内存存储
            if 'global_scan_results' not in _memory_storage:
                _memory_storage['global_scan_results'] = {}
            if scan_type not in _memory_storage['global_scan_results']:
                _memory_storage['global_scan_results'][scan_type] = {}
            _memory_storage['global_scan_results'][scan_type][date_str] = results
            return True
    except Exception as e:
        print(f"保存全局扫描结果失败: {e}")
        import traceback
        print(traceback.format_exc())
        return False


def get_global_scan_results(scan_type: str, date_str: str) -> Optional[Dict]:
    """
    获取全局扫描结果（按扫描类型和日期）
    :param scan_type: 扫描类型 ('noon' 或 'afternoon')
    :param date_str: 日期字符串，格式: 'YYYY-MM-DD'
    :return: 扫描结果（字典），如果不存在返回None
    """
    try:
        # 存储键格式: global_scan_results:{scan_type}:{date}
        key = f'global_scan_results:{scan_type}:{date_str}'
        
        if _storage_type == 'upstash_redis':
            return _upstash_redis_get(key)
        elif _storage_type == 'vercel_kv':
            from vercel_kv import kv
            value = kv.get(key)
            if value:
                return json.loads(value)
            return None
        else:
            # 内存存储
            if 'global_scan_results' not in _memory_storage:
                return None
            if scan_type not in _memory_storage['global_scan_results']:
                return None
            return _memory_storage['global_scan_results'][scan_type].get(date_str)
    except Exception as e:
        print(f"获取全局扫描结果失败: {e}")
        import traceback
        print(traceback.format_exc())
        return None


def list_global_scan_results(scan_type: str = None, limit: int = 10) -> list:
    """
    列出全局扫描结果（用于调试或管理）
    :param scan_type: 扫描类型 ('noon' 或 'afternoon')，None 表示所有类型
    :param limit: 返回数量限制
    :return: 扫描结果列表
    """
    try:
        results = []
        
        if _storage_type == 'upstash_redis':
            # Redis 中无法直接列出所有匹配的键，这里返回空列表
            # 实际使用时应该通过具体的键来获取
            return results
        elif _storage_type == 'vercel_kv':
            # Vercel KV 也不支持列出所有键，返回空列表
            return results
        else:
            # 内存存储：可以遍历所有结果
            if 'global_scan_results' not in _memory_storage:
                return results
            
            for st in (['noon', 'afternoon'] if scan_type is None else [scan_type]):
                if st in _memory_storage['global_scan_results']:
                    for date, result in _memory_storage['global_scan_results'][st].items():
                        results.append({
                            'scan_type': st,
                            'date': date,
                            'result': result
                        })
                        if len(results) >= limit:
                            break
                if len(results) >= limit:
                    break
        
        return results
    except Exception as e:
        print(f"列出全局扫描结果失败: {e}")
        return []

