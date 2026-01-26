#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
参数敏感性分析模块
分析不同参数对模型表现的影响
"""
from backtest_engine import BacktestEngine
from risk_metrics import RiskMetrics
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import time


class ParameterSensitivityAnalyzer:
    """参数敏感性分析器"""
    
    def __init__(self, analyzer):
        """
        初始化分析器
        :param analyzer: BullStockAnalyzer实例
        """
        self.analyzer = analyzer
        self.engine = BacktestEngine(analyzer)
        self.risk_metrics = RiskMetrics()
    
    def analyze_match_score_sensitivity(
        self,
        start_date: str,
        end_date: str,
        match_scores: List[float] = [0.75, 0.80, 0.83, 0.85, 0.90, 0.95],
        max_market_cap: float = 100.0,
        scan_mode: str = 'weekly',
        periods: List[int] = [14, 28, 56],
        limit: Optional[int] = 100,
        use_parallel: bool = True,
        max_workers: int = 5
    ) -> Dict:
        """
        分析匹配度阈值对模型表现的影响
        :param start_date: 开始日期
        :param end_date: 结束日期
        :param match_scores: 要测试的匹配度阈值列表
        :param max_market_cap: 最大市值
        :param scan_mode: 扫描模式
        :param periods: 收益周期
        :param limit: 限制扫描数量
        :param use_parallel: 是否并行
        :param max_workers: 最大并发数
        :return: 敏感性分析结果
        """
        print("=" * 80)
        print("📊 匹配度阈值敏感性分析")
        print("=" * 80)
        print(f"测试阈值: {match_scores}")
        print(f"时间范围: {start_date} 至 {end_date}")
        print()
        
        start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
        end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
        
        results = []
        
        for idx, min_match_score in enumerate(match_scores, 1):
            print(f"[{idx}/{len(match_scores)}] 测试匹配度阈值: {min_match_score:.3f}")
            print("-" * 80)
            
            try:
                # 运行回测
                backtest_result = self.engine.run_backtest(
                    start_date=start_date_obj,
                    end_date=end_date_obj,
                    min_match_score=min_match_score,
                    max_market_cap=max_market_cap,
                    scan_mode=scan_mode,
                    max_stocks_per_day=1,
                    periods=periods,
                    limit=limit,
                    use_parallel=use_parallel,
                    max_workers=max_workers
                )
                
                # 计算统计指标
                stats = self._calculate_statistics(backtest_result, periods)
                
                # 计算风险指标（使用第一个周期）
                if periods:
                    period_key = f'{periods[0]}天'
                    risk_metrics = self.risk_metrics.calculate_period_metrics(
                        backtest_result, period_key
                    )
                    stats['risk_metrics'] = risk_metrics.get('metrics', {})
                
                results.append({
                    'min_match_score': min_match_score,
                    'statistics': stats,
                    'backtest_result': backtest_result
                })
                
                print(f"  ✅ 完成: 有效股票数={stats.get('valid_stocks', 0)}, "
                      f"平均收益={stats.get('avg_gain', 0):+.2f}%")
                
            except Exception as e:
                print(f"  ❌ 失败: {e}")
                results.append({
                    'min_match_score': min_match_score,
                    'error': str(e)
                })
            
            print()
        
        # 生成对比报告
        comparison = self._generate_comparison(results, 'min_match_score')
        
        return {
            'parameter': 'min_match_score',
            'tested_values': match_scores,
            'results': results,
            'comparison': comparison
        }
    
    def analyze_market_cap_sensitivity(
        self,
        start_date: str,
        end_date: str,
        market_caps: List[float] = [50.0, 60.0, 80.0, 100.0, 150.0, 200.0],
        min_match_score: float = 0.83,
        scan_mode: str = 'weekly',
        periods: List[int] = [14, 28, 56],
        limit: Optional[int] = 100,
        use_parallel: bool = True,
        max_workers: int = 5
    ) -> Dict:
        """
        分析市值上限对模型表现的影响
        :param start_date: 开始日期
        :param end_date: 结束日期
        :param market_caps: 要测试的市值上限列表
        :param min_match_score: 匹配度阈值
        :param scan_mode: 扫描模式
        :param periods: 收益周期
        :param limit: 限制扫描数量
        :param use_parallel: 是否并行
        :param max_workers: 最大并发数
        :return: 敏感性分析结果
        """
        print("=" * 80)
        print("📊 市值上限敏感性分析")
        print("=" * 80)
        print(f"测试市值上限: {market_caps}")
        print(f"时间范围: {start_date} 至 {end_date}")
        print()
        
        start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
        end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
        
        results = []
        
        for idx, max_market_cap in enumerate(market_caps, 1):
            print(f"[{idx}/{len(market_caps)}] 测试市值上限: {max_market_cap} 亿元")
            print("-" * 80)
            
            try:
                # 运行回测
                backtest_result = self.engine.run_backtest(
                    start_date=start_date_obj,
                    end_date=end_date_obj,
                    min_match_score=min_match_score,
                    max_market_cap=max_market_cap,
                    scan_mode=scan_mode,
                    max_stocks_per_day=1,
                    periods=periods,
                    limit=limit,
                    use_parallel=use_parallel,
                    max_workers=max_workers
                )
                
                # 计算统计指标
                stats = self._calculate_statistics(backtest_result, periods)
                
                # 计算风险指标
                if periods:
                    period_key = f'{periods[0]}天'
                    risk_metrics = self.risk_metrics.calculate_period_metrics(
                        backtest_result, period_key
                    )
                    stats['risk_metrics'] = risk_metrics.get('metrics', {})
                
                results.append({
                    'max_market_cap': max_market_cap,
                    'statistics': stats,
                    'backtest_result': backtest_result
                })
                
                print(f"  ✅ 完成: 有效股票数={stats.get('valid_stocks', 0)}, "
                      f"平均收益={stats.get('avg_gain', 0):+.2f}%")
                
            except Exception as e:
                print(f"  ❌ 失败: {e}")
                results.append({
                    'max_market_cap': max_market_cap,
                    'error': str(e)
                })
            
            print()
        
        # 生成对比报告
        comparison = self._generate_comparison(results, 'max_market_cap')
        
        return {
            'parameter': 'max_market_cap',
            'tested_values': market_caps,
            'results': results,
            'comparison': comparison
        }
    
    def _calculate_statistics(self, backtest_result: Dict, periods: List[int]) -> Dict:
        """计算统计指标"""
        results = backtest_result.get('results', [])
        
        # 收集所有有效的股票数据
        all_stocks = []
        for day_result in results:
            if 'stocks' in day_result:
                for stock in day_result['stocks']:
                    if 'gains' in stock and stock['gains']:
                        all_stocks.append(stock)
        
        stats = {
            'total_days': len(results),
            'days_with_stocks': sum(1 for r in results if r.get('stocks') and len(r['stocks']) > 0),
            'valid_stocks': len(all_stocks)
        }
        
        # 按周期统计
        periods_stats = {}
        for period_days in periods:
            period_key = f'{period_days}天'
            gains = []
            
            for stock in all_stocks:
                if period_key in stock.get('gains', {}) and stock['gains'][period_key]:
                    gain = stock['gains'][period_key]['gain']
                    gains.append(gain)
            
            if len(gains) > 0:
                avg_gain = sum(gains) / len(gains)
                positive_count = sum(1 for g in gains if g > 0)
                positive_rate = positive_count / len(gains) * 100
                
                periods_stats[period_key] = {
                    'count': len(gains),
                    'avg_gain': round(avg_gain, 2),
                    'positive_rate': round(positive_rate, 2)
                }
        
        stats['periods_stats'] = periods_stats
        
        # 使用第一个周期的平均收益作为主要指标
        if periods_stats:
            first_period = list(periods_stats.keys())[0]
            stats['avg_gain'] = periods_stats[first_period]['avg_gain']
            stats['positive_rate'] = periods_stats[first_period]['positive_rate']
        else:
            stats['avg_gain'] = 0.0
            stats['positive_rate'] = 0.0
        
        return stats
    
    def _generate_comparison(self, results: List[Dict], param_key: str) -> Dict:
        """生成对比报告"""
        comparison = {
            'parameter': param_key,
            'summary': []
        }
        
        for result in results:
            if 'error' in result:
                continue
            
            param_value = result.get(param_key)
            stats = result.get('statistics', {})
            
            comparison['summary'].append({
                'parameter_value': param_value,
                'valid_stocks': stats.get('valid_stocks', 0),
                'avg_gain': stats.get('avg_gain', 0.0),
                'positive_rate': stats.get('positive_rate', 0.0),
                'max_drawdown': stats.get('risk_metrics', {}).get('max_drawdown_pct', 0.0),
                'sharpe_ratio': stats.get('risk_metrics', {}).get('sharpe_ratio', 0.0)
            })
        
        return comparison
    
    def print_comparison_report(self, analysis_result: Dict):
        """打印对比报告"""
        print("\n" + "=" * 80)
        print(f"📊 {analysis_result['parameter']} 敏感性分析结果")
        print("=" * 80)
        print()
        
        comparison = analysis_result.get('comparison', {})
        summary = comparison.get('summary', [])
        
        if not summary:
            print("无有效结果")
            return
        
        # 打印表格
        param_name = analysis_result['parameter']
        print(f"{param_name:<15} {'有效股票':<10} {'平均收益':<12} {'胜率':<10} {'最大回撤':<12} {'夏普比率':<10}")
        print("-" * 80)
        
        for item in summary:
            print(f"{item['parameter_value']:<15} "
                  f"{item['valid_stocks']:<10} "
                  f"{item['avg_gain']:>+10.2f}% "
                  f"{item['positive_rate']:>8.1f}% "
                  f"{item['max_drawdown']:>10.2f}% "
                  f"{item['sharpe_ratio']:>8.2f}")
        
        print("=" * 80)
        
        # 找出最佳参数
        if summary:
            best_by_gain = max(summary, key=lambda x: x['avg_gain'])
            best_by_sharpe = max(summary, key=lambda x: x['sharpe_ratio'])
            
            print(f"\n📈 最佳平均收益: {param_name}={best_by_gain['parameter_value']}, "
                  f"收益={best_by_gain['avg_gain']:+.2f}%")
            print(f"📊 最佳夏普比率: {param_name}={best_by_sharpe['parameter_value']}, "
                  f"夏普={best_by_sharpe['sharpe_ratio']:.2f}")
