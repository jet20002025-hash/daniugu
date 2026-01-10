#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Vercel 环境扫描辅助函数
用于在 Vercel serverless 环境中分批处理扫描任务
"""
import time
import json
from typing import Dict, List, Any
import pandas as pd
import scan_progress_store


def process_scan_batch_vercel(
    analyzer,
    stock_batch: pd.DataFrame,
    common_features: Dict,
    scan_id: str,
    batch_num: int,
    total_batches: int,
    total_stocks: int,
    min_match_score: float,
    max_market_cap: float,
    start_idx: int,
    existing_candidates: List[Dict],
    scan_config: Dict = None
) -> Dict:
    """
    处理一批股票的扫描（Vercel 环境）
    :param analyzer: BullStockAnalyzer 实例
    :param stock_batch: 当前批次的股票列表（DataFrame）
    :param common_features: 共同特征模板
    :param scan_id: 扫描任务ID
    :param batch_num: 当前批次号
    :param total_batches: 总批次数
    :param total_stocks: 总股票数
    :param min_match_score: 最小匹配度阈值
    :param max_market_cap: 最大市值
    :param start_idx: 起始索引（在总股票列表中的位置）
    :param existing_candidates: 已有候选股票列表
    :return: 扫描结果
    """
    # 获取扫描配置（如果未提供，使用默认值）
    if scan_config is None:
        scan_config = {
            'stock_timeout': 8,
            'batch_delay': 3
        }
    
    # 从配置获取超时时间
    max_stock_time = scan_config.get('stock_timeout', 8)
    
    batch_size = len(stock_batch)
    candidates = existing_candidates.copy() if existing_candidates else []
    
    # 获取列名
    code_col = None
    name_col = None
    for col in stock_batch.columns:
        col_lower = str(col).lower()
        if 'code' in col_lower or '代码' in col:
            code_col = col
        elif 'name' in col_lower or '名称' in col:
            name_col = col
    
    if code_col is None:
        code_col = stock_batch.columns[0]
    if name_col is None and len(stock_batch.columns) >= 2:
        name_col = stock_batch.columns[1]
    
    # 开始处理批次
    batch_start_time = time.time()
    processed_count = 0
    
    for idx, (_, row) in enumerate(stock_batch.iterrows()):
        stock_code = str(row[code_col])
        stock_name = str(row[name_col]) if name_col else stock_code
        current_idx = start_idx + idx + 1
        
        try:
            # 检查超时（根据用户等级使用不同的超时时间）
            stock_start_time = time.time()
            
            # 获取股票周线数据
            weekly_df = analyzer.fetcher.get_weekly_kline(stock_code, weeks=100)
            if weekly_df is None or len(weekly_df) < 40:
                continue
            
            # 查找买点
            for i in range(40, len(weekly_df)):
                # 检查单只股票处理时间
                if time.time() - stock_start_time > max_stock_time:
                    break
                
                try:
                    features = analyzer.extract_features_at_start_point(
                        stock_code, i, lookback_weeks=40
                    )
                    if features is None:
                        continue
                    
                    match_score = analyzer._calculate_match_score(
                        features, common_features, analyzer.tolerance
                    )
                    total_match = match_score.get('总匹配度', 0)
                    
                    if total_match >= min_match_score:
                        # 找到符合条件的买点
                        buy_date = weekly_df.iloc[i]['日期']
                        if isinstance(buy_date, pd.Timestamp):
                            buy_date_str = buy_date.strftime('%Y-%m-%d')
                        else:
                            buy_date_str = str(buy_date)
                        
                        buy_price = float(weekly_df.iloc[i]['收盘'])
                        
                        # 计算后续表现
                        gain_4w = None
                        gain_10w = None
                        max_gain_10w = None
                        gain_20w = None
                        
                        if i + 4 < len(weekly_df):
                            future_price_4w = float(weekly_df.iloc[i + 4]['收盘'])
                            gain_4w = (future_price_4w - buy_price) / buy_price * 100
                        
                        if i + 10 < len(weekly_df):
                            future_price_10w = float(weekly_df.iloc[i + 10]['收盘'])
                            gain_10w = (future_price_10w - buy_price) / buy_price * 100
                            max_price_10w = float(weekly_df.iloc[i+1:i+11]['最高'].max())
                            max_gain_10w = (max_price_10w - buy_price) / buy_price * 100
                        
                        if i + 20 < len(weekly_df):
                            future_price_20w = float(weekly_df.iloc[i + 20]['收盘'])
                            gain_20w = (future_price_20w - buy_price) / buy_price * 100
                        
                        # 计算止损和最佳卖点（简化版）
                        stop_loss_price = buy_price * 0.90  # 10%止损
                        ma20 = float(weekly_df.iloc[i]['MA20']) if 'MA20' in weekly_df.columns else buy_price
                        if ma20 > 0:
                            stop_loss_price = min(stop_loss_price, ma20 * 0.95)
                        
                        best_sell_price = None
                        best_sell_date = None
                        if i + 1 < len(weekly_df):
                            future_window = weekly_df.iloc[i+1:]
                            if len(future_window) > 0:
                                max_price_pos = future_window['最高'].values.argmax()
                                max_price = float(future_window.iloc[max_price_pos]['最高'])
                                max_date = future_window.iloc[max_price_pos]['日期']
                                if isinstance(max_date, pd.Timestamp):
                                    best_sell_date = max_date.strftime('%Y-%m-%d')
                                else:
                                    best_sell_date = str(max_date)
                                best_sell_price = max_price
                        
                        candidate = {
                            'code': stock_code,
                            'name': stock_name,
                            'buy_date': buy_date_str,
                            'buy_price': round(buy_price, 2),
                            'match_score': round(total_match, 3),
                            'gain_4w': round(gain_4w, 2) if gain_4w is not None else None,
                            'gain_10w': round(gain_10w, 2) if gain_10w is not None else None,
                            'max_gain_10w': round(max_gain_10w, 2) if max_gain_10w is not None else None,
                            'gain_20w': round(gain_20w, 2) if gain_20w is not None else None,
                            'stop_loss_price': round(stop_loss_price, 2),
                            'best_sell_price': round(best_sell_price, 2) if best_sell_price else None,
                            'best_sell_date': best_sell_date
                        }
                        
                        candidates.append(candidate)
                        break  # 找到第一个符合条件的买点就停止
                
                except Exception as e:
                    # 单只股票处理出错，继续下一个
                    continue
            
            processed_count += 1
            
            # 更新进度（每处理5只股票更新一次，避免频繁写Redis）
            if processed_count % 5 == 0 or processed_count == batch_size:
                # 计算整体进度
                overall_current = start_idx + processed_count
                percentage = (overall_current / total_stocks) * 100 if total_stocks > 0 else 0
                
                progress = {
                    'type': 'scan',
                    'scan_id': scan_id,
                    'current': overall_current,
                    'total': total_stocks,
                    'status': '进行中',
                    'detail': f'正在扫描第 {batch_num}/{total_batches} 批: {stock_code} {stock_name}... ({overall_current}/{total_stocks}) | 已找到: {len(candidates)} 只',
                    'percentage': round(percentage, 1),
                    'found': len(candidates),
                    'batch': batch_num,
                    'total_batches': total_batches,
                    'current_stock': stock_code,
                    'current_stock_name': stock_name,
                    'candidates': candidates[-10:],  # 只保存最近10只，避免数据过大
                    'last_update_time': time.time()
                }
                scan_progress_store.save_scan_progress(scan_id, progress)
        
        except Exception as e:
            # 单只股票处理出错，继续下一个
            continue
    
    # 批次处理完成
    batch_end_time = time.time()
    batch_duration = batch_end_time - batch_start_time
    
    overall_current = start_idx + batch_size
    percentage = (overall_current / total_stocks) * 100 if total_stocks > 0 else 100.0 if overall_current >= total_stocks else percentage
    
    # 判断是否完成所有批次
    is_complete = (batch_num >= total_batches)
    
    progress = {
        'type': 'scan',
        'scan_id': scan_id,
        'current': overall_current,
        'total': total_stocks,
        'status': '完成' if is_complete else '进行中',
        'detail': f'第 {batch_num}/{total_batches} 批完成，已处理 {overall_current}/{total_stocks} 只股票，找到 {len(candidates)} 只符合条件的股票' + ('（全部完成）' if is_complete else '（等待下一批）'),
        'percentage': round(percentage, 1) if not is_complete else 100.0,
        'found': len(candidates),
        'batch': batch_num,
        'total_batches': total_batches,
        'candidates': candidates[-50:],  # 保存最近50只候选股票
        'last_update_time': time.time(),
        'batch_duration': round(batch_duration, 2)
    }
    
    # 保存进度
    scan_progress_store.save_scan_progress(scan_id, progress)
    
    # 如果完成，保存最终结果
    if is_complete:
        # 获取进度信息
        progress_info = scan_progress_store.get_scan_progress(scan_id)
        is_global_scan = progress_info and progress_info.get('is_global_scan', False)
        scan_type = progress_info.get('scan_type') if progress_info else None
        scan_date = progress_info.get('scan_date') if progress_info else None
        username = progress_info.get('username', 'anonymous') if progress_info else 'anonymous'
        user_tier = progress_info.get('user_tier') if progress_info else None
        is_auto_scan = progress_info.get('is_auto_scan', False) if progress_info else False
        
        from datetime import datetime, timezone, timedelta
        beijing_tz = timezone(timedelta(hours=8))
        beijing_now = datetime.now(beijing_tz)
        current_date = beijing_now.strftime('%Y-%m-%d')
        
        results = {
            'success': True,
            'message': f'扫描完成，共找到 {len(candidates)} 只符合条件的股票',
            'candidates': candidates,
            'total_scanned': overall_current,
            'found_count': len(candidates),
            'scan_id': scan_id,
            'scan_type': scan_type,
            'scan_date': scan_date or current_date,
            'username': username,
            'user_tier': user_tier,
            'completed_at': beijing_now.strftime('%Y-%m-%d %H:%M:%S')
        }
        scan_progress_store.save_scan_results(scan_id, results)
        
        # 如果是VIP用户的手动扫描，保存到用户历史记录（7天）
        if user_tier == 'premium' and not is_auto_scan and username != 'anonymous':
            try:
                # 保存用户扫描历史（按日期和用户名）
                user_history_key = f'user_scan_history:{username}:{current_date}'
                existing_history = scan_progress_store._upstash_redis_get(user_history_key) if hasattr(scan_progress_store, '_upstash_redis_get') else None
                
                scan_ids_list = []
                if existing_history:
                    if isinstance(existing_history, list):
                        scan_ids_list = existing_history
                    elif isinstance(existing_history, str):
                        try:
                            import json
                            scan_ids_list = json.loads(existing_history)
                        except:
                            scan_ids_list = [existing_history]
                    else:
                        scan_ids_list = [existing_history]
                
                # 添加当前扫描ID（如果不存在）
                if scan_id not in scan_ids_list:
                    scan_ids_list.append(scan_id)
                    # 只保留最近10次扫描
                    scan_ids_list = scan_ids_list[-10:]
                    
                    # 保存回Redis（TTL 7天 = 604800秒）
                    if hasattr(scan_progress_store, '_upstash_redis_set'):
                        scan_progress_store._upstash_redis_set(user_history_key, json.dumps(scan_ids_list, ensure_ascii=False), ttl=604800)
                        print(f"[vercel_scan_helper] ✅ VIP用户扫描历史已保存 - 用户: {username}, 日期: {current_date}, 扫描ID: {scan_id}")
            except Exception as e:
                print(f"[vercel_scan_helper] ⚠️ 保存VIP用户扫描历史失败: {e}")
        
        # 如果是全局扫描，保存到全局扫描结果存储（按类型和日期）
        if is_global_scan and scan_type and scan_date:
            scan_time_display = '11:30' if scan_type == 'noon' else '15:00'
            
            global_results = {
                'success': True,
                'message': f'扫描完成，共找到 {len(candidates)} 只符合条件的股票',
                'candidates': candidates,
                'total_scanned': overall_current,
                'found_count': len(candidates),
                'scan_id': scan_id,
                'scan_type': scan_type,
                'scan_date': scan_date,
                'scan_time': scan_time_display,  # 显示时间（11:30 或 15:00）
                'completed_at': beijing_now.strftime('%Y-%m-%d %H:%M:%S')
            }
            scan_progress_store.save_global_scan_results(scan_type, scan_date, global_results)
            print(f"[vercel_scan_helper] ✅ 全局扫描结果已保存 - 类型: {scan_type}, 日期: {scan_date}, 扫描时间: {scan_time_display}")
    
    return {
        'success': True,
        'progress': progress,
        'candidates': candidates,
        'batch': batch_num,
        'is_complete': is_complete,
        'has_more': not is_complete
    }

