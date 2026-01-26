#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
回测报告生成器模块
生成验证报告和统计数据
"""
from typing import Dict, List
from datetime import datetime
import json
from risk_metrics import RiskMetrics


class BacktestReport:
    """回测报告生成器类"""
    
    def __init__(self, backtest_result: Dict, include_risk_metrics: bool = True):
        """
        初始化报告生成器
        :param backtest_result: 回测结果字典（来自BacktestEngine.run_backtest）
        :param include_risk_metrics: 是否包含风险指标
        """
        self.backtest_result = backtest_result
        self.include_risk_metrics = include_risk_metrics
        self.risk_metrics = RiskMetrics() if include_risk_metrics else None
        self.statistics = self._calculate_statistics()
    
    def _calculate_statistics(self) -> Dict:
        """计算统计数据"""
        results = self.backtest_result.get('results', [])
        periods = self.backtest_result.get('periods', [14, 28, 56, 84, 140])
        
        # 收集所有有效的股票数据
        all_stocks = []
        for day_result in results:
            if 'stocks' in day_result:
                for stock in day_result['stocks']:
                    if 'gains' in stock and stock['gains']:
                        all_stocks.append(stock)
        
        if len(all_stocks) == 0:
            return {
                'total_days': len(results),
                'valid_stocks': 0,
                'periods_stats': {}
            }
        
        # 按周期统计
        periods_stats = {}
        for period_days in periods:
            period_key = f'{period_days}天'
            gains = []
            positive_count = 0
            
            for stock in all_stocks:
                if period_key in stock.get('gains', {}) and stock['gains'][period_key]:
                    gain = stock['gains'][period_key]['gain']
                    gains.append(gain)
                    if gain > 0:
                        positive_count += 1
            
            if len(gains) > 0:
                avg_gain = sum(gains) / len(gains)
                max_gain = max(gains)
                min_gain = min(gains)
                positive_rate = positive_count / len(gains) * 100
                
                period_stat = {
                    'count': len(gains),
                    'avg_gain': round(avg_gain, 2),
                    'max_gain': round(max_gain, 2),
                    'min_gain': round(min_gain, 2),
                    'positive_count': positive_count,
                    'positive_rate': round(positive_rate, 2)
                }
                
                # 计算风险指标
                if self.include_risk_metrics and self.risk_metrics:
                    risk_metrics = self.risk_metrics.calculate_all_metrics(gains)
                    period_stat['risk_metrics'] = risk_metrics
                
                periods_stats[period_key] = period_stat
        
        # 总体统计
        total_days = len(results)
        days_with_stocks = sum(1 for r in results if r.get('stocks') and len(r['stocks']) > 0)
        valid_stocks = len(all_stocks)
        
        return {
            'total_days': total_days,
            'days_with_stocks': days_with_stocks,
            'valid_stocks': valid_stocks,
            'periods_stats': periods_stats
        }
    
    def generate_text_report(self) -> str:
        """生成文本格式的报告"""
        lines = []
        lines.append("=" * 80)
        lines.append("📊 回测验证报告")
        lines.append("=" * 80)
        lines.append("")
        
        # 基本信息
        lines.append("📅 基本信息:")
        lines.append(f"  开始日期: {self.backtest_result.get('start_date')}")
        lines.append(f"  结束日期: {self.backtest_result.get('end_date')}")
        lines.append(f"  扫描模式: {self.backtest_result.get('scan_mode')}")
        lines.append(f"  扫描日期数: {self.backtest_result.get('scan_dates_count')}")
        lines.append(f"  总交易日数: {self.backtest_result.get('total_trading_days')}")
        lines.append(f"  匹配度阈值: {self.backtest_result.get('min_match_score'):.3f}")
        lines.append(f"  市值上限: {self.backtest_result.get('max_market_cap')} 亿元")
        lines.append(f"  每天最多选择: {self.backtest_result.get('max_stocks_per_day')} 只股票")
        lines.append("")
        
        # 统计信息
        lines.append("📈 统计信息:")
        lines.append(f"  总扫描天数: {self.statistics['total_days']}")
        lines.append(f"  有股票的天数: {self.statistics['days_with_stocks']}")
        lines.append(f"  有效股票数: {self.statistics['valid_stocks']}")
        lines.append("")
        
        # 各周期表现
        lines.append("💰 各周期收益表现:")
        lines.append("-" * 80)
        if self.include_risk_metrics:
            lines.append(f"{'周期':<12} {'样本数':<10} {'平均涨幅':<12} {'最大涨幅':<12} {'最小涨幅':<12} {'胜率':<10} {'最大回撤':<12} {'夏普比率':<10}")
        else:
            lines.append(f"{'周期':<12} {'样本数':<10} {'平均涨幅':<12} {'最大涨幅':<12} {'最小涨幅':<12} {'胜率':<10}")
        lines.append("-" * 80)
        
        periods_stats = self.statistics.get('periods_stats', {})
        for period_key in sorted(periods_stats.keys(), key=lambda x: int(x.replace('天', ''))):
            stats = periods_stats[period_key]
            if self.include_risk_metrics and 'risk_metrics' in stats:
                risk = stats['risk_metrics']
                lines.append(
                    f"{period_key:<12} "
                    f"{stats['count']:<10} "
                    f"{stats['avg_gain']:>+10.2f}% "
                    f"{stats['max_gain']:>+10.2f}% "
                    f"{stats['min_gain']:>+10.2f}% "
                    f"{stats['positive_rate']:>8.1f}% "
                    f"{risk.get('max_drawdown_pct', 0):>10.2f}% "
                    f"{risk.get('sharpe_ratio', 0):>8.2f}"
                )
            else:
                lines.append(
                    f"{period_key:<12} "
                    f"{stats['count']:<10} "
                    f"{stats['avg_gain']:>+10.2f}% "
                    f"{stats['max_gain']:>+10.2f}% "
                    f"{stats['min_gain']:>+10.2f}% "
                    f"{stats['positive_rate']:>8.1f}%"
                )
        
        lines.append("")
        
        # 风险指标详细说明
        if self.include_risk_metrics:
            lines.append("📊 风险指标详细说明:")
            lines.append("-" * 80)
            for period_key in sorted(periods_stats.keys(), key=lambda x: int(x.replace('天', ''))):
                stats = periods_stats[period_key]
                if 'risk_metrics' in stats:
                    risk = stats['risk_metrics']
                    lines.append(f"\n{period_key}:")
                    lines.append(f"  最大回撤: {risk.get('max_drawdown_pct', 0):.2f}%")
                    lines.append(f"  波动率: {risk.get('volatility', 0):.4f}")
                    lines.append(f"  夏普比率: {risk.get('sharpe_ratio', 0):.2f}")
                    lines.append(f"  索提诺比率: {risk.get('sortino_ratio', 0):.2f}")
                    lines.append(f"  盈亏比: {risk.get('win_loss_ratio', 0):.2f}")
                    lines.append(f"  平均盈利: {risk.get('avg_win', 0):.2f}%")
                    lines.append(f"  平均亏损: {risk.get('avg_loss', 0):.2f}%")
            lines.append("")
        
        # 详细结果（可选，如果股票数量不多则显示）
        if self.statistics['valid_stocks'] <= 50:
            lines.append("=" * 80)
            lines.append("📋 详细结果（前50只股票）")
            lines.append("=" * 80)
            lines.append("")
            
            count = 0
            for day_result in self.backtest_result.get('results', []):
                if 'stocks' in day_result:
                    for stock in day_result['stocks']:
                        if 'gains' in stock and stock['gains']:
                            count += 1
                            if count > 50:
                                break
                            
                            lines.append(f"{count}. {stock['stock_name']} ({stock['stock_code']})")
                            lines.append(f"   日期: {day_result['date']}, 匹配度: {stock['match_score']:.3f}")
                            lines.append(f"   买入价: {stock['buy_price']:.2f}")
                            
                            # 显示关键周期收益
                            key_periods = ['14天', '28天', '56天']
                            gain_strs = []
                            for period in key_periods:
                                if period in stock['gains'] and stock['gains'][period]:
                                    gain = stock['gains'][period]['gain']
                                    gain_strs.append(f"{period}: {gain:+.2f}%")
                            if gain_strs:
                                lines.append(f"   收益: {', '.join(gain_strs)}")
                            lines.append("")
                            
                            if count >= 50:
                                break
                    if count >= 50:
                        break
        
        lines.append("=" * 80)
        lines.append(f"报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("=" * 80)
        
        return "\n".join(lines)
    
    def generate_json_report(self) -> Dict:
        """生成JSON格式的报告"""
        return {
            'report_type': 'backtest_validation',
            'generated_at': datetime.now().isoformat(),
            'backtest_config': {
                'start_date': self.backtest_result.get('start_date'),
                'end_date': self.backtest_result.get('end_date'),
                'scan_mode': self.backtest_result.get('scan_mode'),
                'min_match_score': self.backtest_result.get('min_match_score'),
                'max_market_cap': self.backtest_result.get('max_market_cap'),
                'max_stocks_per_day': self.backtest_result.get('max_stocks_per_day'),
                'periods': self.backtest_result.get('periods')
            },
            'statistics': self.statistics,
            'detailed_results': self.backtest_result.get('results', [])
        }
    
    def save_report(self, output_dir: str = '.', prefix: str = 'backtest_report') -> Dict[str, str]:
        """
        保存报告到文件
        :param output_dir: 输出目录
        :param prefix: 文件名前缀
        :return: 保存的文件路径字典
        """
        import os
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # 保存文本报告
        text_report = self.generate_text_report()
        text_file = os.path.join(output_dir, f'{prefix}_{timestamp}.txt')
        with open(text_file, 'w', encoding='utf-8') as f:
            f.write(text_report)
        
        # 保存JSON报告
        json_report = self.generate_json_report()
        json_file = os.path.join(output_dir, f'{prefix}_{timestamp}.json')
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(json_report, f, ensure_ascii=False, indent=2)
        
        return {
            'text_report': text_file,
            'json_report': json_file
        }
    
    def print_summary(self):
        """打印简要摘要"""
        print("\n" + "=" * 80)
        print("📊 回测验证摘要")
        print("=" * 80)
        print(f"时间范围: {self.backtest_result.get('start_date')} 至 {self.backtest_result.get('end_date')}")
        print(f"有效股票数: {self.statistics['valid_stocks']}")
        print()
        
        periods_stats = self.statistics.get('periods_stats', {})
        if periods_stats:
            print("各周期表现:")
            print("-" * 80)
            for period_key in sorted(periods_stats.keys(), key=lambda x: int(x.replace('天', ''))):
                stats = periods_stats[period_key]
                print(f"  {period_key}: 平均 {stats['avg_gain']:+.2f}%, 胜率 {stats['positive_rate']:.1f}% "
                      f"({stats['positive_count']}/{stats['count']})")
        print("=" * 80)
