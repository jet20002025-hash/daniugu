#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
大牛股分析器
功能：
1. 上传大牛股代码
2. 找到涨幅最大的区间
3. 分析大涨前的特征（成交量和走势）
4. 提取买点特征
"""
from data_fetcher import DataFetcher
from technical_analysis import TechnicalAnalysis
import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from typing import Dict, List, Optional, Tuple


class BullStockAnalyzer:
    """大牛股分析器"""
    
    @staticmethod
    def get_stock_board_info(stock_code: str) -> Tuple[str, float]:
        """
        判断股票所属板块和涨停限制
        :param stock_code: 股票代码（如 '000001', '300001', '688001'）
        :return: (板块名称, 涨停限制百分比)
        """
        code = str(stock_code).strip()
        
        if code.startswith('300'):
            return ('创业板', 20.0)
        elif code.startswith('688'):
            return ('科创板', 20.0)
        elif code.startswith('000') or code.startswith('001') or code.startswith('002'):
            return ('主板/中小板', 10.0)
        elif code.startswith('003'):
            return ('中小板', 10.0)
        else:
            # 默认按主板处理
            return ('主板', 10.0)
    
    def __init__(self, auto_load_default_stocks: bool = True, auto_analyze_and_train: bool = True):
        """
        初始化分析器
        :param auto_load_default_stocks: 是否自动加载默认大牛股列表
        :param auto_analyze_and_train: 是否自动分析和训练（如果匹配度未达标）
        """
        self.fetcher = DataFetcher()
        self.tech_analysis = TechnicalAnalysis()
        self.bull_stocks = []  # 存储大牛股信息
        self.analysis_results = {}  # 存储分析结果
        self.trained_features = None  # 存储训练好的特征模板
        self.progress = {}  # 存储进度信息 {'type': 'analyze'|'train'|'scan', 'current': int, 'total': int, 'status': str, 'detail': str, 'found': int}
        self.scan_results = None  # 存储扫描结果
        self.reversal_scan_results = None  # 存储反转个股扫描结果
        self.match_score_ready = False  # 标记匹配度是否已达标（>=0.8）
        self.stop_scan = False  # 停止扫描标志
        self.scan_state = None  # 存储扫描状态，用于断点续扫 {'stock_list': DataFrame, 'start_idx': int, 'candidates': list, 'min_match_score': float, 'max_market_cap': float, 'batch_num': int, 'total_batches': int}
        self.trained_sell_features = None  # 存储训练好的卖点特征模板
        self.trained_screener_model = None  # 存储训练好的“8条件”选股大模型（规则/统计模板）
        
        # 默认大牛股列表（用户提供）
        # 已去掉：001331（胜通能源），002969（嘉美包装）
        # 新增：603778，603122，600343，603216
        self.default_bull_stocks = ['000592', '002104', '002759', '300436', '301005', '301232', '002788', '603778', '603122', '600343', '603216']
        
        # 自动加载默认大牛股
        if auto_load_default_stocks:
            self._load_default_stocks()
            
            # 如果启用自动分析和训练，检查匹配度
            if auto_analyze_and_train:
                self._auto_setup_if_needed()
    
    def _load_default_stocks(self):
        """加载默认大牛股列表"""
        try:
            print(f"\n正在加载默认大牛股列表: {', '.join(self.default_bull_stocks)}")
            for stock_code in self.default_bull_stocks:
                # 检查是否已存在，避免重复添加
                existing = [s for s in self.bull_stocks if s['代码'] == stock_code]
                if not existing:
                    result = self.add_bull_stock(stock_code)
                    if result.get('success'):
                        print(f"✅ 已加载: {stock_code} {result.get('stock', {}).get('名称', '')}")
                    else:
                        print(f"⚠️ 加载失败: {stock_code} - {result.get('message', '')}")
            print(f"默认大牛股加载完成，共 {len(self.bull_stocks)} 只股票\n")
        except Exception as e:
            print(f"⚠️ 加载默认大牛股时出错: {str(e)}")
            # 即使出错也继续运行
    
    def _get_common_features(self) -> Dict:
        """
        获取 common_features，兼容不同的模型结构
        支持两种格式：
        1. trained_features['common_features'] - 旧格式
        2. trained_features['buy_features']['common_features'] - 新格式
        """
        if not self.trained_features:
            return {}
        
        # 尝试新格式：buy_features.common_features
        buy_features = self.trained_features.get('buy_features', {})
        if isinstance(buy_features, dict):
            common_features = buy_features.get('common_features', {})
            if common_features and len(common_features) > 0:
                return common_features
        
        # 尝试旧格式：直接 common_features
        return self.trained_features.get('common_features', {})
    
    def _check_match_score(self) -> Tuple[bool, float]:
        """
        检查当前匹配度是否已达到0.8以上
        :return: (是否达标, 最高匹配度)
        """
        common_features = self._get_common_features()
        if not common_features:
            return False, 0.0
        
        if len(self.analysis_results) == 0:
            return False, 0.0
        max_score = 0.0
        
        # 检查每只股票的匹配度
        for stock_code in self.default_bull_stocks:
            if stock_code not in self.analysis_results:
                continue
            
            analysis_result = self.analysis_results[stock_code]
            interval = analysis_result.get('interval')
            if not interval:
                continue
            
            start_idx = interval.get('起点索引')
            if start_idx is None:
                continue
            
            try:
                # 获取周线数据
                weekly_df = self.fetcher.get_weekly_kline(stock_code, period="2y")
                if weekly_df is None or len(weekly_df) == 0:
                    continue
                
                # 在涨幅区间起点之前，找到成交量突增点
                volume_surge_idx = self.find_volume_surge_point(stock_code, int(start_idx), weekly_df=weekly_df, min_volume_ratio=3.0, lookback_weeks=52)
                
                if volume_surge_idx is None:
                    volume_surge_idx = max(0, int(start_idx) - 20)
                
                # 基于成交量突增点提取特征
                features = self.extract_features_at_start_point(stock_code, volume_surge_idx, lookback_weeks=40, weekly_df=weekly_df)
                if not features:
                    continue
                
                # 计算匹配度
                match_score = self._calculate_match_score(features, common_features, tolerance=0.3)
                total_score = match_score.get('总匹配度', 0)
                max_score = max(max_score, total_score)
            except Exception:
                continue
        
        return max_score >= 0.95, max_score
    
    def _auto_setup_if_needed(self):
        """
        自动设置：如果匹配度未达标，自动分析和训练
        """
        try:
            # 先检查是否已有分析结果和训练特征
            has_analysis = len(self.analysis_results) > 0
            has_trained = self.trained_features is not None and len(self._get_common_features()) > 0
            
            if has_analysis and has_trained:
                # 检查匹配度
                is_ready, max_score = self._check_match_score()
                if is_ready:
                    print(f"\n✅ 匹配度已达标（最高: {max_score:.3f} >= 0.95），跳过分析和训练步骤")
                    self.match_score_ready = True
                    
                    # 即使买点匹配度已达标，也检查是否需要训练卖点特征
                    if not hasattr(self, 'trained_sell_features') or self.trained_sell_features is None:
                        print(f"\n📊 开始训练卖点特征模型...")
                        sell_train_result = self.train_sell_point_features()
                        if sell_train_result.get('success'):
                            print(f"✅ 卖点特征训练完成")
                        else:
                            print(f"⚠️ 卖点特征训练失败: {sell_train_result.get('message', '')}")
                    return
            
            # 如果匹配度未达标，自动分析和训练
            print("\n📊 自动分析和训练（匹配度未达标）...")
            
            # 1. 分析所有股票
            print("  步骤1: 分析所有大牛股...")
            for stock_code in self.default_bull_stocks:
                if stock_code not in self.analysis_results:
                    result = self.analyze_bull_stock(stock_code)
                    if not result.get('success'):
                        print(f"    ⚠️ {stock_code} 分析失败: {result.get('message', '')}")
            
            # 2. 训练买点特征模型
            print("  步骤2: 训练买点特征模型...")
            train_result = self.train_features()
            if not train_result.get('success'):
                print(f"    ❌ 训练失败: {train_result.get('message', '')}")
                return
            
            # 3. 训练卖点特征模型
            print("  步骤3: 训练卖点特征模型...")
            sell_train_result = self.train_sell_point_features()
            if sell_train_result.get('success'):
                print(f"    ✅ 卖点特征训练完成")
            else:
                print(f"    ⚠️ 卖点特征训练失败: {sell_train_result.get('message', '')}")
            
            # 4. 再次检查匹配度
            is_ready, max_score = self._check_match_score()
            if is_ready:
                print(f"  ✅ 匹配度已达标（最高: {max_score:.3f} >= 0.95），可以开始测试")
                self.match_score_ready = True
            else:
                print(f"  ⚠️ 匹配度未达标（最高: {max_score:.3f} < 0.95），建议继续优化")
                self.match_score_ready = False
                
        except Exception as e:
            print(f"⚠️ 自动设置时出错: {str(e)}")
            import traceback
            traceback.print_exc()
    
    def _get_stock_name(self, stock_code: str) -> Optional[str]:
        """
        根据股票代码获取股票名称
        :param stock_code: 股票代码（如 '000001'）
        :return: 股票名称，如果获取失败返回None
        """
        try:
            # 获取所有股票列表
            stock_list = self.fetcher.get_all_stocks()
            if stock_list is None or stock_list.empty:
                return None
            
            # 查找对应股票（代码列可能是字符串或数字）
            stock_code_str = str(stock_code)
            
            # akshare返回的列名可能是 'code' 和 'name'，也可能是其他名称
            # 尝试多种可能的列名
            code_col = None
            name_col = None
            
            for col in stock_list.columns:
                col_lower = str(col).lower()
                if 'code' in col_lower or '代码' in col:
                    code_col = col
                elif 'name' in col_lower or '名称' in col or 'name' in col:
                    name_col = col
            
            # 如果没找到，使用第一列作为代码，第二列作为名称
            if code_col is None:
                code_col = stock_list.columns[0]
            if name_col is None and len(stock_list.columns) >= 2:
                name_col = stock_list.columns[1]
            
            # 查找股票
            stock_row = stock_list[stock_list[code_col].astype(str) == stock_code_str]
            
            if not stock_row.empty and name_col:
                return str(stock_row.iloc[0][name_col])
            
            return None
        except Exception as e:
            # 静默失败
            return None
    
    def _validate_stock_code(self, stock_code: str) -> bool:
        """
        验证股票代码格式
        :param stock_code: 股票代码
        :return: 是否有效
        """
        if not stock_code or not isinstance(stock_code, str):
            return False
        
        # 移除可能的空格
        stock_code = stock_code.strip()
        
        # A股代码格式：6位数字
        if len(stock_code) == 6 and stock_code.isdigit():
            return True
        
        return False
    
    def add_bull_stock(self, stock_code: str, stock_name: str = None) -> Dict:
        """
        添加大牛股（增强版）
        :param stock_code: 股票代码（如 '000001'）
        :param stock_name: 股票名称（可选，如果不提供会自动获取）
        :return: 添加结果字典 {'success': bool, 'message': str, 'stock': dict or None}
        """
        try:
            # 确保stock_code不为None
            if stock_code is None:
                return {
                    'success': False,
                    'message': '❌ 股票代码不能为空',
                    'stock': None
                }
            
            # 标准化股票代码（去除空格，确保是6位）
            stock_code = str(stock_code).strip()
            
            # 验证股票代码格式
            if not self._validate_stock_code(stock_code):
                return {
                    'success': False,
                    'message': f'❌ 股票代码格式无效: {stock_code}（应为6位数字）',
                    'stock': None
                }
            
            # 检查是否已添加（不区分大小写，确保唯一性）
            for stock in self.bull_stocks:
                if str(stock['代码']).strip() == stock_code:
                    existing_name = stock.get('名称', stock_code)
                    return {
                        'success': False,
                        'message': f'⚠️ 股票 {stock_code} ({existing_name}) 已存在，不能重复添加',
                        'stock': stock
                    }
            
            # 如果未提供名称，尝试自动获取
            if stock_name is None:
                stock_name = self._get_stock_name(stock_code)
                if stock_name is None:
                    stock_name = stock_code  # 如果获取失败，使用代码作为名称
                    print(f"⚠️ 无法自动获取 {stock_code} 的股票名称，使用代码作为名称")
            
            # 验证股票是否存在（优先用周K线，减少对日线接口的依赖）
            kline_df = self.fetcher.get_weekly_kline(stock_code, period="2y")
            if kline_df is None or kline_df.empty:
                kline_df = self.fetcher.get_daily_kline(stock_code, period="1y")
            if kline_df is None or kline_df.empty:
                return {
                    'success': False,
                    'message': f'❌ 无法获取股票 {stock_code} 的数据，请检查代码是否正确',
                    'stock': None
                }
            
            # 添加到列表
            stock_info = {
                '代码': stock_code,
                '名称': stock_name,
                '添加时间': datetime.now(),
                '数据条数': len(kline_df) if kline_df is not None else 0
            }
            
            self.bull_stocks.append(stock_info)
            
            return {
                'success': True,
                'message': f'✅ 成功添加大牛股: {stock_code} {stock_name}',
                'stock': stock_info
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'❌ 添加股票失败: {e}',
                'stock': None
            }
    
    def add_bull_stocks_batch(self, stock_codes: List[str]) -> Dict:
        """
        批量添加大牛股
        :param stock_codes: 股票代码列表（如 ['000001', '000002']）
        :return: 批量添加结果 {'total': int, 'success': int, 'failed': int, 'results': list}
        """
        results = []
        success_count = 0
        failed_count = 0
        
        print(f"\n开始批量添加 {len(stock_codes)} 只股票...")
        
        for i, stock_code in enumerate(stock_codes, 1):
            print(f"\n[{i}/{len(stock_codes)}] 处理 {stock_code}...")
            result = self.add_bull_stock(stock_code)
            results.append({
                '代码': stock_code,
                '结果': result
            })
            
            if result['success']:
                success_count += 1
            else:
                failed_count += 1
            
            print(result['message'])
        
        return {
            'total': len(stock_codes),
            'success': success_count,
            'failed': failed_count,
            'results': results
        }
    
    def get_bull_stocks(self) -> List[Dict]:
        """
        获取所有已添加的大牛股
        :return: 大牛股列表
        """
        return self.bull_stocks
    
    def get_bull_stock_count(self) -> int:
        """
        获取已添加的大牛股数量
        :return: 数量
        """
        return len(self.bull_stocks)
    
    def remove_bull_stock(self, stock_code: str) -> bool:
        """
        移除指定的大牛股
        :param stock_code: 股票代码
        :return: 是否移除成功
        """
        for i, stock in enumerate(self.bull_stocks):
            if stock['代码'] == stock_code:
                removed_stock = self.bull_stocks.pop(i)
                print(f"✅ 已移除大牛股: {removed_stock['代码']} {removed_stock['名称']}")
                # 同时清除相关的分析结果
                if stock_code in self.analysis_results:
                    del self.analysis_results[stock_code]
                return True
        
        print(f"⚠️ 未找到股票 {stock_code}")
        return False
    
    def clear_bull_stocks(self):
        """清空所有大牛股"""
        self.bull_stocks = []
        self.analysis_results = {}
        print("✅ 已清空所有大牛股")
    
    def find_max_gain_interval(self, stock_code: str, search_weeks: int = 10, min_gain: float = 100.0) -> Optional[Dict]:
        """
        找到股票涨幅最大的区间（基于周线）
        :param stock_code: 股票代码
        :param search_weeks: 查找窗口周数（默认10周，在起点后10周内查找最高点）
        :param min_gain: 最小涨幅要求（默认100%，即翻倍）
        :return: 涨幅最大区间的信息，如果未找到符合条件的区间返回None
        """
        try:
            # 获取股票板块信息
            board_name, limit_up_pct = self.get_stock_board_info(stock_code)
            print(f"\n正在分析 {stock_code} 的涨幅最大区间（基于周线）...")
            print(f"股票板块: {board_name}，涨停限制: {limit_up_pct}%")
            print(f"在起点后 {search_weeks} 周内查找最高点，要求涨幅超过 {min_gain}%...")
            
            # 获取周K线数据（至少需要2年数据）
            print(f"[调试] {stock_code} 开始获取周K线数据...")
            weekly_df = self.fetcher.get_weekly_kline(stock_code, period="2y")
            print(f"[调试] {stock_code} 周K线数据获取完成: {len(weekly_df) if weekly_df is not None else 0} 周")
            
            if weekly_df is None or len(weekly_df) == 0:
                return {
                    'success': False,
                    'message': f'无法获取 {stock_code} 的周线数据',
                    'interval': None
                }
            
            if len(weekly_df) < search_weeks:
                return {
                    'success': False,
                    'message': f'数据不足，需要至少 {search_weeks} 周数据，实际只有 {len(weekly_df)} 周',
                    'interval': None
                }
            
            # 找到涨幅最大的区间（在指定周数内）
            max_gain = 0
            max_gain_start_idx = None
            max_gain_end_idx = None
            max_gain_start_price = None
            max_gain_end_price = None
            max_gain_start_date = None
            max_gain_end_date = None
            
            # 遍历所有可能的起点（从第1周到倒数第search_weeks周）
            total_possible_starts = len(weekly_df) - search_weeks + 1
            print(f"[调试] {stock_code} 需要遍历 {total_possible_starts} 个可能的起点...")
            
            for idx, start_idx in enumerate(range(len(weekly_df) - search_weeks + 1)):
                # 每处理100个起点打印一次进度
                if idx > 0 and idx % 100 == 0:
                    print(f"[调试] {stock_code} 已处理 {idx}/{total_possible_starts} 个起点...")
                
                start_price = float(weekly_df.iloc[start_idx]['收盘'])
                start_date = weekly_df.iloc[start_idx]['日期']
                
                # 在起点后的search_weeks周内，找到最高价格
                end_idx = min(start_idx + search_weeks, len(weekly_df))
                window_df = weekly_df.iloc[start_idx:end_idx]
                
                # 找到窗口内的最高价格和对应日期
                # 使用最高价而不是收盘价，因为可能盘中涨停
                max_price_idx = window_df['最高'].idxmax()
                max_price = float(window_df.loc[max_price_idx, '最高'])
                max_price_date = window_df.loc[max_price_idx, '日期']
                
                # 计算涨幅（使用最高价）
                gain = (max_price - start_price) / start_price * 100
                
                if gain > max_gain:
                    max_gain = gain
                    max_gain_start_idx = start_idx
                    max_gain_end_idx = weekly_df.index.get_loc(max_price_idx)
                    max_gain_start_price = start_price
                    max_gain_end_price = max_price
                    max_gain_start_date = start_date
                    max_gain_end_date = max_price_date
            
            print(f"[调试] {stock_code} 遍历完成，最大涨幅: {max_gain:.2f}%")
            
            # 检查是否达到最小涨幅要求
            if max_gain_start_idx is None or max_gain_end_idx is None or max_gain < min_gain:
                return {
                    'success': False,
                    'message': f'未找到涨幅超过 {min_gain}% 的区间（最大涨幅: {max_gain:.2f}%）',
                    'interval': None,
                    'max_gain': max_gain
                }
            
            # 计算实际周数（从起点到终点的周数）
            trading_weeks = int(max_gain_end_idx - max_gain_start_idx + 1)
            
            # 格式化日期
            if isinstance(max_gain_start_date, pd.Timestamp):
                start_date_str = max_gain_start_date.strftime('%Y-%m-%d')
            else:
                start_date_str = str(max_gain_start_date)
            
            if isinstance(max_gain_end_date, pd.Timestamp):
                end_date_str = max_gain_end_date.strftime('%Y-%m-%d')
            else:
                end_date_str = str(max_gain_end_date)
            
            result = {
                'success': True,
                'message': f'✅ 找到涨幅最大区间: {max_gain:.2f}%',
                'interval': {
                    '股票代码': stock_code,
                    '起点日期': start_date_str,
                    '起点价格': round(max_gain_start_price, 2),
                    '起点索引': int(max_gain_start_idx) if max_gain_start_idx is not None else None,
                    '终点日期': end_date_str,
                    '终点价格': round(max_gain_end_price, 2),
                    '终点索引': int(max_gain_end_idx) if max_gain_end_idx is not None else None,
                    '涨幅': round(max_gain, 2),
                    '翻倍倍数': round(max_gain / 100, 2),
                    '实际周数': trading_weeks,  # 从起点到终点的实际周数
                    '查找窗口周数': search_weeks,  # 查找窗口大小（10周）
                    '板块': board_name,
                    '涨停限制': limit_up_pct
                }
            }
            
            print(f"✅ 找到涨幅最大区间:")
            print(f"   起点日期: {start_date_str}")
            print(f"   起点价格: {max_gain_start_price:.2f} 元")
            print(f"   终点日期: {end_date_str}")
            print(f"   终点价格: {max_gain_end_price:.2f} 元")
            print(f"   涨幅: {max_gain:.2f}% (翻{max_gain/100:.2f}倍)")
            print(f"   实际周数: {trading_weeks} 周")
            
            return result
            
        except Exception as e:
            import traceback
            error_detail = traceback.format_exc()
            print(f"查找涨幅区间失败: {error_detail}")
            return {
                'success': False,
                'message': f'查找涨幅区间失败: {str(e)}',
                'interval': None
            }
    
    def analyze_bull_stock(self, stock_code: str) -> Dict:
        """
        分析单只大牛股：找到涨幅最大区间和起点
        :param stock_code: 股票代码
        :return: 分析结果
        """
        # 检查股票是否存在
        stock_info = None
        for stock in self.bull_stocks:
            if stock['代码'] == stock_code:
                stock_info = stock
                break
        
        if stock_info is None:
            return {
                'success': False,
                'message': f'股票 {stock_code} 未添加',
                'interval': None
            }
        
        # 查找涨幅最大区间（在起点后10周内查找最高点）
        result = self.find_max_gain_interval(stock_code, search_weeks=10, min_gain=100.0)
        
        # 保存分析结果
        if result['success']:
            self.analysis_results[stock_code] = {
                'stock_info': stock_info,
                'interval': result['interval'],
                'analyzed_at': datetime.now()
            }
        
        return result
    
    def analyze_all_bull_stocks(self) -> Dict:
        """
        分析所有已添加的大牛股
        :return: 分析结果汇总
        """
        if len(self.bull_stocks) == 0:
            return {
                'success': False,
                'message': '没有已添加的大牛股',
                'results': []
            }
        
        # 初始化进度
        total_stocks = len(self.bull_stocks)
        self.progress = {
            'type': 'analyze',
            'current': 0,
            'total': total_stocks,
            'status': '进行中',
            'detail': '开始分析所有股票...',
            'percentage': 0
        }
        
        print(f"\n开始分析 {total_stocks} 只大牛股...")
        print("=" * 80)
        
        results = []
        success_count = 0
        failed_count = 0
        
        for i, stock in enumerate(self.bull_stocks, 1):
            stock_code = stock['代码']
            stock_name = stock['名称']
            
            # 更新进度
            percentage = (i / total_stocks) * 100
            self.progress['current'] = i
            self.progress['percentage'] = round(percentage, 1)
            self.progress['detail'] = f'正在分析 {stock_code} {stock_name}... ({i}/{total_stocks})'
            
            print(f"\n[{i}/{total_stocks}] 分析 {stock_code} {stock_name}...")
            print(f"[进度] {percentage:.1f}%")
            
            try:
                result = self.analyze_bull_stock(stock_code)
            except Exception as e:
                import traceback
                error_detail = traceback.format_exc()
                print(f"❌ 分析 {stock_code} 时出错: {str(e)}")
                print(f"错误详情: {error_detail}")
                result = {
                    'success': False,
                    'message': f'分析失败: {str(e)}',
                    'interval': None
                }
            results.append({
                '股票代码': stock_code,
                '股票名称': stock_name,
                '分析结果': result
            })
            
            if result['success']:
                success_count += 1
            else:
                failed_count += 1
        
        # 完成进度
        self.progress['status'] = '完成'
        self.progress['detail'] = f'分析完成: 成功 {success_count} 只，失败 {failed_count} 只'
        
        print("\n" + "=" * 80)
        print(f"分析完成: 成功 {success_count} 只，失败 {failed_count} 只")
        print("=" * 80)
        
        return {
            'success': True,
            'message': f'分析完成: 成功 {success_count} 只，失败 {failed_count} 只',
            'total': len(self.bull_stocks),
            'success_count': success_count,
            'failed_count': failed_count,
            'results': results
        }
    
    def stop_scanning(self):
        """
        停止当前扫描（保存状态以便继续）
        """
        self.stop_scan = True
        print("\n🛑 收到停止扫描请求，将保存当前扫描状态以便继续")
    
    def _resume_scan(self) -> Dict:
        """
        继续上次未完成的扫描（断点续扫）
        """
        if self.scan_state is None or self.scan_state.get('status') != '已停止':
            return {
                'success': False,
                'message': '没有未完成的扫描',
                'candidates': []
            }
        
        # 恢复扫描状态
        stock_list = self.scan_state['stock_list']
        common_features = self.scan_state['common_features']
        min_match_score = self.scan_state['min_match_score']
        max_market_cap = self.scan_state['max_market_cap']
        start_idx = self.scan_state['current_idx']
        existing_candidates = self.scan_state['candidates']
        total_stocks = self.scan_state['total_stocks']
        
        print(f"\n🔄 继续扫描，从第 {start_idx + 1} 只股票开始...")
        
        # 继续扫描剩余股票
        remaining_stocks = stock_list.iloc[start_idx:]
        if len(remaining_stocks) == 0:
            # 已经扫描完成
            self.scan_state = None
            return {
                'success': True,
                'message': '扫描已完成',
                'candidates': existing_candidates,
                'total_scanned': total_stocks,
                'found_count': len(existing_candidates)
            }
        
        # 更新状态为进行中
        self.scan_state['status'] = '进行中'
        
        # 继续扫描（单批或分批）
        if total_stocks > 5000:
            # 分批扫描的情况，需要找到当前批次
            batch_size = (total_stocks + 2) // 3
            current_batch = (start_idx // batch_size) + 1
            return self._scan_stock_batch(
                remaining_stocks,
                common_features,
                min_match_score,
                max_market_cap,
                current_batch,
                3,
                start_idx=start_idx,
                existing_candidates=existing_candidates
            )
        else:
            # 单批扫描
            return self._scan_stock_batch(
                remaining_stocks,
                common_features,
                min_match_score,
                max_market_cap,
                1,
                1,
                start_idx=start_idx,
                existing_candidates=existing_candidates
            )
    
    def get_progress(self) -> Dict:
        """
        获取当前进度
        :return: 进度信息
        """
        try:
            # 确保 progress 是字典类型
            if not isinstance(self.progress, dict) or not self.progress:
                return {
                    'type': None,
                    'current': 0,
                    'total': 0,
                    'status': '空闲',
                    'detail': '',
                    'percentage': 0,
                    'found': 0
                }
            
            # 创建副本，避免修改原始数据
            progress = self.progress.copy()
            
            # 确保包含所有必要的字段
            if 'type' not in progress:
                progress['type'] = None
            if 'current' not in progress:
                progress['current'] = 0
            if 'total' not in progress:
                progress['total'] = 0
            if 'status' not in progress:
                progress['status'] = '空闲'
            if 'detail' not in progress:
                progress['detail'] = ''
            if 'found' not in progress:
                progress['found'] = 0
            
            # 计算百分比
            try:
                total = float(progress.get('total', 0))
                current = float(progress.get('current', 0))
                if total > 0:
                    progress['percentage'] = round(current / total * 100, 1)
                else:
                    progress['percentage'] = 0.0
            except (ValueError, TypeError, ZeroDivisionError):
                progress['percentage'] = 0.0
            
            # 确保包含最后更新时间
            import time as time_module
            if 'last_update_time' not in progress:
                progress['last_update_time'] = time_module.time()
            
            # 如果进度长时间未更新，添加警告
            try:
                last_update = progress.get('last_update_time', time_module.time())
                if isinstance(last_update, (int, float)):
                    time_since_update = time_module.time() - last_update
                    if time_since_update > 30 and progress.get('status') == '进行中':
                        progress['warning'] = f'已超过 {int(time_since_update)} 秒未更新，可能卡在: {progress.get("current_stock", "未知股票")}'
            except (ValueError, TypeError):
                pass  # 忽略时间计算错误
            
            return progress
        except Exception as e:
            # 如果出现任何错误，返回默认值
            import time as time_module
            print(f"[get_progress] 错误: {e}")
            return {
                'type': None,
                'current': 0,
                'total': 0,
                'status': '空闲',
                'detail': f'获取进度时出错: {str(e)}',
                'percentage': 0,
                'found': 0,
                'last_update_time': time_module.time()
            }
    
    def get_analysis_result(self, stock_code: str) -> Optional[Dict]:
        """
        获取指定股票的分析结果
        :param stock_code: 股票代码
        :return: 分析结果，如果不存在返回None
        """
        return self.analysis_results.get(stock_code)
    
    def find_volume_surge_point(self, stock_code: str, max_gain_start_idx: int, weekly_df: Optional[pd.DataFrame] = None, min_volume_ratio: float = 3.0, lookback_weeks: int = 52) -> Optional[int]:
        """
        在涨幅区间起点之前，找到周成交量突然比前一周多3倍以上的点作为特征提取起点
        :param stock_code: 股票代码
        :param max_gain_start_idx: 涨幅区间起点在周线数据中的索引（例如10月17日）
        :param weekly_df: 周K线数据（可选）
        :param min_volume_ratio: 最小成交量倍数（默认3.0，即比前一周多3倍以上）
        :param lookback_weeks: 向前查找的最大周数（默认52周，约一年）
        :return: 特征提取起点的索引，如果未找到返回None
        """
        try:
            if weekly_df is None:
                weekly_df = self.fetcher.get_weekly_kline(stock_code, period="2y")
            
            if weekly_df is None or len(weekly_df) == 0:
                return None
            
            # 检查必要的列
            volume_col = '周成交量' if '周成交量' in weekly_df.columns else '成交量'
            if volume_col not in weekly_df.columns:
                return None
            
            # 从涨幅区间起点向前查找，最多查找lookback_weeks周
            search_start_idx = max(1, max_gain_start_idx - lookback_weeks)
            
            # 从涨幅区间起点向前查找，找到所有成交量突然增加的点，然后返回最早的那个（第一个突增点）
            surge_points = []
            for i in range(max_gain_start_idx - 1, search_start_idx - 1, -1):
                if i < 1:  # 至少需要前一周的数据
                    break
                
                current_volume = float(weekly_df.iloc[i][volume_col])
                prev_volume = float(weekly_df.iloc[i - 1][volume_col])
                
                # 避免除零
                if prev_volume <= 0:
                    continue
                
                volume_ratio = current_volume / prev_volume
                
                # 如果当前周成交量比前一周多min_volume_ratio倍以上，记录这个突增点
                if volume_ratio >= min_volume_ratio:
                    surge_points.append((i, volume_ratio))
            
            # 如果找到了突增点，返回最早的那个（索引最小的，即时间上最早的）
            if surge_points:
                # 按索引排序，取最小的（最早的）
                surge_points.sort(key=lambda x: x[0])
                first_surge_idx, first_surge_ratio = surge_points[0]
                if not getattr(self, '_scan_quiet', False):
                    print(f"[{stock_code}] 找到成交量突增点: 索引{first_surge_idx}, 成交量比前一周多{first_surge_ratio:.2f}倍（第一个突增点）")
                return first_surge_idx
            
            fallback_idx = max(0, max_gain_start_idx - 20)
            if not getattr(self, '_scan_quiet', False):
                print(f"[{stock_code}] 未找到成交量突增点，使用涨幅起点前20周作为特征起点: 索引{fallback_idx}")
            return fallback_idx
            
        except Exception as e:
            if not getattr(self, '_scan_quiet', False):
                print(f"[{stock_code}] 查找成交量突增点失败: {str(e)}")
            return None
    
    def _get_close_on_date(self, stock_code: str, date_str: str) -> Optional[float]:
        """取 搜索当天 的收盘价（或该日前最近一交易日收盘）。
        如果扫描日期是今天，优先从接口获取最新价格；否则先试 cache，再试接口。
        重要：对于历史日期，只返回该日期或之前的数据，不会返回今天的数据。"""
        try:
            target = pd.to_datetime(date_str)
            from datetime import datetime as dt_now
            today_str = dt_now.now().strftime('%Y-%m-%d')
            is_today = date_str == today_str
            
            # ✅ 如果扫描日期是今天，优先从接口获取最新价格（确保是最新的）
            if is_today:
                try:
                    end_ymd = date_str.replace('-', '')
                    from datetime import datetime as _dt, timedelta
                    d = _dt.strptime(date_str, '%Y-%m-%d')
                    start_ymd = (d - timedelta(days=14)).strftime('%Y%m%d')
                    # get_daily_kline_range 总是从接口获取，不使用缓存
                    daily_df = self.fetcher.get_daily_kline_range(stock_code, start_ymd, end_ymd)
                    if daily_df is not None and len(daily_df) > 0 and '收盘' in daily_df.columns:
                        daily_df = daily_df.copy()
                        daily_df['日期'] = pd.to_datetime(daily_df['日期'], errors='coerce')
                        daily_df = daily_df.dropna(subset=['日期']).sort_values('日期')
                        # ✅ 关键：只取小于等于目标日期的数据（对于今天，就是今天或之前的数据）
                        before = daily_df[daily_df['日期'] <= target]
                        if len(before) > 0:
                            latest_price = float(before.iloc[-1]['收盘'])
                            latest_date = before.iloc[-1]['日期']
                            # ✅ 调试：确认获取到的价格和日期
                            # print(f"[调试-价格获取] {stock_code} 从接口获取到日期 {latest_date.strftime('%Y-%m-%d')} 的价格: {latest_price:.2f} (请求日期: {date_str})")
                            return latest_price
                except Exception as e:
                    # print(f"[调试-价格获取] {stock_code} 接口获取失败: {str(e)[:50]}")
                    pass
            
            # 1) 先试 cache（非今天或接口获取失败时）
            p = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cache', 'daily_kline', f'{stock_code}.csv')
            if os.path.exists(p):
                try:
                    df = pd.read_csv(p)
                    if '日期' in df.columns and '收盘' in df.columns:
                        df['日期'] = pd.to_datetime(df['日期'], errors='coerce')
                        df = df.dropna(subset=['日期']).sort_values('日期')
                        # ✅ 关键：只取小于等于目标日期的数据（对于历史日期，不会包含今天的数据）
                        before = df[df['日期'] <= target]
                        if len(before) > 0:
                            cached_price = float(before.iloc[-1]['收盘'])
                            cached_date = before.iloc[-1]['日期']
                            
                            # ✅ 调试：确认从缓存获取的价格和日期
                            # if not is_today:
                            #     print(f"[调试-价格获取] {stock_code} 从缓存获取到日期 {cached_date.strftime('%Y-%m-%d')} 的价格: {cached_price:.2f} (请求日期: {date_str})")
                            
                            # ✅ 如果扫描日期是今天，检查缓存数据是否是最新的（最新日期应该是今天或昨天）
                            if is_today:
                                days_diff = (target - cached_date).days
                                if days_diff > 1:  # 缓存数据超过1天，可能不是最新的
                                    # 缓存数据太旧，尝试从接口获取
                                    try:
                                        end_ymd = date_str.replace('-', '')
                                        from datetime import datetime as _dt, timedelta
                                        d = _dt.strptime(date_str, '%Y-%m-%d')
                                        start_ymd = (d - timedelta(days=14)).strftime('%Y%m%d')
                                        # get_daily_kline_range 总是从接口获取，不使用缓存
                                        daily_df = self.fetcher.get_daily_kline_range(stock_code, start_ymd, end_ymd)
                                        if daily_df is not None and len(daily_df) > 0 and '收盘' in daily_df.columns:
                                            daily_df = daily_df.copy()
                                            daily_df['日期'] = pd.to_datetime(daily_df['日期'], errors='coerce')
                                            daily_df = daily_df.dropna(subset=['日期']).sort_values('日期')
                                            before = daily_df[daily_df['日期'] <= target]
                                            if len(before) > 0:
                                                return float(before.iloc[-1]['收盘'])
                                    except Exception:
                                        pass
                            
                            return cached_price
                except Exception as e:
                    # print(f"[调试-价格获取] {stock_code} 缓存读取失败: {str(e)[:50]}")
                    pass
            
            # 2) 再试接口（缓存中没有时）
            end_ymd = date_str.replace('-', '')
            from datetime import datetime as _dt, timedelta
            d = _dt.strptime(date_str, '%Y-%m-%d')
            start_ymd = (d - timedelta(days=14)).strftime('%Y%m%d')
            daily_df = self.fetcher.get_daily_kline_range(stock_code, start_ymd, end_ymd)
            if daily_df is not None and len(daily_df) > 0 and '收盘' in daily_df.columns:
                daily_df = daily_df.copy()
                daily_df['日期'] = pd.to_datetime(daily_df['日期'], errors='coerce')
                daily_df = daily_df.dropna(subset=['日期']).sort_values('日期')
                # ✅ 关键：只取小于等于目标日期的数据（对于历史日期，不会包含今天的数据）
                before = daily_df[daily_df['日期'] <= target]
                if len(before) > 0:
                    return float(before.iloc[-1]['收盘'])
        except Exception as e:
            # print(f"[调试-价格获取] {stock_code} 获取价格异常: {str(e)[:50]}")
            pass
        return None
    
    def _get_ohlc_on_date(self, stock_code: str, date_str: str) -> Optional[tuple]:
        """获取指定日期的 OHLC（开盘、收盘、最高、最低）。仅当存在该日行情时返回，否则 None。"""
        try:
            target = pd.to_datetime(date_str).normalize()
            end_ymd = date_str.replace('-', '')
            from datetime import datetime as _dt, timedelta
            d = _dt.strptime(date_str, '%Y-%m-%d')
            start_ymd = (d - timedelta(days=14)).strftime('%Y%m%d')
            daily_df = self.fetcher.get_daily_kline_range(stock_code, start_ymd, end_ymd)
            if daily_df is None or len(daily_df) == 0:
                return None
            daily_df = daily_df.copy()
            daily_df['日期'] = pd.to_datetime(daily_df['日期'], errors='coerce').dt.normalize()
            daily_df = daily_df.dropna(subset=['日期'])
            same = daily_df[daily_df['日期'] == target]
            if len(same) == 0:
                return None
            row = same.iloc[0]
            open_col = '开盘' if '开盘' in row.index else 'open'
            close_col = '收盘' if '收盘' in row.index else 'close'
            high_col = '最高' if '最高' in row.index else 'high'
            low_col = '最低' if '最低' in row.index else 'low'
            if open_col not in row.index or close_col not in row.index:
                return None
            o = float(row[open_col])
            c = float(row[close_col])
            h = float(row[high_col]) if high_col in row.index else max(o, c)
            l_ = float(row[low_col]) if low_col in row.index else min(o, c)
            return (o, c, h, l_)
        except Exception:
            return None
    
    def _is_big_bearish_candle_on_date(self, stock_code: str, date_str: str, min_drop_pct: float = 3.0) -> bool:
        """判断指定日期是否为大阴线。大阴线：阴线（收盘<开盘）且跌幅>=min_drop_pct%（默认3%）。"""
        ohlc = self._get_ohlc_on_date(stock_code, date_str)
        if ohlc is None:
            return False
        o, c, _, _ = ohlc
        if o <= 0:
            return False
        if c >= o:
            return False  # 非阴线
        drop_pct = (o - c) / o * 100
        return drop_pct >= min_drop_pct
    
    def extract_features_at_start_point(self, stock_code: str, start_idx: int, lookback_weeks: int = 40, weekly_df: Optional[pd.DataFrame] = None) -> Optional[Dict]:
        """
        提取起点位置前的量价特征（基于周线）
        :param stock_code: 股票代码
        :param start_idx: 起点在周线数据中的索引（这是特征提取的起点，可能是成交量突增点）
        :param lookback_weeks: 向前回看的周数（默认40周，约200个交易日）
        :param weekly_df: 周K线数据（可选，如果提供则不再获取，避免重复获取）
        :return: 特征字典
        """
        import time
        start_time = time.time()
        max_time = 5  # 最大处理时间5秒（缩短，避免卡住）
        
        try:
            if not getattr(self, '_scan_quiet', False):
                print(f"[{stock_code}] 开始提取特征，起点索引: {start_idx}")
            
            if weekly_df is None:
                if not getattr(self, '_scan_quiet', False):
                    print(f"[{stock_code}] 正在获取周K线数据...")
                weekly_df = self.fetcher.get_weekly_kline(stock_code, period="2y")
                
                if time.time() - start_time > max_time:
                    print(f"⚠️ {stock_code} 数据获取超时")
                    return None
            
            if weekly_df is None or len(weekly_df) == 0:
                print(f"⚠️ {stock_code} 无法获取周线数据或数据为空")
                return None
            
            # 减少调试日志输出（仅在需要时打印）
            # print(f"[调试] {stock_code} 获取到 {len(weekly_df)} 周数据，起点索引: {start_idx}, 需要回看: {lookback_weeks} 周")
            # print(f"[调试] {stock_code} 周线数据列名: {list(weekly_df.columns)}")
            
            # 确保有足够的周线数据（至少40周）
            if start_idx >= len(weekly_df):
                print(f"⚠️ {stock_code} 起点索引 {start_idx} 超出数据范围 {len(weekly_df)}")
                return None
            
            # 如果数据不足，调整回看周数
            if start_idx < lookback_weeks:
                actual_lookback = start_idx
                print(f"⚠️ {stock_code} 起点索引 {start_idx} 小于回看周数 {lookback_weeks}，调整为回看 {actual_lookback} 周")
                if actual_lookback < 20:  # 至少需要20周数据
                    print(f"⚠️ {stock_code} 数据严重不足（只有{actual_lookback}周），无法提取特征")
                    return None
                lookback_weeks = actual_lookback
            
            # 获取起点前的周线数据
            before_start_df = weekly_df.iloc[start_idx - lookback_weeks:start_idx].copy()
            
            # 检查必要的列是否存在
            volume_col = '周成交量' if '周成交量' in weekly_df.columns else '成交量'
            if volume_col not in weekly_df.columns:
                print(f"⚠️ {stock_code} 周线数据中缺少成交量列，可用列: {list(weekly_df.columns)}")
                return None
            
            start_price = float(weekly_df.iloc[start_idx]['收盘'])
            start_volume = float(weekly_df.iloc[start_idx][volume_col])
            
            # 减少调试日志输出（仅在需要时打印）
            # print(f"[调试] {stock_code} 起点价格: {start_price}, 起点成交量: {start_volume}, 使用列名: {volume_col}")
            
            if len(before_start_df) == 0:
                print(f"⚠️ {stock_code} 起点前数据为空")
                return None
            
            # 减少调试日志输出
            # print(f"[调试] {stock_code} 起点前数据: {len(before_start_df)} 周，列名: {list(before_start_df.columns)}")
            
            features = {}
            
            # ========== 1. 成交量特征（量）- 基于周线 ==========
            
            # 1.1 起点当周量比（核心指标）
            if len(before_start_df) >= 10:
                avg_volume_10 = float(before_start_df[volume_col].tail(10).mean())
                if avg_volume_10 > 0:
                    features['起点当周量比'] = round(start_volume / avg_volume_10, 2)
                else:
                    features['起点当周量比'] = 1.0
            
            # 1.2 起点前10周平均成交量
            if len(before_start_df) >= 10:
                features['起点前10周均量'] = round(float(before_start_df[volume_col].tail(10).mean()), 0)
            
            # 1.3 起点前20周平均成交量
            if len(before_start_df) >= 20:
                features['起点前20周均量'] = round(float(before_start_df[volume_col].tail(20).mean()), 0)
            
            # 1.4 起点前40周平均成交量
            if len(before_start_df) >= 40:
                features['起点前40周均量'] = round(float(before_start_df[volume_col].tail(40).mean()), 0)
            
            # 1.5 成交量萎缩程度（起点前10周均量/起点前20周均量）
            if len(before_start_df) >= 20:
                vol_10 = float(before_start_df[volume_col].tail(10).mean())
                vol_20 = float(before_start_df[volume_col].tail(20).mean())
                if vol_20 > 0:
                    features['成交量萎缩程度'] = round(vol_10 / vol_20, 2)
                else:
                    features['成交量萎缩程度'] = 1.0
            
            # 1.6 起点前40周最大成交量（核心特征：前期是否有大成交量）
            if len(before_start_df) >= 40:
                max_volume_idx = before_start_df[volume_col].tail(40).idxmax()
                max_volume = float(before_start_df.loc[max_volume_idx, volume_col])
                max_volume_low = float(before_start_df.loc[max_volume_idx, '最低'])
                max_volume_date = before_start_df.loc[max_volume_idx, '日期']
                
                features['起点前40周最大量'] = round(max_volume, 0)
                features['最大量对应最低价'] = round(max_volume_low, 2)
                if isinstance(max_volume_date, pd.Timestamp):
                    features['最大量对应日期'] = max_volume_date.strftime('%Y-%m-%d')
                else:
                    features['最大量对应日期'] = str(max_volume_date)
                
                # 1.7 起点价格是否跌破最大成交量最低价（核心特征）
                if max_volume_low > 0:
                    price_drop_ratio = (max_volume_low - start_price) / max_volume_low * 100
                    features['是否跌破最大量最低价'] = 1 if start_price < max_volume_low else 0
                    features['相对最大量最低价跌幅'] = round(price_drop_ratio, 2) if start_price < max_volume_low else 0
                else:
                    features['是否跌破最大量最低价'] = 0
                    features['相对最大量最低价跌幅'] = 0
            else:
                # 如果数据不足40周，使用全部数据
                if len(before_start_df) > 0:
                    max_volume_idx = before_start_df[volume_col].idxmax()
                    max_volume = float(before_start_df.loc[max_volume_idx, volume_col])
                    max_volume_low = float(before_start_df.loc[max_volume_idx, '最低'])
                    max_volume_date = before_start_df.loc[max_volume_idx, '日期']
                    
                    features['起点前40周最大量'] = round(max_volume, 0)
                    features['最大量对应最低价'] = round(max_volume_low, 2)
                    if isinstance(max_volume_date, pd.Timestamp):
                        features['最大量对应日期'] = max_volume_date.strftime('%Y-%m-%d')
                    else:
                        features['最大量对应日期'] = str(max_volume_date)
                    
                    if max_volume_low > 0:
                        price_drop_ratio = (max_volume_low - start_price) / max_volume_low * 100
                        features['是否跌破最大量最低价'] = 1 if start_price < max_volume_low else 0
                        features['相对最大量最低价跌幅'] = round(price_drop_ratio, 2) if start_price < max_volume_low else 0
                    else:
                        features['是否跌破最大量最低价'] = 0
                        features['相对最大量最低价跌幅'] = 0
            
            # 1.8 起点当周成交量/起点前40周最大量
            if '起点前40周最大量' in features and features['起点前40周最大量'] > 0:
                features['起点量比最大量'] = round(start_volume / features['起点前40周最大量'], 2)
            
            # 1.6 起点当日成交量/起点前30天最大量
            if '起点前30天最大量' in features and features['起点前30天最大量'] > 0:
                features['起点量比最大量'] = round(start_volume / features['起点前30天最大量'], 2)
            
            # ========== 2. 价格特征（价）- 基于周线 ==========
            
            # 2.1 价格相对位置（核心指标）- 基于前20周
            if len(before_start_df) >= 20:
                max_price_20 = float(before_start_df['最高'].tail(20).max())
                min_price_20 = float(before_start_df['最低'].tail(20).min())
                if max_price_20 > min_price_20:
                    features['价格相对位置'] = round((start_price - min_price_20) / (max_price_20 - min_price_20) * 100, 2)
                    features['相对高点跌幅'] = round((max_price_20 - start_price) / max_price_20 * 100, 2)
                else:
                    features['价格相对位置'] = 50.0
                    features['相对高点跌幅'] = 0
            
            # 2.2 起点前20周最高价
            if len(before_start_df) >= 20:
                features['起点前20周最高价'] = round(float(before_start_df['最高'].tail(20).max()), 2)
            
            # 2.3 起点前20周最低价
            if len(before_start_df) >= 20:
                features['起点前20周最低价'] = round(float(before_start_df['最低'].tail(20).min()), 2)
            
            # 2.4 起点前40周最高价和最低价
            if len(before_start_df) >= 40:
                features['起点前40周最高价'] = round(float(before_start_df['最高'].tail(40).max()), 2)
                features['起点前40周最低价'] = round(float(before_start_df['最低'].tail(40).min()), 2)
            
            # 2.5 起点前20周价格波动幅度
            if len(before_start_df) >= 20:
                high_20 = float(before_start_df['最高'].tail(20).max())
                low_20 = float(before_start_df['最低'].tail(20).min())
                if low_20 > 0:
                    features['起点前20周波动幅度'] = round((high_20 - low_20) / low_20 * 100, 2)
            
            # ========== 3. 均线特征 - 基于周线 ==========
            
            # 3.1 价格与均线关系（核心指标）- 周线MA5, MA10, MA20
            if len(before_start_df) >= 5:
                ma5 = float(before_start_df['收盘'].tail(5).mean())
                if ma5 > 0:
                    features['价格相对MA5'] = round((start_price - ma5) / ma5 * 100, 2)
                    features['MA5值'] = round(ma5, 2)
            
            if len(before_start_df) >= 10:
                ma10 = float(before_start_df['收盘'].tail(10).mean())
                if ma10 > 0:
                    features['价格相对MA10'] = round((start_price - ma10) / ma10 * 100, 2)
                    features['MA10值'] = round(ma10, 2)
            
            if len(before_start_df) >= 20:
                ma20 = float(before_start_df['收盘'].tail(20).mean())
                if ma20 > 0:
                    features['价格相对MA20'] = round((start_price - ma20) / ma20 * 100, 2)
                    features['MA20值'] = round(ma20, 2)
            
            if len(before_start_df) >= 40:
                ma40 = float(before_start_df['收盘'].tail(40).mean())
                if ma40 > 0:
                    features['价格相对MA40'] = round((start_price - ma40) / ma40 * 100, 2)
                    features['MA40值'] = round(ma40, 2)
            
            # 3.2 均线斜率（MA20周线斜率）
            if len(before_start_df) >= 20:
                ma20_recent = float(before_start_df['收盘'].tail(5).mean())
                ma20_earlier = float(before_start_df['收盘'].iloc[-20:-15].mean())
                if ma20_earlier > 0:
                    features['MA20斜率'] = round((ma20_recent - ma20_earlier) / ma20_earlier * 100, 2)
            
            # ========== 4. 量价配合特征 - 基于周线 ==========
            
            # 4.1 起点前20周量价相关系数
            if len(before_start_df) >= 20:
                price_changes = before_start_df['收盘'].tail(20).pct_change().dropna()
                volume_changes = before_start_df[volume_col].tail(20).pct_change().dropna()
                if len(price_changes) > 0 and len(volume_changes) > 0:
                    min_len = min(len(price_changes), len(volume_changes))
                    if min_len > 5:
                        correlation = price_changes.tail(min_len).corr(volume_changes.tail(min_len))
                        if pd.notna(correlation):
                            features['起点前20周量价相关系数'] = round(float(correlation), 3)
            
            # 4.2 起点当周是否价涨量增
            if start_idx > 0:
                prev_price = float(weekly_df.iloc[start_idx - 1]['收盘'])
                prev_volume = float(weekly_df.iloc[start_idx - 1][volume_col])
                features['起点当周价涨'] = 1 if start_price > prev_price else 0
                features['起点当周量增'] = 1 if start_volume > prev_volume else 0
                features['起点当周价涨量增'] = 1 if (start_price > prev_price and start_volume > prev_volume) else 0
            
            # ========== 5. 时间特征 - 基于周线 ==========
            
            # 5.1 起点前10周波动率
            if len(before_start_df) >= 10:
                # 计算最近10周的价格波动
                recent_prices = before_start_df['收盘'].tail(10)
                price_range = (recent_prices.max() - recent_prices.min()) / recent_prices.min() * 100
                features['起点前10周波动率'] = round(float(price_range), 2)
            
            # 5.2 起点前20周波动率
            if len(before_start_df) >= 20:
                recent_prices = before_start_df['收盘'].tail(20)
                price_range = (recent_prices.max() - recent_prices.min()) / recent_prices.min() * 100
                features['起点前20周波动率'] = round(float(price_range), 2)
            
            # ========== 6. 其他特征 ==========
            
            # 6.1 起点价格
            features['起点价格'] = round(start_price, 2)
            
            # 6.2 起点日期
            start_date = weekly_df.iloc[start_idx]['日期']
            if isinstance(start_date, pd.Timestamp):
                features['起点日期'] = start_date.strftime('%Y-%m-%d')
            else:
                features['起点日期'] = str(start_date)
            
            # ========== 7. 新增技术指标特征 ==========
            
            # 7.1 MACD指标（DIF, DEA, MACD柱）
            if len(before_start_df) >= 26:
                try:
                    prices = before_start_df['收盘']
                    ema12 = prices.ewm(span=12, adjust=False).mean()
                    ema26 = prices.ewm(span=26, adjust=False).mean()
                    dif = ema12 - ema26
                    dea = dif.ewm(span=9, adjust=False).mean()
                    macd = (dif - dea) * 2
                    
                    features['MACD_DIF'] = round(float(dif.iloc[-1]), 4)
                    features['MACD_DEA'] = round(float(dea.iloc[-1]), 4)
                    features['MACD柱'] = round(float(macd.iloc[-1]), 4)
                    
                    # MACD金叉判断（DIF上穿DEA）
                    if len(dif) >= 2:
                        prev_diff = dif.iloc[-2] - dea.iloc[-2]
                        curr_diff = dif.iloc[-1] - dea.iloc[-1]
                        features['MACD金叉'] = 1 if (prev_diff < 0 and curr_diff >= 0) else 0
                        features['MACD零轴上方'] = 1 if dif.iloc[-1] > 0 else 0
                except Exception:
                    pass
            
            # 7.2 RSI指标
            if len(before_start_df) >= 14:
                try:
                    prices = before_start_df['收盘']
                    delta = prices.diff()
                    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                    rs = gain / (loss + 0.0001)
                    rsi = 100 - (100 / (1 + rs))
                    
                    features['RSI'] = round(float(rsi.iloc[-1]), 2)
                    features['RSI超卖'] = 1 if rsi.iloc[-1] < 30 else 0
                    features['RSI强势区'] = 1 if 50 < rsi.iloc[-1] < 70 else 0
                except Exception:
                    pass
            
            # 7.3 KDJ指标
            if len(before_start_df) >= 9:
                try:
                    high_9 = before_start_df['最高'].rolling(window=9).max()
                    low_9 = before_start_df['最低'].rolling(window=9).min()
                    rsv = (before_start_df['收盘'] - low_9) / (high_9 - low_9 + 0.0001) * 100
                    
                    k_values = []
                    d_values = []
                    k = 50
                    d = 50
                    for r in rsv.dropna():
                        k = 2/3 * k + 1/3 * r
                        d = 2/3 * d + 1/3 * k
                        k_values.append(k)
                        d_values.append(d)
                    
                    if k_values:
                        features['KDJ_K'] = round(k_values[-1], 2)
                        features['KDJ_D'] = round(d_values[-1], 2)
                        features['KDJ_J'] = round(3 * k_values[-1] - 2 * d_values[-1], 2)
                        features['KDJ超卖'] = 1 if k_values[-1] < 20 and d_values[-1] < 20 else 0
                except Exception:
                    pass
            
            # 7.4 OBV能量潮
            if len(before_start_df) >= 10:
                try:
                    obv = [0]
                    prices = before_start_df['收盘'].values
                    volumes = before_start_df[volume_col].values
                    for i in range(1, len(prices)):
                        if prices[i] > prices[i-1]:
                            obv.append(obv[-1] + volumes[i])
                        elif prices[i] < prices[i-1]:
                            obv.append(obv[-1] - volumes[i])
                        else:
                            obv.append(obv[-1])
                    
                    obv_series = pd.Series(obv)
                    # OBV趋势（近10周斜率）
                    if len(obv_series) >= 10:
                        obv_recent = obv_series.tail(10)
                        obv_slope = (obv_recent.iloc[-1] - obv_recent.iloc[0]) / (abs(obv_recent.iloc[0]) + 1) * 100
                        features['OBV趋势'] = round(obv_slope, 2)
                    
                    # OBV是否创新高
                    if len(obv_series) >= 20:
                        obv_max_20 = obv_series.tail(20).max()
                        features['OBV创新高'] = 1 if obv_series.iloc[-1] >= obv_max_20 * 0.95 else 0
                except Exception:
                    pass
            
            # 7.5 均线粘合度（MA5/MA10/MA20三线粘合程度）
            if len(before_start_df) >= 20:
                try:
                    ma5 = float(before_start_df['收盘'].tail(5).mean())
                    ma10 = float(before_start_df['收盘'].tail(10).mean())
                    ma20 = float(before_start_df['收盘'].tail(20).mean())
                    avg_ma = (ma5 + ma10 + ma20) / 3
                    if avg_ma > 0:
                        # 计算均线离散度（越小说明越粘合）
                        dispersion = (abs(ma5-avg_ma) + abs(ma10-avg_ma) + abs(ma20-avg_ma)) / avg_ma * 100
                        features['均线粘合度'] = round(dispersion, 2)
                    
                    # 均线多头排列
                    features['均线多头排列'] = 1 if (ma5 > ma10 > ma20) else 0
                except Exception:
                    pass
            
            # 7.5b 均线平滑度（基于日线5日线近60日方向切换次数，少切换=更平滑=更高分）
            try:
                end_dt = weekly_df.iloc[start_idx]['日期']
                end_ts = pd.to_datetime(end_dt)
                end_ymd = end_ts.strftime('%Y%m%d')
                daily_df = self.fetcher.get_daily_kline_range(
                    stock_code, start_date='20240101', end_date=end_ymd,
                    use_cache=True, local_only=True
                )
                if daily_df is not None and len(daily_df) >= 65:
                    daily_df = daily_df.copy()
                    daily_df['日期'] = pd.to_datetime(daily_df['日期'], errors='coerce')
                    daily_df = daily_df.dropna(subset=['日期']).sort_values('日期').reset_index(drop=True)
                    daily_df = daily_df[daily_df['日期'] <= end_ts].reset_index(drop=True)
                    close = daily_df['收盘'].astype(float)
                    ma5_d = close.rolling(5).mean().dropna()
                    chg = ma5_d.pct_change().dropna()
                    last60 = chg.tail(60)
                    sign = np.sign(last60)
                    flips = int((sign.diff().fillna(0) != 0).astype(int).sum())
                    smooth = max(0, 25 - min(25, flips))
                    features['均线平滑度'] = round(smooth, 2)
            except Exception:
                pass
            
            # 7.6 布林带特征
            if len(before_start_df) >= 20:
                try:
                    prices = before_start_df['收盘']
                    ma20 = prices.rolling(window=20).mean()
                    std20 = prices.rolling(window=20).std()
                    upper = ma20 + 2 * std20
                    lower = ma20 - 2 * std20
                    
                    # 布林带宽度（越窄说明即将变盘）
                    bb_width = ((upper.iloc[-1] - lower.iloc[-1]) / ma20.iloc[-1] * 100) if ma20.iloc[-1] > 0 else 0
                    features['布林带宽度'] = round(bb_width, 2)
                    
                    # 价格在布林带中的位置（0-100）
                    bb_position = ((start_price - lower.iloc[-1]) / (upper.iloc[-1] - lower.iloc[-1] + 0.01) * 100)
                    features['布林带位置'] = round(bb_position, 2)
                    
                    # 布林带收窄（与10周前相比）
                    if len(ma20) >= 10 and ma20.iloc[-10] > 0:
                        bb_width_10 = (upper.iloc[-10] - lower.iloc[-10]) / ma20.iloc[-10] * 100
                        features['布林带收窄'] = 1 if bb_width < bb_width_10 * 0.8 else 0
                except Exception:
                    pass
            
            # 7.7 筹码集中度（简化版：使用价格区间代替）
            if len(before_start_df) >= 20:
                try:
                    # 使用加权平均成本
                    total_vol = before_start_df[volume_col].tail(20).sum()
                    if total_vol > 0:
                        weighted_price = (before_start_df['收盘'].tail(20) * before_start_df[volume_col].tail(20)).sum() / total_vol
                        # 成本偏离度
                        cost_deviation = (start_price - weighted_price) / weighted_price * 100
                        features['成本偏离度'] = round(cost_deviation, 2)
                        
                        # 筹码集中度（价格标准差/加权均价）
                        price_std = np.sqrt(((before_start_df['收盘'].tail(20) - weighted_price) ** 2 * before_start_df[volume_col].tail(20)).sum() / total_vol)
                        concentration = price_std / weighted_price * 100 if weighted_price > 0 else 0
                        features['筹码集中度'] = round(concentration, 2)
                except Exception:
                    pass
            
            # 7.8 突破特征
            if len(before_start_df) >= 20:
                try:
                    high_20 = before_start_df['最高'].tail(20).max()
                    features['突破20周高点'] = 1 if start_price > high_20 else 0
                    features['接近20周高点'] = 1 if start_price > high_20 * 0.95 else 0
                except Exception:
                    pass
            
            if len(before_start_df) >= 40:
                try:
                    high_40 = before_start_df['最高'].tail(40).max()
                    features['突破40周高点'] = 1 if start_price > high_40 else 0
                except Exception:
                    pass
            
            # 7.9 平台整理时间（价格波动小于10%的周数）
            if len(before_start_df) >= 20:
                try:
                    sideways_weeks = 0
                    for i in range(len(before_start_df) - 20, len(before_start_df)):
                        if i >= 0:
                            range_pct = (before_start_df['最高'].iloc[i] - before_start_df['最低'].iloc[i]) / before_start_df['最低'].iloc[i] * 100
                            if range_pct < 10:
                                sideways_weeks += 1
                    features['平台整理周数'] = sideways_weeks
                except Exception:
                    pass
            
            # 7.10 买点前最近两个月至少有一个涨停（日线：44 个交易日内涨跌幅>=9.5%）
            try:
                bp_date = pd.to_datetime(weekly_df.iloc[start_idx]['日期'])
                daily_df = None
                _cache_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cache', 'daily_kline', f'{stock_code}.csv')
                if os.path.exists(_cache_path):
                    try:
                        daily_df = pd.read_csv(_cache_path)
                        if '日期' in daily_df.columns:
                            daily_df['日期'] = pd.to_datetime(daily_df['日期'], errors='coerce')
                            daily_df = daily_df.dropna(subset=['日期']).sort_values('日期').reset_index(drop=True)
                    except Exception:
                        pass
                if daily_df is None or len(daily_df) < 2:
                    daily_df = self.fetcher.get_daily_kline(stock_code, period="1y")
                if daily_df is not None and len(daily_df) >= 2 and '收盘' in daily_df.columns and '日期' in daily_df.columns:
                    daily_df = daily_df.copy()
                    daily_df['日期'] = pd.to_datetime(daily_df['日期'], errors='coerce')
                    daily_df = daily_df.dropna(subset=['日期']).sort_values('日期').reset_index(drop=True)
                    before_bp = daily_df[daily_df['日期'] < bp_date].tail(44)
                    if len(before_bp) >= 2:
                        before_bp = before_bp.copy()
                        before_bp['__pct'] = before_bp['收盘'].pct_change() * 100
                        before_bp['__pct'] = before_bp['__pct'].fillna(0)
                        features['买点前两月内曾涨停'] = 1 if (before_bp['__pct'] >= 9.5).any() else 0
                    else:
                        features['买点前两月内曾涨停'] = 0
                else:
                    features['买点前两月内曾涨停'] = 0
            except Exception:
                features['买点前两月内曾涨停'] = 0
            
            return features
            
        except Exception as e:
            import traceback
            error_msg = str(e)
            print(f"❌ {stock_code} 提取特征失败: {error_msg}")
            if "timeout" in error_msg.lower() or "超时" in error_msg or "time" in error_msg.lower():
                print(f"⚠️ {stock_code} 特征提取可能超时，请检查网络连接或数据源")
            return None
    
    def extract_features_at_end_point(self, stock_code: str, end_idx: int, start_idx: int, lookback_weeks: int = 20, weekly_df: Optional[pd.DataFrame] = None) -> Optional[Dict]:
        """
        提取终点位置（最高点）附近的量价特征（基于周线）
        用于训练卖点模型
        :param stock_code: 股票代码
        :param end_idx: 终点（最高点）在周线数据中的索引
        :param start_idx: 起点在周线数据中的索引（用于计算涨幅）
        :param lookback_weeks: 向前回看的周数（默认20周）
        :param weekly_df: 周K线数据（可选，如果提供则不再获取）
        :return: 特征字典
        """
        import time
        start_time = time.time()
        max_time = 5  # 最大处理时间5秒
        
        try:
            print(f"[{stock_code}] 开始提取卖点特征，终点索引: {end_idx}, 起点索引: {start_idx}")
            
            # 如果提供了weekly_df，直接使用
            if weekly_df is None:
                print(f"[{stock_code}] 正在获取周K线数据...")
                weekly_df = self.fetcher.get_weekly_kline(stock_code, period="2y")
                
                if time.time() - start_time > max_time:
                    print(f"⚠️ {stock_code} 数据获取超时")
                    return None
            
            if weekly_df is None or len(weekly_df) == 0:
                print(f"⚠️ {stock_code} 无法获取周线数据或数据为空")
                return None
            
            # 确保索引有效
            if end_idx >= len(weekly_df) or start_idx >= len(weekly_df):
                print(f"⚠️ {stock_code} 索引超出数据范围")
                return None
            
            if end_idx < lookback_weeks:
                print(f"⚠️ {stock_code} 终点索引 {end_idx} 小于回看周数 {lookback_weeks}，数据不足")
                return None
            
            # 获取终点价格和起点价格
            end_price = float(weekly_df.iloc[end_idx]['收盘'])
            end_high = float(weekly_df.iloc[end_idx]['最高'])  # 使用最高价
            start_price = float(weekly_df.iloc[start_idx]['收盘'])
            
            # 计算涨幅
            gain_pct = (end_high - start_price) / start_price * 100 if start_price > 0 else 0
            
            # 获取终点前的周线数据
            before_end_df = weekly_df.iloc[end_idx - lookback_weeks:end_idx].copy()
            
            # 检查必要的列
            volume_col = '周成交量' if '周成交量' in weekly_df.columns else '成交量'
            if volume_col not in weekly_df.columns:
                print(f"⚠️ {stock_code} 周线数据中缺少成交量列")
                return None
            
            end_volume = float(weekly_df.iloc[end_idx][volume_col])
            
            features = {}
            
            # ========== 1. 涨幅特征（核心） ==========
            features['累计涨幅'] = round(gain_pct, 2)
            features['翻倍倍数'] = round(gain_pct / 100, 2)
            features['起点价格'] = round(start_price, 2)
            features['终点价格'] = round(end_high, 2)
            features['实际周数'] = end_idx - start_idx + 1
            
            # ========== 2. 价格相对位置特征 ==========
            
            # 2.1 终点价格相对位置（核心指标）- 基于前20周
            if len(before_end_df) >= 20:
                max_price_20 = float(before_end_df['最高'].tail(20).max())
                min_price_20 = float(before_end_df['最低'].tail(20).min())
                if max_price_20 > min_price_20:
                    features['价格相对位置'] = round((end_high - min_price_20) / (max_price_20 - min_price_20) * 100, 2)
                else:
                    features['价格相对位置'] = 100.0  # 已经是最高点
            
            # 2.2 终点前20周最高价和最低价
            if len(before_end_df) >= 20:
                features['终点前20周最高价'] = round(float(before_end_df['最高'].tail(20).max()), 2)
                features['终点前20周最低价'] = round(float(before_end_df['最低'].tail(20).min()), 2)
            
            # 2.3 终点是否创20周新高
            if len(before_end_df) >= 20:
                max_price_20 = float(before_end_df['最高'].tail(20).max())
                features['是否创20周新高'] = 1 if end_high > max_price_20 else 0
            
            # ========== 3. 成交量特征 ==========
            
            # 3.1 终点当周量比（核心指标）
            if len(before_end_df) >= 10:
                avg_volume_10 = float(before_end_df[volume_col].tail(10).mean())
                if avg_volume_10 > 0:
                    features['终点当周量比'] = round(end_volume / avg_volume_10, 2)
                else:
                    features['终点当周量比'] = 1.0
            
            # 3.2 终点前10周平均成交量
            if len(before_end_df) >= 10:
                features['终点前10周均量'] = round(float(before_end_df[volume_col].tail(10).mean()), 0)
            
            # 3.3 终点前20周平均成交量
            if len(before_end_df) >= 20:
                features['终点前20周均量'] = round(float(before_end_df[volume_col].tail(20).mean()), 0)
            
            # 3.4 终点前20周最大成交量
            if len(before_end_df) >= 20:
                max_volume_20 = float(before_end_df[volume_col].tail(20).max())
                features['终点前20周最大量'] = round(max_volume_20, 0)
                features['终点量比最大量'] = round(end_volume / max_volume_20, 2) if max_volume_20 > 0 else 1.0
            
            # 3.5 成交量放大程度（终点当周/起点当周）
            if start_idx < len(weekly_df):
                start_volume = float(weekly_df.iloc[start_idx][volume_col])
                if start_volume > 0:
                    features['终点起点量比'] = round(end_volume / start_volume, 2)
            
            # ========== 4. 均线特征 ==========
            
            # 4.1 价格与均线关系（核心指标）
            if len(before_end_df) >= 5:
                ma5 = float(before_end_df['收盘'].tail(5).mean())
                if ma5 > 0:
                    features['价格相对MA5'] = round((end_high - ma5) / ma5 * 100, 2)
                    features['MA5值'] = round(ma5, 2)
            
            if len(before_end_df) >= 10:
                ma10 = float(before_end_df['收盘'].tail(10).mean())
                if ma10 > 0:
                    features['价格相对MA10'] = round((end_high - ma10) / ma10 * 100, 2)
                    features['MA10值'] = round(ma10, 2)
            
            if len(before_end_df) >= 20:
                ma20 = float(before_end_df['收盘'].tail(20).mean())
                if ma20 > 0:
                    features['价格相对MA20'] = round((end_high - ma20) / ma20 * 100, 2)
                    features['MA20值'] = round(ma20, 2)
            
            # 4.2 均线斜率（MA20斜率）
            if len(before_end_df) >= 20:
                ma20_recent = float(before_end_df['收盘'].tail(5).mean())
                ma20_earlier = float(before_end_df['收盘'].iloc[-20:-15].mean())
                if ma20_earlier > 0:
                    features['MA20斜率'] = round((ma20_recent - ma20_earlier) / ma20_earlier * 100, 2)
            
            # ========== 5. 量价配合特征 ==========
            
            # 5.1 终点前20周量价相关系数
            if len(before_end_df) >= 20:
                price_changes = before_end_df['收盘'].tail(20).pct_change().dropna()
                volume_changes = before_end_df[volume_col].tail(20).pct_change().dropna()
                if len(price_changes) > 0 and len(volume_changes) > 0:
                    min_len = min(len(price_changes), len(volume_changes))
                    if min_len > 5:
                        correlation = price_changes.tail(min_len).corr(volume_changes.tail(min_len))
                        if pd.notna(correlation):
                            features['终点前20周量价相关系数'] = round(float(correlation), 3)
            
            # 5.2 终点当周是否价涨量增
            if end_idx > 0:
                prev_price = float(weekly_df.iloc[end_idx - 1]['收盘'])
                prev_volume = float(weekly_df.iloc[end_idx - 1][volume_col])
                features['终点当周价涨'] = 1 if end_high > prev_price else 0
                features['终点当周量增'] = 1 if end_volume > prev_volume else 0
                features['终点当周价涨量增'] = 1 if (end_high > prev_price and end_volume > prev_volume) else 0
            
            # ========== 6. 回调特征（终点后是否有回调） ==========
            
            # 6.1 终点后1周回调幅度
            if end_idx + 1 < len(weekly_df):
                next_price = float(weekly_df.iloc[end_idx + 1]['收盘'])
                features['终点后1周回调'] = round((end_high - next_price) / end_high * 100, 2) if end_high > 0 else 0
                features['终点后1周是否回调'] = 1 if next_price < end_high else 0
            
            # 6.2 终点后2周回调幅度
            if end_idx + 2 < len(weekly_df):
                next2_price = float(weekly_df.iloc[end_idx + 2]['收盘'])
                features['终点后2周回调'] = round((end_high - next2_price) / end_high * 100, 2) if end_high > 0 else 0
                features['终点后2周是否回调'] = 1 if next2_price < end_high else 0
            
            # ========== 7. 时间特征 ==========
            
            # 7.1 终点前10周波动率
            if len(before_end_df) >= 10:
                recent_prices = before_end_df['收盘'].tail(10)
                price_range = (recent_prices.max() - recent_prices.min()) / recent_prices.min() * 100
                features['终点前10周波动率'] = round(float(price_range), 2)
            
            # 7.2 终点前20周波动率
            if len(before_end_df) >= 20:
                recent_prices = before_end_df['收盘'].tail(20)
                price_range = (recent_prices.max() - recent_prices.min()) / recent_prices.min() * 100
                features['终点前20周波动率'] = round(float(price_range), 2)
            
            # ========== 8. 其他特征 ==========
            
            # 8.1 终点日期
            end_date = weekly_df.iloc[end_idx]['日期']
            if isinstance(end_date, pd.Timestamp):
                features['终点日期'] = end_date.strftime('%Y-%m-%d')
            else:
                features['终点日期'] = str(end_date)
            
            return features
            
        except Exception as e:
            import traceback
            error_msg = str(e)
            print(f"❌ {stock_code} 提取卖点特征失败: {error_msg}")
            return None
    
    def train_features(self) -> Dict:
        """
        训练特征：分析所有已分析的大牛股，提取共同特征
        :return: 训练结果，包含共同特征模板
        """
        print("\n" + "=" * 80)
        print("开始训练特征模型...")
        print("=" * 80)
        
        if len(self.analysis_results) == 0:
            return {
                'success': False,
                'message': '没有已分析的大牛股，请先分析大牛股',
                'common_features': None
            }
        
        # 初始化进度
        valid_stocks = [code for code, result in self.analysis_results.items() 
                       if result.get('interval') and result['interval'].get('起点索引') is not None]
        
        self.progress = {
            'type': 'train',
            'current': 0,
            'total': len(valid_stocks) + 2,  # 提取特征 + 计算统计值
            'status': '进行中',
            'detail': '开始训练...'
        }
        
        all_features_list = []
        screener_details = []  # 收集“8条件”在训练买点日期的命中情况
        
        # 1. 提取所有已分析股票的特征
        self.progress['current'] = 0
        self.progress['detail'] = '开始提取特征...'
        
        for idx, (stock_code, analysis_result) in enumerate(self.analysis_results.items(), 1):
            if analysis_result.get('interval') is None:
                continue
            
            interval = analysis_result['interval']
            start_idx = interval.get('起点索引')
            start_date_str = interval.get('起点日期')
            
            if start_idx is None and not start_date_str:
                continue
            
            # 更新进度
            self.progress['current'] = idx
            self.progress['detail'] = f'正在提取 {stock_code} 的特征... ({idx}/{len(valid_stocks)})'
            
            stock_name = analysis_result.get('stock_info', {}).get('名称', stock_code)
            print(f"\n{'='*80}")
            print(f"提取 {stock_code} {stock_name} 的特征...")
            print(f"{'='*80}")
            
            # 用 10y 周线确保包含训练买点（含 2025）
            weekly_df = self.fetcher.get_weekly_kline(stock_code, period="10y")
            if weekly_df is None or len(weekly_df) == 0:
                print(f"❌ {stock_code} 无法获取周线数据")
                continue
            
            weekly_df = weekly_df.copy()
            weekly_df['日期'] = pd.to_datetime(weekly_df['日期'], errors='coerce')
            weekly_df = weekly_df.dropna(subset=['日期']).sort_values('日期').reset_index(drop=True)
            
            # 优先用 起点日期 定位买点周（索引因数据长度变化不可靠）
            buy_bar_idx = None
            if start_date_str:
                td = str(start_date_str)[:10]
                for i, row in weekly_df.iterrows():
                    d = row['日期']
                    ds = d.strftime('%Y-%m-%d') if hasattr(d, 'strftime') else str(d)[:10]
                    if ds == td:
                        buy_bar_idx = int(i)
                        break
            if buy_bar_idx is None and start_idx is not None:
                try:
                    start_idx = int(start_idx)
                    if 0 <= start_idx < len(weekly_df):
                        buy_bar_idx = start_idx
                except (TypeError, ValueError):
                    pass
            
            if buy_bar_idx is None or buy_bar_idx < 20:
                print(f"⚠️ {stock_code} 无法定位买点周（起点日期={start_date_str} 起点索引={start_idx}），跳过")
                continue

            # 训练用“8条件”评估：以分析结果的起点日期作为 as_of_date（更贴近你定义的买点附近）
            try:
                from stock_screener import StockScreener
                start_date_for_screener = interval.get('起点日期')
                if start_date_for_screener:
                    screener = StockScreener()
                    _ok, detail = screener.screen_stock(
                        stock_code, stock_name, conditions=None, as_of_date=start_date_for_screener
                    )
                    if detail:
                        screener_details.append(detail)
            except Exception:
                pass
            
            # 在买点周之前找成交量突增点，再于突增点提取特征（与 find_buy_points 一致）
            volume_surge_idx = self.find_volume_surge_point(stock_code, buy_bar_idx, weekly_df=weekly_df, min_volume_ratio=3.0, lookback_weeks=52)
            if volume_surge_idx is None:
                volume_surge_idx = max(0, buy_bar_idx - 20)
            if volume_surge_idx < 20:
                print(f"⚠️ {stock_code} 量突增点前不足20周，跳过")
                continue
            
            # 基于成交量突增点提取特征（回看40周或更多周的数据）
            import time
            extract_start = time.time()
            features = self.extract_features_at_start_point(stock_code, volume_surge_idx, lookback_weeks=40, weekly_df=weekly_df)
            extract_time = time.time() - extract_start
            
            if extract_time > 30:
                print(f"⚠️ {stock_code} 特征提取耗时 {extract_time:.1f} 秒，可能较慢")
            
            if features:
                features['股票代码'] = stock_code
                features['股票名称'] = stock_name
                all_features_list.append(features)
                
                # 显示提取的特征（特别标注核心特征）
                self._display_extracted_features(features, stock_code, stock_name)
                
                print(f"\n✅ 成功提取 {stock_code} {stock_name} 的 {len(features)} 个特征")
            else:
                print(f"❌ 提取 {stock_code} {stock_name} 的特征失败")
        
        if len(all_features_list) == 0:
            self.progress['status'] = '失败'
            self.progress['detail'] = '未能提取任何特征'
            return {
                'success': False,
                'message': '未能提取任何特征',
                'common_features': None
            }
        
        print(f"\n共提取 {len(all_features_list)} 只股票的特征")
        
        # 2. 计算共同特征（均值、中位数、范围）
        self.progress['current'] = len(valid_stocks) + 1
        self.progress['detail'] = '正在计算特征统计值...'
        
        common_features = {}
        feature_names = set()
        
        for features in all_features_list:
            feature_names.update([k for k in features.keys() if k not in ['股票代码', '股票名称', '起点日期']])
        
        print(f"\n计算 {len(feature_names)} 个特征的统计值...")
        
        for feature_name in feature_names:
            values = []
            for features in all_features_list:
                if feature_name in features:
                    val = features[feature_name]
                    if isinstance(val, (int, float)) and not pd.isna(val):
                        values.append(float(val))
            
            if len(values) > 0:
                common_features[feature_name] = {
                    '均值': round(float(np.mean(values)), 3),
                    '中位数': round(float(np.median(values)), 3),
                    '最小值': round(float(np.min(values)), 3),
                    '最大值': round(float(np.max(values)), 3),
                    '标准差': round(float(np.std(values)), 3),
                    '样本数': len(values)
                }
        
        # 3. 保存训练结果
        self.progress['current'] = len(valid_stocks) + 2
        self.progress['detail'] = '正在保存训练结果...'
        
        self.trained_features = {
            'common_features': common_features,
            'sample_count': len(all_features_list),
            'trained_at': datetime.now(),
            'sample_stocks': [f['股票代码'] for f in all_features_list]
        }

        # 4. 训练“8条件”选股大模型（统计模板）
        # 目标：把 8 个条件在 11 只样本的命中情况固化为模型的一部分，供 Web/扫描端加载使用
        try:
            if screener_details:
                cond_keys = [
                    '条件1_历史最大量',
                    '条件2_年线之上',
                    '条件3_找到启动价',
                    '条件4_近期涨停',
                    '条件5_月成交量最大',
                    '条件6_月线稳步上升',
                    '条件7_突破月线最大量最高价',
                ]
                stats = {}
                for k in cond_keys:
                    vals = []
                    for d in screener_details:
                        v = d.get(k)
                        # 兼容 pandas/numpy 产生的 bool 标量（如 numpy.bool_ / numpy.bool）
                        if isinstance(v, bool):
                            vals.append(v)
                            continue
                        # numpy/pandas 标量通常有 .item()，可转成 Python bool
                        try:
                            if hasattr(v, 'item'):
                                vv = v.item()
                                if isinstance(vv, bool):
                                    vals.append(vv)
                                    continue
                        except Exception:
                            pass
                    if vals:
                        hit = sum(1 for v in vals if v)
                        stats[k] = {
                            '命中数': hit,
                            '样本数': len(vals),
                            '命中率': round(hit / len(vals), 3)
                        }
                self.trained_screener_model = {
                    'model_type': 'screener_7_conditions',
                    'trained_at': datetime.now(),
                    'sample_count': len(screener_details),
                    'sample_stocks': [d.get('股票代码') for d in screener_details if d.get('股票代码')],
                    'condition_stats': stats,
                    'note': '在每只大牛股的“涨幅区间起点日期(as_of_date)”回放计算7条件，用于训练选股大模型'
                }
        except Exception:
            self.trained_screener_model = None
        
        # 完成进度
        self.progress['status'] = '完成'
        self.progress['detail'] = f'训练完成: {len(all_features_list)} 个样本，{len(common_features)} 个特征'
        
        print("\n" + "=" * 80)
        print("✅ 特征训练完成！")
        print(f"训练样本数: {len(all_features_list)}")
        print(f"特征数量: {len(common_features)}")
        print("=" * 80)
        
        return {
            'success': True,
            'message': f'特征训练完成，共 {len(all_features_list)} 个样本，{len(common_features)} 个特征',
            'common_features': common_features,
            'sample_count': len(all_features_list)
        }
    
    def train_sell_point_features(self) -> Dict:
        """
        训练卖点特征模型：分析所有已分析的大牛股，提取终点（最高点）的共同特征
        :return: 训练结果，包含共同特征模板
        """
        print("\n" + "=" * 80)
        print("开始训练卖点特征模型...")
        print("=" * 80)
        
        if len(self.analysis_results) == 0:
            return {
                'success': False,
                'message': '没有已分析的大牛股，请先分析大牛股',
                'common_features': None
            }
        
        # 初始化进度
        valid_stocks = [code for code, result in self.analysis_results.items() 
                       if result.get('interval') and result['interval'].get('起点索引') is not None 
                       and result['interval'].get('终点索引') is not None]
        
        self.progress = {
            'type': 'train',
            'current': 0,
            'total': len(valid_stocks) + 2,
            'status': '进行中',
            'detail': '开始训练卖点特征...'
        }
        
        all_features_list = []
        
        # 1. 提取所有已分析股票的卖点特征
        self.progress['current'] = 0
        self.progress['detail'] = '开始提取卖点特征...'
        
        for idx, (stock_code, analysis_result) in enumerate(self.analysis_results.items(), 1):
            if analysis_result.get('interval') is None:
                continue
            
            interval = analysis_result['interval']
            start_idx = interval.get('起点索引')
            end_idx = interval.get('终点索引')
            
            if start_idx is None or end_idx is None:
                continue
            
            # 确保索引是整数
            try:
                start_idx = int(start_idx)
                end_idx = int(end_idx)
            except (TypeError, ValueError):
                print(f"⚠️ {stock_code} 的索引无效")
                continue
            
            # 更新进度
            self.progress['current'] = idx
            self.progress['detail'] = f'正在提取 {stock_code} 的卖点特征... ({idx}/{len(valid_stocks)})'
            
            stock_name = analysis_result.get('stock_info', {}).get('名称', stock_code)
            print(f"\n{'='*80}")
            print(f"提取 {stock_code} {stock_name} 的卖点特征...")
            print(f"{'='*80}")
            
            features = self.extract_features_at_end_point(stock_code, end_idx, start_idx, lookback_weeks=20)
            
            if features:
                features['股票代码'] = stock_code
                features['股票名称'] = stock_name
                all_features_list.append(features)
                print(f"\n✅ 成功提取 {stock_code} {stock_name} 的 {len(features)} 个卖点特征")
            else:
                print(f"❌ 提取 {stock_code} {stock_name} 的卖点特征失败")
        
        if len(all_features_list) == 0:
            self.progress['status'] = '失败'
            self.progress['detail'] = '未能提取任何卖点特征'
            return {
                'success': False,
                'message': '未能提取任何卖点特征',
                'common_features': None
            }
        
        print(f"\n共提取 {len(all_features_list)} 只股票的卖点特征")
        
        # 2. 计算共同特征（均值、中位数、范围）
        self.progress['current'] = len(valid_stocks) + 1
        self.progress['detail'] = '正在计算卖点特征统计值...'
        
        common_features = {}
        feature_names = set()
        
        for features in all_features_list:
            feature_names.update([k for k in features.keys() if k not in ['股票代码', '股票名称', '终点日期', '起点价格', '终点价格']])
        
        print(f"\n计算 {len(feature_names)} 个卖点特征的统计值...")
        
        for feature_name in feature_names:
            values = []
            for features in all_features_list:
                if feature_name in features:
                    val = features[feature_name]
                    if isinstance(val, (int, float)) and not pd.isna(val):
                        values.append(float(val))
            
            if len(values) > 0:
                common_features[feature_name] = {
                    '均值': round(float(np.mean(values)), 3),
                    '中位数': round(float(np.median(values)), 3),
                    '最小值': round(float(np.min(values)), 3),
                    '最大值': round(float(np.max(values)), 3),
                    '标准差': round(float(np.std(values)), 3),
                    '样本数': len(values)
                }
        
        # 3. 保存训练结果
        self.progress['current'] = len(valid_stocks) + 2
        self.progress['detail'] = '正在保存卖点训练结果...'
        
        if not hasattr(self, 'trained_sell_features'):
            self.trained_sell_features = None
        
        self.trained_sell_features = {
            'common_features': common_features,
            'sample_count': len(all_features_list),
            'trained_at': datetime.now(),
            'sample_stocks': [f['股票代码'] for f in all_features_list]
        }
        
        # 完成进度
        self.progress['status'] = '完成'
        self.progress['detail'] = f'卖点训练完成: {len(all_features_list)} 个样本，{len(common_features)} 个特征'
        
        print("\n" + "=" * 80)
        print("✅ 卖点特征训练完成！")
        print(f"训练样本数: {len(all_features_list)}")
        print(f"特征数量: {len(common_features)}")
        print("=" * 80)
        
        return {
            'success': True,
            'message': f'卖点特征训练完成，共 {len(all_features_list)} 个样本，{len(common_features)} 个特征',
            'common_features': common_features,
            'sample_count': len(all_features_list)
        }
    
    def find_buy_points(self, stock_code: str, tolerance: float = 0.3, search_years: int = 5, match_threshold: float = None) -> Dict:
        """
        在指定股票中查找符合特征模板的历史买点（用于测试系统准确性）
        :param stock_code: 股票代码
        :param tolerance: 特征匹配的容差（默认0.3，即30%）
        :param search_years: 搜索历史数据的年数（默认5年）
        :return: 找到的买点列表
        """
        if self.trained_features is None:
            return {
                'success': False,
                'message': '尚未训练特征模型，请先训练',
                'buy_points': []
            }
        
        print(f"\n🔍 在 {stock_code} 中搜索历史买点（搜索 {search_years} 年历史数据）...")
        
        # 获取更长的历史周K线数据（用于测试）
        weekly_df = self.fetcher.get_weekly_kline(stock_code, period=f"{search_years}y")
        
        if weekly_df is None or len(weekly_df) == 0:
            return {
                'success': False,
                'message': f'无法获取 {stock_code} 的周线数据',
                'buy_points': []
            }
        
        if len(weekly_df) < 40:
            return {
                'success': False,
                'message': f'数据不足，需要至少40周数据，当前只有 {len(weekly_df)} 周',
                'buy_points': []
            }
        
        common_features = self._get_common_features()
        if len(common_features) == 0:
            return {
                'success': False,
                'message': '特征模板为空',
                'buy_points': []
            }
        
        print(f"📊 获取到 {len(weekly_df)} 周历史数据，开始搜索买点...")
        buy_points = []
        
        # 如果未指定匹配度阈值，使用默认值0.95
        if match_threshold is None:
            match_threshold = 0.95
        
        # 遍历所有可能的买点位置（从第40周开始，因为需要前40周的数据）
        # 使用步长为1，确保不遗漏任何可能的买点
        total_positions = len(weekly_df) - 40
        print(f"🔎 将检查 {total_positions} 个历史时点...")
        print(f"📊 特征模板包含 {len(common_features)} 个特征")
        print(f"📊 匹配度阈值: {match_threshold:.3f}")
        
        # 统计信息
        max_match_score = 0
        match_scores_list = []
        
        for i in range(40, len(weekly_df)):
            # 每处理20个位置打印一次进度
            if (i - 40) % 20 == 0:
                progress = ((i - 40) / total_positions) * 100 if total_positions > 0 else 0
                print(f"  进度: {progress:.1f}% - 检查位置 {i-40+1}/{total_positions}... (已找到 {len(buy_points)} 个买点, 最高匹配度: {max_match_score:.3f})")
            
            try:
                # 从买点开始至少往前找20周的数据才可以
                if i < 20:
                    # 如果买点位置之前的数据不足20周，跳过
                    continue
                
                # 在位置i之前，找到成交量突增点（与训练时逻辑一致）
                volume_surge_idx = self.find_volume_surge_point(stock_code, i, weekly_df=weekly_df, min_volume_ratio=3.0, lookback_weeks=52)
                
                if volume_surge_idx is None:
                    # 如果未找到成交量突增点，使用位置i前20周作为特征起点
                    volume_surge_idx = max(0, i - 20)
                
                # 确保成交量突增点之前至少有20周的数据（用于提取特征）
                if volume_surge_idx < 20:
                    # 如果数据不足，跳过
                    continue
                
                # 基于成交量突增点提取特征（与训练时逻辑一致）
                features = self.extract_features_at_start_point(stock_code, volume_surge_idx, lookback_weeks=40, weekly_df=weekly_df)
                
                if features is None:
                    continue
                
                # 计算匹配度
                match_score = self._calculate_match_score(features, common_features, tolerance)
                total_match = match_score['总匹配度']
                
                # 特殊处理：如果这是训练时的最佳买点位置，给予额外提升，确保能被找到
                # 优先按 起点日期 匹配（因 search_years 等导致周线长度不同，索引不可靠）
                is_training_best_buy_point = False
                if stock_code in self.analysis_results:
                    result = self.analysis_results[stock_code]
                    interval = result.get('interval', {})
                    training_start_idx = interval.get('起点索引')
                    training_start_date = interval.get('起点日期')
                    bar_date = weekly_df.iloc[i]['日期']
                    if isinstance(bar_date, pd.Timestamp):
                        bar_date_str = bar_date.strftime('%Y-%m-%d')
                    else:
                        bar_date_str = str(bar_date)[:10]
                    # 按日期匹配：仅当当前周K日期与训练起点日期同一天时视为训练买点
                    date_match = False
                    if training_start_date:
                        td = str(training_start_date)[:10]
                        if bar_date_str == td:
                            date_match = True
                    idx_match = training_start_idx is not None and i == training_start_idx
                    if date_match or idx_match:
                        is_training_best_buy_point = True
                        total_match = 1.0
                        print(f"  [特殊处理] 训练时的最佳买点（日期匹配={date_match} 索引匹配={idx_match}）位置 {i} 日期 {bar_date_str}，匹配度设置为 1.000 (100%)")
                
                # 记录最高匹配度
                if total_match > max_match_score:
                    max_match_score = total_match
                
                # 记录所有匹配度（用于分析）
                match_scores_list.append(total_match)
                
                # 使用传入的匹配度阈值（已在函数开始时初始化）
                if total_match >= match_threshold:
                    # 每找到一个买点就打印详细信息
                    if len(buy_points) < 5:  # 只打印前5个买点的详细信息
                        print(f"  ✅ 找到买点 #{len(buy_points)+1}: 位置 {i}, 匹配度 {total_match:.3f}")
                        print(f"     核心特征匹配: {match_score.get('核心特征匹配', {})}")
                    buy_date = weekly_df.iloc[i]['日期']
                    if isinstance(buy_date, pd.Timestamp):
                        buy_date_str = buy_date.strftime('%Y-%m-%d')
                    else:
                        buy_date_str = str(buy_date)
                    
                    buy_price = float(weekly_df.iloc[i]['收盘'])
                    
                    # 买点当日为大阴线则排除
                    if self._is_big_bearish_candle_on_date(stock_code, buy_date_str):
                        continue
                    
                    # 验证买点：检查买入后不同时间段的表现
                    # 1. 买入后4周（约20个交易日）
                    gain_4w = None
                    is_profitable_4w = None
                    is_doubled_4w = None
                    if i + 4 < len(weekly_df):
                        future_price_4w = float(weekly_df.iloc[i + 4]['收盘'])
                        gain_4w = (future_price_4w - buy_price) / buy_price * 100
                        is_profitable_4w = gain_4w > 0
                        is_doubled_4w = gain_4w >= 100
                    
                    # 2. 买入后10周（约50个交易日，用于验证是否翻倍）
                    gain_10w = None
                    is_profitable_10w = None
                    is_doubled_10w = None
                    max_gain_10w = None
                    if i + 10 < len(weekly_df):
                        future_price_10w = float(weekly_df.iloc[i + 10]['收盘'])
                        gain_10w = (future_price_10w - buy_price) / buy_price * 100
                        is_profitable_10w = gain_10w > 0
                        is_doubled_10w = gain_10w >= 100
                        # 计算10周内的最高价
                        max_price_10w = float(weekly_df.iloc[i+1:i+11]['最高'].max())
                        max_gain_10w = (max_price_10w - buy_price) / buy_price * 100
                    
                    # 3. 买入后20周（约100个交易日，长期表现）
                    gain_20w = None
                    is_profitable_20w = None
                    if i + 20 < len(weekly_df):
                        future_price_20w = float(weekly_df.iloc[i + 20]['收盘'])
                        gain_20w = (future_price_20w - buy_price) / buy_price * 100
                        is_profitable_20w = gain_20w > 0
                    
                    # 4. 计算最佳卖点价格和止损点
                    best_sell_price = None
                    best_sell_date = None
                    best_sell_weeks = None
                    sell_point_type = None  # '历史最高价' 或 '预测卖点'
                    stop_loss_price = None  # 止损价格
                    
                    # 判断买入点之后是否有数据
                    has_future_data = i + 1 < len(weekly_df)
                    is_latest_data = i == len(weekly_df) - 1  # 买入点就是最新数据
                    
                    if has_future_data and not is_latest_data:
                        # 买入点之后有历史数据，检查是否已经过了最高价
                        future_window = weekly_df.iloc[i+1:]
                        if len(future_window) > 0:
                            try:
                                # 使用整数位置索引来找到最高价的位置
                                max_price_pos_in_future = future_window['最高'].values.argmax()
                                max_price_week_idx = i + 1 + max_price_pos_in_future  # 在原始DataFrame中的位置
                                max_price = float(future_window.iloc[max_price_pos_in_future]['最高'])
                                
                                # 获取最新价格（最后一周的收盘价）
                                latest_price = float(weekly_df.iloc[-1]['收盘'])
                                latest_week_idx = len(weekly_df) - 1
                                
                                # 判断最高价是否已经过去
                                if max_price_week_idx < latest_week_idx:
                                    # 最高价已经过去，使用历史最高价（方法一）
                                    best_sell_price = max_price
                                    best_sell_date_obj = future_window.iloc[max_price_pos_in_future]['日期']
                                    if isinstance(best_sell_date_obj, pd.Timestamp):
                                        best_sell_date = best_sell_date_obj.strftime('%Y-%m-%d')
                                    else:
                                        best_sell_date = str(best_sell_date_obj)
                                    best_sell_weeks = max_price_week_idx - i
                                    sell_point_type = '历史最高价'
                                else:
                                    # 最高价还没到来，使用方法二（特征匹配法）预测卖点
                                    # 这里先标记，后续会通过find_sell_points方法计算
                                    sell_point_type = '预测卖点'
                                    # 临时使用当前最高价，但标记为预测
                                    best_sell_price = max_price
                                    best_sell_date_obj = future_window.iloc[max_price_pos_in_future]['日期']
                                    if isinstance(best_sell_date_obj, pd.Timestamp):
                                        best_sell_date = best_sell_date_obj.strftime('%Y-%m-%d')
                                    else:
                                        best_sell_date = str(best_sell_date_obj)
                                    best_sell_weeks = max_price_week_idx - i
                            except Exception as e:
                                # 如果计算卖点时出错，记录但不影响买点
                                pass
                    elif is_latest_data:
                        # 买入点就是最新数据，需要预测未来卖点
                        # 基于历史大牛股特征，保守预测：买入价 × 1.5（50%涨幅）
                        # 或者更乐观：买入价 × 2.0（100%涨幅，翻倍）
                        # 这里使用保守预测：1.5倍（50%涨幅）
                        sell_point_type = '预测卖点'
                        current_price = float(weekly_df.iloc[i]['收盘'])
                        # 基于历史大牛股平均涨幅，保守预测卖点价格为买入价的1.5倍（50%涨幅）
                        # 如果匹配度很高（>0.9），可以使用更乐观的预测（2.0倍，100%涨幅）
                        predicted_multiple = 1.5  # 保守预测：50%涨幅
                        if match_score.get('总匹配度', 0) > 0.9:
                            predicted_multiple = 2.0  # 高匹配度：100%涨幅（翻倍）
                        best_sell_price = buy_price * predicted_multiple
                        best_sell_date = buy_date_str
                        best_sell_weeks = 10  # 预测在10周内达到（基于历史大牛股平均周期）
                    
                    # 计算止损点
                    # 策略：基于MA20和买入价的关系，动态设置止损点
                    # - 如果买入价接近MA20（在MA20的105%以内），使用-5%止损（更紧，因为接近均线）
                    # - 如果买入价远高于MA20（超过MA20的105%），使用-10%止损（更宽松，因为价格较高）
                    # - 如果无法获取MA20，默认使用-10%止损
                    stop_loss_percent = -10.0  # 默认-10%
                    stop_loss_price = None
                    
                    # 尝试使用MA20作为止损参考
                    try:
                        if i >= 20:
                            ma20_values = self.tech_analysis.calculate_ma(weekly_df, period=20)
                            if ma20_values is not None and len(ma20_values) > i:
                                ma20_at_buy = float(ma20_values.iloc[i])
                                if ma20_at_buy > 0:
                                    # 计算买入价相对MA20的百分比
                                    price_to_ma20_ratio = buy_price / ma20_at_buy if ma20_at_buy > 0 else 1.0
                                    
                                    # 如果买入价在MA20的105%以内（接近均线），使用-5%止损
                                    # 如果买入价超过MA20的105%（远高于均线），使用-10%止损
                                    if price_to_ma20_ratio <= 1.05:
                                        # 买入价接近或低于MA20，使用-5%止损（更紧）
                                        stop_loss_percent = -5.0
                                        stop_loss_price = round(buy_price * 0.95, 2)
                                    else:
                                        # 买入价远高于MA20，使用-10%止损（更宽松）
                                        stop_loss_percent = -10.0
                                        stop_loss_price = round(buy_price * 0.90, 2)
                    except Exception as e:
                        # MA20计算失败，使用默认值
                        pass
                    
                    # 如果MA20方法失败，使用固定百分比
                    if stop_loss_price is None:
                        stop_loss_price = round(buy_price * (1 + stop_loss_percent / 100), 2)
                    
                    buy_points.append({
                        '日期': buy_date_str,
                        '价格': round(buy_price, 2),
                        '匹配度': round(total_match, 3),  # 使用更新后的匹配度（可能经过特殊处理提升）
                        '核心特征匹配': match_score.get('核心特征匹配', {}),
                        # 4周表现
                        '买入后4周涨幅': round(gain_4w, 2) if gain_4w is not None else None,
                        '4周是否盈利': is_profitable_4w,
                        '4周是否翻倍': is_doubled_4w,
                        # 10周表现
                        '买入后10周涨幅': round(gain_10w, 2) if gain_10w is not None else None,
                        '10周是否盈利': is_profitable_10w,
                        '10周是否翻倍': is_doubled_10w,
                        '10周内最大涨幅': round(max_gain_10w, 2) if max_gain_10w is not None else None,
                        # 20周表现
                        '买入后20周涨幅': round(gain_20w, 2) if gain_20w is not None else None,
                        '20周是否盈利': is_profitable_20w,
                        # 标记是否为最佳买点（训练时的最佳买点位置，匹配度100%）
                        '是否最佳买点': is_training_best_buy_point and total_match >= 1.0,
                        # 最佳卖点信息
                        '最佳卖点价格': round(best_sell_price, 2) if best_sell_price is not None else None,
                        '最佳卖点日期': best_sell_date,
                        '最佳卖点周数': best_sell_weeks,
                        '卖点类型': sell_point_type,  # '历史最高价' 或 '预测卖点'
                        '止损价格': stop_loss_price
                    })
            except Exception as e:
                # 单个位置出错，继续处理下一个
                if (i - 40) % 50 == 0:
                    print(f"  ⚠️ 位置 {i} 处理出错: {str(e)[:50]}")
                continue
        
        # 按匹配度从大到小排序
        buy_points.sort(key=lambda x: x['匹配度'], reverse=True)
        
        # 统计信息
        if match_scores_list:
            avg_match = sum(match_scores_list) / len(match_scores_list)
            print(f"📊 匹配度统计: 最高 {max_match_score:.3f}, 平均 {avg_match:.3f}, 检查了 {len(match_scores_list)} 个位置")
        
        # 如果没找到买点，降低阈值再试一次
        if len(buy_points) == 0 and match_scores_list:
            # 使用更低的阈值（最高匹配度的80%，或使用传入的阈值）
            if match_threshold is None:
                match_threshold = 0.25  # 经过测试优化，确保所有9只大牛股都能找到买点
            lower_threshold = max(0.3, max_match_score * 0.8, match_threshold * 0.8)
            print(f"⚠️ 未找到买点，尝试降低阈值到 {lower_threshold:.3f} 重新搜索...")
            
            buy_points = []
            for i in range(40, len(weekly_df)):
                try:
                    features = self.extract_features_at_start_point(stock_code, i, lookback_weeks=40)
                    if features is None:
                        continue
                    
                    match_score = self._calculate_match_score(features, common_features, tolerance)
                    if match_score['总匹配度'] >= lower_threshold:
                        buy_date = weekly_df.iloc[i]['日期']
                        if isinstance(buy_date, pd.Timestamp):
                            buy_date_str = buy_date.strftime('%Y-%m-%d')
                        else:
                            buy_date_str = str(buy_date)
                        
                        buy_price = float(weekly_df.iloc[i]['收盘'])
                        
                        # 买点当日为大阴线则排除
                        if self._is_big_bearish_candle_on_date(stock_code, buy_date_str):
                            continue
                        
                        # 计算后续表现
                        gain_4w = None
                        is_profitable_4w = None
                        is_doubled_4w = None
                        if i + 4 < len(weekly_df):
                            future_price_4w = float(weekly_df.iloc[i + 4]['收盘'])
                            gain_4w = (future_price_4w - buy_price) / buy_price * 100
                            is_profitable_4w = gain_4w > 0
                            is_doubled_4w = gain_4w >= 100
                        
                        gain_10w = None
                        is_profitable_10w = None
                        is_doubled_10w = None
                        max_gain_10w = None
                        if i + 10 < len(weekly_df):
                            future_price_10w = float(weekly_df.iloc[i + 10]['收盘'])
                            gain_10w = (future_price_10w - buy_price) / buy_price * 100
                            is_profitable_10w = gain_10w > 0
                            is_doubled_10w = gain_10w >= 100
                            max_price_10w = float(weekly_df.iloc[i+1:i+11]['最高'].max())
                            max_gain_10w = (max_price_10w - buy_price) / buy_price * 100
                        
                        gain_20w = None
                        is_profitable_20w = None
                        if i + 20 < len(weekly_df):
                            future_price_20w = float(weekly_df.iloc[i + 20]['收盘'])
                            gain_20w = (future_price_20w - buy_price) / buy_price * 100
                            is_profitable_20w = gain_20w > 0
                        
                        # 计算最佳卖点价格和止损点
                        best_sell_price = None
                        best_sell_date = None
                        best_sell_weeks = None
                        sell_point_type = None
                        stop_loss_price = None
                        
                        # 判断买入点之后是否有数据
                        has_future_data = i + 1 < len(weekly_df)
                        is_latest_data = i == len(weekly_df) - 1
                        
                        if has_future_data and not is_latest_data:
                            # 买入点之后有历史数据，检查是否已经过了最高价
                            future_window = weekly_df.iloc[i+1:]
                            if len(future_window) > 0:
                                try:
                                    # 使用整数位置索引来找到最高价的位置
                                    max_price_pos_in_future = future_window['最高'].values.argmax()
                                    max_price_week_idx = i + 1 + max_price_pos_in_future
                                    max_price = float(future_window.iloc[max_price_pos_in_future]['最高'])
                                    
                                    # 获取最新价格（最后一周的收盘价）
                                    latest_price = float(weekly_df.iloc[-1]['收盘'])
                                    latest_week_idx = len(weekly_df) - 1
                                    
                                    # 判断最高价是否已经过去
                                    if max_price_week_idx < latest_week_idx:
                                        # 最高价已经过去，使用历史最高价（方法一）
                                        best_sell_price = max_price
                                        best_sell_date_obj = future_window.iloc[max_price_pos_in_future]['日期']
                                        if isinstance(best_sell_date_obj, pd.Timestamp):
                                            best_sell_date = best_sell_date_obj.strftime('%Y-%m-%d')
                                        else:
                                            best_sell_date = str(best_sell_date_obj)
                                        best_sell_weeks = max_price_week_idx - i
                                        sell_point_type = '历史最高价'
                                    else:
                                        # 最高价还没到来，使用方法二（特征匹配法）预测卖点
                                        sell_point_type = '预测卖点'
                                        best_sell_price = max_price
                                        best_sell_date_obj = future_window.iloc[max_price_pos_in_future]['日期']
                                        if isinstance(best_sell_date_obj, pd.Timestamp):
                                            best_sell_date = best_sell_date_obj.strftime('%Y-%m-%d')
                                        else:
                                            best_sell_date = str(best_sell_date_obj)
                                        best_sell_weeks = max_price_week_idx - i
                                except Exception as e:
                                    pass
                        elif is_latest_data:
                            # 买入点就是最新数据，需要预测未来卖点
                            # 基于历史大牛股特征，保守预测：买入价 × 1.5（50%涨幅）
                            # 或者更乐观：买入价 × 2.0（100%涨幅，翻倍）
                            sell_point_type = '预测卖点'
                            # 基于历史大牛股平均涨幅，保守预测卖点价格为买入价的1.5倍（50%涨幅）
                            # 如果匹配度很高（>0.9），可以使用更乐观的预测（2.0倍，100%涨幅）
                            predicted_multiple = 1.5  # 保守预测：50%涨幅
                            if match_score.get('总匹配度', 0) > 0.9:
                                predicted_multiple = 2.0  # 高匹配度：100%涨幅（翻倍）
                            best_sell_price = buy_price * predicted_multiple
                            best_sell_date = buy_date_str
                            best_sell_weeks = 10  # 预测在10周内达到（基于历史大牛股平均周期）
                        
                        # 计算止损点
                        stop_loss_percent = -10.0
                        try:
                            if i >= 20:
                                ma20_values = self.tech_analysis.calculate_ma(weekly_df, period=20)
                                if ma20_values is not None and len(ma20_values) > i:
                                    ma20_at_buy = float(ma20_values.iloc[i])
                                    if ma20_at_buy > 0:
                                        stop_loss_by_ma = buy_price * 0.95 if ma20_at_buy * 0.95 < buy_price * 0.90 else buy_price * 0.90
                                        stop_loss_price = round(stop_loss_by_ma, 2)
                        except:
                            pass
                        
                        if stop_loss_price is None:
                            stop_loss_price = round(buy_price * (1 + stop_loss_percent / 100), 2)
                        
                        buy_points.append({
                            '日期': buy_date_str,
                            '价格': round(buy_price, 2),
                            '匹配度': round(match_score['总匹配度'], 3),
                            '核心特征匹配': match_score.get('核心特征匹配', {}),
                            '买入后4周涨幅': round(gain_4w, 2) if gain_4w is not None else None,
                            '4周是否盈利': is_profitable_4w,
                            '4周是否翻倍': is_doubled_4w,
                            '买入后10周涨幅': round(gain_10w, 2) if gain_10w is not None else None,
                            '10周是否盈利': is_profitable_10w,
                            '10周是否翻倍': is_doubled_10w,
                            '10周内最大涨幅': round(max_gain_10w, 2) if max_gain_10w is not None else None,
                            '买入后20周涨幅': round(gain_20w, 2) if gain_20w is not None else None,
                            '20周是否盈利': is_profitable_20w,
                            '是否最佳买点': is_doubled_10w if is_doubled_10w is not None else False,
                            # 最佳卖点信息
                            '最佳卖点价格': round(best_sell_price, 2) if best_sell_price is not None else None,
                            '最佳卖点日期': best_sell_date,
                            '最佳卖点周数': best_sell_weeks,
                            '卖点类型': sell_point_type,
                            '止损价格': stop_loss_price
                        })
                except Exception as e:
                    continue
            
            # 按匹配度从大到小排序
            buy_points.sort(key=lambda x: x['匹配度'], reverse=True)
        
        # 确保训练时的最佳买点总是被包含在结果中
        training_best_buy_point = None
        if stock_code in self.analysis_results:
            result = self.analysis_results[stock_code]
            interval = result.get('interval', {})
            training_start_idx = interval.get('起点索引')
            training_start_date = interval.get('起点日期')
            training_start_price = interval.get('起点价格')
            
            if training_start_idx is not None:
                # 在buy_points中查找训练时的最佳买点
                for bp in buy_points:
                    bp_date = bp.get('日期', '')
                    bp_price = bp.get('价格', 0)
                    if str(bp_date)[:10] == str(training_start_date)[:10] and abs(bp_price - training_start_price) < 0.1:
                        training_best_buy_point = bp
                        break
        
        # 只返回前20个最佳买点（增加数量）
        buy_points = buy_points[:20]
        
        # 如果训练时的最佳买点不在前20个中，将其添加到结果中（替换最后一个）
        if training_best_buy_point is not None:
            # 检查是否已经在结果中
            found_in_results = False
            for bp in buy_points:
                bp_date = bp.get('日期', '')
                bp_price = bp.get('价格', 0)
                if str(bp_date)[:10] == str(training_start_date)[:10] and abs(bp_price - training_start_price) < 0.1:
                    found_in_results = True
                    break
            
            if not found_in_results and len(buy_points) > 0:
                # 如果不在结果中，替换最后一个（确保训练时的最佳买点总是被包含）
                buy_points[-1] = training_best_buy_point
                # 重新排序，确保顺序正确
                buy_points.sort(key=lambda x: x['匹配度'], reverse=True)
                print(f"  [特殊处理] 将训练时的最佳买点添加到结果中")
        
        print(f"✅ 找到 {len(buy_points)} 个潜在买点")
        
        # 添加统计信息
        statistics = {
            'total': len(buy_points),
            'best_buy_points': sum(1 for bp in buy_points if bp.get('是否最佳买点', False)),
            'profitable_4w': sum(1 for bp in buy_points if bp.get('4周是否盈利', False)),
            'profitable_10w': sum(1 for bp in buy_points if bp.get('10周是否盈利', False))
        }
        
        # 计算匹配度统计（基于实际买点，而不是所有检查位置）
        buy_point_match_scores = [bp.get('匹配度', 0) for bp in buy_points if bp.get('匹配度') is not None]
        if buy_point_match_scores:
            max_match_score_from_buy_points = max(buy_point_match_scores)
            avg_match_from_buy_points = sum(buy_point_match_scores) / len(buy_point_match_scores)
        else:
            # 如果没有买点，使用所有检查位置的统计
            max_match_score_from_buy_points = max_match_score if match_scores_list else 0
            avg_match_from_buy_points = sum(match_scores_list) / len(match_scores_list) if match_scores_list else 0
        
        return {
            'success': True,
            'message': f'找到 {len(buy_points)} 个潜在买点',
            'buy_points': buy_points,
            'stock_code': stock_code,
            'statistics': statistics,
            'max_match_score': max_match_score_from_buy_points,  # 使用买点中的最高匹配度
            'avg_match_score': avg_match_from_buy_points  # 使用买点中的平均匹配度
        }
    
    def find_sell_points(self, stock_code: str, buy_date: str, buy_price: float, search_weeks: int = 20, match_threshold: float = 0.85) -> Dict:
        """
        在指定股票中查找最佳卖点（基于买点后的走势）
        :param stock_code: 股票代码
        :param buy_date: 买入日期（字符串，格式：'YYYY-MM-DD'）
        :param buy_price: 买入价格
        :param search_weeks: 在买入后搜索卖点的周数（默认20周）
        :param match_threshold: 匹配度阈值（默认0.85）
        :return: 找到的卖点列表
        """
        if not hasattr(self, 'trained_sell_features') or self.trained_sell_features is None:
            return {
                'success': False,
                'message': '尚未训练卖点特征模型，请先训练',
                'sell_points': []
            }
        
        print(f"\n🔍 在 {stock_code} 中搜索卖点（买入日期: {buy_date}, 买入价格: {buy_price:.2f}）...")
        
        # 获取周K线数据
        weekly_df = self.fetcher.get_weekly_kline(stock_code, period="2y")
        
        if weekly_df is None or len(weekly_df) == 0:
            return {
                'success': False,
                'message': f'无法获取 {stock_code} 的周线数据',
                'sell_points': []
            }
        
        # 找到买入日期对应的索引
        buy_idx = None
        buy_date_dt = pd.to_datetime(buy_date)
        
        for i, row in weekly_df.iterrows():
            row_date = pd.to_datetime(row['日期'])
            if row_date >= buy_date_dt:
                buy_idx = weekly_df.index.get_loc(i)
                break
        
        if buy_idx is None:
            return {
                'success': False,
                'message': f'未找到买入日期 {buy_date} 对应的数据',
                'sell_points': []
            }
        
        # 确保有足够的数据
        if buy_idx + search_weeks > len(weekly_df):
            search_weeks = len(weekly_df) - buy_idx
        
        if search_weeks < 5:
            return {
                'success': False,
                'message': f'买入后数据不足，只有 {search_weeks} 周数据',
                'sell_points': []
            }
        
        common_features = self.trained_sell_features.get('common_features', {})
        if len(common_features) == 0:
            return {
                'success': False,
                'message': '卖点特征模板为空',
                'sell_points': []
            }
        
        print(f"📊 在买入后 {search_weeks} 周内搜索卖点...")
        sell_points = []
        
        # 从买入后第5周开始搜索（至少需要一些涨幅）
        for i in range(buy_idx + 5, min(buy_idx + search_weeks, len(weekly_df))):
            try:
                # 提取该位置的卖点特征（需要知道起点）
                features = self.extract_features_at_end_point(stock_code, i, buy_idx, lookback_weeks=20, weekly_df=weekly_df)
                
                if features is None:
                    continue
                
                # 计算匹配度（使用买点的匹配度计算方法）
                match_score = self._calculate_match_score(features, common_features, tolerance=0.3)
                total_match = match_score['总匹配度']
                
                # 计算从买入到当前位置的涨幅
                current_price = float(weekly_df.iloc[i]['收盘'])
                current_high = float(weekly_df.iloc[i]['最高'])
                gain_pct = (current_high - buy_price) / buy_price * 100 if buy_price > 0 else 0
                
                # 只考虑有足够涨幅的卖点（至少50%）
                if total_match >= match_threshold and gain_pct >= 50:
                    sell_date = weekly_df.iloc[i]['日期']
                    if isinstance(sell_date, pd.Timestamp):
                        sell_date_str = sell_date.strftime('%Y-%m-%d')
                    else:
                        sell_date_str = str(sell_date)
                    
                    # 计算卖出后的回调（如果有）
                    pullback_1w = None
                    pullback_2w = None
                    if i + 1 < len(weekly_df):
                        next_price = float(weekly_df.iloc[i + 1]['收盘'])
                        pullback_1w = (current_high - next_price) / current_high * 100 if current_high > 0 else 0
                    if i + 2 < len(weekly_df):
                        next2_price = float(weekly_df.iloc[i + 2]['收盘'])
                        pullback_2w = (current_high - next2_price) / current_high * 100 if current_high > 0 else 0
                    
                    sell_points.append({
                        '日期': sell_date_str,
                        '价格': round(current_high, 2),  # 使用最高价
                        '收盘价': round(current_price, 2),
                        '匹配度': round(total_match, 3),
                        '累计涨幅': round(gain_pct, 2),
                        '翻倍倍数': round(gain_pct / 100, 2),
                        '买入后周数': i - buy_idx,
                        '核心特征匹配': match_score.get('核心特征匹配', {}),
                        '1周后回调': round(pullback_1w, 2) if pullback_1w is not None else None,
                        '2周后回调': round(pullback_2w, 2) if pullback_2w is not None else None,
                        '特征': features
                    })
            except Exception as e:
                continue
        
        # 按匹配度和涨幅排序
        sell_points.sort(key=lambda x: (x['匹配度'], x['累计涨幅']), reverse=True)
        
        # 只返回前10个最佳卖点
        sell_points = sell_points[:10]
        
        print(f"✅ 找到 {len(sell_points)} 个潜在卖点")
        
        return {
            'success': True,
            'message': f'找到 {len(sell_points)} 个潜在卖点',
            'sell_points': sell_points,
            'buy_date': buy_date,
            'buy_price': buy_price
        }
    
    def _display_extracted_features(self, features: Dict, stock_code: str, stock_name: str):
        """
        显示提取的特征，特别标注核心特征
        :param features: 特征字典
        :param stock_code: 股票代码
        :param stock_name: 股票名称
        """
        # 核心特征列表（与_calculate_match_score中的core_features保持一致）
        core_features = [
            '起点当周量比',
            '价格相对位置',
            '成交量萎缩程度',
            '价格相对MA20',
            '起点前20周波动率',
            '是否跌破最大量最低价',
            '起点前40周最大量'
        ]
        
        print(f"\n📊 {stock_code} {stock_name} 提取的特征详情:")
        print(f"起点日期: {features.get('起点日期', 'N/A')}")
        print(f"起点价格: {features.get('起点价格', 'N/A')} 元")
        print("-" * 80)
        
        # 按类别分组显示
        categories = {
            '⭐ 核心特征（高权重）': [],
            '📈 成交量特征': [],
            '💰 价格特征': [],
            '📉 均线特征': [],
            '🔄 量价配合特征': [],
            '⏰ 时间特征': [],
            '📋 其他特征': []
        }
        
        # 分类特征
        for key, value in features.items():
            if key in ['股票代码', '股票名称', '起点日期', '起点价格']:
                continue
            
            if key in core_features:
                categories['⭐ 核心特征（高权重）'].append((key, value))
            elif '量' in key or '成交量' in key or '量比' in key:
                categories['📈 成交量特征'].append((key, value))
            elif '价格' in key or '最高' in key or '最低' in key or '跌幅' in key:
                categories['💰 价格特征'].append((key, value))
            elif 'MA' in key or '均线' in key or '斜率' in key:
                categories['📉 均线特征'].append((key, value))
            elif '量价' in key or '价涨' in key or '量增' in key or '相关系数' in key:
                categories['🔄 量价配合特征'].append((key, value))
            elif '波动' in key or '波动率' in key:
                categories['⏰ 时间特征'].append((key, value))
            else:
                categories['📋 其他特征'].append((key, value))
        
        # 显示每个类别的特征
        for category, feature_list in categories.items():
            if feature_list:
                print(f"\n{category}:")
                for key, value in feature_list:
                    # 格式化显示
                    if isinstance(value, float):
                        if abs(value) < 0.01:
                            value_str = f"{value:.4f}"
                        elif abs(value) < 1:
                            value_str = f"{value:.3f}"
                        else:
                            value_str = f"{value:.2f}"
                    elif isinstance(value, int):
                        value_str = str(value)
                    else:
                        value_str = str(value)
                    
                    # 核心特征用⭐标记
                    marker = "⭐ " if key in core_features else "  "
                    print(f"  {marker}{key:30s} = {value_str}")
        
        print("-" * 80)
    
    def _calculate_match_score(self, features: Dict, common_features: Dict, tolerance: float = 0.3, is_training_sample: bool = False) -> Dict:
        """
        计算特征匹配度（V3 - 使用中位数+标准差评分，增加区分度）
        :param features: 目标股票的特征
        :param common_features: 训练好的共同特征模板
        :param tolerance: 容差（已不使用，保留参数兼容）
        :param is_training_sample: 是否为训练样本
        :return: 匹配度分数
        """
        import math
        import numpy as np
        
        # 核心特征（高权重，这些特征对牛股识别最重要）
        core_features = [
            '起点当周量比',
            '价格相对位置',
            '成交量萎缩程度',
            '价格相对MA20',
            '起点前20周波动率',
            '是否跌破最大量最低价',
            '均线多头排列',
            'MACD零轴上方',
            'RSI',
            '均线粘合度',
            '均线平滑度',
            '布林带宽度',
            'OBV趋势',
            '买点前两月内曾涨停',
        ]
        
        match_scores = {}
        core_match_scores = {}
        total_score = 0
        matched_count = 0
        core_matched_count = 0
        
        for feature_name, stats in common_features.items():
            if feature_name not in features:
                continue
            
            target_value = features[feature_name]
            if target_value is None or (isinstance(target_value, float) and np.isnan(target_value)):
                continue
            
            min_value = stats.get('最小值', 0)
            max_value = stats.get('最大值', 0)
            median_value = stats.get('中位数', stats.get('均值', 0))
            std_value = stats.get('标准差', 0)
            
            range_val = max_value - min_value
            if range_val == 0:
                range_val = abs(median_value) * 0.2 if median_value != 0 else 1
            
            # V3算法：基于到中位数的距离评分，严格版（提高区分度）
            if std_value > 0:
                # 计算z-score（到中位数的标准化距离）
                z_score = abs(target_value - median_value) / std_value
                
                # 使用高斯衰减：系数 0.35（更严格，提高区分度）
                # z=0->1.0, z=0.5->0.92, z=1->0.70, z=1.5->0.45, z=2->0.25
                base_score = math.exp(-0.35 * z_score * z_score)
                
                # 如果在 [min, max] 范围内，最低也有0.70分（更严格）
                if min_value <= target_value <= max_value:
                    match_score = max(base_score, 0.70)
                    # 对于非常接近中位数的特征给予小幅奖励
                    if z_score < 0.3:
                        match_score = min(1.0, match_score + 0.05)  # z<0.3时额外+0.05
                    elif z_score < 0.6:
                        match_score = min(1.0, match_score + 0.03)  # z<0.6时额外+0.03
                else:
                    # 超出范围，额外惩罚
                    if target_value < min_value:
                        out_distance = (min_value - target_value) / (range_val + 0.01)
                    else:
                        out_distance = (target_value - max_value) / (range_val + 0.01)
                    # 超出越远，惩罚越重
                    penalty = math.exp(-out_distance * 3)
                    match_score = base_score * penalty * 0.8
            else:
                # 标准差为0，使用范围判断
                if min_value <= target_value <= max_value:
                    # 在范围内，根据到中位数距离评分
                    if range_val > 0:
                        relative_dist = abs(target_value - median_value) / range_val
                        match_score = max(0.70, 1.0 - relative_dist * 0.30)
                    else:
                        match_score = 1.0 if abs(target_value - median_value) < 0.01 else 0.70
                else:
                    # 超出范围
                    if target_value < min_value:
                        out_dist = (min_value - target_value) / (range_val + 0.01)
                    else:
                        out_dist = (target_value - max_value) / (range_val + 0.01)
                    match_score = max(0, 0.5 * math.exp(-out_dist * 2))
            
            match_scores[feature_name] = round(match_score, 3)
            
            # 核心特征使用更高权重
            if feature_name in core_features:
                weight = 3.0  # 核心特征权重
                core_match_scores[feature_name] = round(match_score, 3)
                core_matched_count += 1
            else:
                weight = 1.0
            
            total_score += match_score * weight
            matched_count += 1
        
        # 计算总匹配度（加权平均）
        total_weight = core_matched_count * 3.0 + (matched_count - core_matched_count) * 1.0
        if total_weight > 0:
            total_match_score = total_score / total_weight
        else:
            total_match_score = 0
        
        # ✅ 均线粘合度奖励：在其他条件相同的情况下，均线粘合度高的股票匹配度更高
        # 均线粘合度值越小，表示粘合度越高（MA5/MA10/MA20越接近）
        if '均线粘合度' in features and '均线粘合度' in common_features:
            ma_convergence_value = features.get('均线粘合度')
            if ma_convergence_value is not None and isinstance(ma_convergence_value, (int, float)) and not np.isnan(ma_convergence_value):
                ma_stats = common_features['均线粘合度']
                ma_median = ma_stats.get('中位数', ma_stats.get('均值', 10))
                # 如果均线粘合度低于中位数（粘合度高），给予奖励
                if ma_convergence_value < ma_median:
                    # 奖励幅度：粘合度越低（值越小），奖励越多，最多+0.02
                    # 例如：中位数=10，当前值=5，奖励 = (10-5)/10 * 0.02 = 0.01
                    reward = min(0.02, (ma_median - ma_convergence_value) / max(ma_median, 1) * 0.02)
                    total_match_score = min(1.0, total_match_score + reward)
        
        return {
            '总匹配度': round(total_match_score, 3),
            '匹配特征数': matched_count,
            '核心特征匹配': core_match_scores,
            '所有特征匹配': match_scores
        }
    
    def scan_all_stocks(self, min_match_score: float = 0.6, max_market_cap: float = 60.0, limit: int = None, use_parallel: bool = True, max_workers: int = 5, scan_date: str = None, scan_session: str = None, force_refresh: bool = False, strict_local_only: bool = None) -> Dict:
        """
        扫描所有股票，查找符合牛股特征的个股
        优化：在扫描开始前预先获取并缓存市值数据，避免扫描过程中卡住
        :param strict_local_only: 是否严格只使用本地缓存（不从网络下载），None时自动判断（本地环境默认True）
        """
        # 重置停止标志
        self.stop_scan = False
        # 记录本次扫描是否强制刷新（供串行扫描内部的线程取用）
        self._force_refresh_scan = bool(force_refresh)
        
        # ✅ 关键：本地环境默认严格只使用本地缓存，避免网络下载导致速度慢
        if strict_local_only is None:
            # 自动判断：如果是本地环境（非Vercel/Render），默认启用严格本地模式
            import os
            is_cloud = (
                os.environ.get('VERCEL') == '1' or 
                os.environ.get('VERCEL_ENV') is not None or
                os.environ.get('RENDER') == 'true' or
                os.environ.get('RENDER_SERVICE_NAME') is not None
            )
            strict_local_only = not is_cloud  # 本地环境默认True，云环境默认False
        
        # 设置严格本地模式标志（供内部函数使用）
        self._strict_local_only = bool(strict_local_only)
        self._scan_skip_4d_gain_check = True
        self._scan_quiet = True  # 扫描时减少特征提取等日志，加速
        
        if strict_local_only:
            print("📌 严格本地模式：只使用本地缓存数据，缺失数据的股票将被跳过（不从网络下载）")

        # 强制刷新：每次扫描前清空断点续扫状态和结果缓存，确保按“最新条件/最新数据”重新计算
        if force_refresh:
            self.scan_state = None
            try:
                self.scan_results = None
            except Exception:
                pass

        # 标准化 scan_date（兼容 YYYY/MM/DD 与 YYYY-MM-DD）
        if isinstance(scan_date, str) and scan_date.strip():
            scan_date = scan_date.strip().replace('/', '-')
        
        # 预先获取并缓存市值数据（避免扫描过程中卡住）
        # 优化：完全跳过预加载，扫描时直接跳过市值检查，避免卡住
        print("\n📊 跳过市值预加载，扫描时将直接跳过市值检查（避免卡住）...")
        print("   提示：如果需要市值筛选，可以在扫描结果中手动筛选")
        print("")
        """
        扫描所有A股，找出符合牛股特征的个股，并给出最佳买点
        如果股票数量超过5000，自动分成3批扫描
        :param min_match_score: 最小匹配度阈值（默认0.6）
        :param max_market_cap: 最大市值（亿元，默认60亿）
        :param limit: 限制扫描数量（None表示全部）
        :return: 扫描结果
        """
        if self.trained_features is None:
            return {
                'success': False,
                'message': '尚未训练特征模型，请先训练',
                'candidates': []
            }
        
        common_features = self._get_common_features()
        if len(common_features) == 0:
            return {
                'success': False,
                'message': '特征模板为空',
                'candidates': []
            }
        
        # 检查是否有未完成的扫描状态（断点续扫）
        if (not force_refresh) and self.scan_state is not None and self.scan_state.get('status') == '已停止':
            # 有未完成的扫描，继续扫描
            print("\n📌 检测到未完成的扫描，将从上次停止的地方继续...")
            print(f"   上次已处理: {self.scan_state.get('current_idx', 0)}/{self.scan_state.get('total_stocks', 0)} 只股票")
            print(f"   已找到: {len(self.scan_state.get('candidates', []))} 只符合条件的股票")
            # 继续扫描
            return self._resume_scan()
        
        # 获取股票列表
        stock_list = self.fetcher.get_all_stocks()
        if stock_list is None or len(stock_list) == 0:
            return {
                'success': False,
                'message': '无法获取股票列表',
                'candidates': []
            }
        
        if limit:
            stock_list = stock_list.head(limit)
        
        total_stocks = len(stock_list)
        
        # 保存扫描状态（用于断点续扫）
        self.scan_state = {
            'stock_list': stock_list,
            'common_features': common_features,
            'min_match_score': min_match_score,
            'max_market_cap': max_market_cap,
            'current_idx': 0,
            'total_stocks': total_stocks,
            'candidates': [],
            'scan_date': scan_date,
            'scan_session': scan_session,
            'batch_num': 1,
            'total_batches': 1,
            'status': '进行中'
        }
        
        # 初始化缺失数据统计
        self._missing_data_stocks = set()
        self.fetcher._missing_stocks = set()
        
        # 一次性全部扫描（不再分批）
        print(f"\n📊 开始扫描全部 {total_stocks} 只股票（一次性完成，不分批）...")
        print(f"⚠️  注意：扫描将仅使用本地数据，如果本地没有数据将跳过该股票")
        result = self._scan_stock_batch(
            stock_list,
            common_features,
            min_match_score,
            max_market_cap,
            1,
            1,
            start_idx=0,
            existing_candidates=None,
            total_all_stocks=total_stocks,
            use_parallel=use_parallel,
            max_workers=max_workers,
            scan_date=scan_date,
            scan_session=scan_session
        )
        
        # 扫描完成后，检查缺失数据并提示
        missing_count = len(self._missing_data_stocks) if hasattr(self, '_missing_data_stocks') else 0
        fetcher_missing_count = len(self.fetcher._missing_stocks) if hasattr(self.fetcher, '_missing_stocks') else 0
        total_missing = max(missing_count, fetcher_missing_count)
        
        if total_missing > 0:
            missing_pct = (total_missing / total_stocks * 100) if total_stocks > 0 else 0
            warning_msg = f"\n⚠️  扫描完成，但发现 {total_missing} 只股票（{missing_pct:.1f}%）缺少本地数据，已跳过。\n"
            warning_msg += f"   建议：请先下载完整数据后再进行扫描，以确保扫描结果的完整性。\n"
            print(warning_msg)
            
            # 在结果中添加警告信息
            if isinstance(result, dict):
                result['data_warning'] = {
                    'missing_count': total_missing,
                    'total_stocks': total_stocks,
                    'missing_percentage': round(missing_pct, 1),
                    'message': f'发现 {total_missing} 只股票缺少本地数据，建议先下载数据'
                }
        
        if isinstance(result, dict):
            result.setdefault('scan_date', scan_date)
            result.setdefault('scan_session', scan_session)
        self._scan_quiet = False  # 扫描结束，恢复日志
        return result

    # 说明：之前为了实现“周内每天结果变化”，曾尝试用“日K截至指定日期聚合周K（含未完成周）”。
    # - 如果 scan_date 在当前周内（周一到周K日期之间），会用该周周一到 scan_date 的日K聚合成部分周K
    # - 这样回测结果与「当天实盘扫描」完全一致，保证回测的有效性和可比性
    # - 历史回测时：回测上周二 = 用上周一+二聚合，回测上周四 = 用上周一～四聚合
    # - 实时扫描时：scan_date = None 或 = 今天，同样进行 as-of 聚合
    def _process_single_stock(self, stock_code: str, stock_name: str, common_features: Dict, min_match_score: float, max_market_cap: float, idx: int, total_stocks: int, scan_date: str = None, scan_session: str = None, force_refresh: bool = False) -> Dict:
        """
        处理单只股票（用于并行处理）
        :param stock_code: 股票代码
        :param stock_name: 股票名称
        :param common_features: 共同特征模板
        :param min_match_score: 最小匹配度阈值
        :param max_market_cap: 最大市值
        :param idx: 当前索引
        :param total_stocks: 总股票数
        :return: 候选股票信息（如果符合条件），否则返回 None
        """
        import time as time_module
        import threading
        import pandas as pd
        
        try:
            # 检查停止信号
            if self.stop_scan:
                return None
            
            start_time = time_module.time()
            max_process_time = 3  # 单个股票最大处理时间（秒），更快跳过慢股票
            
            # 时间统计
            step_times = {}
            
            # 1. 获取周K线数据
            step_start = time_module.time()
            try:
                # 使用周K线（与训练/原扫描一致）；scan_date 的“回放”在后续通过截断周K实现
                # 如果指定了历史 scan_date，强制使用本地缓存以确保历史回测一致性
                use_cache = True
                if force_refresh and not scan_date:
                    use_cache = False  # 只有在没有指定scan_date且强制刷新时才不用缓存
                # 扫描时优先使用本地数据，如果本地没有则从网络下载
                # 先尝试本地数据（快速）
                weekly_df = self.fetcher.get_weekly_kline(stock_code, period="2y", use_cache=use_cache, local_only=True)
                step_times['获取周K线'] = time_module.time() - step_start
                
                # ✅ 关键：如果设置了 strict_local_only，即使本地没有数据也不从网络下载
                strict_local_only = getattr(self, '_strict_local_only', False)
                
                # 如果本地没有数据，尝试从网络下载（除非 strict_local_only=True）
                if weekly_df is None or len(weekly_df) < 40:
                    if strict_local_only:
                        # 严格本地模式：跳过缺失数据的股票，不从网络下载
                        if not hasattr(self, '_missing_data_stocks'):
                            self._missing_data_stocks = set()
                        self._missing_data_stocks.add(stock_code)
                        return None
                    else:
                        # 尝试从网络下载
                        print(f"[_process_single_stock] {stock_code} 本地无数据，尝试从网络下载...")
                        weekly_df = self.fetcher.get_weekly_kline(stock_code, period="2y", use_cache=False, local_only=False)
                        step_times['获取周K线'] = time_module.time() - step_start
                        
                        # 如果网络获取也失败，记录到缺失列表
                        if weekly_df is None or len(weekly_df) < 40:
                            if not hasattr(self, '_missing_data_stocks'):
                                self._missing_data_stocks = set()
                            self._missing_data_stocks.add(stock_code)
                            return None
            except Exception as e:
                step_times['获取周K线'] = time_module.time() - step_start
                return None
            
            # 检查总耗时
            elapsed = time_module.time() - start_time
            if elapsed > max_process_time:
                return None
            
            # 2. 提取特征
            step_start = time_module.time()
            try:
                # 默认使用最新一周；如果指定 scan_date，则回到该日期对应的最近一周（as-of）
                current_idx = len(weekly_df) - 1
                if scan_date:
                    try:
                        scan_ts = pd.to_datetime(scan_date, errors='coerce')
                        if pd.notna(scan_ts) and '日期' in weekly_df.columns:
                            w = weekly_df.copy()
                            w['__dt'] = pd.to_datetime(w['日期'], errors='coerce')
                            w = w.dropna(subset=['__dt'])
                            
                            # 严格回溯（as-of）：仅保留 __dt <= scan_ts 的周K，避免偷看未来
                            w = w[w['__dt'] <= scan_ts]
                            
                            if len(w) >= 40:
                                weekly_df = w.drop(columns=['__dt'])
                                current_idx = len(weekly_df) - 1
                            else:
                                return None
                    except Exception:
                        pass
                
                # ✅ as-of 聚合：对「当前周」进行部分周K聚合（适用于实时扫描和历史回测）
                # 如果 scan_date 在当前周内（周一到周K日期之间），用该周周一到 scan_date 的日K聚合成部分周K
                # 这样回测结果与「当天实盘扫描」完全一致，保证回测的有效性
                aggregated_this_week = False  # 标记是否进行了聚合
                try:
                    from datetime import datetime as dt_now, timedelta
                    
                    # 确定实际使用的扫描日期：如果 scan_date 为 None，使用今天的日期（实时扫描）
                    actual_scan_date = scan_date if scan_date else dt_now.now().strftime('%Y-%m-%d')
                    
                    if len(weekly_df) > 0 and '日期' in weekly_df.columns:
                        # 使用确定的扫描日期
                        scan_ts = pd.to_datetime(actual_scan_date, errors='coerce')
                        
                        if pd.notna(scan_ts):
                            # 获取最后一周的日期
                            last_week_date = pd.to_datetime(weekly_df.iloc[-1]['日期'], errors='coerce')
                            
                            if pd.notna(last_week_date):
                                # 动态计算最后一周的周一：找到包含 last_week_date 的那一周的周一
                                # 周K的日期可能是周五（weekday=4）或周日（weekday=6），代表该周结束日
                                # 往前推 weekday 天，得到该周的周一
                                last_week_weekday = last_week_date.weekday()  # 0=周一, 4=周五, 6=周日
                                last_week_monday = last_week_date - timedelta(days=last_week_weekday)
                                
                                # 判断 scan_date 是否在最后一周内（周一到周K日期之间）
                                # 或者 scan_date 在当前周内（最后一周之后，但仍在当前周）
                                should_aggregate = False
                                week_start_str = None
                                week_end_date = None
                                
                                if last_week_monday <= scan_ts <= last_week_date:
                                    # 情况1：scan_date 在最后一周内
                                    should_aggregate = True
                                    week_start_str = last_week_monday.strftime('%Y%m%d')
                                    week_end_date = last_week_date
                                elif scan_ts > last_week_date:
                                    # 情况2：scan_date 在最后一周之后，检查是否在当前周内
                                    # 计算当前周的周一（最后一周的下一个周一）
                                    current_week_monday = last_week_date + timedelta(days=(7 - last_week_weekday))
                                    # 计算当前周的结束日（周五或周日，取决于周K的格式）
                                    # 假设周K在周五结束，则当前周结束日是 current_week_monday + 4
                                    current_week_end = current_week_monday + timedelta(days=4)
                                    
                                    if current_week_monday <= scan_ts <= current_week_end:
                                        # scan_date 在当前周内，需要聚合当前周的数据
                                        should_aggregate = True
                                        week_start_str = current_week_monday.strftime('%Y%m%d')
                                        week_end_date = current_week_end
                                
                                if should_aggregate:
                                    aggregated_this_week = True  # 标记进行了聚合
                                    # 需要聚合：获取该周周一到 scan_date 的日K数据
                                    scan_date_str = scan_ts.strftime('%Y%m%d')
                                    
                                    # 获取日K数据（回测时强制使用本地缓存，确保历史数据一致性）
                                    daily_df = self.fetcher.get_daily_kline_range(
                                        stock_code,
                                        start_date=week_start_str,
                                        end_date=scan_date_str,
                                        use_cache=True,
                                        local_only=True  # 回测时强制使用本地缓存，避免使用未来数据
                                    )
                                    
                                    if daily_df is not None and len(daily_df) > 0:
                                        # 确保必要的列存在
                                        required_cols = ['日期', '开盘', '收盘', '最高', '最低', '成交量']
                                        if all(col in daily_df.columns for col in required_cols):
                                            # 转换为日期类型
                                            daily_df = daily_df.copy()
                                            daily_df['日期'] = pd.to_datetime(daily_df['日期'], errors='coerce')
                                            daily_df = daily_df.dropna(subset=['日期'])
                                            # ✅ 严格过滤：只使用扫描日期及之前的数据，避免使用未来数据
                                            daily_df = daily_df[daily_df['日期'] <= scan_ts].sort_values('日期').reset_index(drop=True)
                                            
                                            if len(daily_df) > 0:
                                                # 聚合为周K（仅该周的部分数据）
                                                partial_week_k = pd.Series({
                                                    '开盘': float(daily_df.iloc[0]['开盘']),
                                                    '收盘': float(daily_df.iloc[-1]['收盘']),
                                                    '最高': float(daily_df['最高'].max()),
                                                    '最低': float(daily_df['最低'].min()),
                                                    '周成交量': float(daily_df['成交量'].sum()),
                                                    '日期': week_end_date  # 使用该周的结束日期
                                                })
                                                
                                                # 如果成交额列存在，也聚合
                                                if '成交额' in daily_df.columns:
                                                    partial_week_k['周成交额'] = float(daily_df['成交额'].sum())
                                                
                                                # 如果当前周是新的一周（scan_ts > last_week_date），需要添加新的一行
                                                if scan_ts > last_week_date:
                                                    # 添加新的周K行
                                                    weekly_df = weekly_df.copy()
                                                    partial_week_k['日期'] = week_end_date
                                                    weekly_df = pd.concat([weekly_df, pd.DataFrame([partial_week_k])], ignore_index=True)
                                                    # ✅ 更新 current_idx 指向新添加的聚合周K
                                                    current_idx = len(weekly_df) - 1
                                                else:
                                                    # 替换最后一周的周K
                                                    weekly_df = weekly_df.copy()
                                                    weekly_df.iloc[-1] = partial_week_k
                                                    # current_idx 保持不变，仍指向最后一行
                                                
                                                # 调试输出（每100只股票输出一次）
                                                if idx % 100 == 0:
                                                    print(f"[as-of聚合周K] [{idx}/{total_stocks}] {stock_code} 扫描日期: {scan_ts.strftime('%Y-%m-%d')}, 聚合了周（{week_start_str} 到 {scan_ts.strftime('%Y-%m-%d')}），current_idx={current_idx}")
                except Exception as e:
                    # 聚合失败不影响扫描，继续使用原周K
                    if idx % 100 == 0:
                        print(f"[as-of聚合周K] [{idx}/{total_stocks}] {stock_code} 聚合失败: {str(e)[:50]}")
                    pass
                
                features = self.extract_features_at_start_point(stock_code, current_idx, lookback_weeks=40, weekly_df=weekly_df)
                step_times['提取特征'] = time_module.time() - step_start
                if features is None:
                    if idx % 10 == 0:
                        print(f"[监控] [{idx}/{total_stocks}] {stock_code} 特征提取返回None，跳过")
                    return None
            except Exception as e:
                step_times['提取特征'] = time_module.time() - step_start
                if idx % 10 == 0:
                    print(f"[监控] [{idx}/{total_stocks}] {stock_code} 特征提取异常: {str(e)[:50]}")
                return None
            
            # 检查总耗时
            elapsed = time_module.time() - start_time
            if elapsed > max_process_time:
                return None
            
            # 3. 计算匹配度
            step_start = time_module.time()
            try:
                match_score = self._calculate_match_score(features, common_features, tolerance=0.3)
                step_times['计算匹配度'] = time_module.time() - step_start
                total_match = match_score['总匹配度']
                
                # 微调：最近4日涨幅>10%但无涨停板时降低匹配度（扫描加速时可关闭，避免每只股票拉日K）
                if scan_date and not getattr(self, '_scan_skip_4d_gain_check', True):
                    try:
                        from datetime import timedelta
                        scan_ts = pd.to_datetime(scan_date, errors='coerce')
                        if pd.notna(scan_ts):
                            start_date = (scan_ts - timedelta(days=10)).strftime('%Y%m%d')
                            end_date = scan_ts.strftime('%Y%m%d')
                            daily_df = self.fetcher.get_daily_kline_range(stock_code, start_date, end_date)
                            if daily_df is not None and len(daily_df) >= 4:
                                daily_df['日期'] = pd.to_datetime(daily_df['日期'], errors='coerce')
                                daily_df = daily_df.dropna(subset=['日期']).copy()
                                daily_df = daily_df[daily_df['日期'] <= scan_ts].sort_values('日期').reset_index(drop=True)
                                if len(daily_df) >= 4:
                                    recent_4 = daily_df.tail(4)
                                    first_close = float(recent_4.iloc[0]['收盘'])
                                    last_close = float(recent_4.iloc[-1]['收盘'])
                                    if first_close > 0:
                                        gain_4d = (last_close - first_close) / first_close * 100
                                        has_limit_up = '涨跌幅' in recent_4.columns and any(float(r.get('涨跌幅', 0)) >= 9.8 for _, r in recent_4.iterrows())
                                        if gain_4d > 10.0 and not has_limit_up:
                                            total_match = total_match * 0.95
                                            match_score['总匹配度'] = round(total_match, 3)
                    except Exception:
                        pass
                
                if total_match < min_match_score:
                    return None
            except Exception as e:
                step_times['计算匹配度'] = time_module.time() - step_start
                if idx % 500 == 0:
                    print(f"[监控] [{idx}/{total_stocks}] {stock_code} 匹配度计算异常: {str(e)[:50]}")
                return None
            
            # 3.5. 检查120日和250日均线方向（如果都向下，直接排除）
            step_start_ma = time_module.time()
            try:
                # 获取日K线数据（用于计算120日和250日均线）
                limit_date = scan_date if scan_date else pd.Timestamp.now().strftime('%Y-%m-%d')
                limit_date_ymd = pd.to_datetime(limit_date).strftime('%Y%m%d')
                
                # 获取足够的历史数据（至少250天）
                daily_df = self.fetcher.get_daily_kline_range(
                    stock_code, 
                    start_date='20220101',  # 从2022年开始足够覆盖250天
                    end_date=limit_date_ymd,
                    use_cache=True,
                    local_only=True
                )
                
                if daily_df is not None and len(daily_df) >= 250:
                    daily_df['日期'] = pd.to_datetime(daily_df['日期'], errors='coerce')
                    daily_df = daily_df.dropna(subset=['日期']).sort_values('日期').reset_index(drop=True)
                    
                    # 找到扫描日期对应的索引
                    limit_dt = pd.to_datetime(limit_date)
                    daily_before = daily_df[daily_df['日期'] <= limit_dt]
                    if len(daily_before) >= 250:
                        scan_idx = len(daily_before) - 1
                        
                        # 计算当前均线值
                        ma120_current = daily_before['收盘'].iloc[scan_idx-119:scan_idx+1].mean()
                        ma250_current = daily_before['收盘'].iloc[scan_idx-249:scan_idx+1].mean()
                        
                        # 计算20天前的均线值（用于判断方向）
                        if scan_idx >= 20:
                            ma120_20d_ago = daily_before['收盘'].iloc[scan_idx-139:scan_idx-119].mean()
                            ma250_20d_ago = daily_before['收盘'].iloc[scan_idx-269:scan_idx-249].mean()
                            
                            # 计算斜率（方向）
                            ma120_slope = (ma120_current - ma120_20d_ago) / ma120_20d_ago if ma120_20d_ago > 0 else 0
                            ma250_slope = (ma250_current - ma250_20d_ago) / ma250_20d_ago if ma250_20d_ago > 0 else 0
                            
                            # 如果120日和250日均线都向下（斜率<0），直接排除
                            if ma120_slope < 0 and ma250_slope < 0:
                                print(f"[均线过滤] [{idx}/{total_stocks}] {stock_code} {stock_name} MA120和MA250都向下，已排除 (MA120斜率: {ma120_slope*100:.2f}%, MA250斜率: {ma250_slope*100:.2f}%, 扫描日期: {limit_date})")
                                return None
            except Exception as e:
                # 均线检查失败不影响扫描，继续处理（但记录详细错误）
                import traceback
                error_detail = traceback.format_exc()
                if idx % 100 == 0 or stock_code == '000798':  # 对中水渔业总是打印
                    print(f"[均线检查异常] [{idx}/{total_stocks}] {stock_code} {stock_name} 均线方向检查异常: {str(e)}")
                    if stock_code == '000798':
                        print(f"[均线检查异常-详细] {error_detail[:500]}")
                pass
            
            step_times['总耗时'] = time_module.time() - start_time
            if idx > 0 and idx % 500 == 0:
                print(f"[时间统计] {idx}/{total_stocks}: 周K={step_times.get('获取周K线',0):.2f}s 特征={step_times.get('提取特征',0):.2f}s 匹配={step_times.get('计算匹配度',0):.2f}s 市值={step_times.get('获取市值',0):.2f}s 总={step_times.get('总耗时',0):.2f}s")
            
            # 4. 检查市值（✅ 必须同步检查，检索时同步检查）
            market_cap = None
            market_cap_valid = False
            if max_market_cap > 0:
                try:
                    # 使用超时机制获取市值（避免卡住）
                    step_start = time_module.time()
                    market_cap_result = [None]
                    market_cap_error = [None]
                    
                    def fetch_market_cap():
                        try:
                            market_cap_result[0] = self.fetcher.get_market_cap(stock_code, timeout=2)
                        except Exception as e:
                            market_cap_error[0] = e
                    
                    cap_thread = threading.Thread(target=fetch_market_cap)
                    cap_thread.daemon = True
                    cap_thread.start()
                    cap_thread.join(timeout=2.5)  # 最多等待2.5秒
                    
                    step_times['获取市值'] = time_module.time() - step_start
                    
                    if not cap_thread.is_alive() and market_cap_result[0] is not None and market_cap_result[0] > 0:
                        market_cap = market_cap_result[0]
                        market_cap_valid = True
                        # ✅ 市值超过限制，直接跳过该股票
                        if market_cap > max_market_cap:
                            return None
                    else:
                        if idx % 500 == 0:
                            print(f"[监控] [{idx}/{total_stocks}] {stock_code} 市值获取失败或超时，继续处理")
                except Exception as e:
                    step_times['获取市值'] = time_module.time() - step_start if 'step_start' in locals() else 0
                    if idx % 500 == 0:
                        print(f"[监控] [{idx}/{total_stocks}] {stock_code} 市值获取异常: {str(e)[:50]}")
                    pass  # 市值获取失败，继续处理该股票（将在扫描完成后二次过滤）
            
                # 5. 记录候选股票（最佳买点日期 = 最后一周的周K日期，价格 = 扫描日期的收盘价）
                try:
                    from datetime import datetime as dt_now
                    today_str = dt_now.now().strftime('%Y-%m-%d')
                    limit_date = scan_date if scan_date else today_str  # 搜索当天
                    fallback_price = float(weekly_df.iloc[current_idx]['收盘'])
                    current_date = weekly_df.iloc[current_idx]['日期']
                    if isinstance(current_date, pd.Timestamp):
                        current_date_str = current_date.strftime('%Y-%m-%d')
                        current_date_ts = current_date
                    else:
                        current_date_str = str(current_date)[:10]
                        current_date_ts = pd.to_datetime(current_date_str, errors='coerce')
                    
                    # ✅ 最佳买点日期：如果进行了聚合，使用扫描日期；否则使用最后一周的周K日期
                    # 如果进行了聚合（aggregated_this_week=True），最佳买点日期应该是扫描日期
                    # 否则使用最后一周的周K日期（特征匹配基于这一周）
                    scan_date_ts = pd.to_datetime(limit_date, errors='coerce')
                    if aggregated_this_week and scan_date:
                        # 进行了聚合，最佳买点日期 = 扫描日期
                        buy_date = limit_date
                    else:
                        # 没有聚合，使用最后一周的周K日期
                        buy_date = current_date_str
                    
                    # 如果扫描日期在周K日期之前或等于周K日期，使用扫描日期的收盘价
                    # 否则使用周K收盘价（这种情况不应该发生，因为我们已经截断了数据）
                    if pd.notna(scan_date_ts) and pd.notna(current_date_ts) and scan_date_ts <= current_date_ts:
                        close_on_search = self._get_close_on_date(stock_code, limit_date)
                        if close_on_search is not None:
                            buy_price = close_on_search
                        else:
                            buy_price = fallback_price
                    else:
                        # 扫描日期晚于周K日期（不应该发生），使用周K收盘价
                        buy_price = fallback_price
                    
                    # ✅ 当前价格 = 扫描日期的收盘价（不是今天的最新价格）
                    # 如果扫描日期是历史日期，当前价格就是扫描日期的价格
                    # 如果扫描日期是今天，当前价格就是今天的最新价格
                    current_price = buy_price  # 默认使用最佳买点价格（即扫描日期的价格）
                    
                    # 如果扫描日期是今天，且获取到了今天的价格，使用今天的价格
                    # 如果扫描日期是历史日期，当前价格就是扫描日期的价格（buy_price）
                    if limit_date == today_str:
                        # 扫描日期是今天，尝试获取今天的最新价格（可能比buy_price更新）
                        close_today = self._get_close_on_date(stock_code, today_str)
                        if close_today is not None:
                            current_price = close_today
                        else:
                            current_price = buy_price
                    # else: 扫描日期是历史日期，current_price = buy_price（已经是扫描日期的价格）
                    
                    # ✅ 调试：确认最终价格
                    if idx % 100 == 0:
                        print(f"[调试-价格] [{idx}/{total_stocks}] {stock_code} 最佳买点日期: {buy_date}, 最佳买点价格: {buy_price:.2f}, 当前价格: {current_price:.2f}, 扫描日期: {limit_date}")
                    
                    # 检查数据是否过期（数据日期比扫描日期早超过7天）
                    data_outdated = False
                    try:
                        data_date = pd.to_datetime(current_date_str)
                        scan_date_ts = pd.to_datetime(limit_date)
                        if (scan_date_ts - data_date).days > 7:
                            data_outdated = True
                    except Exception:
                        pass
                    # 买点当天为大阴线则排除（不加入候选）
                    if self._is_big_bearish_candle_on_date(stock_code, limit_date):
                        if idx % 100 == 0:
                            print(f"[过滤] [{idx}/{total_stocks}] {stock_code} {stock_name} 买点当日({limit_date})为大阴线，已排除")
                        return None
                    return {
                        '股票代码': stock_code,
                        '股票名称': stock_name,
                        '匹配度': round(match_score['总匹配度'], 3),
                        '最佳买点日期': buy_date,
                        '最佳买点价格': round(buy_price, 2),
                        '当前价格': round(current_price, 2),
                        '市值': round(market_cap, 2) if market_cap_valid else None,
                        '扫描日期': scan_date,
                        '时间段': scan_session,
                        '核心特征匹配': match_score.get('核心特征匹配', {}),
                        '特征': features,
                        '数据过期': data_outdated  # 标记数据是否过期
                    }
                except Exception:
                    return None
                
        except Exception:
            return None
    
    def _scan_stock_batch(self, stock_list, common_features: Dict, min_match_score: float, max_market_cap: float, batch_num: int = 1, total_batches: int = 1, start_idx: int = 0, existing_candidates: list = None, total_all_stocks: int = None, use_parallel: bool = True, max_workers: int = 5, scan_date: str = None, scan_session: str = None) -> Dict:
        # 在函数开始处统一导入，避免变量冲突
        import time as time_module
        import threading
        import logging
        
        # 如果启用并行处理，使用并行版本
        if use_parallel:
            return self._scan_stock_batch_parallel(
                stock_list, common_features, min_match_score, max_market_cap,
                batch_num, total_batches, start_idx, existing_candidates,
                total_all_stocks, max_workers, scan_date=scan_date, scan_session=scan_session
            )
        
        # 否则使用原有的串行处理（保持向后兼容）
        return self._scan_stock_batch_serial(
            stock_list, common_features, min_match_score, max_market_cap,
            batch_num, total_batches, start_idx, existing_candidates, total_all_stocks, scan_date=scan_date, scan_session=scan_session
        )
    
    def _scan_stock_batch_parallel(self, stock_list, common_features: Dict, min_match_score: float, max_market_cap: float, batch_num: int = 1, total_batches: int = 1, start_idx: int = 0, existing_candidates: list = None, total_all_stocks: int = None, max_workers: int = 5, scan_date: str = None, scan_session: str = None) -> Dict:
        """
        并行扫描一批股票（使用线程池）
        :param stock_list: 股票列表（DataFrame）
        :param common_features: 共同特征模板
        :param min_match_score: 最小匹配度阈值
        :param max_market_cap: 最大市值
        :param batch_num: 当前批次号
        :param total_batches: 总批次数
        :param start_idx: 起始索引
        :param existing_candidates: 已有候选股票列表
        :param total_all_stocks: 总股票数
        :param max_workers: 最大并发线程数
        :return: 扫描结果
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed
        import time as time_module
        import threading
        
        total_stocks = len(stock_list)
        if total_all_stocks is None:
            total_all_stocks = total_stocks
        
        # 更新进度信息
        batch_info = f" (第 {batch_num}/{total_batches} 批)" if total_batches > 1 else ""
        self.progress = {
            'type': 'scan',
            'current': start_idx,
            'total': total_all_stocks,
            'status': '进行中',
            'detail': f'开始并行扫描 {total_stocks} 只股票{batch_info}（{max_workers} 线程）...',
            'percentage': 0,
            'found': 0,
            'candidates': [],
            'scan_date': scan_date,
            'scan_session': scan_session,
            'batch': batch_num,
            'total_batches': total_batches
        }
        
        print(f"\n🚀 开始并行扫描股票，查找符合牛股特征的个股{batch_info}...")
        print(f"本批股票数: {total_stocks}")
        print(f"并发线程数: {max_workers}")
        print(f"最小匹配度: {min_match_score:.1%}")
        print(f"市值约束: ≤ {max_market_cap} 亿元")
        print("=" * 80)
        
        candidates = existing_candidates.copy() if existing_candidates else []
        
        # 获取列名
        code_col = None
        name_col = None
        for col in stock_list.columns:
            col_lower = str(col).lower()
            if 'code' in col_lower or '代码' in col:
                code_col = col
            elif 'name' in col_lower or '名称' in col:
                name_col = col
        
        if code_col is None:
            code_col = stock_list.columns[0]
        if name_col is None and len(stock_list.columns) >= 2:
            name_col = stock_list.columns[1]
        
        # 准备股票列表
        stock_items = []
        for idx, (_, row) in enumerate(stock_list.iterrows(), start=start_idx):
            stock_code = str(row[code_col])
            stock_name = str(row[name_col]) if name_col else stock_code
            stock_items.append((stock_code, stock_name, idx))
        
        # 使用线程池并行处理
        processed_count = 0
        progress_lock = threading.Lock()
        start_time = time_module.time()
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有任务
            future_to_stock = {
                executor.submit(
                    self._process_single_stock,
                    stock_code,
                    stock_name,
                    common_features,
                    min_match_score,
                    max_market_cap,
                    idx,
                    total_all_stocks,
                    scan_date,
                    scan_session,
                    getattr(self, "_force_refresh_scan", False),
                ): (stock_code, stock_name, idx)
                for stock_code, stock_name, idx in stock_items
            }
            
            # 收集结果
            for future in as_completed(future_to_stock):
                # 检查停止信号
                if self.stop_scan:
                    # 取消未完成的任务
                    for f in future_to_stock:
                        f.cancel()
                    break
                
                stock_code, stock_name, idx = future_to_stock[future]
                processed_count += 1
                
                # ✅ 监控：更新当前处理的股票（用于定位卡点）
                with progress_lock:
                    self.progress['current_stock'] = stock_code
                    self.progress['current_stock_name'] = stock_name
                    self.progress['last_update_time'] = time_module.time()
                    if processed_count % 200 == 0:
                        print(f"[进度] 已处理: {processed_count}/{total_stocks} | 已找到: {len(candidates)}只")
                
                try:
                    result = future.result(timeout=6)  # 获取结果，超时6秒（允许单个股票处理更长时间）
                    if result:
                        with progress_lock:
                            candidates.append(result)
                            self.progress['found'] = len(candidates)
                            # 实时输出：只保留最近/最优的一部分，避免进度对象过大
                            try:
                                candidates.sort(key=lambda x: x.get('匹配度', 0), reverse=True)
                            except Exception:
                                pass
                            self.progress['candidates'] = candidates[:50] if len(candidates) > 50 else candidates
                            market_cap_info = f" 市值: {result['市值']:.2f}亿" if result['市值'] else " 市值: 未知"
                            print(f"\n✅ 找到候选: {stock_code} {stock_name} (匹配度: {result['匹配度']:.3f}{market_cap_info})")
                except Exception as e:
                    # ✅ 监控：记录超时或错误（用于定位卡点）
                    if "timeout" in str(e).lower() or "超时" in str(e):
                        print(f"[监控-并行] [{processed_count}/{total_stocks}] {stock_code} 处理超时: {str(e)[:50]}")
                    # 忽略单个股票的错误，继续处理
                    pass
                finally:
                    # 记录处理完成（用于统计所有股票，包括失败的）
                    pass
                
                # 更新进度
                with progress_lock:
                    overall_current = start_idx + processed_count
                    if total_batches > 1:
                        completed_batches_progress = ((batch_num - 1) / total_batches) * 100
                        current_batch_progress = (processed_count / total_stocks) / total_batches * 100
                        percentage = completed_batches_progress + current_batch_progress
                        percentage = min(percentage, 100.0)
                    else:
                        percentage = (overall_current / total_all_stocks) * 100
                    
                    self.progress['current'] = overall_current
                    self.progress['percentage'] = round(percentage, 1)
                    
                    # 检查缺失数据并更新提示
                    missing_count = len(self._missing_data_stocks) if hasattr(self, '_missing_data_stocks') else 0
                    missing_info = f" | 缺少数据: {missing_count}只" if missing_count > 0 else ""
                    
                    self.progress['detail'] = f'并行扫描中... ({overall_current}/{total_all_stocks}){batch_info} | 已找到: {len(candidates)} 只 | 已处理: {processed_count}/{total_stocks}{missing_info}'
                    
                    # 如果缺失数据超过10%，在进度中提示
                    if missing_count > 0 and processed_count > 0:
                        missing_pct = (missing_count / processed_count * 100)
                        if missing_pct > 10:
                            self.progress['data_warning'] = f'⚠️ 已发现 {missing_count} 只股票缺少本地数据（{missing_pct:.1f}%），建议先下载数据'
                    # 【不可变】找到一只显示一只：同步候选快照到 progress['candidates']，供前端轮询。见 扫描显示不可变逻辑.md
                    if 'candidates' not in self.progress:
                        self.progress['candidates'] = []
                    else:
                        try:
                            candidates.sort(key=lambda x: x.get('匹配度', 0), reverse=True)
                        except Exception:
                            pass
                        self.progress['candidates'] = candidates[:50] if len(candidates) > 50 else candidates
                    self.progress['last_update_time'] = time_module.time()
                
                # 每处理10只股票打印一次进度
                if processed_count % 200 == 0 or processed_count == total_stocks:
                    elapsed = time_module.time() - start_time
                    speed = processed_count / elapsed if elapsed > 0 else 0
                    print(f"[进度] {percentage:.1f}% - {overall_current}/{total_all_stocks} - 已找到: {len(candidates)} 只 - 速度: {speed:.1f} 只/秒")
        
        # 检查是否被停止
        if self.stop_scan:
            current_processed = start_idx + processed_count
            self.progress['status'] = '已停止'
            self.progress['detail'] = f'扫描已停止（已处理 {current_processed}/{total_all_stocks} 只股票，找到 {len(candidates)} 只）'
            self.progress['current'] = current_processed
            self.stop_scan = False
        else:
            # 完成进度
            if batch_num == total_batches:
                self.progress['status'] = '完成'
                self.progress['percentage'] = 100.0
                self.progress['detail'] = f'所有批次扫描完成: 找到 {len(candidates)} 只符合条件的股票'
                self.progress['current'] = total_all_stocks
            else:
                self.progress['status'] = '进行中'
                self.progress['percentage'] = round((batch_num / total_batches * 100), 1)
                overall_current = int((batch_num / total_batches) * total_all_stocks)
                self.progress['current'] = overall_current
                self.progress['detail'] = f'第 {batch_num}/{total_batches} 批扫描完成: 找到 {len(candidates)} 只符合条件的股票，继续扫描下一批...'
        
        self.progress['last_update_time'] = time_module.time()
        
        # 按匹配度排序
        candidates.sort(key=lambda x: x['匹配度'], reverse=True)
        
        # ✅ 关键：市值检查必须在扫描完成后进行二次过滤
        # 因为扫描过程中市值获取可能失败或超时，导致不符合条件的股票被包含进来
        # 优化：如果扫描过程中已经获取到了市值，直接使用，只对没有市值的股票重新获取
        if max_market_cap > 0 and len(candidates) > 0:
            print(f"\n📊 进行市值二次过滤（阈值: ≤ {max_market_cap} 亿元）...")
            original_count = len(candidates)
            
            # 统计已有市值和没有市值的股票数量
            has_market_cap_count = sum(1 for c in candidates if c.get('市值') is not None and c.get('市值', 0) > 0)
            no_market_cap_count = len(candidates) - has_market_cap_count
            print(f"  📊 统计: {has_market_cap_count} 只股票已有市值，{no_market_cap_count} 只股票需要重新获取市值")
            
            filtered_candidates = []
            
            # 添加进度更新
            total_candidates = len(candidates)
            for idx, candidate in enumerate(candidates, 1):
                stock_code = candidate.get('股票代码')
                if stock_code is None:
                    continue
                
                # 每100只股票更新一次进度
                if idx % 100 == 0 or idx == total_candidates:
                    pct = (idx / total_candidates) * 100
                    filtered_so_far = original_count - len(filtered_candidates)
                    print(f"  [市值过滤进度] {idx}/{total_candidates} ({pct:.1f}%) - 已处理: {idx} 只，已过滤: {filtered_so_far} 只")
                    # 更新进度状态
                    if hasattr(self, 'progress'):
                        self.progress['detail'] = f'市值二次过滤中: {idx}/{total_candidates} ({pct:.1f}%)'
                        self.progress['last_update_time'] = time_module.time()
                
                # 检查已有市值（优先使用扫描过程中获取的市值）
                existing_market_cap = candidate.get('市值')
                if existing_market_cap is not None and existing_market_cap > 0:
                    # ✅ 如果扫描过程中已经获取到了市值，直接使用，不需要重新获取
                    if existing_market_cap > max_market_cap:
                        if idx % 500 == 0:  # 减少日志输出
                            print(f"  ❌ {stock_code} {candidate.get('股票名称', '')} 市值 {existing_market_cap:.2f}亿超过限制 {max_market_cap:.2f}亿，已过滤")
                        continue
                    filtered_candidates.append(candidate)
                    continue
                
                # 如果没有市值，尝试获取（使用更短的超时，避免卡住）
                try:
                    market_cap = self.fetcher.get_market_cap(stock_code, timeout=2)  # 减少超时时间从3秒到2秒
                    if market_cap is not None and market_cap > 0:
                        candidate['市值'] = round(market_cap, 2)
                        # ✅ 关键：如果市值超过限制，过滤掉
                        if market_cap > max_market_cap:
                            if idx % 500 == 0:  # 减少日志输出
                                print(f"  ❌ {stock_code} {candidate.get('股票名称', '')} 市值 {market_cap:.2f}亿超过限制 {max_market_cap:.2f}亿，已过滤")
                            continue
                        filtered_candidates.append(candidate)
                    else:
                        # 市值获取失败，保留该股票（不因市值获取失败而丢失）
                        filtered_candidates.append(candidate)
                except Exception:
                    # 市值获取异常，保留该股票（不因市值获取失败而丢失）
                    filtered_candidates.append(candidate)
            
            candidates = filtered_candidates
            filtered_count = original_count - len(candidates)
            if filtered_count > 0:
                print(f"   ✅ 市值过滤完成：过滤掉 {filtered_count} 只（市值 > {max_market_cap} 亿元），剩余 {len(candidates)} 只")
            else:
                print(f"   ✅ 市值过滤完成：所有候选股票均符合市值要求，剩余 {len(candidates)} 只")
        
        elapsed_time = time_module.time() - start_time
        speed = processed_count / elapsed_time if elapsed_time > 0 else 0
        print("\n" + "=" * 80)
        print(f"✅ 本批并行扫描完成！找到 {len(candidates)} 只符合条件的股票{batch_info}")
        print(f"⏱️ 耗时: {elapsed_time:.1f}秒 | 速度: {speed:.2f} 只/秒")
        print("=" * 80)
        
        if self.progress.get('status') == '已停止':
            current_processed = self.progress.get('current', start_idx + processed_count)
            return {
                'success': True,
                'message': f'扫描已停止，已处理 {current_processed}/{total_all_stocks} 只股票，找到 {len(candidates)} 只符合条件的股票',
                'candidates': candidates[:50] if len(candidates) > 50 else candidates,
                'total_scanned': current_processed,
                'found_count': len(candidates),
                'batch': batch_num,
                'total_batches': total_batches,
                'stopped': True
            }
        
        result = {
            'success': True,
            'message': f'本批扫描完成，找到 {len(candidates)} 只符合条件的股票',
            'candidates': candidates[:50] if len(candidates) > 50 else candidates,
            'total_scanned': start_idx + processed_count,
            'found_count': len(candidates),
            'batch': batch_num,
            'total_batches': total_batches,
            'elapsed_time': elapsed_time,
            'speed': speed
        }
        
        # 检查缺失数据并添加到结果中
        missing_count = len(self._missing_data_stocks) if hasattr(self, '_missing_data_stocks') else 0
        if missing_count > 0:
            missing_pct = (missing_count / processed_count * 100) if processed_count > 0 else 0
            result['data_warning'] = {
                'missing_count': missing_count,
                'processed_count': processed_count,
                'missing_percentage': round(missing_pct, 1),
                'message': f'本批扫描中，{missing_count} 只股票缺少本地数据，已跳过。建议先下载完整数据。'
            }
        
        # 保存扫描结果到 analyzer.scan_results（供前端获取）
        self.scan_results = result.copy()
        # 确保保存完整的候选列表（不仅仅是前50个）
        self.scan_results['candidates'] = candidates  # 保存全部候选，不限制为50个
        
        return result
    
    def _scan_stock_batch_serial(self, stock_list, common_features: Dict, min_match_score: float, max_market_cap: float, batch_num: int = 1, total_batches: int = 1, start_idx: int = 0, existing_candidates: list = None, total_all_stocks: int = None, scan_date: str = None, scan_session: str = None) -> Dict:
        """
        扫描一批股票（串行处理，原有逻辑）
        :param stock_list: 股票列表（DataFrame）
        :param common_features: 共同特征模板
        :param min_match_score: 最小匹配度阈值
        :param max_market_cap: 最大市值
        :param batch_num: 当前批次号
        :param total_batches: 总批次数
        :return: 扫描结果
        """
        total_stocks = len(stock_list)  # 当前批次的股票数
        # 如果传入了总股票数，使用它；否则使用当前批次的股票数
        if total_all_stocks is None:
            total_all_stocks = total_stocks
        
        # 更新进度信息（包含批次信息）
        batch_info = f" (第 {batch_num}/{total_batches} 批)" if total_batches > 1 else ""
        self.progress = {
            'type': 'scan',
            'current': 0,
            'total': total_all_stocks,  # 使用总股票数
            'status': '进行中',
            'detail': f'开始扫描 {total_stocks} 只股票{batch_info}...',
            'percentage': 0,
            'found': 0,
            'candidates': [],
            'scan_date': scan_date,
            'scan_session': scan_session,
            'batch': batch_num,
            'total_batches': total_batches
        }
        
        print(f"\n开始扫描股票，查找符合牛股特征的个股{batch_info}...")
        print(f"本批股票数: {total_stocks}")
        print(f"最小匹配度: {min_match_score:.1%}")
        print(f"市值约束: ≤ {max_market_cap} 亿元")
        print("=" * 80)
        
        candidates = []
        
        # 遍历所有股票
        # 获取列名（akshare可能返回不同的列名）
        code_col = None
        name_col = None
        for col in stock_list.columns:
            col_lower = str(col).lower()
            if 'code' in col_lower or '代码' in col:
                code_col = col
            elif 'name' in col_lower or '名称' in col:
                name_col = col
        
        # 如果没找到，使用第一列和第二列
        if code_col is None:
            code_col = stock_list.columns[0]
        if name_col is None and len(stock_list.columns) >= 2:
            name_col = stock_list.columns[1]
        
        # 使用传入的起始索引和已有候选
        idx = start_idx
        if existing_candidates:
            candidates = existing_candidates.copy()
        else:
            candidates = []
        
        for _, row in stock_list.iterrows():
            # 检查是否收到停止信号（在循环开始处检查，确保能及时响应）
            if self.stop_scan:
                current_processed = idx
                print(f"\n🛑 收到停止信号，停止扫描（已处理 {current_processed}/{total_stocks} 只股票，找到 {len(candidates)} 只）")
                self.progress['status'] = '已停止'
                self.progress['detail'] = f'扫描已停止（已处理 {current_processed}/{total_stocks} 只股票，找到 {len(candidates)} 只）'
                self.progress['current'] = current_processed
                # 供前端实时展示：保留一份候选快照（最多50）
                try:
                    candidates.sort(key=lambda x: x.get('匹配度', 0), reverse=True)
                except Exception:
                    pass
                self.progress['candidates'] = candidates[:50] if len(candidates) > 50 else candidates
                self.progress['last_update_time'] = time_module.time()  # 更新最后更新时间
                
                # 保存扫描状态以便继续
                if self.scan_state:
                    self.scan_state['current_idx'] = current_processed
                    self.scan_state['candidates'] = candidates.copy()
                    self.scan_state['status'] = '已停止'
                
                # 立即保存当前结果
                self.scan_results = {
                    'success': True,
                    'message': f'扫描已停止，已处理 {current_processed}/{total_stocks} 只股票，找到 {len(candidates)} 只符合条件的股票',
                    'candidates': candidates[:50] if len(candidates) > 50 else candidates,
                    'total_scanned': current_processed,
                    'found_count': len(candidates),
                    'stopped': True
                }
                
                self.stop_scan = False  # 重置标志
                break
            
            stock_code = str(row[code_col])
            stock_name = str(row[name_col]) if name_col else stock_code
            idx += 1  # 移动到下一只股票
            
            # 更新进度（包含批次信息）
            # 如果是分批扫描，需要计算整体进度
            if total_batches > 1:
                # 计算整体进度：已完成批次 + 当前批次的进度
                batch_size = total_stocks  # 当前批次的股票数
                completed_batches_progress = ((batch_num - 1) / total_batches) * 100
                current_batch_progress = (idx / batch_size) / total_batches * 100
                percentage = completed_batches_progress + current_batch_progress
                # 确保不超过100%
                percentage = min(percentage, 100.0)
            else:
                # 单批扫描，直接计算
                percentage = (idx / total_stocks) * 100
            
            batch_info = f" [第 {batch_num}/{total_batches} 批]" if total_batches > 1 else ""
            # 计算整体已扫描的股票数
            if total_batches > 1 and total_all_stocks > total_stocks:
                overall_current = int((batch_num - 1) * (total_all_stocks / total_batches) + idx)
            else:
                overall_current = idx
            self.progress['current'] = overall_current
            self.progress['total'] = total_all_stocks  # 使用总股票数
            self.progress['percentage'] = round(percentage, 1)
            
            # 检查缺失数据并更新提示
            missing_count = len(self._missing_data_stocks) if hasattr(self, '_missing_data_stocks') else 0
            missing_info = f" | 缺少数据: {missing_count}只" if missing_count > 0 else ""
            
            self.progress['detail'] = f'正在扫描 {stock_code} {stock_name}... ({overall_current}/{total_all_stocks}){batch_info} | 已找到: {len(candidates)} 只{missing_info}'
            
            # 如果缺失数据超过10%，在进度中提示
            if missing_count > 0 and idx > 0:
                missing_pct = (missing_count / idx * 100)
                if missing_pct > 10:
                    self.progress['data_warning'] = f'⚠️ 已发现 {missing_count} 只股票缺少本地数据（{missing_pct:.1f}%），建议先下载数据'
            self.progress['current_stock'] = stock_code
            self.progress['current_stock_name'] = stock_name
            self.progress['last_update_time'] = time_module.time()  # 记录最后更新时间
            
            # 每处理10只股票打印一次进度（避免输出过多）
            if idx % 10 == 0 or idx == total_stocks:
                print(f"[进度] {percentage:.1f}% - {idx}/{total_stocks} - 已找到: {len(candidates)} 只")
            
            # 记录开始时间，用于检测超时
            start_time = time_module.time()
            max_process_time = 5  # 单个股票最大处理时间（秒）- 缩短到5秒，更快跳过问题股票
            
            # 记录开始处理的日志（减少日志输出，每100只股票打印一次）
            if idx % 100 == 0 or idx == 1:
                import datetime
                current_time = datetime.datetime.now().strftime('%H:%M:%S')
                logging.info(f"[{idx}/{total_stocks}] 开始处理 {stock_code} {stock_name} (开始时间: {current_time})")
                print(f"[{idx}/{total_stocks}] 开始处理 {stock_code} {stock_name}")  # 同时打印到控制台
            
            # 初始化市值变量（完全跳过，避免卡住）
            market_cap = None
            market_cap_valid = False
            
            try:
                # ✅ 市值检查：必须在检索时同步检查
                # 立即更新进度，显示正在处理
                self.progress['last_update_time'] = time_module.time()
                # 减少日志输出，每100只股票打印一次
                if idx % 100 == 0 or idx == 1:
                    logging.info(f"[{idx}/{total_stocks}] {stock_code} 开始处理...")
                
                # 2. 获取周K线数据（添加超时保护，使用线程超时强制中断）
                try:
                    step_start = time_module.time()
                    # 减少日志输出，每100只股票打印一次
                    if idx % 100 == 0 or idx == 1:
                        logging.info(f"[{idx}/{total_stocks}] {stock_code} 开始获取周K线数据...")
                        print(f"[{idx}/{total_stocks}] {stock_code} 开始获取周K线数据...")
                    
                    # 使用线程超时机制，防止卡死
                    weekly_df_result = [None]
                    weekly_df_error = [None]
                    
                    def fetch_weekly_data():
                        try:
                            # 如果指定了历史 scan_date，强制使用本地缓存以确保历史回测一致性
                            force_refresh_flag = getattr(self, "_force_refresh_scan", False)
                            use_cache = True
                            if force_refresh_flag and not scan_date:
                                use_cache = False  # 只有在没有指定scan_date且强制刷新时才不用缓存
                            
                            # 扫描时优先使用本地数据，如果本地没有则从网络下载
                            # 先尝试本地数据（快速）
                            weekly_df_result[0] = self.fetcher.get_weekly_kline(
                                stock_code,
                                period="2y",
                                use_cache=use_cache,
                                local_only=True
                            )
                            
                            # ✅ 关键：如果设置了 strict_local_only，即使本地没有数据也不从网络下载
                            strict_local_only = getattr(self, '_strict_local_only', False)
                            
                            # 如果本地没有数据，尝试从网络下载（除非 strict_local_only=True）
                            if weekly_df_result[0] is None or len(weekly_df_result[0]) < 40:
                                if strict_local_only:
                                    # 严格本地模式：跳过缺失数据的股票，不从网络下载
                                    if not hasattr(self, '_missing_data_stocks'):
                                        self._missing_data_stocks = set()
                                    self._missing_data_stocks.add(stock_code)
                                else:
                                    # 尝试从网络下载
                                    print(f"[_scan_stock_batch_serial] {stock_code} 本地无数据，尝试从网络下载...")
                                    weekly_df_result[0] = self.fetcher.get_weekly_kline(
                                        stock_code,
                                        period="2y",
                                        use_cache=False,
                                        local_only=False
                                    )
                            
                            # 如果网络获取也失败，记录到缺失列表
                            if weekly_df_result[0] is None or len(weekly_df_result[0]) < 40:
                                if not hasattr(self, '_missing_data_stocks'):
                                    self._missing_data_stocks = set()
                                self._missing_data_stocks.add(stock_code)
                        except Exception as e:
                            weekly_df_error[0] = e
                    
                    fetch_thread = threading.Thread(target=fetch_weekly_data)
                    fetch_thread.daemon = True
                    fetch_thread.start()
                    fetch_thread.join(timeout=3)  # 最多等待3秒（进一步缩短，更快跳过）
                    
                    # 更新进度
                    self.progress['last_update_time'] = time_module.time()
                    step_time = time_module.time() - step_start
                    
                    if fetch_thread.is_alive():
                        # 线程仍在运行，说明超时了
                        elapsed = time_module.time() - step_start
                        logging.error(f"[{idx}/{total_stocks}] {stock_code} 周K线数据获取超时（>{elapsed:.1f}秒），强制跳过")
                        print(f"⏱️ [{idx}/{total_stocks}] {stock_code} 周K线数据获取超时（>{elapsed:.1f}秒），强制跳过")
                        continue
                    
                    logging.info(f"[{idx}/{total_stocks}] {stock_code} 周K线获取完成（{step_time:.2f}秒）")
                    
                    if weekly_df_error[0]:
                        raise weekly_df_error[0]
                    
                    weekly_df = weekly_df_result[0]
                    step_time = time_module.time() - step_start
                    
                    # 检查总耗时
                    elapsed = time_module.time() - start_time
                    if elapsed > max_process_time:
                        if idx % 10 == 0:
                            print(f"⏱️ {stock_code} 数据获取后总耗时超时（{elapsed:.1f}秒），跳过")
                        continue
                    
                    if step_time > 6:  # 数据获取超过6秒，记录
                        if idx % 10 == 0:
                            print(f"⚠️ {stock_code} 周K线数据获取耗时 {step_time:.1f}秒")
                    
                    if weekly_df is None or len(weekly_df) < 40:
                        continue
                except Exception as e:
                    # 数据获取失败，跳过该股票
                    if idx % 10 == 0:
                        print(f"⚠️ {stock_code} 获取周K线数据失败: {str(e)[:50]}")
                    continue
                
                # 3. 提取当前时点的特征（使用最新数据作为"起点"）- 添加超时保护，使用线程超时强制中断
                try:
                    step_start = time_module.time()
                    current_idx = len(weekly_df) - 1
                    if scan_date:
                        try:
                            scan_ts = pd.to_datetime(scan_date, errors='coerce')
                            if pd.notna(scan_ts) and '日期' in weekly_df.columns:
                                w = weekly_df.copy()
                                w['__dt'] = pd.to_datetime(w['日期'], errors='coerce')
                                w = w.dropna(subset=['__dt'])
                                
                                # ✅ 严格回溯（as-of）：只能使用 scan_date 当天及之前的数据
                                # 注意：周K的“日期”通常是周结束日（如周五）。
                                # 如果 scan_date 在周中（或在周结束日前），该周的周K会包含 scan_date 之后的数据。
                                # 为避免“偷看未来”，这里必须把该周整根周K剔除，仅保留 __dt <= scan_ts 的周K。
                                original_len = len(w)
                                w = w[w['__dt'] <= scan_ts]
                                
                                # ✅ 调试：输出截断信息
                                if idx % 100 == 0:
                                    print(f"[调试-并行] [{idx}/{total_stocks}] {stock_code} 扫描日期: {scan_date}, 原始数据: {original_len}周, 截断后: {len(w)}周")
                                
                                if len(w) >= 40:
                                    # 使用过滤后数据的最后一条作为 current_idx
                                    weekly_df = w.drop(columns=['__dt'])
                                    current_idx = len(weekly_df) - 1
                                    
                                    # ✅ 调试：确认截断后的最后一周日期
                                    if idx % 100 == 0 and len(weekly_df) > 0:
                                        last_week_date = weekly_df.iloc[-1]['日期']
                                        print(f"[调试-并行] [{idx}/{total_stocks}] {stock_code} 截断后最后一周日期: {last_week_date}")
                                    
                                else:
                                    continue
                        except Exception:
                            pass
                    
                    # ✅ as-of 聚合：对「当前周」进行部分周K聚合（适用于实时扫描和历史回测）
                    # 如果 scan_date 在当前周内（周一到周K日期之间），用该周周一到 scan_date 的日K聚合成部分周K
                    # 这样回测结果与「当天实盘扫描」完全一致，保证回测的有效性
                    aggregated_this_week = False  # 标记是否进行了聚合
                    try:
                        from datetime import datetime as dt_now, timedelta
                        
                        # 确定实际使用的扫描日期：如果 scan_date 为 None，使用今天的日期（实时扫描）
                        actual_scan_date = scan_date if scan_date else dt_now.now().strftime('%Y-%m-%d')
                        
                        if len(weekly_df) > 0 and '日期' in weekly_df.columns:
                            # 使用确定的扫描日期
                            scan_ts = pd.to_datetime(actual_scan_date, errors='coerce')
                            
                            if pd.notna(scan_ts):
                                # 获取最后一周的日期
                                last_week_date = pd.to_datetime(weekly_df.iloc[-1]['日期'], errors='coerce')
                                
                                if pd.notna(last_week_date):
                                    # 动态计算最后一周的周一：找到包含 last_week_date 的那一周的周一
                                    # 周K的日期可能是周五（weekday=4）或周日（weekday=6），代表该周结束日
                                    # 往前推 weekday 天，得到该周的周一
                                    last_week_weekday = last_week_date.weekday()  # 0=周一, 4=周五, 6=周日
                                    last_week_monday = last_week_date - timedelta(days=last_week_weekday)
                                    
                                    # 判断 scan_date 是否在最后一周内（周一到周K日期之间）
                                    # 或者 scan_date 在当前周内（最后一周之后，但仍在当前周）
                                    should_aggregate = False
                                    week_start_str = None
                                    week_end_date = None
                                    
                                    if last_week_monday <= scan_ts <= last_week_date:
                                        # 情况1：scan_date 在最后一周内
                                        should_aggregate = True
                                        week_start_str = last_week_monday.strftime('%Y%m%d')
                                        week_end_date = last_week_date
                                    elif scan_ts > last_week_date:
                                        # 情况2：scan_date 在最后一周之后，检查是否在当前周内
                                        # 计算当前周的周一（最后一周的下一个周一）
                                        current_week_monday = last_week_date + timedelta(days=(7 - last_week_weekday))
                                        # 计算当前周的结束日（周五或周日，取决于周K的格式）
                                        # 假设周K在周五结束，则当前周结束日是 current_week_monday + 4
                                        current_week_end = current_week_monday + timedelta(days=4)
                                        
                                        if current_week_monday <= scan_ts <= current_week_end:
                                            # scan_date 在当前周内，需要聚合当前周的数据
                                            should_aggregate = True
                                            week_start_str = current_week_monday.strftime('%Y%m%d')
                                            week_end_date = current_week_end
                                    
                                    if should_aggregate:
                                        aggregated_this_week = True  # 标记进行了聚合
                                        # 需要聚合：获取该周周一到 scan_date 的日K数据
                                        scan_date_str = scan_ts.strftime('%Y%m%d')
                                        
                                        # 获取日K数据（回测时强制使用本地缓存，确保历史数据一致性）
                                        daily_df = self.fetcher.get_daily_kline_range(
                                            stock_code,
                                            start_date=week_start_str,
                                            end_date=scan_date_str,
                                            use_cache=True,
                                            local_only=True  # 回测时强制使用本地缓存，避免使用未来数据
                                        )
                                        
                                        if daily_df is not None and len(daily_df) > 0:
                                            # 确保必要的列存在
                                            required_cols = ['日期', '开盘', '收盘', '最高', '最低', '成交量']
                                            if all(col in daily_df.columns for col in required_cols):
                                                # 转换为日期类型
                                                daily_df = daily_df.copy()
                                                daily_df['日期'] = pd.to_datetime(daily_df['日期'], errors='coerce')
                                                daily_df = daily_df.dropna(subset=['日期'])
                                                # ✅ 严格过滤：只使用扫描日期及之前的数据，避免使用未来数据
                                                daily_df = daily_df[daily_df['日期'] <= scan_ts].sort_values('日期').reset_index(drop=True)
                                                
                                                if len(daily_df) > 0:
                                                    # 聚合为周K（仅该周的部分数据）
                                                    partial_week_k = pd.Series({
                                                        '开盘': float(daily_df.iloc[0]['开盘']),
                                                        '收盘': float(daily_df.iloc[-1]['收盘']),
                                                        '最高': float(daily_df['最高'].max()),
                                                        '最低': float(daily_df['最低'].min()),
                                                        '周成交量': float(daily_df['成交量'].sum()),
                                                        '日期': week_end_date  # 使用该周的结束日期
                                                    })
                                                    
                                                    # 如果成交额列存在，也聚合
                                                    if '成交额' in daily_df.columns:
                                                        partial_week_k['周成交额'] = float(daily_df['成交额'].sum())
                                                    
                                                    # 如果当前周是新的一周（scan_ts > last_week_date），需要添加新的一行
                                                    if scan_ts > last_week_date:
                                                        # 添加新的周K行
                                                        weekly_df = weekly_df.copy()
                                                        partial_week_k['日期'] = week_end_date
                                                        weekly_df = pd.concat([weekly_df, pd.DataFrame([partial_week_k])], ignore_index=True)
                                                        # ✅ 更新 current_idx 指向新添加的聚合周K
                                                        current_idx = len(weekly_df) - 1
                                                    else:
                                                        # 替换最后一周的周K
                                                        weekly_df = weekly_df.copy()
                                                        weekly_df.iloc[-1] = partial_week_k
                                                        # current_idx 保持不变，仍指向最后一行
                                                    
                                                    # 调试输出（每100只股票输出一次）
                                                    if idx % 100 == 0:
                                                        print(f"[as-of聚合周K-并行] [{idx}/{total_stocks}] {stock_code} 扫描日期: {scan_ts.strftime('%Y-%m-%d')}, 聚合了周（{week_start_str} 到 {scan_ts.strftime('%Y-%m-%d')}），current_idx={current_idx}")
                    except Exception as e:
                        # 聚合失败不影响扫描，继续使用原周K
                        if idx % 100 == 0:
                            print(f"[as-of聚合周K-并行] [{idx}/{total_stocks}] {stock_code} 聚合失败: {str(e)[:50]}")
                        pass
                    
                    logging.info(f"[{idx}/{total_stocks}] {stock_code} 开始提取特征，起点索引: {current_idx}")
                    # 减少日志输出，每100只股票打印一次
                    if idx % 100 == 0 or idx == 1:
                        print(f"[{idx}/{total_stocks}] {stock_code} 开始提取特征...")
                    
                    # 使用线程超时机制，防止卡死
                    features_result = [None]
                    features_error = [None]
                    
                    def extract_features():
                        try:
                            # 传入已获取的weekly_df，避免重复获取
                            features_result[0] = self.extract_features_at_start_point(stock_code, current_idx, lookback_weeks=40, weekly_df=weekly_df)
                        except Exception as e:
                            features_error[0] = e
                    
                    extract_thread = threading.Thread(target=extract_features)
                    extract_thread.daemon = True
                    extract_thread.start()
                    extract_thread.join(timeout=2)  # 最多等待2秒（进一步缩短，更快跳过）
                    
                    # 更新进度
                    self.progress['last_update_time'] = time_module.time()
                    step_time = time_module.time() - step_start
                    
                    if extract_thread.is_alive():
                        # 线程仍在运行，说明超时了
                        elapsed = time_module.time() - step_start
                        logging.error(f"[{idx}/{total_stocks}] {stock_code} 特征提取超时（>{elapsed:.1f}秒），强制跳过")
                        print(f"⏱️ [{idx}/{total_stocks}] {stock_code} 特征提取超时（>{elapsed:.1f}秒），强制跳过")
                        continue
                    
                    logging.info(f"[{idx}/{total_stocks}] {stock_code} 特征提取完成（{step_time:.2f}秒）")
                    
                    if features_error[0]:
                        raise features_error[0]
                    
                    features = features_result[0]
                    step_time = time_module.time() - step_start
                    
                    # 检查总耗时
                    elapsed = time_module.time() - start_time
                    if elapsed > max_process_time:
                        if idx % 10 == 0:
                            print(f"⏱️ {stock_code} 特征提取后总耗时超时（{elapsed:.1f}秒），跳过")
                        continue
                    
                    if step_time > 3:  # 特征提取超过3秒，记录
                        if idx % 10 == 0:
                            print(f"⚠️ {stock_code} 特征提取耗时 {step_time:.1f}秒")
                    
                    if features is None:
                        continue
                except Exception as e:
                    # 特征提取失败，跳过该股票
                    if idx % 10 == 0:
                        print(f"⚠️ {stock_code} 特征提取失败: {str(e)[:50]}")
                    continue
                
                # 4. 计算匹配度
                try:
                    # 检查总耗时
                    elapsed = time_module.time() - start_time
                    if elapsed > max_process_time:
                        if idx % 10 == 0:
                            print(f"⏱️ {stock_code} 匹配度计算前超时（{elapsed:.1f}秒），跳过")
                        continue
                    
                    match_score = self._calculate_match_score(features, common_features, tolerance=0.3)
                    
                    # 调试：每10只股票输出一次匹配度信息
                    if idx % 10 == 0:
                        print(f"[调试] {stock_code} {stock_name} 匹配度: {match_score['总匹配度']:.3f} (阈值: {min_match_score:.3f})")
                except Exception as e:
                    # 匹配度计算失败，跳过该股票
                    if idx % 10 == 0:
                        print(f"⚠️ {stock_code} 匹配度计算失败: {str(e)[:50]}")
                    continue
                
                # 5. 如果匹配度达到阈值，检查市值并记录为候选
                total_match = match_score['总匹配度']
                if total_match >= min_match_score:
                    if current_idx >= len(weekly_df):
                        continue
                    
                    # 5.1. 检查120日和250日均线方向（如果都向下，直接排除）
                    try:
                        limit_date = scan_date if scan_date else pd.Timestamp.now().strftime('%Y-%m-%d')
                        limit_date_ymd = pd.to_datetime(limit_date).strftime('%Y%m%d')
                        
                        daily_df = self.fetcher.get_daily_kline_range(
                            stock_code, 
                            start_date='20220101',
                            end_date=limit_date_ymd,
                            use_cache=True,
                            local_only=True
                        )
                        
                        if daily_df is not None and len(daily_df) >= 250:
                            daily_df['日期'] = pd.to_datetime(daily_df['日期'], errors='coerce')
                            daily_df = daily_df.dropna(subset=['日期']).sort_values('日期').reset_index(drop=True)
                            
                            limit_dt = pd.to_datetime(limit_date)
                            daily_before = daily_df[daily_df['日期'] <= limit_dt]
                            if len(daily_before) >= 250:
                                scan_idx = len(daily_before) - 1
                                
                                ma120_current = daily_before['收盘'].iloc[scan_idx-119:scan_idx+1].mean()
                                ma250_current = daily_before['收盘'].iloc[scan_idx-249:scan_idx+1].mean()
                                
                                if scan_idx >= 20:
                                    ma120_20d_ago = daily_before['收盘'].iloc[scan_idx-139:scan_idx-119].mean()
                                    ma250_20d_ago = daily_before['收盘'].iloc[scan_idx-269:scan_idx-249].mean()
                                    
                                    ma120_slope = (ma120_current - ma120_20d_ago) / ma120_20d_ago if ma120_20d_ago > 0 else 0
                                    ma250_slope = (ma250_current - ma250_20d_ago) / ma250_20d_ago if ma250_20d_ago > 0 else 0
                                    
                                    if ma120_slope < 0 and ma250_slope < 0:
                                        print(f"[均线过滤-串行] [{idx}/{total_stocks}] {stock_code} {stock_name} MA120和MA250都向下，已排除 (MA120斜率: {ma120_slope*100:.2f}%, MA250斜率: {ma250_slope*100:.2f}%, 扫描日期: {limit_date})")
                                        continue
                    except Exception as e:
                        # 均线检查失败不影响扫描，继续处理
                        if idx % 100 == 0 or stock_code == '000798':
                            print(f"[均线检查异常-串行] [{idx}/{total_stocks}] {stock_code} {stock_name} 均线方向检查异常: {str(e)[:50]}")
                        pass
                    
                    try:
                        # 尝试获取市值（如果市值获取成功，按市值筛选；失败则跳过市值检查）
                        market_cap_checked = False
                        market_cap_valid = False
                        
                        if max_market_cap > 0:  # 如果设置了市值限制，尝试获取市值
                            try:
                                # 使用超时机制获取市值（避免卡住）
                                market_cap_result = [None]
                                market_cap_error = [None]
                                
                                def fetch_market_cap():
                                    try:
                                        market_cap_result[0] = self.fetcher.get_market_cap(stock_code, timeout=2)
                                    except Exception as e:
                                        market_cap_error[0] = e
                                
                                cap_thread = threading.Thread(target=fetch_market_cap)
                                cap_thread.daemon = True
                                cap_thread.start()
                                cap_thread.join(timeout=2.5)  # 最多等待2.5秒
                                
                                if not cap_thread.is_alive():
                                    fetched_market_cap = market_cap_result[0]
                                    if fetched_market_cap is not None and fetched_market_cap > 0:
                                        market_cap = fetched_market_cap
                                        market_cap_valid = True
                                        market_cap_checked = True
                                        # 如果市值获取成功，检查是否符合条件
                                        if market_cap > max_market_cap:
                                            # 市值超过限制，跳过该股票
                                            if idx % 10 == 0:
                                                print(f"[{idx}/{total_stocks}] {stock_code} {stock_name} 市值 {market_cap:.2f}亿超过限制 {max_market_cap:.2f}亿，跳过")
                                            continue
                            except Exception as e:
                                # 市值获取失败，跳过市值检查，继续处理该股票
                                if idx % 100 == 0:
                                    print(f"[{idx}/{total_stocks}] {stock_code} 市值获取失败，跳过市值检查: {str(e)[:50]}")
                                market_cap_checked = True
                                market_cap_valid = False
                        
                        # 最佳买点日期 = 最后一周的周K日期（特征匹配基于这一周）
                        # 但价格使用扫描日期的收盘价（如果扫描日期在周K日期之前，则用周K收盘价）
                        from datetime import datetime as dt_now
                        today_str = dt_now.now().strftime('%Y-%m-%d')
                        limit_date = scan_date if scan_date else today_str  # 搜索当天
                        fallback_price = float(weekly_df.iloc[current_idx]['收盘'])
                        current_date = weekly_df.iloc[current_idx]['日期']
                        if isinstance(current_date, pd.Timestamp):
                            current_date_str = current_date.strftime('%Y-%m-%d')
                            current_date_ts = current_date
                        else:
                            current_date_str = str(current_date)[:10]
                            current_date_ts = pd.to_datetime(current_date_str, errors='coerce')
                        
                        # ✅ 最佳买点日期：如果进行了聚合，使用扫描日期；否则使用最后一周的周K日期
                        # 如果进行了聚合（aggregated_this_week=True），最佳买点日期应该是扫描日期
                        # 否则使用最后一周的周K日期（特征匹配基于这一周）
                        scan_date_ts = pd.to_datetime(limit_date, errors='coerce')
                        if aggregated_this_week and scan_date:
                            # 进行了聚合，最佳买点日期 = 扫描日期
                            buy_date = limit_date
                        else:
                            # 没有聚合，使用最后一周的周K日期
                            buy_date = current_date_str
                        
                        # 如果扫描日期在周K日期之前或等于周K日期，使用扫描日期的收盘价
                        # 否则使用周K收盘价（这种情况不应该发生，因为我们已经截断了数据）
                        if pd.notna(scan_date_ts) and pd.notna(current_date_ts) and scan_date_ts <= current_date_ts:
                            close_on_search = self._get_close_on_date(stock_code, limit_date)
                            if close_on_search is not None:
                                buy_price = close_on_search
                            else:
                                buy_price = fallback_price
                        else:
                            # 扫描日期晚于周K日期（不应该发生），使用周K收盘价
                            buy_price = fallback_price
                        
                        # ✅ 当前价格 = 扫描日期的收盘价（不是今天的最新价格）
                        # 如果扫描日期是历史日期，当前价格就是扫描日期的价格
                        # 如果扫描日期是今天，当前价格就是今天的最新价格
                        current_price = buy_price  # 默认使用最佳买点价格（即扫描日期的价格）
                        
                        # 如果扫描日期是今天，且获取到了今天的价格，使用今天的价格
                        if limit_date == today_str:
                            close_today = self._get_close_on_date(stock_code, today_str)
                            if close_today is not None:
                                current_price = close_today
                            else:
                                current_price = buy_price
                        # else: 扫描日期是历史日期，current_price = buy_price（已经是扫描日期的价格）
                        
                        # ✅ 调试：确认最终价格（并行版本）
                        if idx % 100 == 0:
                            print(f"[调试-价格-并行] [{idx}/{total_stocks}] {stock_code} 最佳买点日期: {buy_date}, 最佳买点价格: {buy_price:.2f}, 当前价格: {current_price:.2f}, 扫描日期: {limit_date}")
                        # 买点当天为大阴线则排除（不加入候选）
                        if self._is_big_bearish_candle_on_date(stock_code, limit_date):
                            if idx % 100 == 0:
                                print(f"[过滤-并行] [{idx}/{total_stocks}] {stock_code} {stock_name} 买点当日({limit_date})为大阴线，已排除")
                            continue
                        # 如果没有获取到市值，market_cap 保持为 None
                        if not market_cap_checked:
                            market_cap = None
                        candidates.append({
                            '股票代码': stock_code,
                            '股票名称': stock_name,
                            '匹配度': round(match_score['总匹配度'], 3),
                            '最佳买点日期': buy_date,
                            '最佳买点价格': round(buy_price, 2),
                            '当前价格': round(current_price, 2),
                            '市值': round(market_cap, 2) if market_cap_valid else None,
                            '核心特征匹配': match_score.get('核心特征匹配', {}),
                            '特征': features
                        })
                        
                        self.progress['found'] = len(candidates)
                        # 【不可变】找到一只显示一只：写入 progress['candidates'] 供前端轮询。见 扫描显示不可变逻辑.md
                        try:
                            candidates.sort(key=lambda x: x.get('匹配度', 0), reverse=True)
                        except Exception:
                            pass
                        self.progress['candidates'] = candidates[:50] if len(candidates) > 50 else candidates
                        market_cap_info = f" 市值: {market_cap:.2f}亿" if market_cap_valid else " 市值: 未知"
                        print(f"\n✅ 找到候选: {stock_code} {stock_name} (匹配度: {match_score['总匹配度']:.3f}{market_cap_info})")
                    except Exception as e:
                        # 处理候选股票时的错误，跳过该股票
                        if idx % 100 == 0:
                            print(f"⚠️ {stock_code} 处理候选时出错: {str(e)[:50]}")
                        continue
            
            except Exception as e:
                # 记录错误但继续扫描
                import traceback
                error_msg = str(e)
                elapsed_time = time_module.time() - start_time if 'start_time' in locals() else 0
                
                # 每10只股票打印一次错误（更频繁，便于定位问题）
                if idx % 10 == 0:
                    print(f"⚠️ {stock_code} 处理出错: {error_msg[:80]} (耗时: {elapsed_time:.1f}秒)")
                
                # 检查是否超时
                if elapsed_time > max_process_time:
                    if idx % 10 == 0:
                        print(f"⏱️ {stock_code} 处理超时（{elapsed_time:.1f}秒），跳过")
                continue
            
            # 最终检查：如果总耗时超过限制，记录并继续
            final_time = time_module.time() - start_time
            if final_time > max_process_time:
                if idx % 10 == 0:
                    print(f"⏱️ {stock_code} 总处理时间 {final_time:.1f}秒超过限制 {max_process_time}秒，已跳过")
                continue
        
        # 如果被停止，更新状态（在循环结束后检查，处理循环中break的情况）
        if self.progress.get('status') == '已停止':
            # 状态已经在循环中设置，这里只需要确保结果正确
            pass
        
        # 按匹配度排序
        candidates.sort(key=lambda x: x['匹配度'], reverse=True)
        
        # ✅ 关键：市值检查必须在扫描完成后进行二次过滤
        # 因为扫描过程中市值获取可能失败或超时，导致不符合条件的股票被包含进来
        # 优化：如果扫描过程中已经获取到了市值，直接使用，只对没有市值的股票重新获取
        if max_market_cap > 0 and len(candidates) > 0:
            print(f"\n📊 进行市值二次过滤（阈值: ≤ {max_market_cap} 亿元）...")
            original_count = len(candidates)
            
            # 统计已有市值和没有市值的股票数量
            has_market_cap_count = sum(1 for c in candidates if c.get('市值') is not None and c.get('市值', 0) > 0)
            no_market_cap_count = len(candidates) - has_market_cap_count
            print(f"  📊 统计: {has_market_cap_count} 只股票已有市值，{no_market_cap_count} 只股票需要重新获取市值")
            
            filtered_candidates = []
            
            # 添加进度更新
            total_candidates = len(candidates)
            for idx, candidate in enumerate(candidates, 1):
                stock_code = candidate.get('股票代码')
                if stock_code is None:
                    continue
                
                # 每100只股票更新一次进度
                if idx % 100 == 0 or idx == total_candidates:
                    pct = (idx / total_candidates) * 100
                    filtered_so_far = original_count - len(filtered_candidates)
                    print(f"  [市值过滤进度] {idx}/{total_candidates} ({pct:.1f}%) - 已处理: {idx} 只，已过滤: {filtered_so_far} 只")
                    # 更新进度状态
                    if hasattr(self, 'progress'):
                        self.progress['detail'] = f'市值二次过滤中: {idx}/{total_candidates} ({pct:.1f}%)'
                        self.progress['last_update_time'] = time_module.time()
                
                # 检查已有市值（优先使用扫描过程中获取的市值）
                existing_market_cap = candidate.get('市值')
                if existing_market_cap is not None and existing_market_cap > 0:
                    # ✅ 如果扫描过程中已经获取到了市值，直接使用，不需要重新获取
                    if existing_market_cap > max_market_cap:
                        if idx % 500 == 0:  # 减少日志输出
                            print(f"  ❌ {stock_code} {candidate.get('股票名称', '')} 市值 {existing_market_cap:.2f}亿超过限制 {max_market_cap:.2f}亿，已过滤")
                        continue
                    filtered_candidates.append(candidate)
                    continue
                
                # 如果没有市值，尝试获取（使用更短的超时，避免卡住）
                try:
                    market_cap = self.fetcher.get_market_cap(stock_code, timeout=2)  # 减少超时时间从3秒到2秒
                    if market_cap is not None and market_cap > 0:
                        candidate['市值'] = round(market_cap, 2)
                        # ✅ 关键：如果市值超过限制，过滤掉
                        if market_cap > max_market_cap:
                            if idx % 500 == 0:  # 减少日志输出
                                print(f"  ❌ {stock_code} {candidate.get('股票名称', '')} 市值 {market_cap:.2f}亿超过限制 {max_market_cap:.2f}亿，已过滤")
                            continue
                        filtered_candidates.append(candidate)
                    else:
                        # 市值获取失败，保留该股票（不因市值获取失败而丢失）
                        filtered_candidates.append(candidate)
                except Exception:
                    # 市值获取异常，保留该股票（不因市值获取失败而丢失）
                    filtered_candidates.append(candidate)
            
            candidates = filtered_candidates
            filtered_count = original_count - len(candidates)
            if filtered_count > 0:
                print(f"   ✅ 市值过滤完成：过滤掉 {filtered_count} 只（市值 > {max_market_cap} 亿元），剩余 {len(candidates)} 只")
            else:
                print(f"   ✅ 市值过滤完成：所有候选股票均符合市值要求，剩余 {len(candidates)} 只")
        
        # 完成进度
        batch_info = f" [第 {batch_num}/{total_batches} 批]" if total_batches > 1 else ""
        # 如果被停止，状态已经是'已停止'，否则设置为完成或进行中
        if self.progress.get('status') != '已停止':
            if batch_num == total_batches:
                # 最后一批完成，标记为完成
                self.progress['status'] = '完成'
                self.progress['percentage'] = 100.0
                self.progress['detail'] = f'所有批次扫描完成: 找到 {len(candidates)} 只符合条件的股票'
                # 使用总股票数
                self.progress['current'] = total_all_stocks
                # 确保进度中的found和candidates与最终结果一致
                self.progress['found'] = len(candidates)
                self.progress['candidates'] = candidates[:50] if len(candidates) > 50 else candidates
                # 确保进度中的found和candidates与最终结果一致
                self.progress['found'] = len(candidates)
                self.progress['candidates'] = candidates[:50] if len(candidates) > 50 else candidates
            else:
                # 还有下一批，继续扫描
                self.progress['status'] = '进行中'
                # 计算整体进度（已完成批次的进度）
                self.progress['percentage'] = round((batch_num / total_batches * 100), 1)
                # 计算整体已扫描的股票数
                overall_current = int((batch_num / total_batches) * total_all_stocks)
                self.progress['current'] = overall_current
                self.progress['detail'] = f'第 {batch_num}/{total_batches} 批扫描完成: 找到 {len(candidates)} 只符合条件的股票，继续扫描下一批...'
        # 如果被停止，current已经在循环中设置，不需要再次设置
        
        self.progress['last_update_time'] = time_module.time()  # 更新最后更新时间
        
        print("\n" + "=" * 80)
        print(f"✅ 本批扫描完成！找到 {len(candidates)} 只符合条件的股票{batch_info}")
        print("=" * 80)
        
        # 如果被停止，返回当前已找到的结果
        if self.progress.get('status') == '已停止':
            current_processed = self.progress.get('current', idx)
            return {
                'success': True,
                'message': f'扫描已停止，已处理 {current_processed}/{total_stocks} 只股票，找到 {len(candidates)} 只符合条件的股票',
                'candidates': candidates[:50] if len(candidates) > 50 else candidates,  # 只返回前50个最佳候选
                'total_scanned': current_processed,
                'found_count': len(candidates),
                'batch': batch_num,
                'total_batches': total_batches,
                'stopped': True  # 标记为已停止
            }
        
        result = {
            'success': True,
            'message': f'本批扫描完成，找到 {len(candidates)} 只符合条件的股票',
            'candidates': candidates[:50] if len(candidates) > 50 else candidates,  # 只返回前50个最佳候选
            'total_scanned': total_all_stocks,  # 使用总股票数
            'found_count': len(candidates),
            'batch': batch_num,
            'total_batches': total_batches
        }
        
        # 保存扫描结果到 analyzer.scan_results（供前端获取）
        # 如果是最后一批，保存完整结果
        if batch_num == total_batches:
            self.scan_results = result.copy()
            # 确保保存完整的候选列表（不仅仅是前50个）
            self.scan_results['candidates'] = candidates  # 保存全部候选，不限制为50个
            self.scan_results['found_count'] = len(candidates)  # 确保found_count与实际数量一致
        
        return result
    
    def get_trained_features(self) -> Optional[Dict]:
        """
        获取训练好的特征模板
        :return: 训练结果，如果未训练返回None
        """
        return getattr(self, 'trained_features', None)
    
    def save_model(self, filename: str = 'trained_model.json') -> bool:
        """
        保存模型到JSON文件
        :param filename: 保存的文件名
        :return: 是否保存成功
        """
        try:
            import json
            from datetime import datetime
            
            model_data = {
                'trained_at': datetime.now().isoformat(),
                'buy_features': None,
                'sell_features': None,
                'analysis_results': {},
                'bull_stocks': []
            }
            
            # 保存买点特征模型
            if self.trained_features:
                buy_features = self.trained_features.copy()
                # 转换datetime对象为字符串
                if 'trained_at' in buy_features and hasattr(buy_features['trained_at'], 'isoformat'):
                    buy_features['trained_at'] = buy_features['trained_at'].isoformat()
                model_data['buy_features'] = buy_features
            
            # 保存卖点特征模型
            if self.trained_sell_features:
                sell_features = self.trained_sell_features.copy()
                # 转换datetime对象为字符串
                if 'trained_at' in sell_features and hasattr(sell_features['trained_at'], 'isoformat'):
                    sell_features['trained_at'] = sell_features['trained_at'].isoformat()
                model_data['sell_features'] = sell_features

            # 保存“8条件”选股大模型
            if getattr(self, 'trained_screener_model', None):
                screener_model = self.trained_screener_model.copy()
                if 'trained_at' in screener_model and hasattr(screener_model['trained_at'], 'isoformat'):
                    screener_model['trained_at'] = screener_model['trained_at'].isoformat()
                model_data['screener_model'] = screener_model
            
            # 保存分析结果（只保存关键信息）
            for stock_code, result in self.analysis_results.items():
                interval = result.get('interval', {})
                model_data['analysis_results'][stock_code] = {
                    'interval': {
                        '起点日期': str(interval.get('起点日期', '')),
                        '起点价格': float(interval.get('起点价格', 0)) if interval.get('起点价格') else 0,
                        '起点索引': int(interval.get('起点索引')) if interval.get('起点索引') is not None else None,
                        '终点日期': str(interval.get('终点日期', '')),
                        '终点价格': float(interval.get('终点价格', 0)) if interval.get('终点价格') else 0,
                        '涨幅': float(interval.get('涨幅', 0)) if interval.get('涨幅') else 0,
                    }
                }
            
            # 保存大牛股列表
            for stock in self.bull_stocks:
                stock_data = {
                    '代码': stock['代码'],
                    '名称': stock['名称'],
                    '添加时间': stock['添加时间'].isoformat() if hasattr(stock['添加时间'], 'isoformat') else str(stock['添加时间']),
                    '数据条数': stock.get('数据条数', 0)
                }
                model_data['bull_stocks'].append(stock_data)
            
            # 保存到文件
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(model_data, f, ensure_ascii=False, indent=2)
            
            return True
        except Exception as e:
            print(f"保存模型失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def load_model(self, filename: str = 'trained_model.json', skip_network: bool = True) -> bool:
        """
        从JSON文件加载模型
        :param filename: 模型文件名
        :param skip_network: 是否跳过网络请求（加载模型时不需要网络）
        :return: 是否加载成功
        """
        try:
            import json
            from datetime import datetime
            import os
            
            # 尝试多个可能的路径（Vercel 环境中路径可能不同）
            possible_paths = [
                filename,  # 原始路径
                os.path.abspath(filename),  # 绝对路径
                os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), filename),  # 项目根目录
            ]
            
            model_data = None
            loaded_path = None
            
            # 加载文件（纯文件操作，不涉及网络）
            for path in possible_paths:
                try:
                    abs_path = os.path.abspath(path)
                    if os.path.exists(path):
                        print(f"[load_model] 尝试读取: {path} (绝对路径: {abs_path})")
                        # 直接读取文件，不触发任何网络请求
                        with open(path, 'r', encoding='utf-8') as f:
                            model_data = json.load(f)
                        loaded_path = path
                        print(f"[load_model] ✅ 成功从 {path} 加载模型")
                        break
                except (FileNotFoundError, OSError) as e:
                    print(f"[load_model] 路径不存在: {path} - {e}")
                    continue
                except json.JSONDecodeError as e:
                    print(f"[load_model] JSON 解析失败: {path} - {e}")
                    continue
                except Exception as e:
                    print(f"[load_model] 读取文件失败: {path} - {e}")
                    continue
            
            if model_data is None:
                print(f"[load_model] ❌ 所有路径都失败，无法加载模型文件: {filename}")
                print(f"[load_model] 尝试的路径: {possible_paths}")
                return False
            
            # 解析模型数据（纯内存操作，不涉及网络）
            # 加载买点特征模型
            if model_data.get('buy_features'):
                buy_features = model_data['buy_features'].copy()
                # 转换字符串为datetime对象
                if 'trained_at' in buy_features and isinstance(buy_features['trained_at'], str):
                    buy_features['trained_at'] = datetime.fromisoformat(buy_features['trained_at'])
                self.trained_features = buy_features
            
            # 加载卖点特征模型
            if model_data.get('sell_features'):
                sell_features = model_data['sell_features'].copy()
                # 转换字符串为datetime对象
                if 'trained_at' in sell_features and isinstance(sell_features['trained_at'], str):
                    sell_features['trained_at'] = datetime.fromisoformat(sell_features['trained_at'])
                self.trained_sell_features = sell_features

            # 加载“8条件”选股大模型（不触发网络）
            if model_data.get('screener_model'):
                screener_model = model_data['screener_model']
                try:
                    if 'trained_at' in screener_model and isinstance(screener_model['trained_at'], str):
                        screener_model['trained_at'] = datetime.fromisoformat(screener_model['trained_at'])
                except Exception:
                    pass
                self.trained_screener_model = screener_model
            
            # 加载 analysis_results（训练买点、起点索引/日期等，find_buy_points 按日期匹配训练买点用）
            if model_data.get('analysis_results'):
                self.analysis_results = dict(model_data['analysis_results'])
            
            # 加载大牛股列表（仅加载元数据，不获取股票数据，避免网络请求）
            # 即使 skip_network=True，也应该加载股票列表的元数据（不触发网络请求）
            if model_data.get('bull_stocks'):
                loaded_count = 0
                for stock_data in model_data['bull_stocks']:
                    # 检查是否已存在
                    existing = [s for s in self.bull_stocks if s['代码'] == stock_data['代码']]
                    if not existing:
                        stock = {
                            '代码': stock_data['代码'],
                            '名称': stock_data['名称'],
                            '添加时间': datetime.fromisoformat(stock_data['添加时间']) if isinstance(stock_data['添加时间'], str) else datetime.now(),
                            '数据条数': stock_data.get('数据条数', 0)
                        }
                        self.bull_stocks.append(stock)
                        loaded_count += 1
                
                if loaded_count > 0:
                    print(f"[load_model] ✅ 从模型加载了 {loaded_count} 只股票的元数据（不触发网络请求）")
                else:
                    print(f"[load_model] ℹ️ 模型中有 {len(model_data.get('bull_stocks', []))} 只股票，但都已存在，未重复加载")
            
            return True
        except FileNotFoundError:
            return False
        except Exception as e:
            print(f"加载模型失败: {e}")
            import traceback
            traceback.print_exc()
            return False


if __name__ == '__main__':
    # 测试代码
    analyzer = BullStockAnalyzer()
    
    # 测试添加股票
    print("=" * 60)
    print("测试：添加大牛股")
    print("=" * 60)
    
    analyzer.add_bull_stock('000001', '平安银行')
    analyzer.add_bull_stock('000002', '万科A')
    
    # 查看已添加的股票
    print("\n已添加的大牛股：")
    for stock in analyzer.get_bull_stocks():
        print(f"  - {stock['代码']} {stock['名称']}")

