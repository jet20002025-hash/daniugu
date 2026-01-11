"""
数据获取模块
使用akshare获取A股市场数据
"""
import akshare as ak
import pandas as pd
import time
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')


class DataFetcher:
    """数据获取类"""
    
    def __init__(self):
        self.stock_list = None
        self._market_cap_cache = None  # 缓存市值数据，避免重复获取
        
    def _get_stock_list_from_cache(self, check_age=False):
        """
        从缓存中获取股票列表
        :param check_age: 是否检查缓存年龄（用于判断是否过期）
        :return: 如果 check_age=True，返回 (stock_df, cache_timestamp, is_expired)，否则返回 stock_df
        """
        try:
            import os
            import json
            from datetime import datetime, timezone
            
            # 尝试使用 Upstash Redis
            redis_url = os.environ.get('UPSTASH_REDIS_REST_URL')
            redis_token = os.environ.get('UPSTASH_REDIS_REST_TOKEN')
            if redis_url and redis_token:
                import requests
                try:
                    # 获取缓存数据和时间戳
                    response = requests.get(
                        f"{redis_url}/get/stock_list_all",
                        headers={"Authorization": f"Bearer {redis_token}"},
                        timeout=2  # 缓存获取应该很快
                    )
                    if response.status_code == 200:
                        result = response.json()
                        value_str = result.get('result')
                        if value_str:
                            # 解析 JSON 字符串
                            stock_data = json.loads(value_str) if isinstance(value_str, str) else value_str
                            # 转换为 DataFrame（确保数据格式正确）
                            if isinstance(stock_data, list) and len(stock_data) > 0:
                                import pandas as pd
                                stock_df = pd.DataFrame(stock_data)
                                
                                # 尝试获取缓存时间戳
                                cache_timestamp = None
                                is_expired = False
                                if check_age:
                                    try:
                                        # 尝试获取缓存的TTL（剩余时间）
                                        ttl_response = requests.get(
                                            f"{redis_url}/ttl/stock_list_all",
                                            headers={"Authorization": f"Bearer {redis_token}"},
                                            timeout=2
                                        )
                                        if ttl_response.status_code == 200:
                                            ttl_result = ttl_response.json()
                                            ttl_seconds = ttl_result.get('result', -1)
                                            if ttl_seconds > 0:
                                                # TTL = 86400秒（24小时），缓存时间 = 当前时间 - (86400 - TTL)
                                                cache_age_seconds = 86400 - ttl_seconds
                                                cache_timestamp = datetime.now(timezone.utc).timestamp() - cache_age_seconds
                                                # 如果在交易时间段内且缓存超过5分钟，认为过期
                                                from datetime import timedelta
                                                beijing_now = datetime.now(timezone.utc) + timedelta(hours=8)
                                                is_in_trading_time = (
                                                    (beijing_now.hour == 9 and beijing_now.minute >= 30) or
                                                    beijing_now.hour == 10 or
                                                    (beijing_now.hour == 11 and beijing_now.minute <= 30) or
                                                    beijing_now.hour == 13 or
                                                    beijing_now.hour == 14 or
                                                    (beijing_now.hour == 15 and beijing_now.minute == 0)
                                                )
                                                if is_in_trading_time and cache_age_seconds > 300:  # 5分钟 = 300秒
                                                    is_expired = True
                                                    print(f"[get_all_stocks] ⚠️ 缓存已过期（交易时间段内，缓存年龄: {cache_age_seconds//60}分钟），需要刷新")
                                    except Exception as e:
                                        print(f"[get_all_stocks] ⚠️ 获取缓存TTL失败: {e}")
                                
                                if check_age:
                                    print(f"[get_all_stocks] ✅ 从 Redis 缓存获取股票列表: {len(stock_df)} 只，缓存年龄: {cache_age_seconds//60 if cache_timestamp else 'unknown'}分钟")
                                    return stock_df, cache_timestamp, is_expired
                                else:
                                    print(f"[get_all_stocks] ✅ 从 Redis 缓存获取股票列表: {len(stock_df)} 只")
                                    return stock_df
                            else:
                                print(f"[get_all_stocks] ⚠️ 缓存数据格式错误: {type(stock_data)}")
                except Exception as e:
                    print(f"[get_all_stocks] ⚠️ 从 Redis 缓存获取失败: {e}")
            
            # 尝试使用 Vercel KV（Vercel KV 不支持 TTL 查询，暂时不检查年龄）
            try:
                from vercel_kv import kv
                cached_data = kv.get('stock_list_all')
                if cached_data:
                    stock_data = json.loads(cached_data) if isinstance(cached_data, str) else cached_data
                    # 转换为 DataFrame（确保数据格式正确）
                    if isinstance(stock_data, list) and len(stock_data) > 0:
                        import pandas as pd
                        stock_df = pd.DataFrame(stock_data)
                        if check_age:
                            # Vercel KV 不支持TTL查询，返回 None 表示未知
                            print(f"[get_all_stocks] ✅ 从 Vercel KV 缓存获取股票列表: {len(stock_df)} 只（无法检查缓存年龄）")
                            return stock_df, None, False
                        else:
                            print(f"[get_all_stocks] ✅ 从 Vercel KV 缓存获取股票列表: {len(stock_df)} 只")
                            return stock_df
                    else:
                        print(f"[get_all_stocks] ⚠️ Vercel KV 缓存数据格式错误: {type(stock_data)}")
            except Exception as e:
                print(f"[get_all_stocks] ⚠️ 从 Vercel KV 缓存获取失败: {e}")
                
        except Exception as e:
            print(f"[get_all_stocks] ⚠️ 从缓存获取股票列表失败: {e}")
        
        if check_age:
            return None, None, True  # 缓存不存在，认为过期
        return None
    
    def _save_stock_list_to_cache(self, stock_df):
        """将股票列表保存到缓存（TTL: 24小时 = 86400秒）"""
        try:
            import os
            import json
            
            # 确保 stock_df 是 DataFrame
            if stock_df is None or len(stock_df) == 0:
                print(f"[_save_stock_list_to_cache] ⚠️ 股票列表为空，无法保存到缓存")
                return False
            
            # 将 DataFrame 转换为 JSON 格式（字典列表）
            try:
                stock_data = stock_df.to_dict('records')
                stock_json = json.dumps(stock_data, default=str, ensure_ascii=False)
                print(f"[_save_stock_list_to_cache] 准备保存 {len(stock_df)} 只股票到缓存，JSON 大小: {len(stock_json)} 字符")
            except Exception as e:
                print(f"[_save_stock_list_to_cache] ⚠️ 转换 DataFrame 到 JSON 失败: {e}")
                import traceback
                print(traceback.format_exc())
                return False
            
            # 尝试使用 Upstash Redis（最多重试2次）
            redis_url = os.environ.get('UPSTASH_REDIS_REST_URL')
            redis_token = os.environ.get('UPSTASH_REDIS_REST_TOKEN')
            
            # 诊断日志：检查环境变量是否设置
            if not redis_url:
                print(f"[_save_stock_list_to_cache] ⚠️ UPSTASH_REDIS_REST_URL 环境变量未设置，跳过 Redis 保存")
            if not redis_token:
                print(f"[_save_stock_list_to_cache] ⚠️ UPSTASH_REDIS_REST_TOKEN 环境变量未设置，跳过 Redis 保存")
            if redis_url and not redis_token:
                print(f"[_save_stock_list_to_cache] ⚠️ UPSTASH_REDIS_REST_URL 已设置，但 UPSTASH_REDIS_REST_TOKEN 未设置，跳过 Redis 保存")
            if not redis_url and redis_token:
                print(f"[_save_stock_list_to_cache] ⚠️ UPSTASH_REDIS_REST_TOKEN 已设置，但 UPSTASH_REDIS_REST_URL 未设置，跳过 Redis 保存")
            
            if redis_url and redis_token:
                print(f"[_save_stock_list_to_cache] ✅ Redis 环境变量已设置，尝试保存到 Redis...")
                import requests
                max_retries = 2
                for attempt in range(max_retries):
                    try:
                        # 缓存 24 小时（86400秒）
                        # Upstash Redis REST API: POST /setex/{key}/{ttl}
                        # 请求体格式：JSON 字符串（值本身是 JSON 字符串）
                        # 注意：使用 data 参数发送字符串，而不是 json 参数（避免双重编码）
                        if attempt > 0:
                            print(f"[_save_stock_list_to_cache] 重试保存到 Upstash Redis（第 {attempt + 1}/{max_retries} 次）...")
                        else:
                            print(f"[_save_stock_list_to_cache] 尝试保存到 Upstash Redis...")
                        print(f"[_save_stock_list_to_cache] JSON 大小: {len(stock_json)} 字符")
                        # Upstash Redis REST API setex 需要将值作为字符串发送
                        # 使用 data 参数直接发送字符串，避免双重 JSON 编码
                        response = requests.post(
                            f"{redis_url}/setex/stock_list_all/86400",
                            headers={
                                "Authorization": f"Bearer {redis_token}",
                                "Content-Type": "application/json"
                            },
                            data=stock_json.encode('utf-8'),  # 使用 data 参数发送 UTF-8 编码的字符串
                            timeout=15  # 增加超时时间到15秒（数据较大，可能需要更长时间）
                        )
                        if response.status_code == 200:
                            try:
                                result = response.json()
                                # Upstash 返回格式: {"result": "OK"} 或 {"result": true}
                                if result.get('result') == 'OK' or result.get('result') is True:
                                    print(f"[_save_stock_list_to_cache] ✅ 股票列表已保存到 Redis 缓存（TTL: 24小时，股票数: {len(stock_df)}）")
                                    return True
                                else:
                                    print(f"[_save_stock_list_to_cache] ⚠️ Redis 保存返回异常结果: {result}")
                                    if attempt < max_retries - 1:
                                        import time
                                        time.sleep(1)  # 等待1秒后重试
                                        continue
                            except Exception as parse_error:
                                print(f"[_save_stock_list_to_cache] ⚠️ Redis 保存响应解析失败: {parse_error}，但状态码为200，认为保存成功")
                                return True
                        else:
                            try:
                                error_msg = response.text[:1000] if hasattr(response, 'text') else str(response.status_code)
                            except:
                                error_msg = f"状态码: {response.status_code}"
                            print(f"[_save_stock_list_to_cache] ⚠️ Redis 保存失败，状态码: {response.status_code}, 响应: {error_msg}")
                            print(f"[_save_stock_list_to_cache] 响应头: {dict(response.headers) if hasattr(response, 'headers') else 'N/A'}")
                            if attempt < max_retries - 1:
                                import time
                                time.sleep(1)  # 等待1秒后重试
                                continue
                    except requests.exceptions.Timeout:
                        print(f"[_save_stock_list_to_cache] ⚠️ Redis 保存超时（15秒）")
                        if attempt < max_retries - 1:
                            import time
                            time.sleep(1)  # 等待1秒后重试
                            continue
                    except Exception as e:
                        import traceback
                        error_detail = traceback.format_exc()
                        print(f"[_save_stock_list_to_cache] ⚠️ 保存到 Redis 缓存失败: {e}")
                        print(f"[_save_stock_list_to_cache] 错误详情: {error_detail}")
                        if attempt < max_retries - 1:
                            import time
                            time.sleep(1)  # 等待1秒后重试
                            continue
            
            # 尝试使用 Vercel KV（如果没有使用 Redis 或 Redis 保存失败）
            # 即使 Redis 可用，也尝试 Vercel KV 作为备用方案
            try:
                from vercel_kv import kv
                print(f"[_save_stock_list_to_cache] 尝试保存到 Vercel KV（备用方案）...")
                print(f"[_save_stock_list_to_cache] JSON 大小: {len(stock_json)} 字符")
                kv.set('stock_list_all', stock_json, ttl=86400)  # 24小时
                print(f"[_save_stock_list_to_cache] ✅ 股票列表已保存到 Vercel KV 缓存（TTL: 24小时，股票数: {len(stock_df)}）")
                return True
            except ImportError:
                print(f"[_save_stock_list_to_cache] ⚠️ Vercel KV 未安装或不可用（这是正常的，如果使用 Redis）")
                # ImportError 不是真正的错误，只是表示 Vercel KV 不可用，不阻止继续执行
            except Exception as e:
                import traceback
                error_detail = traceback.format_exc()
                print(f"[_save_stock_list_to_cache] ⚠️ 保存到 Vercel KV 缓存失败: {e}")
                print(f"[_save_stock_list_to_cache] 错误详情: {error_detail}")
                # Vercel KV 失败不是致命错误，继续执行
                
        except Exception as e:
            import traceback
            error_detail = traceback.format_exc()
            print(f"[_save_stock_list_to_cache] ⚠️ 保存股票列表到缓存失败: {e}")
            print(f"[_save_stock_list_to_cache] 错误详情: {error_detail}")
        
        print(f"[_save_stock_list_to_cache] ❌ 所有缓存保存方式均失败，返回 False")
        return False
        
    def get_all_stocks(self, timeout=10, max_retries=3):
        """
        获取所有A股股票列表（优先从缓存获取）
        返回: DataFrame，包含股票代码、名称等信息
        :param timeout: 超时时间（秒），默认10秒
        :param max_retries: 最大重试次数，默认3次
        """
        import signal
        import threading
        import os
        
        # 首先尝试从缓存获取（优先从缓存读取，避免每次调用 akshare API）
        # 在交易时间段内，检查缓存年龄，如果过期则刷新
        print("[get_all_stocks] 尝试从缓存获取股票列表...")
        from datetime import datetime, timezone, timedelta
        beijing_now = datetime.now(timezone.utc) + timedelta(hours=8)
        is_in_trading_time = (
            (beijing_now.hour == 9 and beijing_now.minute >= 30) or
            beijing_now.hour == 10 or
            (beijing_now.hour == 11 and beijing_now.minute <= 30) or
            beijing_now.hour == 13 or
            beijing_now.hour == 14 or
            (beijing_now.hour == 15 and beijing_now.minute == 0)
        )
        
        # 如果在交易时间段内，检查缓存年龄
        if is_in_trading_time:
            cached_stocks, cache_timestamp, is_expired = self._get_stock_list_from_cache(check_age=True)
            if cached_stocks is not None and len(cached_stocks) > 0 and not is_expired:
                self.stock_list = cached_stocks
                print(f"[get_all_stocks] ✅ 从缓存获取成功（交易时间段内，缓存未过期），股票数: {len(cached_stocks)} 只")
                return cached_stocks
            elif cached_stocks is not None and len(cached_stocks) > 0 and is_expired:
                print(f"[get_all_stocks] ⚠️ 缓存已过期（交易时间段内，缓存超过5分钟），将从 API 获取最新数据...")
                # 继续执行，从 API 获取最新数据
            elif cached_stocks is None:
                print(f"[get_all_stocks] ⚠️ 缓存不存在，将从 API 获取...")
            else:
                print(f"[get_all_stocks] ⚠️ 缓存数据为空，将从 API 获取...")
        else:
            # 非交易时间段，直接使用缓存（如果存在）
            cached_stocks = self._get_stock_list_from_cache(check_age=False)
            if cached_stocks is not None and len(cached_stocks) > 0:
                self.stock_list = cached_stocks
                print(f"[get_all_stocks] ✅ 从缓存获取成功，股票数: {len(cached_stocks)} 只（非交易时间段，无需调用 akshare API）")
                return cached_stocks
        
        print("[get_all_stocks] ⚠️ 缓存中没有股票列表，开始从 akshare API 获取...")
        print("[get_all_stocks] 💡 提示：建议在交易时间段通过 Cron Job 自动刷新缓存，避免扫描时超时")
        
        # 检测 Vercel 环境，在 Vercel 中使用更短的超时和更少的重试
        is_vercel = (
            os.environ.get('VERCEL') == '1' or 
            os.environ.get('VERCEL_ENV') is not None or
            os.environ.get('VERCEL_URL') is not None
        )
        
        # Vercel 环境中，serverless 函数有 10 秒限制，使用更短的超时
        # 考虑到需要留出时间给其他代码执行，实际超时应该更短
        if is_vercel:
            timeout = min(timeout, 5)  # Vercel 中最多5秒，留出5秒给其他处理
            max_retries = 1  # Vercel 中只尝试1次，避免超过执行时间限制
            print(f"[get_all_stocks] Vercel 环境检测到，使用超短超时时间: {timeout}秒，只尝试 {max_retries} 次（避免超过10秒限制）")
            print(f"[get_all_stocks] ⚠️ 如果缓存不存在，可能会因为 akshare API 响应慢而导致超时")
        else:
            max_retries = min(max_retries, 3)  # 本地环境中最多重试3次
            print(f"[get_all_stocks] 本地环境，超时时间: {timeout}秒，最多重试 {max_retries} 次")
        
        for attempt in range(max_retries):
            try:
                print(f"[get_all_stocks] 尝试获取股票列表（第 {attempt + 1}/{max_retries} 次，超时: {timeout}秒）...")
                
                # 使用线程和超时机制
                result = [None]
                error = [None]
                start_time = time.time()
                
                def fetch_stocks():
                    try:
                        # 在 Vercel 环境中，尝试使用更快的接口或添加额外错误处理
                        if is_vercel:
                            try:
                                print(f"[get_all_stocks] Vercel 环境：开始调用 ak.stock_info_a_code_name()...")
                                result[0] = ak.stock_info_a_code_name()
                                elapsed = time.time() - start_time
                                print(f"[get_all_stocks] Vercel 环境：ak.stock_info_a_code_name() 调用成功，耗时 {elapsed:.2f}秒")
                            except Exception as e:
                                error[0] = e
                                elapsed = time.time() - start_time
                                print(f"[get_all_stocks] ❌ Vercel 环境中获取失败（耗时 {elapsed:.2f}秒）: {e}")
                                # 在 Vercel 中，不打印完整堆栈，避免日志过长
                        else:
                            result[0] = ak.stock_info_a_code_name()
                    except Exception as e:
                        error[0] = e
                        import traceback
                        elapsed = time.time() - start_time
                        print(f"[get_all_stocks] ❌ 获取失败（耗时 {elapsed:.2f}秒）: {e}")
                        if not is_vercel:
                            print(f"[get_all_stocks] 错误堆栈: {traceback.format_exc()}")
                
                fetch_thread = threading.Thread(target=fetch_stocks)
                fetch_thread.daemon = True
                fetch_thread.start()
                fetch_thread.join(timeout=timeout)
                
                elapsed_total = time.time() - start_time
                
                if fetch_thread.is_alive():
                    print(f"[get_all_stocks] ⏱️ 获取超时（>{timeout}秒，实际耗时 {elapsed_total:.2f}秒）")
                    if is_vercel:
                        # 在 Vercel 中，超时直接返回 None，不重试
                        print(f"[get_all_stocks] Vercel 环境中超时，直接返回 None（避免超过10秒执行时间限制）")
                        return None
                    if attempt < max_retries - 1:
                        # 不在 Vercel 中时，等待后重试
                        print(f"[get_all_stocks] 等待 2 秒后重试...")
                        import time
                        time.sleep(2)
                        continue  # 重试
                    else:
                        print(f"[get_all_stocks] ❌ 所有重试都超时")
                        return None
                
                if error[0]:
                    print(f"[get_all_stocks] ❌ 获取出错（耗时 {elapsed_total:.2f}秒）: {error[0]}")
                    if is_vercel:
                        # 在 Vercel 中，如果出错，直接返回 None，不重试
                        print(f"[get_all_stocks] Vercel 环境中获取出错，直接返回 None（避免超过10秒执行时间限制）")
                        return None
                    if attempt < max_retries - 1:
                        print(f"[get_all_stocks] 等待 2 秒后重试...")
                        import time
                        time.sleep(2)
                        continue  # 重试
                    else:
                        raise error[0]
                
                if result[0] is not None and len(result[0]) > 0:
                    stock_info = result[0]
                    self.stock_list = stock_info
                    elapsed_total = time.time() - start_time
                    print(f"[get_all_stocks] ✅ 成功获取 {len(stock_info)} 只A股股票（耗时 {elapsed_total:.2f}秒）")
                    
                    # 将获取的股票列表保存到缓存（异步保存，不阻塞）
                    try:
                        import threading
                        def save_cache():
                            try:
                                self._save_stock_list_to_cache(stock_info)
                            except Exception as e:
                                print(f"[get_all_stocks] ⚠️ 后台保存缓存失败（不影响使用）: {e}")
                        
                        cache_thread = threading.Thread(target=save_cache)
                        cache_thread.daemon = True
                        cache_thread.start()
                        # 不等待缓存保存完成，立即返回结果
                        print(f"[get_all_stocks] 已启动后台线程保存股票列表到缓存...")
                    except Exception as e:
                        print(f"[get_all_stocks] ⚠️ 启动缓存保存线程失败（不影响使用）: {e}")
                    
                    return stock_info
                else:
                    print(f"[get_all_stocks] ⚠️ 返回结果为空（耗时 {elapsed_total:.2f}秒）")
                    if is_vercel:
                        # 在 Vercel 中，如果结果为空，直接返回 None，不重试
                        print(f"[get_all_stocks] Vercel 环境中结果为空，直接返回 None")
                        return None
                    if attempt < max_retries - 1:
                        print(f"[get_all_stocks] 等待 2 秒后重试...")
                        import time
                        time.sleep(2)
                        continue  # 重试
                    else:
                        print(f"[get_all_stocks] ❌ 所有重试都失败，返回 None")
                        return None
                        
            except Exception as e:
                import traceback
                error_detail = traceback.format_exc()
                elapsed_total = time.time() - start_time if 'start_time' in locals() else 0
                print(f"[get_all_stocks] ❌ 获取股票列表失败（第 {attempt + 1} 次尝试，耗时 {elapsed_total:.2f}秒）: {e}")
                if not is_vercel:
                    print(f"[get_all_stocks] 错误详情: {error_detail}")
                
                if is_vercel:
                    # 在 Vercel 中，如果出错，直接返回 None，不重试
                    print(f"[get_all_stocks] Vercel 环境中出错，直接返回 None（避免超过10秒执行时间限制）")
                    return None
                
                if attempt < max_retries - 1:
                    print(f"[get_all_stocks] 等待 2 秒后重试...")
                    import time
                    time.sleep(2)
                    continue  # 重试
                else:
                    print(f"[get_all_stocks] ❌ 所有重试都失败")
                    return None
        
        print(f"[get_all_stocks] ❌ 所有重试都失败，返回 None")
        return None
    
    def get_market_cap(self, stock_code, timeout=5):
        """
        获取股票总市值（单位：亿元）
        :param stock_code: 股票代码（如 '000001'）
        :param timeout: 超时时间（秒），默认5秒
        :return: 总市值（亿元），如果获取失败返回None
        """
        try:
            import threading
            import time
            
            # 使用缓存，避免重复获取全部股票数据
            if self._market_cap_cache is None:
                # 使用实时行情接口（批量获取）- 这个操作可能很慢，使用超时保护
                result = [None]
                error = [None]
                
                def fetch_all_stocks():
                    try:
                        result[0] = ak.stock_zh_a_spot_em()
                    except Exception as e:
                        error[0] = e
                
                # 如果缓存为空，需要获取全部股票数据（可能很慢）
                fetch_thread = threading.Thread(target=fetch_all_stocks)
                fetch_thread.daemon = True
                fetch_thread.start()
                fetch_thread.join(timeout=timeout)
                
                if fetch_thread.is_alive():
                    # 超时了，返回None，不阻塞
                    return None
                
                if error[0]:
                    return None
                
                df = result[0]
                if df is not None and not df.empty:
                    self._market_cap_cache = df
                else:
                    return None
            else:
                df = self._market_cap_cache
            
            if df is not None and not df.empty:
                # 查找对应股票（代码列是字符串类型）
                # 确保stock_code是字符串格式
                stock_code_str = str(stock_code)
                stock_row = df[df['代码'] == stock_code_str]
                
                if not stock_row.empty:
                    if '总市值' in stock_row.columns:
                        market_cap = stock_row.iloc[0]['总市值']
                        if pd.notna(market_cap):
                            try:
                                market_cap = float(market_cap)
                                # 总市值单位是元，转换为亿元
                                return market_cap / 100000000
                            except (ValueError, TypeError):
                                pass
            
            return None
        except Exception as e:
            # 静默失败，返回None（可以取消注释下面的行来调试）
            # print(f"获取市值失败 {stock_code}: {e}")
            return None
    
    def get_daily_kline(self, stock_code, period="1y"):
        """
        获取日K线数据
        :param stock_code: 股票代码（如 '000001'）
        :param period: 时间周期，'1y'表示1年
        :return: DataFrame，包含日期、开盘、收盘、最高、最低、成交量等
        """
        try:
            # 计算开始日期（2年前，确保有足够历史数据）
            # 结束日期使用今天，确保获取最新数据
            end_date = datetime.now().strftime('%Y%m%d')
            start_date = (datetime.now() - timedelta(days=365 * 2)).strftime('%Y%m%d')
            
            # 获取日K线数据
            df = ak.stock_zh_a_hist(symbol=stock_code, period="daily", 
                                    start_date=start_date, end_date=end_date, adjust="qfq")
            
            if df is None or df.empty:
                return None
            
            # akshare返回的DataFrame列名通常是中文，直接使用位置索引更可靠
            # 标准列顺序：日期、开盘、收盘、最高、最低、成交量、成交额、振幅、涨跌幅、涨跌额、换手率
            # 但实际返回的列数可能不同，使用位置索引访问
            
            # 先尝试使用列名（如果akshare返回的是标准列名）
            # 注意：即使列数不足6，也要尝试重命名
            if len(df.columns) >= 5:  # 至少需要5列：日期、开盘、收盘、最高、最低
                # 使用位置索引重命名关键列
                # 根据2025-12-31的正确数据核对：
                # 正确：开盘=4.66, 收盘=4.65, 最高=4.68, 最低=4.62
                # akshare实际返回的顺序可能是：日期、开盘、收盘、最高、最低、成交量
                # 或者：日期、其他、开盘、收盘、最高、最低
                # 需要根据列名或数据逻辑判断
                rename_dict = {}
                if len(df.columns) > 0:
                    rename_dict[df.columns[0]] = '日期'
                
                # 尝试根据列名判断
                col_names = [str(col).lower() for col in df.columns]
                
                # 查找包含"开盘"、"收盘"、"最高"、"最低"的列
                open_idx = None
                close_idx = None
                high_idx = None
                low_idx = None
                
                for i, col_name in enumerate(col_names):
                    if '开盘' in col_name or 'open' in col_name:
                        open_idx = i
                    elif '收盘' in col_name or 'close' in col_name:
                        close_idx = i
                    elif '最高' in col_name or 'high' in col_name:
                        high_idx = i
                    elif '最低' in col_name or 'low' in col_name:
                        low_idx = i
                
                # 如果找到了列名，使用列名映射
                if open_idx and close_idx and high_idx and low_idx:
                    rename_dict[df.columns[open_idx]] = '开盘'
                    rename_dict[df.columns[close_idx]] = '收盘'
                    rename_dict[df.columns[high_idx]] = '最高'
                    rename_dict[df.columns[low_idx]] = '最低'
                else:
                    # 如果没找到列名，根据2025-12-31的正确数据推断：
                    # 正确：开盘=4.66, 收盘=4.65, 最高=4.68, 最低=4.62
                    # 之前错误显示：列1=2.00, 列2=4.66, 列3=4.65, 列4=4.68
                    # 所以列顺序是：日期、其他、开盘、收盘、最高、最低
                    # 列1可能是涨跌幅或其他数据，跳过
                    if len(df.columns) > 2:
                        rename_dict[df.columns[2]] = '开盘'  # 列2是开盘
                    if len(df.columns) > 3:
                        rename_dict[df.columns[3]] = '收盘'  # 列3是收盘
                    if len(df.columns) > 4:
                        rename_dict[df.columns[4]] = '最高'  # 列4是最高
                    if len(df.columns) > 5:
                        rename_dict[df.columns[5]] = '最低'  # 列5是最低
                    
                    # 如果列1存在但不是开盘，保留原列名（可能是涨跌幅等）
                    if len(df.columns) > 1 and df.columns[1] not in rename_dict:
                        # 不重命名列1，保持原样
                        pass
                    
                    if len(df.columns) > 6:
                        rename_dict[df.columns[6]] = '成交量'  # 列6是成交量
                
                # 执行重命名
                if rename_dict:
                    df = df.rename(columns=rename_dict)
                    print(f"[调试] 列重命名完成，新列名: {list(df.columns)}")
                else:
                    print(f"[警告] 未执行列重命名，原始列名: {list(df.columns)}")
            
            # 确保日期列存在且可转换
            if '日期' in df.columns:
                df['日期'] = pd.to_datetime(df['日期'], errors='coerce')
            else:
                print(f"[错误] 未找到'日期'列，可用列: {list(df.columns)}")
                return None
            
            # 验证必要的列是否存在，如果不存在则使用位置索引创建
            required_cols = ['开盘', '收盘', '最高', '最低']
            missing_cols = [col for col in required_cols if col not in df.columns]
            if missing_cols:
                # print(f"[警告] 缺少必要的列: {missing_cols}")
                # print(f"[调试] 当前列名: {list(df.columns)}")
                # print(f"[调试] 列数: {len(df.columns)}")
                # 如果列数足够，尝试使用位置索引创建新列
                # 根据2025-12-31的正确数据：列顺序是 日期、其他、开盘、收盘、最高、最低
                if len(df.columns) >= 6:
                    # print(f"[调试] 使用位置索引创建缺失的列...")
                    if '开盘' not in df.columns and len(df.columns) > 2:
                        df['开盘'] = df.iloc[:, 2]
                    if '收盘' not in df.columns and len(df.columns) > 3:
                        df['收盘'] = df.iloc[:, 3]
                    if '最高' not in df.columns and len(df.columns) > 4:
                        df['最高'] = df.iloc[:, 4]
                    if '最低' not in df.columns and len(df.columns) > 5:
                        df['最低'] = df.iloc[:, 5]
                    # print(f"[调试] 创建后的列名: {list(df.columns)}")
            
            # 删除日期为空的记录
            df = df.dropna(subset=['日期'])
            
            if df.empty:
                return None
            
            df = df.sort_values('日期').reset_index(drop=True)
            
            return df
        except Exception as e:
            print(f"获取 {stock_code} 日K线数据失败: {e}")
            return None
    
    def get_weekly_kline(self, stock_code, period="1y"):
        """
        获取周K线数据（包含周成交量）
        :param stock_code: 股票代码（如 '000001'）
        :param period: 时间周期，'1y'表示1年
        :return: DataFrame，包含周日期、开盘、收盘、最高、最低、周成交量等
        """
        try:
            print(f"开始获取 {stock_code} 的周K线数据...")
            # 方法1: 尝试直接使用akshare的周K线接口
            try:
                end_date = datetime.now().strftime('%Y%m%d')
                start_date = (datetime.now() - timedelta(days=365 * 2)).strftime('%Y%m%d')
                
                print(f"尝试直接获取周K线: {stock_code}, {start_date} - {end_date}")
                df = ak.stock_zh_a_hist(symbol=stock_code, period="weekly", 
                                        start_date=start_date, end_date=end_date, adjust="qfq")
                print(f"直接获取周K线结果: {df is not None}, {len(df) if df is not None else 0} 条")
                
                if df is not None and not df.empty:
                    # 重命名列
                    if len(df.columns) >= 6:
                        rename_dict = {}
                        if len(df.columns) > 0:
                            rename_dict[df.columns[0]] = '日期'
                        # 根据2025-12-31的正确数据推断：
                        # 正确：开盘=4.66, 收盘=4.65, 最高=4.68, 最低=4.62
                        # 之前错误显示：列1=2.00, 列2=4.66, 列3=4.65, 列4=4.68
                        # 所以列顺序是：日期、其他（列1，可能是涨跌幅）、开盘（列2）、收盘（列3）、最高（列4）、最低（列5）
                        # 列1跳过（可能是涨跌幅或其他数据）
                        if len(df.columns) > 2:
                            rename_dict[df.columns[2]] = '开盘'  # 列2是开盘
                        if len(df.columns) > 3:
                            rename_dict[df.columns[3]] = '收盘'  # 列3是收盘
                        if len(df.columns) > 4:
                            rename_dict[df.columns[4]] = '最高'  # 列4是最高
                        if len(df.columns) > 5:
                            rename_dict[df.columns[5]] = '最低'  # 列5是最低
                        if len(df.columns) > 6:
                            rename_dict[df.columns[6]] = '成交量'  # 列6是成交量
                        
                        df = df.rename(columns=rename_dict)
                    
                    # 确保日期列存在且可转换
                    if '日期' in df.columns:
                        df['日期'] = pd.to_datetime(df['日期'], errors='coerce')
                        df = df.dropna(subset=['日期'])
                        df = df.sort_values('日期').reset_index(drop=True)
                        # 重命名成交量为周成交量
                        if '成交量' in df.columns:
                            df = df.rename(columns={'成交量': '周成交量'})
                        return df
            except Exception as e1:
                print(f"直接获取周K线失败: {e1}，尝试从日K线聚合...")
                # 如果直接获取失败，使用聚合方式
            
            # 方法2: 从日K线聚合为周K线
            print(f"开始从日K线聚合周K线: {stock_code}")
            daily_df = self.get_daily_kline(stock_code, period)
            if daily_df is None or daily_df.empty:
                print(f"无法获取 {stock_code} 的日K线数据")
                return None
            print(f"获取到 {len(daily_df)} 条日K线数据，开始聚合...")
            
            # 确保必要的列存在
            required_cols = ['日期', '开盘', '收盘', '最高', '最低', '成交量']
            missing_cols = [col for col in required_cols if col not in daily_df.columns]
            if missing_cols:
                print(f"警告：缺少必要的列 {missing_cols}")
                return None
            
            # 转换为周K线
            weekly_df = daily_df.copy()
            
            # 使用ISO周（周一开始）
            weekly_df['年周'] = weekly_df['日期'].dt.to_period('W-SUN')  # 周日结束的周
            
            # 按周聚合
            def agg_week(group):
                return pd.Series({
                    '开盘': group['开盘'].iloc[0],
                    '收盘': group['收盘'].iloc[-1],
                    '最高': group['最高'].max(),
                    '最低': group['最低'].min(),
                    '周成交量': group['成交量'].sum()  # 周成交量 = 该周所有交易日的成交量之和
                })
            
            weekly_kline = weekly_df.groupby('年周').apply(agg_week).reset_index()
            
            # 如果成交额列存在，也聚合
            if '成交额' in weekly_df.columns:
                weekly_kline['周成交额'] = weekly_df.groupby('年周')['成交额'].sum().values
            
            # 将周期转换为日期（使用该周的最后一天）
            weekly_kline['日期'] = weekly_kline['年周'].dt.to_timestamp() + pd.Timedelta(days=6)
            weekly_kline = weekly_kline.sort_values('日期').reset_index(drop=True)
            
            # 计算周涨跌幅
            weekly_kline['涨跌幅'] = weekly_kline['收盘'].pct_change() * 100
            weekly_kline['涨跌幅'] = weekly_kline['涨跌幅'].fillna(0)
            
            return weekly_kline
        except Exception as e:
            import traceback
            print(f"获取 {stock_code} 周K线数据失败: {e}")
            print(f"错误详情: {traceback.format_exc()}")
            return None
    
    def get_monthly_kline(self, stock_code, period="1y"):
        """
        获取月K线数据
        :param stock_code: 股票代码
        :param period: 时间周期
        :return: DataFrame，月K线数据
        """
        try:
            # 先获取日K线，然后转换为月K线
            daily_df = self.get_daily_kline(stock_code, period)
            if daily_df is None or daily_df.empty:
                return None
            
            # 转换为月K线
            monthly_df = daily_df.copy()
            
            # 确保必要的列存在
            required_cols = ['日期', '开盘', '收盘', '最高', '最低', '成交量']
            missing_cols = [col for col in required_cols if col not in monthly_df.columns]
            if missing_cols:
                print(f"警告：缺少必要的列 {missing_cols}")
                return None
            
            monthly_df['年月'] = monthly_df['日期'].dt.to_period('M')
            
            # 按月聚合（使用apply方式，更兼容）
            def agg_month(group):
                return pd.Series({
                    '开盘': group['开盘'].iloc[0],
                    '收盘': group['收盘'].iloc[-1],
                    '最高': group['最高'].max(),
                    '最低': group['最低'].min(),
                    '成交量': group['成交量'].sum()
                })
            
            monthly_kline = monthly_df.groupby('年月').apply(agg_month).reset_index()
            
            # 如果成交额列存在，也聚合
            if '成交额' in monthly_df.columns:
                monthly_kline['成交额'] = monthly_df.groupby('年月')['成交额'].sum().values
            
            monthly_kline['日期'] = monthly_kline['年月'].dt.to_timestamp()
            monthly_kline = monthly_kline.sort_values('日期').reset_index(drop=True)
            
            # 计算月涨跌幅
            monthly_kline['涨跌幅'] = monthly_kline['收盘'].pct_change() * 100
            monthly_kline['涨跌幅'] = monthly_kline['涨跌幅'].fillna(0)
            
            return monthly_kline
        except Exception as e:
            import traceback
            print(f"获取 {stock_code} 月K线数据失败: {e}")
            print(f"错误详情: {traceback.format_exc()}")
            return None
    
    def get_limit_up_info(self, stock_code, days=10):
        """
        获取最近N个交易日的涨停信息
        :param stock_code: 股票代码
        :param days: 查询天数
        :return: 是否有涨停（True/False），涨停日期列表
        """
        try:
            # 获取最近N天的日K线数据
            end_date = datetime.now().strftime('%Y%m%d')
            start_date = (datetime.now() - timedelta(days=days*2)).strftime('%Y%m%d')  # 多取一些，排除非交易日
            
            df = ak.stock_zh_a_hist(symbol=stock_code, period="daily", 
                                    start_date=start_date, end_date=end_date, adjust="qfq")
            
            if df is None or df.empty:
                return False, []
            
            # 使用位置索引访问数据，避免列名问题
            if len(df.columns) < 9:
                return False, []
            
            # 直接使用位置索引
            df.iloc[:, 0] = pd.to_datetime(df.iloc[:, 0], errors='coerce')
            df = df.dropna(subset=[df.columns[0]])
            if df.empty:
                return False, []
            
            # 按日期排序
            df = df.sort_values(by=df.columns[0]).reset_index(drop=True)
            
            # 取最近days个交易日
            recent_df = df.tail(days)
            
            # 判断是否有涨停（涨跌幅 >= 9.5%，考虑ST股是5%）
            # 涨跌幅通常在第8列（索引8）
            pct_chg_col = df.columns[8] if len(df.columns) > 8 else None
            if pct_chg_col is None:
                return False, []
            
            limit_up_mask = recent_df[pct_chg_col] >= 9.5
            date_col = df.columns[0]
            limit_up_days = recent_df[limit_up_mask][date_col].tolist()
            has_limit_up = len(limit_up_days) > 0
            
            return has_limit_up, limit_up_days
        except Exception as e:
            print(f"获取 {stock_code} 涨停信息失败: {e}")
            return False, []

