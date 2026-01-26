#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
神经网络版本的股票特征匹配模型
使用多层感知器（MLP）进行特征匹配度预测
"""
import numpy as np
import json
import os
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import pickle

try:
    from sklearn.neural_network import MLPRegressor
    from sklearn.preprocessing import StandardScaler
    from sklearn.model_selection import train_test_split
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    print("⚠️ scikit-learn未安装，无法使用神经网络模型")
    print("   请运行: pip install scikit-learn")

from bull_stock_analyzer import BullStockAnalyzer


class BullStockNeuralNetwork:
    """基于神经网络的大牛股特征匹配模型"""
    
    def __init__(self, hidden_layer_sizes: Tuple = (128, 64, 32), random_state: int = 42):
        """
        初始化神经网络模型
        :param hidden_layer_sizes: 隐藏层结构，默认(128, 64, 32)
        :param random_state: 随机种子
        """
        if not SKLEARN_AVAILABLE:
            raise ImportError("scikit-learn未安装，请运行: pip install scikit-learn")
        
        self.hidden_layer_sizes = hidden_layer_sizes
        self.random_state = random_state
        self.model = None
        self.scaler = StandardScaler()
        self.feature_names = []
        self.is_trained = False
        self.trained_at = None
        
    def prepare_training_data(self, analyzer: BullStockAnalyzer, target_stocks: List[str]) -> Tuple[np.ndarray, np.ndarray]:
        """
        准备训练数据
        :param analyzer: BullStockAnalyzer实例
        :param target_stocks: 训练股票列表
        :return: (X, y) 特征矩阵和标签（匹配度）
        """
        print("=" * 80)
        print("📊 准备神经网络训练数据")
        print("=" * 80)
        
        # 先添加股票
        print("\n📊 步骤0: 添加训练股票...")
        for stock_code in target_stocks:
            analyzer.add_bull_stock(stock_code)
        
        # 分析所有股票
        print("\n📊 步骤1: 分析所有训练股票...")
        for stock_code in target_stocks:
            print(f"  分析 {stock_code}...", end=" ", flush=True)
            result = analyzer.analyze_bull_stock(stock_code)
            if result.get('success'):
                print("✅")
            else:
                print(f"❌ {result.get('message', '')}")
        
        # 训练特征模板（获取特征列表）
        print("\n📊 步骤2: 训练特征模板...")
        train_result = analyzer.train_features()
        if not train_result.get('success'):
            raise ValueError(f"特征训练失败: {train_result.get('message', '')}")
        
        # 获取特征名称
        common_features = analyzer.trained_features.get('common_features', {})
        self.feature_names = sorted(common_features.keys())
        print(f"  特征数量: {len(self.feature_names)}")
        
        # 提取所有股票的特征
        print("\n📊 步骤3: 提取所有股票的特征...")
        X_list = []
        y_list = []
        
        for stock_code in target_stocks:
            if stock_code not in analyzer.analysis_results:
                continue
            
            analysis_result = analyzer.analysis_results[stock_code]
            interval = analysis_result.get('interval')
            if not interval or interval.get('起点索引') is None:
                continue
            
            start_idx = interval.get('起点索引')
            weekly_df = analyzer.fetcher.get_weekly_kline(stock_code, period="2y")
            if weekly_df is None or len(weekly_df) == 0:
                continue
            
            # 找到成交量突增点
            volume_surge_idx = analyzer.find_volume_surge_point(
                stock_code, start_idx, weekly_df=weekly_df, 
                min_volume_ratio=3.0, lookback_weeks=52
            )
            if volume_surge_idx is None:
                volume_surge_idx = max(0, start_idx - 20)
            
            # 提取特征
            features = analyzer.extract_features_at_start_point(
                stock_code, volume_surge_idx, lookback_weeks=40, weekly_df=weekly_df
            )
            if features is None:
                continue
            
            # 构建特征向量（按照特征名称顺序）
            feature_vector = []
            for feature_name in self.feature_names:
                if feature_name in features:
                    feature_vector.append(float(features[feature_name]) if features[feature_name] is not None else 0.0)
                else:
                    feature_vector.append(0.0)
            
            X_list.append(feature_vector)
            
            # 标签：对于训练样本，期望匹配度为1.0
            # 这里我们使用当前统计模型的匹配度作为标签
            match_score = analyzer._calculate_match_score(
                features, common_features, tolerance=0.3
            )
            total_match = match_score.get('总匹配度', 0.95)  # 训练样本期望高匹配度
            y_list.append(total_match)
            
            stock_name = analysis_result.get('stock_info', {}).get('名称', stock_code)
            print(f"  ✅ {stock_code} {stock_name}: 特征数={len(feature_vector)}, 标签={total_match:.3f}")
        
        X = np.array(X_list)
        y = np.array(y_list)
        
        print(f"\n📊 训练数据准备完成:")
        print(f"  样本数: {len(X)}")
        print(f"  特征数: {X.shape[1]}")
        print(f"  标签范围: [{y.min():.3f}, {y.max():.3f}]")
        print(f"  标签均值: {y.mean():.3f}")
        
        return X, y
    
    def train(self, X: np.ndarray, y: np.ndarray, test_size: float = 0.2):
        """
        训练神经网络模型
        :param X: 特征矩阵
        :param y: 标签（匹配度）
        :param test_size: 测试集比例
        """
        if not SKLEARN_AVAILABLE:
            raise ImportError("scikit-learn未安装，请运行: pip install scikit-learn")
        
        print("\n" + "=" * 80)
        print("🧠 训练神经网络模型")
        print("=" * 80)
        
        # 数据标准化
        print("\n📊 步骤1: 标准化特征数据...")
        X_scaled = self.scaler.fit_transform(X)
        
        # 划分训练集和测试集
        if len(X) > 5:  # 如果样本数足够，划分测试集
            X_train, X_test, y_train, y_test = train_test_split(
                X_scaled, y, test_size=test_size, random_state=self.random_state
            )
            print(f"  训练集: {len(X_train)} 样本")
            print(f"  测试集: {len(X_test)} 样本")
        else:
            X_train, y_train = X_scaled, y
            X_test, y_test = None, None
            print(f"  样本数较少，使用全部数据训练: {len(X_train)} 样本")
        
        # 创建模型
        print(f"\n📊 步骤2: 创建神经网络模型...")
        print(f"  隐藏层结构: {self.hidden_layer_sizes}")
        self.model = MLPRegressor(
            hidden_layer_sizes=self.hidden_layer_sizes,
            activation='relu',
            solver='adam',
            alpha=0.0001,  # L2正则化系数
            batch_size='auto',
            learning_rate='adaptive',
            learning_rate_init=0.001,
            max_iter=1000,
            shuffle=True,
            random_state=self.random_state,
            tol=1e-4,
            verbose=False,
            warm_start=False,
            momentum=0.9,
            nesterovs_momentum=True,
            early_stopping=False,
            validation_fraction=0.1,
            beta_1=0.9,
            beta_2=0.999,
            epsilon=1e-8
        )
        
        # 训练模型
        print(f"\n📊 步骤3: 训练模型...")
        self.model.fit(X_train, y_train)
        self.is_trained = True
        self.trained_at = datetime.now()
        
        # 评估模型
        print(f"\n📊 步骤4: 评估模型...")
        train_score = self.model.score(X_train, y_train)
        print(f"  训练集R²分数: {train_score:.4f}")
        
        if X_test is not None:
            test_score = self.model.score(X_test, y_test)
            print(f"  测试集R²分数: {test_score:.4f}")
            
            # 预测测试集
            y_pred = self.model.predict(X_test)
            mae = np.mean(np.abs(y_pred - y_test))
            rmse = np.sqrt(np.mean((y_pred - y_test) ** 2))
            print(f"  测试集MAE: {mae:.4f}")
            print(f"  测试集RMSE: {rmse:.4f}")
        
        print("\n✅ 神经网络模型训练完成！")
        print("=" * 80)
    
    def predict(self, features: Dict) -> float:
        """
        预测匹配度
        :param features: 特征字典
        :return: 匹配度（0-1）
        """
        if not self.is_trained:
            raise ValueError("模型尚未训练，请先调用train()方法")
        
        # 构建特征向量
        feature_vector = []
        for feature_name in self.feature_names:
            if feature_name in features:
                feature_vector.append(float(features[feature_name]) if features[feature_name] is not None else 0.0)
            else:
                feature_vector.append(0.0)
        
        X = np.array([feature_vector])
        X_scaled = self.scaler.transform(X)
        
        # 预测
        y_pred = self.model.predict(X_scaled)[0]
        
        # 限制在[0, 1]范围内
        return max(0.0, min(1.0, float(y_pred)))
    
    def save_model(self, filepath: str):
        """
        保存模型
        :param filepath: 保存路径
        """
        if not self.is_trained:
            raise ValueError("模型尚未训练，无法保存")
        
        model_data = {
            'model': self.model,
            'scaler': self.scaler,
            'feature_names': self.feature_names,
            'hidden_layer_sizes': self.hidden_layer_sizes,
            'random_state': self.random_state,
            'trained_at': self.trained_at.isoformat() if self.trained_at else None,
            'is_trained': self.is_trained
        }
        
        os.makedirs(os.path.dirname(filepath) if os.path.dirname(filepath) else '.', exist_ok=True)
        
        with open(filepath, 'wb') as f:
            pickle.dump(model_data, f)
        
        print(f"✅ 模型已保存到: {filepath}")
    
    def load_model(self, filepath: str):
        """
        加载模型
        :param filepath: 模型路径
        """
        with open(filepath, 'rb') as f:
            model_data = pickle.load(f)
        
        self.model = model_data['model']
        self.scaler = model_data['scaler']
        self.feature_names = model_data['feature_names']
        self.hidden_layer_sizes = model_data['hidden_layer_sizes']
        self.random_state = model_data['random_state']
        self.is_trained = model_data['is_trained']
        self.trained_at = datetime.fromisoformat(model_data['trained_at']) if model_data['trained_at'] else None
        
        print(f"✅ 模型已加载: {filepath}")
        print(f"  训练时间: {self.trained_at}")
        print(f"  隐藏层结构: {self.hidden_layer_sizes}")
        print(f"  特征数: {len(self.feature_names)}")


def test_neural_network_model():
    """测试神经网络模型"""
    print("=" * 80)
    print("🧠 测试神经网络模型")
    print("=" * 80)
    
    if not SKLEARN_AVAILABLE:
        print("\n❌ scikit-learn未安装，无法测试神经网络模型")
        print("   请运行: pip install scikit-learn")
        return
    
    # 11只训练股票
    target_stocks = ['000592', '002104', '002759', '300436', '301005', '301232', 
                     '002788', '603778', '603122', '600343', '603216']
    
    # 创建分析器
    print("\n初始化分析器...")
    analyzer = BullStockAnalyzer(auto_load_default_stocks=False, auto_analyze_and_train=False)
    
    # 创建神经网络模型
    print("\n创建神经网络模型...")
    nn_model = BullStockNeuralNetwork(
        hidden_layer_sizes=(128, 64, 32),  # 3层隐藏层
        random_state=42
    )
    
    # 准备训练数据
    X, y = nn_model.prepare_training_data(analyzer, target_stocks)
    
    # 训练模型
    nn_model.train(X, y, test_size=0.2)
    
    # 测试所有训练股票
    print("\n" + "=" * 80)
    print("🔍 测试神经网络模型预测结果")
    print("=" * 80)
    
    match_scores = {}
    for stock_code in target_stocks:
        if stock_code not in analyzer.analysis_results:
            continue
        
        analysis_result = analyzer.analysis_results[stock_code]
        interval = analysis_result.get('interval')
        if not interval or interval.get('起点索引') is None:
            continue
        
        start_idx = interval.get('起点索引')
        weekly_df = analyzer.fetcher.get_weekly_kline(stock_code, period="2y")
        if weekly_df is None or len(weekly_df) == 0:
            continue
        
        volume_surge_idx = analyzer.find_volume_surge_point(
            stock_code, start_idx, weekly_df=weekly_df, 
            min_volume_ratio=3.0, lookback_weeks=52
        )
        if volume_surge_idx is None:
            volume_surge_idx = max(0, start_idx - 20)
        
        features = analyzer.extract_features_at_start_point(
            stock_code, volume_surge_idx, lookback_weeks=40, weekly_df=weekly_df
        )
        if features is None:
            continue
        
        # 使用神经网络预测
        nn_score = nn_model.predict(features)
        
        # 使用原始统计模型预测（对比）
        common_features = analyzer.trained_features.get('common_features', {})
        stat_score = analyzer._calculate_match_score(features, common_features, tolerance=0.3)
        stat_total = stat_score.get('总匹配度', 0)
        
        match_scores[stock_code] = {
            'nn_score': nn_score,
            'stat_score': stat_total
        }
        
        stock_name = analysis_result.get('stock_info', {}).get('名称', stock_code)
        print(f"  {stock_code} {stock_name}:")
        print(f"    神经网络: {nn_score:.3f}")
        print(f"    统计模型: {stat_total:.3f}")
        print(f"    差异: {abs(nn_score - stat_total):.3f}")
    
    # 统计
    if match_scores:
        nn_scores = [s['nn_score'] for s in match_scores.values()]
        stat_scores = [s['stat_score'] for s in match_scores.values()]
        
        print(f"\n📊 统计:")
        print(f"  神经网络平均匹配度: {np.mean(nn_scores):.3f}")
        print(f"  统计模型平均匹配度: {np.mean(stat_scores):.3f}")
        print(f"  神经网络最高匹配度: {np.max(nn_scores):.3f}")
        print(f"  统计模型最高匹配度: {np.max(stat_scores):.3f}")
        print(f"  神经网络最低匹配度: {np.min(nn_scores):.3f}")
        print(f"  统计模型最低匹配度: {np.min(stat_scores):.3f}")
        print(f"  平均差异: {np.mean([abs(s['nn_score'] - s['stat_score']) for s in match_scores.values()]):.3f}")
    
    # 保存模型
    print("\n" + "=" * 80)
    print("💾 保存神经网络模型")
    print("=" * 80)
    
    os.makedirs('models', exist_ok=True)
    model_path = 'models/神经网络模型.pkl'
    nn_model.save_model(model_path)
    
    print("\n" + "=" * 80)
    print("✅ 神经网络模型测试完成！")
    print("=" * 80)


if __name__ == '__main__':
    test_neural_network_model()
