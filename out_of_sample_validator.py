#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
样本外验证模块
验证模型在未参与训练的股票上的表现
"""
from backtest_engine import BacktestEngine
from risk_metrics import RiskMetrics
from typing import Dict, List, Optional
from datetime import datetime, timedelta


class OutOfSampleValidator:
    """样本外验证器"""
    
    def __init__(self, analyzer):
        """
        初始化验证器
        :param analyzer: BullStockAnalyzer实例
        """
        self.analyzer = analyzer
        self.engine = BacktestEngine(analyzer)
        self.risk_metrics = RiskMetrics()
    
    def validate_time_split(
        self,
        train_start_date: str,
        train_end_date: str,
        test_start_date: str,
        test_end_date: str,
        min_match_score: float = 0.83,
        max_market_cap: float = 100.0,
        scan_mode: str = 'weekly',
        periods: List[int] = [14, 28, 56],
        limit: Optional[int] = None,
        use_parallel: bool = True,
        max_workers: int = 10
    ) -> Dict:
        """
        时间划分验证：训练期 vs 测试期
        :param train_start_date: 训练期开始日期
        :param train_end_date: 训练期结束日期
        :param test_start_date: 测试期开始日期
        :param test_end_date: 测试期结束日期
        :param min_match_score: 匹配度阈值
        :param max_market_cap: 最大市值
        :param scan_mode: 扫描模式
        :param periods: 收益周期
        :param limit: 限制扫描数量
        :param use_parallel: 是否并行
        :param max_workers: 最大并发数
        :return: 验证结果
        """
        print("=" * 80)
        print("📊 时间划分样本外验证")
        print("=" * 80)
        print(f"训练期: {train_start_date} 至 {train_end_date}")
        print(f"测试期: {test_start_date} 至 {test_end_date}")
        print()
        
        # 在训练期运行回测（作为基准）
        print("步骤1: 在训练期运行回测（基准）...")
        print("-" * 80)
        train_result = self.engine.run_backtest(
            start_date=datetime.strptime(train_start_date, '%Y-%m-%d').date(),
            end_date=datetime.strptime(train_end_date, '%Y-%m-%d').date(),
            min_match_score=min_match_score,
            max_market_cap=max_market_cap,
            scan_mode=scan_mode,
            max_stocks_per_day=1,
            periods=periods,
            limit=limit,
            use_parallel=use_parallel,
            max_workers=max_workers
        )
        train_stats = self._calculate_statistics(train_result, periods)
        
        print("\n步骤2: 在测试期运行回测（样本外）...")
        print("-" * 80)
        test_result = self.engine.run_backtest(
            start_date=datetime.strptime(test_start_date, '%Y-%m-%d').date(),
            end_date=datetime.strptime(test_end_date, '%Y-%m-%d').date(),
            min_match_score=min_match_score,
            max_market_cap=max_market_cap,
            scan_mode=scan_mode,
            max_stocks_per_day=1,
            periods=periods,
            limit=limit,
            use_parallel=use_parallel,
            max_workers=max_workers
        )
        test_stats = self._calculate_statistics(test_result, periods)
        
        # 计算风险指标
        if periods:
            period_key = f'{periods[0]}天'
            train_risk = self.risk_metrics.calculate_period_metrics(train_result, period_key)
            test_risk = self.risk_metrics.calculate_period_metrics(test_result, period_key)
            train_stats['risk_metrics'] = train_risk.get('metrics', {})
            test_stats['risk_metrics'] = test_risk.get('metrics', {})
        
        # 对比分析
        comparison = self._compare_periods(train_stats, test_stats)
        
        return {
            'train_period': {
                'start_date': train_start_date,
                'end_date': train_end_date,
                'statistics': train_stats,
                'backtest_result': train_result
            },
            'test_period': {
                'start_date': test_start_date,
                'end_date': test_end_date,
                'statistics': test_stats,
                'backtest_result': test_result
            },
            'comparison': comparison
        }
    
    def validate_stock_split(
        self,
        start_date: str,
        end_date: str,
        training_stocks: List[str],
        min_match_score: float = 0.83,
        max_market_cap: float = 100.0,
        scan_mode: str = 'weekly',
        periods: List[int] = [14, 28, 56],
        limit: Optional[int] = None,
        use_parallel: bool = True,
        max_workers: int = 10
    ) -> Dict:
        """
        股票划分验证：训练股票 vs 新股票
        :param start_date: 开始日期
        :param end_date: 结束日期
        :param training_stocks: 训练股票列表
        :param min_match_score: 匹配度阈值
        :param max_market_cap: 最大市值
        :param scan_mode: 扫描模式
        :param periods: 收益周期
        :param limit: 限制扫描数量
        :param use_parallel: 是否并行
        :param max_workers: 最大并发数
        :return: 验证结果
        """
        print("=" * 80)
        print("📊 股票划分样本外验证")
        print("=" * 80)
        print(f"时间范围: {start_date} 至 {end_date}")
        print(f"训练股票数: {len(training_stocks)}")
        print()
        
        # 运行回测
        backtest_result = self.engine.run_backtest(
            start_date=datetime.strptime(start_date, '%Y-%m-%d').date(),
            end_date=datetime.strptime(end_date, '%Y-%m-%d').date(),
            min_match_score=min_match_score,
            max_market_cap=max_market_cap,
            scan_mode=scan_mode,
            max_stocks_per_day=1,
            periods=periods,
            limit=limit,
            use_parallel=use_parallel,
            max_workers=max_workers
        )
        
        # 分离训练股票和新股票的结果
        training_stocks_set = set(training_stocks)
        training_results = []
        new_stock_results = []
        
        for day_result in backtest_result.get('results', []):
            if 'stocks' in day_result:
                for stock in day_result['stocks']:
                    stock_code = stock.get('stock_code', '')
                    if stock_code in training_stocks_set:
                        training_results.append(stock)
                    else:
                        new_stock_results.append(stock)
        
        # 计算统计指标
        training_stats = self._calculate_statistics_from_stocks(training_results, periods)
        new_stock_stats = self._calculate_statistics_from_stocks(new_stock_results, periods)
        
        # 计算风险指标
        if periods:
            period_key = f'{periods[0]}天'
            # 从股票结果中提取收益率
            training_returns = self._extract_returns(training_results, period_key)
            new_stock_returns = self._extract_returns(new_stock_results, period_key)
            
            if training_returns:
                training_stats['risk_metrics'] = self.risk_metrics.calculate_all_metrics(training_returns)
            if new_stock_returns:
                new_stock_stats['risk_metrics'] = self.risk_metrics.calculate_all_metrics(new_stock_returns)
        
        # 对比分析
        comparison = self._compare_stocks(training_stats, new_stock_stats)
        
        return {
            'time_period': {
                'start_date': start_date,
                'end_date': end_date
            },
            'training_stocks': {
                'count': len(training_stocks),
                'stocks': training_stocks,
                'statistics': training_stats,
                'results': training_results
            },
            'new_stocks': {
                'count': len(new_stock_results),
                'statistics': new_stock_stats,
                'results': new_stock_results
            },
            'comparison': comparison
        }
    
    def _calculate_statistics(self, backtest_result: Dict, periods: List[int]) -> Dict:
        """计算统计指标"""
        results = backtest_result.get('results', [])
        
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
        
        if periods_stats:
            first_period = list(periods_stats.keys())[0]
            stats['avg_gain'] = periods_stats[first_period]['avg_gain']
            stats['positive_rate'] = periods_stats[first_period]['positive_rate']
        else:
            stats['avg_gain'] = 0.0
            stats['positive_rate'] = 0.0
        
        return stats
    
    def _calculate_statistics_from_stocks(self, stocks: List[Dict], periods: List[int]) -> Dict:
        """从股票列表中计算统计指标"""
        stats = {
            'valid_stocks': len(stocks)
        }
        
        periods_stats = {}
        for period_days in periods:
            period_key = f'{period_days}天'
            gains = []
            
            for stock in stocks:
                if 'gains' in stock and period_key in stock.get('gains', {}) and stock['gains'][period_key]:
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
        
        if periods_stats:
            first_period = list(periods_stats.keys())[0]
            stats['avg_gain'] = periods_stats[first_period]['avg_gain']
            stats['positive_rate'] = periods_stats[first_period]['positive_rate']
        else:
            stats['avg_gain'] = 0.0
            stats['positive_rate'] = 0.0
        
        return stats
    
    def _extract_returns(self, stocks: List[Dict], period_key: str) -> List[float]:
        """从股票结果中提取收益率"""
        returns = []
        for stock in stocks:
            if 'gains' in stock and period_key in stock.get('gains', {}) and stock['gains'][period_key]:
                gain = stock['gains'][period_key]['gain']
                returns.append(gain)
        return returns
    
    def _compare_periods(self, train_stats: Dict, test_stats: Dict) -> Dict:
        """对比训练期和测试期的表现"""
        comparison = {
            'avg_gain_diff': test_stats.get('avg_gain', 0) - train_stats.get('avg_gain', 0),
            'positive_rate_diff': test_stats.get('positive_rate', 0) - train_stats.get('positive_rate', 0),
            'valid_stocks_diff': test_stats.get('valid_stocks', 0) - train_stats.get('valid_stocks', 0)
        }
        
        # 计算相对变化
        if train_stats.get('avg_gain', 0) != 0:
            comparison['avg_gain_change_pct'] = (comparison['avg_gain_diff'] / abs(train_stats.get('avg_gain', 1))) * 100
        else:
            comparison['avg_gain_change_pct'] = 0.0
        
        # 风险指标对比
        train_risk = train_stats.get('risk_metrics', {})
        test_risk = test_stats.get('risk_metrics', {})
        
        if train_risk and test_risk:
            comparison['sharpe_ratio_diff'] = test_risk.get('sharpe_ratio', 0) - train_risk.get('sharpe_ratio', 0)
            comparison['max_drawdown_diff'] = test_risk.get('max_drawdown_pct', 0) - train_risk.get('max_drawdown_pct', 0)
        
        return comparison
    
    def _compare_stocks(self, training_stats: Dict, new_stock_stats: Dict) -> Dict:
        """对比训练股票和新股票的表现"""
        comparison = {
            'avg_gain_diff': new_stock_stats.get('avg_gain', 0) - training_stats.get('avg_gain', 0),
            'positive_rate_diff': new_stock_stats.get('positive_rate', 0) - training_stats.get('positive_rate', 0),
            'valid_stocks_diff': new_stock_stats.get('valid_stocks', 0) - training_stats.get('valid_stocks', 0)
        }
        
        # 计算相对变化
        if training_stats.get('avg_gain', 0) != 0:
            comparison['avg_gain_change_pct'] = (comparison['avg_gain_diff'] / abs(training_stats.get('avg_gain', 1))) * 100
        else:
            comparison['avg_gain_change_pct'] = 0.0
        
        # 风险指标对比
        training_risk = training_stats.get('risk_metrics', {})
        new_stock_risk = new_stock_stats.get('risk_metrics', {})
        
        if training_risk and new_stock_risk:
            comparison['sharpe_ratio_diff'] = new_stock_risk.get('sharpe_ratio', 0) - training_risk.get('sharpe_ratio', 0)
            comparison['max_drawdown_diff'] = new_stock_risk.get('max_drawdown_pct', 0) - training_risk.get('max_drawdown_pct', 0)
        
        return comparison
    
    def print_comparison_report(self, validation_result: Dict, validation_type: str = 'time_split'):
        """打印对比报告"""
        print("\n" + "=" * 80)
        if validation_type == 'time_split':
            print("📊 时间划分样本外验证结果")
        else:
            print("📊 股票划分样本外验证结果")
        print("=" * 80)
        print()
        
        if validation_type == 'time_split':
            train_stats = validation_result['train_period']['statistics']
            test_stats = validation_result['test_period']['statistics']
            comparison = validation_result['comparison']
            
            print("训练期表现:")
            print(f"  有效股票数: {train_stats.get('valid_stocks', 0)}")
            print(f"  平均收益: {train_stats.get('avg_gain', 0):+.2f}%")
            print(f"  胜率: {train_stats.get('positive_rate', 0):.1f}%")
            if 'risk_metrics' in train_stats:
                risk = train_stats['risk_metrics']
                print(f"  夏普比率: {risk.get('sharpe_ratio', 0):.2f}")
                print(f"  最大回撤: {risk.get('max_drawdown_pct', 0):.2f}%")
            
            print("\n测试期表现（样本外）:")
            print(f"  有效股票数: {test_stats.get('valid_stocks', 0)}")
            print(f"  平均收益: {test_stats.get('avg_gain', 0):+.2f}%")
            print(f"  胜率: {test_stats.get('positive_rate', 0):.1f}%")
            if 'risk_metrics' in test_stats:
                risk = test_stats['risk_metrics']
                print(f"  夏普比率: {risk.get('sharpe_ratio', 0):.2f}")
                print(f"  最大回撤: {risk.get('max_drawdown_pct', 0):.2f}%")
            
            print("\n对比分析:")
            print(f"  平均收益差异: {comparison.get('avg_gain_diff', 0):+.2f}%")
            print(f"  胜率差异: {comparison.get('positive_rate_diff', 0):+.2f}%")
            if 'sharpe_ratio_diff' in comparison:
                print(f"  夏普比率差异: {comparison.get('sharpe_ratio_diff', 0):+.2f}")
            
            # 判断是否过拟合
            if comparison.get('avg_gain_diff', 0) < -5.0:  # 测试期收益明显低于训练期
                print("\n⚠️  警告: 可能存在过拟合，测试期表现明显低于训练期")
            elif comparison.get('avg_gain_diff', 0) > 5.0:
                print("\n✅ 模型泛化能力良好，测试期表现优于训练期")
            else:
                print("\n✅ 模型表现稳定，训练期和测试期表现接近")
        
        else:  # stock_split
            training_stats = validation_result['training_stocks']['statistics']
            new_stock_stats = validation_result['new_stocks']['statistics']
            comparison = validation_result['comparison']
            
            print("训练股票表现:")
            print(f"  有效股票数: {training_stats.get('valid_stocks', 0)}")
            print(f"  平均收益: {training_stats.get('avg_gain', 0):+.2f}%")
            print(f"  胜率: {training_stats.get('positive_rate', 0):.1f}%")
            
            print("\n新股票表现（样本外）:")
            print(f"  有效股票数: {new_stock_stats.get('valid_stocks', 0)}")
            print(f"  平均收益: {new_stock_stats.get('avg_gain', 0):+.2f}%")
            print(f"  胜率: {new_stock_stats.get('positive_rate', 0):.1f}%")
            
            print("\n对比分析:")
            print(f"  平均收益差异: {comparison.get('avg_gain_diff', 0):+.2f}%")
            print(f"  胜率差异: {comparison.get('positive_rate_diff', 0):+.2f}%")
        
        print("=" * 80)
