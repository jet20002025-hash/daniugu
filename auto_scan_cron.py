#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自动扫描定时任务
用于Vercel Cron Jobs或外部定时服务调用
"""
import os
import sys
import json
import time
from datetime import datetime, timezone, timedelta

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def get_beijing_time():
    """获取北京时间（UTC+8）"""
    utc_now = datetime.now(timezone.utc)
    beijing_tz = timezone(timedelta(hours=8))
    beijing_now = utc_now.astimezone(beijing_tz)
    return beijing_now

def trigger_auto_scan(user_tier: str = 'free'):
    """
    触发自动扫描
    :param user_tier: 用户等级 ('free' 或 'premium')
    """
    try:
        # 导入必要的模块
        from bull_stock_web import init_analyzer, analyzer, is_vercel
        from scan_limit_helper import get_beijing_time
        
        beijing_now = get_beijing_time()
        print(f"[auto_scan_cron] 开始自动扫描任务 - 用户等级: {user_tier}, 时间: {beijing_now.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # 初始化分析器
        init_analyzer()
        
        if analyzer is None:
            print("[auto_scan_cron] ❌ 分析器初始化失败")
            return False
        
        # 获取扫描配置
        from bull_stock_web import get_scan_config
        scan_config = get_scan_config()
        
        # 设置扫描参数
        min_match_score = 0.93  # 默认匹配度
        max_market_cap = 100.0  # 默认最大市值100亿
        
        if is_vercel:
            # Vercel 环境：使用分批扫描
            import uuid
            import scan_progress_store
            
            # 生成扫描任务ID（使用系统用户标识）
            timestamp = int(time.time())
            unique_id = str(uuid.uuid4())[:8]
            scan_id = f"auto_{user_tier}_{timestamp}_{unique_id}"
            
            print(f"[auto_scan_cron] 生成扫描任务ID: {scan_id}")
            
            # 获取股票列表
            if not hasattr(analyzer, 'fetcher') or analyzer.fetcher is None:
                print("[auto_scan_cron] ❌ 数据获取器未初始化")
                return False
            
            try:
                stock_list = analyzer.fetcher.get_all_stocks(timeout=15, max_retries=3)
                if stock_list is None or len(stock_list) == 0:
                    print("[auto_scan_cron] ❌ 无法获取股票列表")
                    return False
            except Exception as e:
                print(f"[auto_scan_cron] ❌ 获取股票列表失败: {e}")
                return False
            
            total_stocks = len(stock_list)
            batch_size = scan_config['batch_size']
            total_batches = (total_stocks + batch_size - 1) // batch_size
            
            # 初始化扫描进度
            initial_progress = {
                'type': 'scan',
                'scan_id': scan_id,
                'username': f'auto_{user_tier}',  # 系统自动扫描用户
                'current': 0,
                'total': total_stocks,
                'status': '准备中',
                'detail': f'自动扫描任务 - 准备扫描 {total_stocks} 只股票（分 {total_batches} 批）...',
                'percentage': 0,
                'found': 0,
                'batch': 0,
                'total_batches': total_batches,
                'min_match_score': min_match_score,
                'max_market_cap': max_market_cap,
                'candidates': [],
                'start_time': time.time(),
                'is_auto_scan': True,  # 标记为自动扫描
                'user_tier': user_tier
            }
            scan_progress_store.save_scan_progress(scan_id, initial_progress)
            
            # 处理第一批
            try:
                if analyzer.trained_features is None:
                    print("[auto_scan_cron] ❌ 尚未训练特征模型")
                    return False
                
                from vercel_scan_helper import process_scan_batch_vercel
                
                common_features = analyzer.trained_features.get('common_features', {})
                if len(common_features) == 0:
                    print("[auto_scan_cron] ❌ 特征模板为空")
                    return False
                
                # 处理第一批
                first_batch = stock_list.head(batch_size)
                candidates = []
                
                process_scan_batch_vercel(
                    analyzer=analyzer,
                    stock_batch=first_batch,
                    common_features=common_features,
                    scan_id=scan_id,
                    batch_num=1,
                    total_batches=total_batches,
                    total_stocks=total_stocks,
                    min_match_score=min_match_score,
                    max_market_cap=max_market_cap,
                    start_idx=0,
                    existing_candidates=candidates,
                    scan_config=scan_config
                )
                
                print(f"[auto_scan_cron] ✅ 第一批处理完成，任务ID: {scan_id}")
                print(f"[auto_scan_cron] 后续批次将由前端自动继续处理")
                
                return True
            except Exception as e:
                import traceback
                error_detail = traceback.format_exc()
                print(f"[auto_scan_cron] ❌ 处理第一批失败: {error_detail}")
                
                error_progress = initial_progress.copy()
                error_progress.update({
                    'status': '失败',
                    'detail': f'自动扫描启动失败: {str(e)}',
                    'error': error_detail
                })
                scan_progress_store.save_scan_progress(scan_id, error_progress)
                return False
        else:
            # 本地环境：使用传统扫描方式
            print("[auto_scan_cron] 本地环境：使用传统扫描方式")
            # 这里可以调用 analyzer.scan_all_stocks() 等方法
            return True
            
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"[auto_scan_cron] ❌ 自动扫描任务失败: {error_detail}")
        return False

def trigger_auto_scan_by_type(scan_type: str):
    """
    按扫描类型触发自动扫描（用于定时任务）
    :param scan_type: 扫描类型 ('noon' 或 'afternoon')
    """
    try:
        beijing_now = get_beijing_time()
        date_str = beijing_now.strftime('%Y-%m-%d')
        
        print(f"[auto_scan_cron] 开始按类型自动扫描 - 类型: {scan_type}, 日期: {date_str}, 时间: {beijing_now.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # 导入必要的模块
        from bull_stock_web import init_analyzer, analyzer, is_vercel
        from scan_limit_helper import get_beijing_time as get_bj_time
        
        # 初始化分析器
        init_analyzer()
        
        if analyzer is None:
            print("[auto_scan_cron] ❌ 分析器初始化失败")
            return False
        
        # 获取扫描配置
        from bull_stock_web import get_scan_config
        scan_config = get_scan_config()
        
        # 设置扫描参数
        min_match_score = 0.93  # 默认匹配度
        max_market_cap = 100.0  # 默认最大市值100亿
        
        if is_vercel:
            # Vercel 环境：使用分批扫描
            import uuid
            import scan_progress_store
            
            # 生成扫描任务ID（使用扫描类型和日期）
            timestamp = int(time.time())
            unique_id = str(uuid.uuid4())[:8]
            scan_id = f"auto_{scan_type}_{date_str}_{timestamp}_{unique_id}"
            
            print(f"[auto_scan_cron] 生成扫描任务ID: {scan_id}")
            
            # 获取股票列表
            if not hasattr(analyzer, 'fetcher') or analyzer.fetcher is None:
                print("[auto_scan_cron] ❌ 数据获取器未初始化")
                return False
            
            try:
                stock_list = analyzer.fetcher.get_all_stocks(timeout=15, max_retries=3)
                if stock_list is None or len(stock_list) == 0:
                    print("[auto_scan_cron] ❌ 无法获取股票列表")
                    return False
            except Exception as e:
                print(f"[auto_scan_cron] ❌ 获取股票列表失败: {e}")
                return False
            
            total_stocks = len(stock_list)
            batch_size = scan_config['batch_size']
            total_batches = (total_stocks + batch_size - 1) // batch_size
            
            # 初始化扫描进度（包含 scan_type 和 date 信息）
            initial_progress = {
                'type': 'scan',
                'scan_id': scan_id,
                'username': f'auto_{scan_type}',  # 系统自动扫描用户
                'scan_type': scan_type,  # 扫描类型
                'scan_date': date_str,  # 扫描日期
                'current': 0,
                'total': total_stocks,
                'status': '准备中',
                'detail': f'自动扫描任务({scan_type}) - 准备扫描 {total_stocks} 只股票（分 {total_batches} 批）...',
                'percentage': 0,
                'found': 0,
                'batch': 0,
                'total_batches': total_batches,
                'min_match_score': min_match_score,
                'max_market_cap': max_market_cap,
                'candidates': [],
                'start_time': time.time(),
                'is_auto_scan': True,  # 标记为自动扫描
                'is_global_scan': True  # 标记为全局扫描（所有用户可见）
            }
            scan_progress_store.save_scan_progress(scan_id, initial_progress)
            
            # 处理第一批
            try:
                if analyzer.trained_features is None:
                    print("[auto_scan_cron] ❌ 尚未训练特征模型")
                    return False
                
                from vercel_scan_helper import process_scan_batch_vercel
                
                common_features = analyzer.trained_features.get('common_features', {})
                if len(common_features) == 0:
                    print("[auto_scan_cron] ❌ 特征模板为空")
                    return False
                
                # 处理第一批
                first_batch = stock_list.head(batch_size)
                candidates = []
                
                process_scan_batch_vercel(
                    analyzer=analyzer,
                    stock_batch=first_batch,
                    scan_id=scan_id,
                    batch_num=1,
                    total_batches=total_batches,
                    total_stocks=total_stocks,
                    min_match_score=min_match_score,
                    max_market_cap=max_market_cap,
                    existing_candidates=candidates,
                    scan_config=scan_config,
                    common_features=common_features,
                    start_idx=0
                )
                
                print(f"[auto_scan_cron] ✅ 第一批处理完成，任务ID: {scan_id}")
                print(f"[auto_scan_cron] 后续批次将由前端自动继续处理")
                
                return True
            except Exception as e:
                import traceback
                error_detail = traceback.format_exc()
                print(f"[auto_scan_cron] ❌ 处理第一批失败: {error_detail}")
                
                error_progress = initial_progress.copy()
                error_progress.update({
                    'status': '失败',
                    'detail': f'自动扫描启动失败: {str(e)}',
                    'error': error_detail
                })
                scan_progress_store.save_scan_progress(scan_id, error_progress)
                return False
        else:
            # 本地环境：使用传统扫描方式
            print("[auto_scan_cron] 本地环境：使用传统扫描方式")
            # 这里可以调用 analyzer.scan_all_stocks() 等方法
            return True
            
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"[auto_scan_cron] ❌ 自动扫描任务失败: {error_detail}")
        return False


def main():
    """主函数：根据当前时间判断应该执行哪个等级的自动扫描"""
    beijing_now = get_beijing_time()
    current_hour = beijing_now.hour
    current_minute = beijing_now.minute
    
    print(f"[auto_scan_cron] 当前时间: {beijing_now.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 检查是否是中午扫描时间（11:30）
    if current_hour == 11 and current_minute == 30:
        print("[auto_scan_cron] 触发中午自动扫描")
        trigger_auto_scan_by_type('noon')
    
    # 检查是否是下午扫描时间（15:00）
    elif current_hour == 15 and current_minute == 0:
        print("[auto_scan_cron] 触发下午自动扫描")
        trigger_auto_scan_by_type('afternoon')
    
    else:
        print(f"[auto_scan_cron] 当前时间不是自动扫描时间点")
        print(f"[auto_scan_cron] 扫描时间: 11:30 (noon), 15:00 (afternoon)")

if __name__ == '__main__':
    main()



