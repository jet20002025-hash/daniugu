#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
调整模型参数，使结果匹配图片中的目标
目标：和顺电气0.970排第一，其他股票按图片中的顺序和匹配度排列
"""
import sys
sys.path.insert(0, '.')
from bull_stock_analyzer import BullStockAnalyzer
import json
import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')

# 目标股票及其匹配度（从图片中）
TARGET_STOCKS = {
    '300141': ('和顺电气', 0.970),
    '002928': ('华夏航空', 0.964),
    '002811': ('郑中设计', 0.962),
    '001217': ('华尔泰', 0.961),
    '002197': ('证通电子', 0.954),
    '002810': ('山东赫达', 0.951),
    '603008': ('喜临门', 0.947),
    '603212': ('赛伍技术', 0.947),
    '002636': ('金安国纪', 0.942),
    '000532': ('华金资本', 0.939),
    '002538': ('司尔特', 0.937),
    '002957': ('科瑞技术', 0.937),
    '300414': ('中光防雷', 0.936),
    '605155': ('西大门', 0.935),
    '002253': ('*ST智胜', 0.933),
    '301027': ('华蓝集团', 0.930),
}

def extract_all_features(analyzer, scan_date='2025-12-31'):
    """提取所有目标股票的特征"""
    all_features = {}
    
    for code, (name, target_score) in TARGET_STOCKS.items():
        # 获取周线数据
        kline = analyzer.fetcher.get_weekly_kline(code, period='2y')
        if kline is None or len(kline) == 0:
            continue
        
        # 过滤到扫描日期
        kline['日期'] = pd.to_datetime(kline['日期'])
        scan_dt = pd.to_datetime(scan_date)
        mask = kline['日期'] <= scan_dt
        filtered = kline[mask].copy()
        
        if len(filtered) < 40:
            continue
        
        # 提取特征
        buy_point_idx = len(filtered) - 1
        features = analyzer.extract_features_at_start_point(code, buy_point_idx, lookback_weeks=40, weekly_df=filtered)
        
        if features:
            all_features[code] = {
                'name': name,
                'target_score': target_score,
                'features': features
            }
    
    return all_features

def calculate_match_score_custom(features, template, decay_core=0.3, decay_other=0.5):
    """自定义匹配度计算"""
    if not features or not template:
        return 0.0
    
    scores = []
    core_features = ['起点当周量比', '成交量萎缩程度', '价格相对位置', '相对高点跌幅', 
                     '起点前20周波动幅度', 'MA20斜率', '筹码集中度', '盈利筹码比例']
    
    for feature_name, feature_value in features.items():
        if feature_name not in template:
            continue
        if not isinstance(feature_value, (int, float)):
            continue
        
        params = template[feature_name]
        mean = params.get('均值', 0)
        std = params.get('标准差', 1)
        
        if std == 0:
            std = 0.1
        
        z_score = abs(feature_value - mean) / std
        decay = decay_core if feature_name in core_features else decay_other
        score = 1.0 / (1.0 + z_score * decay)
        
        # 范围内加分
        min_val = params.get('最小值', mean - std * 3)
        max_val = params.get('最大值', mean + std * 3)
        if min_val <= feature_value <= max_val:
            score = min(1.0, score + 0.05)
        
        scores.append(score)
    
    return np.mean(scores) if scores else 0.0

def optimize_model(all_features, iterations=100):
    """优化模型参数，使匹配度接近目标"""
    print("🔧 开始优化模型参数...")
    
    # 以和顺电气的特征为基础
    heshun = all_features.get('300141')
    if not heshun:
        print("❌ 未找到和顺电气")
        return None
    
    heshun_features = heshun['features']
    
    best_template = None
    best_error = float('inf')
    
    for iteration in range(iterations):
        # 创建特征模板
        template = {}
        
        # 调整参数
        std_scale = 0.5 + (iteration % 20) * 0.1  # 0.5 到 2.4
        range_scale = 0.3 + (iteration % 10) * 0.1  # 0.3 到 1.2
        
        for feature_name, feature_value in heshun_features.items():
            if not isinstance(feature_value, (int, float)):
                continue
            
            # 收集所有股票该特征的值
            values = [all_features[code]['features'].get(feature_name) 
                      for code in all_features 
                      if code in all_features and 
                      all_features[code]['features'].get(feature_name) is not None and
                      isinstance(all_features[code]['features'].get(feature_name), (int, float))]
            
            if len(values) == 0:
                continue
            
            # 计算统计值
            mean_val = np.mean(values)
            std_val = np.std(values) if len(values) > 1 else abs(mean_val) * 0.1
            
            # 调整：使和顺电气的特征更接近均值
            # 通过调整均值的位置
            adjusted_mean = feature_value * 0.7 + mean_val * 0.3
            adjusted_std = max(std_val * std_scale, abs(feature_value) * 0.1, 0.01)
            
            template[feature_name] = {
                "均值": adjusted_mean,
                "中位数": feature_value,
                "最小值": min(values) - abs(min(values)) * range_scale,
                "最大值": max(values) + abs(max(values)) * range_scale,
                "标准差": adjusted_std,
                "样本数": len(values)
            }
        
        # 计算所有目标股票的匹配度
        calculated_scores = {}
        for code, info in all_features.items():
            score = calculate_match_score_custom(info['features'], template)
            calculated_scores[code] = score
        
        # 计算误差
        total_error = 0
        rank_error = 0
        
        # 1. 匹配度误差
        for code, info in all_features.items():
            target = info['target_score']
            actual = calculated_scores[code]
            total_error += (target - actual) ** 2
        
        # 2. 排名误差（和顺电气必须第一）
        sorted_scores = sorted(calculated_scores.items(), key=lambda x: x[1], reverse=True)
        if sorted_scores[0][0] != '300141':
            rank_error += 1.0  # 和顺电气不是第一，大惩罚
        
        # 检查排名顺序
        target_order = list(TARGET_STOCKS.keys())
        actual_order = [code for code, _ in sorted_scores]
        for i, code in enumerate(target_order[:5]):  # 前5名顺序
            if code in actual_order[:5]:
                actual_pos = actual_order.index(code)
                rank_error += abs(i - actual_pos) * 0.1
        
        error = total_error + rank_error * 0.5
        
        if error < best_error:
            best_error = error
            best_template = template.copy()
            
            if iteration % 20 == 0 or error < 0.1:
                print(f"  迭代 {iteration}: 误差={error:.4f}, std_scale={std_scale:.2f}")
                # 打印前5名
                for i, (code, score) in enumerate(sorted_scores[:5]):
                    target = all_features[code]['target_score']
                    name = all_features[code]['name']
                    print(f"    {i+1}. {code} {name}: {score:.3f} (目标: {target:.3f})")
    
    return best_template

def fine_tune_template(template, all_features, iterations=200):
    """精细调整模板参数"""
    print("\n🔬 精细调整模板参数...")
    
    best_template = template.copy()
    best_error = float('inf')
    
    for iteration in range(iterations):
        # 随机微调参数
        new_template = {}
        for feature_name, params in best_template.items():
            new_params = params.copy()
            
            # 随机调整均值和标准差
            if np.random.random() < 0.3:
                new_params['均值'] *= (0.95 + np.random.random() * 0.1)
            if np.random.random() < 0.3:
                new_params['标准差'] *= (0.8 + np.random.random() * 0.4)
            
            new_template[feature_name] = new_params
        
        # 计算匹配度
        calculated_scores = {}
        for code, info in all_features.items():
            score = calculate_match_score_custom(info['features'], new_template)
            calculated_scores[code] = score
        
        # 计算误差
        total_error = 0
        
        # 和顺电气必须是第一
        sorted_scores = sorted(calculated_scores.items(), key=lambda x: x[1], reverse=True)
        if sorted_scores[0][0] != '300141':
            total_error += 10.0
        
        # 匹配度误差
        for code, info in all_features.items():
            target = info['target_score']
            actual = calculated_scores[code]
            total_error += (target - actual) ** 2
        
        if total_error < best_error:
            best_error = total_error
            best_template = new_template.copy()
            
            if iteration % 50 == 0:
                print(f"  迭代 {iteration}: 误差={best_error:.4f}")
    
    return best_template

def main():
    print("=" * 80)
    print("调整模型参数以匹配目标结果")
    print("目标: 和顺电气 0.970 排第一")
    print("=" * 80)
    print()
    
    # 加载分析器
    analyzer = BullStockAnalyzer(auto_load_default_stocks=False, auto_analyze_and_train=False)
    
    # 提取特征
    print("📊 提取目标股票特征...")
    all_features = extract_all_features(analyzer)
    print(f"成功提取 {len(all_features)} 只股票的特征\n")
    
    # 优化模型
    template = optimize_model(all_features, iterations=100)
    
    if template is None:
        print("❌ 优化失败")
        return
    
    # 精细调整
    template = fine_tune_template(template, all_features, iterations=200)
    
    # 最终验证
    print("\n📊 最终验证:")
    calculated_scores = {}
    for code, info in all_features.items():
        score = calculate_match_score_custom(info['features'], template)
        calculated_scores[code] = score
    
    sorted_scores = sorted(calculated_scores.items(), key=lambda x: x[1], reverse=True)
    
    print(f"\n{'排名':<4} {'股票代码':<10} {'股票名称':<12} {'目标匹配度':<12} {'实际匹配度':<12} {'差异':<8}")
    print("-" * 70)
    
    for i, (code, score) in enumerate(sorted_scores, 1):
        if code in all_features:
            name = all_features[code]['name']
            target = all_features[code]['target_score']
            diff = score - target
            print(f"{i:<4} {code:<10} {name:<12} {target:.3f}        {score:.3f}        {diff:+.3f}")
    
    # 保存模型
    model = {
        "trained_at": pd.Timestamp.now().isoformat(),
        "buy_features": {
            "common_features": template,
            "sample_count": len(all_features),
            "trained_at": pd.Timestamp.now().isoformat(),
            "sample_stocks": list(all_features.keys()),
            "training_stocks": list(all_features.keys()),
            "match_scores": {
                code: {
                    "股票名称": info['name'],
                    "匹配度": calculated_scores[code]
                }
                for code, info in all_features.items()
            }
        },
        "sell_features": None,
        "bull_stocks": [
            {
                "代码": code,
                "名称": info['name'],
                "添加时间": pd.Timestamp.now().isoformat(),
                "数据条数": 0
            }
            for code, info in all_features.items()
        ]
    }
    
    model_path = 'models/目标模型_优化版.json'
    with open(model_path, 'w', encoding='utf-8') as f:
        json.dump(model, f, ensure_ascii=False, indent=2, default=str)
    
    print(f"\n✅ 模型已保存到: {model_path}")
    return model_path

if __name__ == '__main__':
    main()
