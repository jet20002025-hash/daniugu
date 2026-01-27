#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
腾讯实时行情接口（批量支持）
用于盘中扫描当天数据时，从腾讯获取实时价格
"""
import requests
import pandas as pd
from typing import List, Dict, Optional, Tuple

def _format_code_for_tencent(code: str) -> str:
    """将股票代码转换为腾讯格式"""
    code = str(code).strip()
    if code.startswith('6'):
        return f'sh{code}'
    else:
        return f'sz{code}'

def get_tencent_realtime_batch(codes: List[str], timeout: int = 5) -> Dict[str, Dict]:
    """
    批量获取腾讯实时行情（支持多只股票一次请求）
    
    :param codes: 股票代码列表，如 ['000001', '600519', '000858']
    :param timeout: 超时时间（秒），默认 5 秒
    :return: 字典，key 为股票代码，value 为行情数据字典
             格式: {
                 '000001': {
                     'code': '000001',
                     'name': '平安银行',
                     'price': 12.34,  # 现价
                     'change': 0.12,  # 涨跌额
                     'change_pct': 0.98,  # 涨跌幅（%）
                     'volume': 12345678,  # 成交量
                     'amount': 123456789,  # 成交额
                     'high': 12.50,  # 最高
                     'low': 12.20,  # 最低
                     'open': 12.30,  # 开盘
                     'yesterday_close': 12.22,  # 昨收
                     'time': '20260127 14:30:00'  # 时间
                 },
                 ...
             }
    """
    if not codes:
        return {}
    
    try:
        # 转换为腾讯格式
        symbols = [(_format_code_for_tencent(code), code) for code in codes]
        symbol_str = ','.join([s[0] for s in symbols])
        
        url = f'http://qt.gtimg.cn/q={symbol_str}'
        
        session = requests.Session()
        session.trust_env = False
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })
        
        resp = session.get(url, timeout=timeout)
        if resp.status_code != 200:
            return {}
        
        text = resp.text.strip()
        if not text:
            return {}
        
        result = {}
        
        # 解析返回数据（每只股票一行）
        lines = text.split('\n')
        for line in lines:
            if '=' not in line:
                continue
            
            try:
                # 格式: v_sz000001="1~平安银行~000001~12.34~12.22~12.50~12.20~12345678~123456789~0.12~0.98~..."
                parts = line.split('=', 1)
                if len(parts) != 2:
                    continue
                
                var_name = parts[0].strip()
                data_str = parts[1].strip().strip(';').strip('"')
                data_parts = data_str.split('~')
                
                if len(data_parts) < 32:
                    continue
                
                # 提取股票代码（从变量名或数据中）
                code = None
                for s in symbols:
                    if s[0] in var_name:
                        code = s[1]
                        break
                
                if not code:
                    # 从数据中提取（第3个字段通常是代码）
                    if len(data_parts) > 2:
                        code = data_parts[2].strip()
                
                if not code:
                    continue
                
                # 解析数据字段（腾讯接口返回 49 个字段，用 ~ 分隔）
                # 字段索引参考：
                # 0: 未知
                # 1: 股票名称
                # 2: 股票代码
                # 3: 现价
                # 4: 昨收
                # 5: 开盘
                # 6: 最高
                # 7: 最低
                # 8: 成交量
                # 9: 成交额
                # 10: 买一
                # 11: 买一量
                # ... 更多字段
                # 31: 时间（格式：20260127143000）
                
                try:
                    name = data_parts[1] if len(data_parts) > 1 else code
                    price = float(data_parts[3]) if len(data_parts) > 3 and data_parts[3] else None
                    yesterday_close = float(data_parts[4]) if len(data_parts) > 4 and data_parts[4] else None
                    open_price = float(data_parts[5]) if len(data_parts) > 5 and data_parts[5] else None
                    high = float(data_parts[6]) if len(data_parts) > 6 and data_parts[6] else None
                    low = float(data_parts[7]) if len(data_parts) > 7 and data_parts[7] else None
                    volume = int(float(data_parts[8])) if len(data_parts) > 8 and data_parts[8] else 0
                    amount = float(data_parts[9]) if len(data_parts) > 9 and data_parts[9] else 0
                    time_str = data_parts[31] if len(data_parts) > 31 else None
                    
                    # 计算涨跌额和涨跌幅
                    change = None
                    change_pct = None
                    if price is not None and yesterday_close is not None and yesterday_close > 0:
                        change = price - yesterday_close
                        change_pct = (change / yesterday_close) * 100
                    
                    # 格式化时间
                    formatted_time = None
                    if time_str and len(time_str) == 14:
                        formatted_time = f"{time_str[:4]}-{time_str[4:6]}-{time_str[6:8]} {time_str[8:10]}:{time_str[10:12]}:{time_str[12:14]}"
                    
                    result[code] = {
                        'code': code,
                        'name': name,
                        'price': price,
                        'change': change,
                        'change_pct': change_pct,
                        'volume': volume,
                        'amount': amount,
                        'high': high,
                        'low': low,
                        'open': open_price,
                        'yesterday_close': yesterday_close,
                        'time': formatted_time
                    }
                except (ValueError, IndexError) as e:
                    print(f"[get_tencent_realtime_batch] 解析 {code} 数据失败: {e}")
                    continue
                    
            except Exception as e:
                print(f"[get_tencent_realtime_batch] 解析行失败: {e}")
                continue
        
        return result
        
    except requests.exceptions.Timeout:
        print(f"[get_tencent_realtime_batch] 请求超时（{timeout}秒）")
        return {}
    except Exception as e:
        print(f"[get_tencent_realtime_batch] 获取实时行情失败: {e}")
        return {}

def get_tencent_today_kline(code: str, timeout: int = 5) -> Optional[pd.DataFrame]:
    """
    从腾讯获取今天的 K 线数据（用于盘中扫描）
    
    :param code: 股票代码
    :param timeout: 超时时间（秒）
    :return: DataFrame 包含今天的 K 线数据，格式与本地缓存一致
    """
    try:
        batch_result = get_tencent_realtime_batch([code], timeout=timeout)
        if code not in batch_result:
            return None
        
        data = batch_result[code]
        
        # 获取今天的日期
        from datetime import datetime
        today = datetime.now().strftime('%Y-%m-%d')
        
        # 构建今天的 K 线数据
        # 注意：腾讯实时接口只返回当前价格，不返回完整的 K 线
        # 我们使用：开盘、最高、最低、现价（作为收盘）、成交量
        if data['open'] is None or data['price'] is None:
            return None
        
        # 使用现价作为收盘价，开盘价作为开盘，最高/最低使用实时数据
        # 如果最高/最低为空，使用开盘和现价估算
        high = data['high'] if data['high'] is not None else max(data['open'], data['price'])
        low = data['low'] if data['low'] is not None else min(data['open'], data['price'])
        
        df = pd.DataFrame([{
            '日期': today,
            '开盘': data['open'],
            '收盘': data['price'],
            '最高': high,
            '最低': low,
            '成交量': data['volume'] if data['volume'] else 0
        }])
        
        return df
        
    except Exception as e:
        print(f"[get_tencent_today_kline] 获取 {code} 今天 K 线失败: {e}")
        return None
