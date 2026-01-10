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
        stock_code_raw = str(row[code_col])
        stock_name = str(row[name_col]) if name_col else stock_code_raw
        current_idx = start_idx + idx + 1
        
        # 处理股票代码格式：akshare 需要纯数字代码，去除 .SZ 或 .SH 后缀和其他字符
        # 例如：'603597.SH' -> '603597'，'000001.SZ' -> '000001'，'603597.SH ' -> '603597'
        import re
        stock_code = re.sub(r'\.(SZ|SH|sz|sh)$', '', stock_code_raw).strip()
        # 只保留数字部分（6位数字）
        stock_code = re.sub(r'[^0-9]', '', stock_code)
        
        # 特殊处理：煜邦电力 603597（用于调试和分析）
        is_target_stock = (stock_code == '603597')
        if is_target_stock:
            print(f"[vercel_scan_helper] 🔍 ========== 开始处理煜邦电力 ==========")
            print(f"[vercel_scan_helper] 🔍 原始代码: {stock_code_raw}")
            print(f"[vercel_scan_helper] 🔍 处理后的代码: {stock_code}")
            print(f"[vercel_scan_helper] 🔍 股票名称: {stock_name}")
        
        # 验证股票代码格式（应该是6位数字）
        if not stock_code or len(stock_code) != 6 or not stock_code.isdigit():
            if is_target_stock:
                print(f"[vercel_scan_helper] ❌ 煜邦电力股票代码格式错误: {stock_code}（原始: {stock_code_raw}）")
            continue
        
        try:
            # 检查超时（根据用户等级使用不同的超时时间）
            stock_start_time = time.time()
            
            # 获取股票周线数据（添加超时机制和详细日志）
            # 修复：get_weekly_kline 的参数是 period，不是 weeks
            # 在 Vercel 环境中，使用超时机制避免阻塞
            weekly_df = None
            weekly_df_error = None
            
            try:
                import threading
                weekly_df_result = [None]
                weekly_df_error_result = [None]
                
                def fetch_weekly_data():
                    try:
                        if is_target_stock:
                            print(f"[vercel_scan_helper] 🔍 煜邦电力：开始调用 get_weekly_kline，参数: period='2y'")
                        # 修复参数：使用 period="2y" 而不是 weeks=100
                        weekly_df_result[0] = analyzer.fetcher.get_weekly_kline(stock_code, period="2y")
                        if is_target_stock:
                            print(f"[vercel_scan_helper] 🔍 煜邦电力：get_weekly_kline 返回结果: {weekly_df_result[0] is not None}, 长度: {len(weekly_df_result[0]) if weekly_df_result[0] is not None else 0}")
                    except Exception as e:
                        weekly_df_error_result[0] = e
                        import traceback
                        error_detail = traceback.format_exc()
                        if is_target_stock:
                            print(f"[vercel_scan_helper] 🔍 煜邦电力：获取周K线数据异常: {e}")
                            print(f"[vercel_scan_helper] 🔍 煜邦电力：错误详情: {error_detail}")
                        else:
                            print(f"[vercel_scan_helper] {stock_code} ({stock_name}) 获取周K线数据异常: {e}")
                
                fetch_thread = threading.Thread(target=fetch_weekly_data)
                fetch_thread.daemon = True
                fetch_thread.start()
                fetch_thread.join(timeout=5)  # 最多等待5秒，留出时间给后续处理
                
                if fetch_thread.is_alive():
                    # 线程仍在运行，说明超时了
                    elapsed = time.time() - stock_start_time
                    if is_target_stock:
                        print(f"[vercel_scan_helper] ❌ 煜邦电力：周K线数据获取超时（>{elapsed:.1f}秒），可能原因：akshare API 响应慢或网络问题")
                    else:
                        print(f"[vercel_scan_helper] ⏱️ {stock_code} ({stock_name}) 周K线数据获取超时（>{elapsed:.1f}秒），跳过")
                    continue
                
                if weekly_df_error_result[0]:
                    weekly_df_error = weekly_df_error_result[0]
                    if is_target_stock:
                        print(f"[vercel_scan_helper] ❌ 煜邦电力：获取周K线数据失败: {weekly_df_error}")
                        print(f"[vercel_scan_helper] ❌ 可能原因：1) akshare API 错误 2) 股票代码格式问题 3) 网络连接问题")
                    else:
                        print(f"[vercel_scan_helper] ❌ {stock_code} ({stock_name}) 获取周K线数据失败: {weekly_df_error}")
                    continue
                
                weekly_df = weekly_df_result[0]
            except Exception as e:
                import traceback
                error_detail = traceback.format_exc()
                if is_target_stock:
                    print(f"[vercel_scan_helper] ❌ 煜邦电力：获取周K线数据时发生异常: {e}")
                    print(f"[vercel_scan_helper] ❌ 异常详情: {error_detail}")
                else:
                    print(f"[vercel_scan_helper] ❌ {stock_code} ({stock_name}) 获取周K线数据时发生异常: {e}")
                continue
            
            if weekly_df is None or len(weekly_df) < 40:
                if is_target_stock:
                    if weekly_df is None:
                        print(f"[vercel_scan_helper] ❌ 煜邦电力：周K线数据为 None，可能原因：1) akshare API 返回空数据 2) 股票代码不存在 3) API 调用失败")
                    elif len(weekly_df) < 40:
                        print(f"[vercel_scan_helper] ❌ 煜邦电力：周K线数据不足40条（只有 {len(weekly_df)} 条），需要至少40条用于特征分析")
                else:
                    if weekly_df is None:
                        print(f"[vercel_scan_helper] ⚠️ {stock_code} ({stock_name}) 周K线数据为 None，跳过")
                    elif len(weekly_df) < 40:
                        print(f"[vercel_scan_helper] ⚠️ {stock_code} ({stock_name}) 周K线数据不足40条（只有 {len(weekly_df)} 条），跳过")
                continue
            
            if is_target_stock:
                print(f"[vercel_scan_helper] ✅ 煜邦电力：成功获取 {len(weekly_df)} 条周K线数据，继续处理...")
            
            # 查找买点
            found_buy_point = False
            for i in range(40, len(weekly_df)):
                # 检查单只股票处理时间
                if time.time() - stock_start_time > max_stock_time:
                    if is_target_stock and not found_buy_point:
                        print(f"[vercel_scan_helper] ⚠️ 煜邦电力：单只股票处理时间超过限制（{max_stock_time}秒），停止查找买点")
                    break
                
                try:
                    if is_target_stock and i == 40:
                        print(f"[vercel_scan_helper] 🔍 煜邦电力：开始提取特征（起点索引: {i}, 回看周数: 40）")
                    
                    features = analyzer.extract_features_at_start_point(
                        stock_code, i, lookback_weeks=40
                    )
                    if features is None:
                        if is_target_stock and i == 40:
                            print(f"[vercel_scan_helper] ⚠️ 煜邦电力：特征提取返回 None，可能原因：数据不足或提取失败")
                        continue
                    
                    if is_target_stock and i == 40:
                        print(f"[vercel_scan_helper] 🔍 煜邦电力：特征提取成功，特征数量: {len(features) if features else 0}")
                    
                    match_score = analyzer._calculate_match_score(
                        features, common_features, analyzer.tolerance
                    )
                    total_match = match_score.get('总匹配度', 0)
                    
                    if is_target_stock and i == 40:
                        print(f"[vercel_scan_helper] 🔍 煜邦电力：匹配度计算结果: {total_match:.4f} (阈值: {min_match_score})")
                        print(f"[vercel_scan_helper] 🔍 煜邦电力：{'✅ 匹配度符合条件' if total_match >= min_match_score else '❌ 匹配度不符合条件（需要 >= ' + str(min_match_score) + '）'}")
                    
                    if total_match >= min_match_score:
                        found_buy_point = True
                        # 匹配度符合条件，检查市值（如果市值获取失败，则跳过市值检查）
                        market_cap = None
                        market_cap_valid = False
                        
                        # 尝试获取市值（使用超时机制，避免阻塞）
                        try:
                            import threading
                            market_cap_result = [None]
                            
                            def fetch_market_cap():
                                try:
                                    market_cap_result[0] = analyzer.fetcher.get_market_cap(stock_code, timeout=2)
                                except Exception:
                                    pass  # 静默失败
                            
                            cap_thread = threading.Thread(target=fetch_market_cap)
                            cap_thread.daemon = True
                            cap_thread.start()
                            cap_thread.join(timeout=2.5)  # 最多等待2.5秒
                            
                            if not cap_thread.is_alive():
                                market_cap = market_cap_result[0]
                                if market_cap is not None and market_cap > 0:
                                    market_cap_valid = True
                                    # 如果市值获取成功，检查是否符合条件
                                    if is_target_stock:
                                        print(f"[vercel_scan_helper] 🔍 煜邦电力：市值获取成功: {market_cap:.2f} 亿元 (限制: {max_market_cap} 亿元)")
                                    if market_cap > max_market_cap:
                                        # 市值超过限制，跳过该股票
                                        if is_target_stock:
                                            print(f"[vercel_scan_helper] ❌ 煜邦电力：市值 {market_cap:.2f} 亿元超过限制 {max_market_cap} 亿元，被过滤掉")
                                        continue
                                    elif is_target_stock:
                                        print(f"[vercel_scan_helper] ✅ 煜邦电力：市值 {market_cap:.2f} 亿元符合条件（<= {max_market_cap} 亿元）")
                                elif is_target_stock:
                                    print(f"[vercel_scan_helper] ⚠️ 煜邦电力：市值获取返回 None 或 0，跳过市值检查")
                            elif is_target_stock:
                                print(f"[vercel_scan_helper] ⚠️ 煜邦电力：市值获取超时（2.5秒），跳过市值检查")
                        except Exception as e:
                            # 市值获取失败，跳过市值检查，继续处理该股票
                            if is_target_stock:
                                print(f"[vercel_scan_helper] ⚠️ 煜邦电力：市值获取异常，跳过市值检查: {e}")
                            pass
                        
                        # 市值检查通过（或市值获取失败，跳过检查），记录该股票
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
                            'best_sell_date': best_sell_date,
                            'market_cap': round(market_cap, 2) if market_cap_valid else None
                        }
                        
                        candidates.append(candidate)
                        if is_target_stock:
                            print(f"[vercel_scan_helper] ✅ 煜邦电力：成功找到符合条件的买点！")
                            print(f"[vercel_scan_helper] ✅ 买点日期: {buy_date_str}, 买点价格: {buy_price:.2f}, 匹配度: {total_match:.4f}, 市值: {market_cap:.2f}亿元" if market_cap_valid else f"[vercel_scan_helper] ✅ 买点日期: {buy_date_str}, 买点价格: {buy_price:.2f}, 匹配度: {total_match:.4f}, 市值: 未知")
                        break  # 找到第一个符合条件的买点就停止
                
                except Exception as e:
                    # 单只股票处理出错，继续下一个
                    if is_target_stock:
                        import traceback
                        print(f"[vercel_scan_helper] ❌ 煜邦电力：处理买点时发生异常: {e}")
                        print(f"[vercel_scan_helper] ❌ 异常详情: {traceback.format_exc()}")
                    continue
            
            # 检查煜邦电力是否找到符合条件的买点
            if is_target_stock and not found_buy_point:
                print(f"[vercel_scan_helper] ❌ 煜邦电力：遍历完所有买点，未找到符合条件的买点")
                print(f"[vercel_scan_helper] ❌ 可能原因：1) 匹配度不够（需要 >= {min_match_score}） 2) 市值超过限制（限制: {max_market_cap} 亿元） 3) 数据质量问题")
            
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
                    
                    # 保存回Redis（TTL 30天 = 2592000秒）
                    if hasattr(scan_progress_store, '_upstash_redis_set'):
                        scan_progress_store._upstash_redis_set(user_history_key, json.dumps(scan_ids_list, ensure_ascii=False), ttl=2592000)
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

