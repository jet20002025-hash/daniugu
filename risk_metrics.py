#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
风险指标计算模块
计算最大回撤、波动率、夏普比率等风险指标
"""
from typing import Dict, List, Optional
import numpy as np
import pandas as pd


class RiskMetrics:
    """风险指标计算类"""
    
    def __init__(self, risk_free_rate: float = 0.03):
        """
        初始化风险指标计算器
        :param risk_free_rate: 无风险利率（年化，默认3%）
        """
        self.risk_free_rate = risk_free_rate
    
    def calculate_max_drawdown(self, returns: List[float]) -> Dict:
        """
        计算最大回撤
        :param returns: 收益率列表（按时间顺序）
        :return: 最大回撤信息字典
        """
        if not returns or len(returns) == 0:
            return {
                'max_drawdown': 0.0,
                'max_drawdown_pct': 0.0,
                'peak_index': 0,
                'trough_index': 0
            }
        
        # 转换为累计收益
        cumulative = np.cumprod(1 + np.array(returns) / 100.0)  # 假设returns是百分比
        cumulative = cumulative / cumulative[0]  # 归一化到起始值
        
        # 计算回撤
        running_max = np.maximum.accumulate(cumulative)
        drawdown = (cumulative - running_max) / running_max * 100
        
        # 找到最大回撤
        max_dd_idx = np.argmin(drawdown)
        max_dd = drawdown[max_dd_idx]
        
        # 找到峰值位置
        peak_idx = np.argmax(cumulative[:max_dd_idx + 1]) if max_dd_idx > 0 else 0
        
        return {
            'max_drawdown': round(float(max_dd), 2),
            'max_drawdown_pct': round(abs(float(max_dd)), 2),
            'peak_index': int(peak_idx),
            'trough_index': int(max_dd_idx)
        }
    
    def calculate_volatility(self, returns: List[float], annualize: bool = True) -> float:
        """
        计算波动率（标准差）
        :param returns: 收益率列表
        :param annualize: 是否年化（假设252个交易日）
        :return: 波动率
        """
        if not returns or len(returns) == 0:
            return 0.0
        
        returns_array = np.array(returns)
        std = np.std(returns_array)
        
        if annualize:
            # 年化波动率（假设252个交易日）
            std = std * np.sqrt(252)
        
        return round(float(std), 4)
    
    def calculate_sharpe_ratio(
        self, 
        returns: List[float], 
        periods_per_year: int = 252,
        annualize: bool = True
    ) -> float:
        """
        计算夏普比率
        :param returns: 收益率列表
        :param periods_per_year: 每年交易期数（默认252个交易日）
        :param annualize: 是否年化
        :return: 夏普比率
        """
        if not returns or len(returns) == 0:
            return 0.0
        
        returns_array = np.array(returns)
        mean_return = np.mean(returns_array)
        
        if annualize:
            # 年化收益率
            mean_return = mean_return * periods_per_year
        
        # 计算标准差
        std = np.std(returns_array)
        if std == 0:
            return 0.0
        
        if annualize:
            # 年化波动率
            std = std * np.sqrt(periods_per_year)
        
        # 夏普比率 = (收益率 - 无风险利率) / 波动率
        # 注意：这里假设returns是日收益率百分比，需要转换为小数
        excess_return = mean_return / 100.0 - self.risk_free_rate / periods_per_year
        sharpe = excess_return / (std / 100.0) if std > 0 else 0.0
        
        # 年化夏普比率
        if annualize:
            sharpe = sharpe * np.sqrt(periods_per_year)
        
        return round(float(sharpe), 4)
    
    def calculate_sortino_ratio(
        self,
        returns: List[float],
        periods_per_year: int = 252,
        annualize: bool = True
    ) -> float:
        """
        计算索提诺比率（只考虑下行波动）
        :param returns: 收益率列表
        :param periods_per_year: 每年交易期数
        :param annualize: 是否年化
        :return: 索提诺比率
        """
        if not returns or len(returns) == 0:
            return 0.0
        
        returns_array = np.array(returns)
        mean_return = np.mean(returns_array)
        
        if annualize:
            mean_return = mean_return * periods_per_year
        
        # 只计算负收益的标准差（下行波动）
        negative_returns = returns_array[returns_array < 0]
        if len(negative_returns) == 0:
            return 0.0
        
        downside_std = np.std(negative_returns)
        if downside_std == 0:
            return 0.0
        
        if annualize:
            downside_std = downside_std * np.sqrt(periods_per_year)
        
        excess_return = mean_return / 100.0 - self.risk_free_rate / periods_per_year
        sortino = excess_return / (downside_std / 100.0) if downside_std > 0 else 0.0
        
        if annualize:
            sortino = sortino * np.sqrt(periods_per_year)
        
        return round(float(sortino), 4)
    
    def calculate_win_loss_ratio(self, returns: List[float]) -> Dict:
        """
        计算盈亏比
        :param returns: 收益率列表
        :return: 盈亏比信息
        """
        if not returns or len(returns) == 0:
            return {
                'win_loss_ratio': 0.0,
                'avg_win': 0.0,
                'avg_loss': 0.0,
                'win_count': 0,
                'loss_count': 0
            }
        
        returns_array = np.array(returns)
        wins = returns_array[returns_array > 0]
        losses = returns_array[returns_array < 0]
        
        avg_win = float(np.mean(wins)) if len(wins) > 0 else 0.0
        avg_loss = abs(float(np.mean(losses))) if len(losses) > 0 else 0.0
        
        win_loss_ratio = avg_win / avg_loss if avg_loss > 0 else 0.0
        
        return {
            'win_loss_ratio': round(win_loss_ratio, 2),
            'avg_win': round(avg_win, 2),
            'avg_loss': round(avg_loss, 2),
            'win_count': len(wins),
            'loss_count': len(losses)
        }
    
    def calculate_all_metrics(
        self,
        returns: List[float],
        periods_per_year: int = 252,
        annualize: bool = True
    ) -> Dict:
        """
        计算所有风险指标
        :param returns: 收益率列表
        :param periods_per_year: 每年交易期数
        :param annualize: 是否年化
        :return: 所有风险指标字典
        """
        if not returns or len(returns) == 0:
            return {
                'max_drawdown': 0.0,
                'volatility': 0.0,
                'sharpe_ratio': 0.0,
                'sortino_ratio': 0.0,
                'win_loss_ratio': 0.0,
                'avg_return': 0.0,
                'total_return': 0.0
            }
        
        max_dd = self.calculate_max_drawdown(returns)
        volatility = self.calculate_volatility(returns, annualize)
        sharpe = self.calculate_sharpe_ratio(returns, periods_per_year, annualize)
        sortino = self.calculate_sortino_ratio(returns, periods_per_year, annualize)
        win_loss = self.calculate_win_loss_ratio(returns)
        
        returns_array = np.array(returns)
        avg_return = float(np.mean(returns_array))
        total_return = float(np.sum(returns_array))
        
        return {
            'max_drawdown_pct': max_dd['max_drawdown_pct'],
            'volatility': volatility,
            'sharpe_ratio': sharpe,
            'sortino_ratio': sortino,
            'win_loss_ratio': win_loss['win_loss_ratio'],
            'avg_win': win_loss['avg_win'],
            'avg_loss': win_loss['avg_loss'],
            'win_count': win_loss['win_count'],
            'loss_count': win_loss['loss_count'],
            'avg_return': round(avg_return, 2),
            'total_return': round(total_return, 2),
            'positive_rate': round(win_loss['win_count'] / len(returns) * 100, 2) if len(returns) > 0 else 0.0
        }
    
    def calculate_period_metrics(
        self,
        backtest_results: Dict,
        period_key: str = '14天'
    ) -> Dict:
        """
        从回测结果中计算指定周期的风险指标
        :param backtest_results: 回测结果字典（来自BacktestEngine）
        :param period_key: 周期键（如'14天'）
        :return: 风险指标字典
        """
        # 收集该周期的所有收益率
        returns = []
        
        for day_result in backtest_results.get('results', []):
            if 'stocks' in day_result:
                for stock in day_result['stocks']:
                    if 'gains' in stock and period_key in stock['gains']:
                        gain_info = stock['gains'][period_key]
                        if gain_info and 'gain' in gain_info:
                            returns.append(gain_info['gain'])
        
        if len(returns) == 0:
            return {
                'period': period_key,
                'sample_count': 0,
                'metrics': {}
            }
        
        metrics = self.calculate_all_metrics(returns)
        
        return {
            'period': period_key,
            'sample_count': len(returns),
            'metrics': metrics
        }
