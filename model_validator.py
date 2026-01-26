#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
选股模型验证器主类
整合回测引擎和报告生成功能
"""
from bull_stock_analyzer import BullStockAnalyzer
from backtest_engine import BacktestEngine
from backtest_report import BacktestReport
from parameter_sensitivity import ParameterSensitivityAnalyzer
from out_of_sample_validator import OutOfSampleValidator
from datetime import datetime, timedelta
from typing import Dict, Optional, List
import os


class ModelValidator:
    """选股模型验证器"""
    
    def __init__(self, model_path: Optional[str] = None, analyzer: Optional[BullStockAnalyzer] = None):
        """
        初始化验证器
        :param model_path: 模型文件路径（如果提供，会自动加载）
        :param analyzer: BullStockAnalyzer实例（如果提供，直接使用）
        """
        if analyzer is not None:
            self.analyzer = analyzer
        else:
            self.analyzer = BullStockAnalyzer(
                auto_load_default_stocks=False,
                auto_analyze_and_train=False
            )
            
            # 如果提供了模型路径，加载模型
            if model_path:
                self.load_model(model_path)
        
        self.engine = None
        self.report = None
    
    def load_model(self, model_path: str) -> bool:
        """
        加载模型
        :param model_path: 模型文件路径
        :return: 是否加载成功
        """
        print(f"正在加载模型: {model_path}")
        try:
            success = self.analyzer.load_model(model_path, skip_network=True)
            if success:
                print("✅ 模型加载成功")
                if self.analyzer.trained_features:
                    feature_count = len(self.analyzer.trained_features.get('common_features', {}))
                    sample_count = self.analyzer.trained_features.get('sample_count', 0)
                    print(f"   特征数: {feature_count}")
                    print(f"   样本数: {sample_count}")
                return True
            else:
                print("❌ 模型加载失败")
                return False
        except Exception as e:
            print(f"❌ 加载模型时出错: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def validate_backtest(
        self,
        start_date: str,
        end_date: str,
        min_match_score: float = 0.83,
        max_market_cap: float = 100.0,
        scan_mode: str = 'daily',
        max_stocks_per_day: int = 1,
        periods: List[int] = [14, 28, 56, 84, 140],
        limit: Optional[int] = None,
        use_parallel: bool = True,
        max_workers: int = 10,
        save_report: bool = True,
        output_dir: str = '.',
        report_prefix: str = 'backtest_report'
    ) -> Dict:
        """
        运行回测验证
        :param start_date: 开始日期 (格式: 'YYYY-MM-DD')
        :param end_date: 结束日期 (格式: 'YYYY-MM-DD')
        :param min_match_score: 最小匹配度阈值
        :param max_market_cap: 最大市值（亿元）
        :param scan_mode: 扫描模式，'daily'=每日，'weekly'=每周，'monthly'=每月
        :param max_stocks_per_day: 每天最多选择的股票数量
        :param periods: 计算收益的周期列表（天数）
        :param limit: 限制扫描股票数量（None表示全部）
        :param use_parallel: 是否使用并行处理
        :param max_workers: 最大并发线程数
        :param save_report: 是否保存报告
        :param output_dir: 报告输出目录
        :param report_prefix: 报告文件名前缀
        :return: 验证结果字典
        """
        # 转换日期字符串为date对象
        start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
        end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
        
        # 创建回测引擎
        self.engine = BacktestEngine(self.analyzer)
        
        # 运行回测
        backtest_result = self.engine.run_backtest(
            start_date=start_date_obj,
            end_date=end_date_obj,
            min_match_score=min_match_score,
            max_market_cap=max_market_cap,
            scan_mode=scan_mode,
            max_stocks_per_day=max_stocks_per_day,
            periods=periods,
            limit=limit,
            use_parallel=use_parallel,
            max_workers=max_workers
        )
        
        # 生成报告（包含风险指标）
        self.report = BacktestReport(backtest_result, include_risk_metrics=True)
        
        # 打印摘要
        self.report.print_summary()
        
        # 保存报告
        saved_files = {}
        if save_report:
            saved_files = self.report.save_report(output_dir=output_dir, prefix=report_prefix)
            print(f"\n✅ 报告已保存:")
            print(f"   文本报告: {saved_files.get('text_report')}")
            print(f"   JSON报告: {saved_files.get('json_report')}")
        
        return {
            'backtest_result': backtest_result,
            'statistics': self.report.statistics,
            'saved_files': saved_files
        }
    
    def get_text_report(self) -> str:
        """获取文本格式的报告"""
        if self.report is None:
            return "尚未运行验证，请先调用 validate_backtest()"
        return self.report.generate_text_report()
    
    def get_json_report(self) -> Dict:
        """获取JSON格式的报告"""
        if self.report is None:
            return {"error": "尚未运行验证，请先调用 validate_backtest()"}
        return self.report.generate_json_report()
    
    def print_full_report(self):
        """打印完整报告"""
        if self.report is None:
            print("尚未运行验证，请先调用 validate_backtest()")
            return
        
        print(self.report.generate_text_report())
    
    def analyze_parameter_sensitivity(
        self,
        start_date: str,
        end_date: str,
        parameter: str = 'match_score',
        parameter_values: Optional[List] = None,
        min_match_score: float = 0.83,
        max_market_cap: float = 100.0,
        scan_mode: str = 'weekly',
        periods: List[int] = [14, 28, 56],
        limit: Optional[int] = 100,
        use_parallel: bool = True,
        max_workers: int = 5
    ) -> Dict:
        """
        参数敏感性分析
        :param start_date: 开始日期
        :param end_date: 结束日期
        :param parameter: 要分析的参数 ('match_score' 或 'market_cap')
        :param parameter_values: 参数值列表（如果为None，使用默认值）
        :param min_match_score: 匹配度阈值（当parameter='market_cap'时使用）
        :param max_market_cap: 市值上限（当parameter='match_score'时使用）
        :param scan_mode: 扫描模式
        :param periods: 收益周期
        :param limit: 限制扫描数量
        :param use_parallel: 是否并行
        :param max_workers: 最大并发数
        :return: 敏感性分析结果
        """
        analyzer = ParameterSensitivityAnalyzer(self.analyzer)
        
        if parameter == 'match_score':
            if parameter_values is None:
                parameter_values = [0.75, 0.80, 0.83, 0.85, 0.90, 0.95]
            return analyzer.analyze_match_score_sensitivity(
                start_date=start_date,
                end_date=end_date,
                match_scores=parameter_values,
                max_market_cap=max_market_cap,
                scan_mode=scan_mode,
                periods=periods,
                limit=limit,
                use_parallel=use_parallel,
                max_workers=max_workers
            )
        elif parameter == 'market_cap':
            if parameter_values is None:
                parameter_values = [50.0, 60.0, 80.0, 100.0, 150.0, 200.0]
            return analyzer.analyze_market_cap_sensitivity(
                start_date=start_date,
                end_date=end_date,
                market_caps=parameter_values,
                min_match_score=min_match_score,
                scan_mode=scan_mode,
                periods=periods,
                limit=limit,
                use_parallel=use_parallel,
                max_workers=max_workers
            )
        else:
            raise ValueError(f"不支持的参数类型: {parameter}")
    
    def validate_out_of_sample(
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
        样本外验证（时间划分）
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
        validator = OutOfSampleValidator(self.analyzer)
        result = validator.validate_time_split(
            train_start_date=train_start_date,
            train_end_date=train_end_date,
            test_start_date=test_start_date,
            test_end_date=test_end_date,
            min_match_score=min_match_score,
            max_market_cap=max_market_cap,
            scan_mode=scan_mode,
            periods=periods,
            limit=limit,
            use_parallel=use_parallel,
            max_workers=max_workers
        )
        
        # 打印对比报告
        validator.print_comparison_report(result, 'time_split')
        
        return result
    
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
        样本外验证（股票划分）
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
        validator = OutOfSampleValidator(self.analyzer)
        result = validator.validate_stock_split(
            start_date=start_date,
            end_date=end_date,
            training_stocks=training_stocks,
            min_match_score=min_match_score,
            max_market_cap=max_market_cap,
            scan_mode=scan_mode,
            periods=periods,
            limit=limit,
            use_parallel=use_parallel,
            max_workers=max_workers
        )
        
        # 打印对比报告
        validator.print_comparison_report(result, 'stock_split')
        
        return result


def main():
    """示例用法"""
    print("=" * 80)
    print("选股模型验证系统 - 示例")
    print("=" * 80)
    print()
    
    # 方式1: 使用默认模型（如果存在）
    # validator = ModelValidator()
    # validator.load_model('trained_model.json')
    
    # 方式2: 直接指定模型路径
    model_path = 'trained_model.json'
    if not os.path.exists(model_path):
        # 尝试其他可能的模型路径
        possible_paths = [
            'models/模型23.json',
            'models/筹码模型.json',
            'models/model_nero11.pkl'
        ]
        for path in possible_paths:
            if os.path.exists(path):
                model_path = path
                break
    
    if not os.path.exists(model_path):
        print(f"❌ 未找到模型文件，请确保模型文件存在")
        print(f"   尝试查找: {model_path}")
        return
    
    validator = ModelValidator(model_path=model_path)
    
    # 运行回测验证
    # 示例：回测最近一个月的数据
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=30)
    
    print(f"\n开始验证（时间范围: {start_date} 至 {end_date}）...")
    print("注意：这是示例，实际验证可能需要较长时间")
    print()
    
    result = validator.validate_backtest(
        start_date=start_date.strftime('%Y-%m-%d'),
        end_date=end_date.strftime('%Y-%m-%d'),
        min_match_score=0.83,
        max_market_cap=100.0,
        scan_mode='weekly',  # 每周扫描一次，加快速度
        max_stocks_per_day=1,
        periods=[14, 28, 56],  # 只计算2周、4周、8周收益
        limit=100,  # 限制扫描前100只股票（用于测试）
        use_parallel=True,
        max_workers=5
    )
    
    print("\n✅ 验证完成！")


if __name__ == '__main__':
    main()
