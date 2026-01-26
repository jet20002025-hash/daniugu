#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
将和顺电气添加到模型11中，并重新训练
"""
import sys
sys.path.insert(0, '.')
from bull_stock_analyzer import BullStockAnalyzer
import json
import warnings
warnings.filterwarnings('ignore')

def main():
    print("=" * 80)
    print("将和顺电气(300141)添加到模型11并重新训练")
    print("=" * 80)
    print()
    
    # 加载当前模型
    analyzer = BullStockAnalyzer(auto_load_default_stocks=False, auto_analyze_and_train=False)
    
    # 读取当前模型
    with open('models/模型11.json', 'r', encoding='utf-8') as f:
        model = json.load(f)
    
    # 获取当前训练股票
    training_stocks = model.get('buy_features', {}).get('training_stocks', [])
    print(f"当前训练股票: {len(training_stocks)} 只")
    for code in training_stocks:
        print(f"  - {code}")
    
    # 添加和顺电气
    if '300141' not in training_stocks:
        training_stocks.append('300141')
        print(f"\n✅ 已添加和顺电气(300141)")
    else:
        print(f"\n⚠️ 和顺电气(300141)已在训练列表中")
    
    print(f"\n新训练股票列表: {len(training_stocks)} 只")
    
    # 清空analyzer的股票数据，重新加载
    analyzer.bull_stocks = []
    analyzer.features_extracted = False
    
    # 加载所有训练股票的数据
    print("\n📥 加载训练股票数据...")
    for code in training_stocks:
        result = analyzer.add_bull_stock(code)
        if result['success']:
            print(f"  ✅ {code} {result.get('stock', {}).get('名称', '')}")
        else:
            print(f"  ⚠️ {code}: {result.get('message', '')}")
    
    print(f"\n✅ 已加载 {len(analyzer.bull_stocks)} 只股票")
    
    # 重新训练模型
    print("\n🔄 开始训练模型...")
    analyzer.train_features()
    
    # 保存新模型
    new_model_path = 'models/模型12_含和顺电气.json'
    analyzer.save_model(new_model_path)
    print(f"\n✅ 新模型已保存到: {new_model_path}")
    
    # 验证和顺电气的匹配度
    print("\n📊 验证训练股票匹配度:")
    analyzer.load_model(new_model_path, skip_network=True)
    
    # 读取新模型获取匹配度
    with open(new_model_path, 'r', encoding='utf-8') as f:
        new_model = json.load(f)
    
    match_scores = new_model.get('buy_features', {}).get('match_scores', {})
    
    # 按匹配度排序
    sorted_scores = sorted(match_scores.items(), key=lambda x: x[1].get('匹配度', 0), reverse=True)
    
    print(f"\n{'排名':<4} {'股票代码':<8} {'股票名称':<10} {'匹配度':<8}")
    print("-" * 40)
    for i, (code, info) in enumerate(sorted_scores, 1):
        name = info.get('股票名称', 'N/A')
        score = info.get('匹配度', 0)
        marker = " ⭐" if code == '300141' else ""
        print(f"{i:<4} {code:<8} {name:<10} {score:.3f}{marker}")
    
    return new_model_path

if __name__ == '__main__':
    main()
