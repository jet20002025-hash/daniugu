#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
训练并保存模型脚本
1. 分析11只大牛股
2. 训练买点特征模型
3. 训练卖点特征模型
4. 保存模型到文件
"""
from bull_stock_analyzer import BullStockAnalyzer
import json
from datetime import datetime

def save_model(analyzer, filename='trained_model.json'):
    """保存模型到JSON文件"""
    try:
        model_data = {
            'trained_at': datetime.now().isoformat(),
            'buy_features': None,
            'sell_features': None,
            'screener_model': None,
            'analysis_results': {},
            'bull_stocks': []
        }
        
        # 保存买点特征模型
        if analyzer.trained_features:
            buy_features = analyzer.trained_features.copy()
            # 转换datetime对象为字符串
            if 'trained_at' in buy_features and hasattr(buy_features['trained_at'], 'isoformat'):
                buy_features['trained_at'] = buy_features['trained_at'].isoformat()
            model_data['buy_features'] = buy_features
        
        # 保存卖点特征模型
        if analyzer.trained_sell_features:
            sell_features = analyzer.trained_sell_features.copy()
            # 转换datetime对象为字符串
            if 'trained_at' in sell_features and hasattr(sell_features['trained_at'], 'isoformat'):
                sell_features['trained_at'] = sell_features['trained_at'].isoformat()
            model_data['sell_features'] = sell_features

        # 保存“8条件”选股大模型
        if getattr(analyzer, 'trained_screener_model', None):
            screener_model = analyzer.trained_screener_model.copy()
            if 'trained_at' in screener_model and hasattr(screener_model['trained_at'], 'isoformat'):
                screener_model['trained_at'] = screener_model['trained_at'].isoformat()
            model_data['screener_model'] = screener_model
        
        # 保存分析结果（只保存关键信息）
        for stock_code, result in analyzer.analysis_results.items():
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
        for stock in analyzer.bull_stocks:
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
        
        print(f"\n✅ 模型已保存到: {filename}")
        return True
    except Exception as e:
        print(f"\n❌ 保存模型失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def load_model(analyzer, filename='trained_model.json'):
    """从JSON文件加载模型"""
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            model_data = json.load(f)
        
        # 加载买点特征模型
        if model_data.get('buy_features'):
            buy_features = model_data['buy_features'].copy()
            # 转换字符串为datetime对象
            if 'trained_at' in buy_features and isinstance(buy_features['trained_at'], str):
                buy_features['trained_at'] = datetime.fromisoformat(buy_features['trained_at'])
            analyzer.trained_features = buy_features
            print(f"✅ 已加载买点特征模型（特征数: {len(buy_features.get('common_features', {}))}）")
        
        # 加载卖点特征模型
        if model_data.get('sell_features'):
            sell_features = model_data['sell_features'].copy()
            # 转换字符串为datetime对象
            if 'trained_at' in sell_features and isinstance(sell_features['trained_at'], str):
                sell_features['trained_at'] = datetime.fromisoformat(sell_features['trained_at'])
            analyzer.trained_sell_features = sell_features
            print(f"✅ 已加载卖点特征模型（特征数: {len(sell_features.get('common_features', {}))}）")
        
        # 加载分析结果（简化版，只加载关键信息）
        # 注意：完整的分析结果需要重新分析，这里只加载区间信息
        
        # 加载大牛股列表
        if model_data.get('bull_stocks'):
            for stock_data in model_data['bull_stocks']:
                # 检查是否已存在
                existing = [s for s in analyzer.bull_stocks if s['代码'] == stock_data['代码']]
                if not existing:
                    from datetime import datetime
                    stock = {
                        '代码': stock_data['代码'],
                        '名称': stock_data['名称'],
                        '添加时间': datetime.fromisoformat(stock_data['添加时间']) if isinstance(stock_data['添加时间'], str) else datetime.now(),
                        '数据条数': stock_data.get('数据条数', 0)
                    }
                    analyzer.bull_stocks.append(stock)
        
        print(f"✅ 模型加载完成")
        return True
    except FileNotFoundError:
        print(f"⚠️ 模型文件不存在: {filename}")
        return False
    except Exception as e:
        print(f"❌ 加载模型失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("=" * 80)
    print("🚀 开始训练模型（11只大牛股）")
    print("=" * 80)
    
    # 创建分析器（不自动训练，手动控制）
    analyzer = BullStockAnalyzer(auto_load_default_stocks=True, auto_analyze_and_train=False)
    
    print(f"\n✅ 已加载 {len(analyzer.bull_stocks)} 只大牛股")
    
    # 步骤1: 分析所有11只大牛股
    print("\n" + "=" * 80)
    print("📊 步骤1: 分析所有大牛股（找到涨幅最大区间）")
    print("=" * 80)
    
    for i, stock in enumerate(analyzer.bull_stocks, 1):
        stock_code = stock['代码']
        stock_name = stock['名称']
        print(f"\n[{i}/{len(analyzer.bull_stocks)}] 分析 {stock_name} ({stock_code})...")
        result = analyzer.analyze_bull_stock(stock_code)
        if result.get('success'):
            interval = result.get('interval', {})
            gain = interval.get('涨幅', 0)
            print(f"  ✅ 分析完成: 涨幅 {gain:.2f}%")
        else:
            print(f"  ❌ 分析失败: {result.get('message', '')}")
    
    print(f"\n✅ 分析完成，共分析 {len(analyzer.analysis_results)} 只股票")
    
    # 步骤2: 训练买点特征模型
    print("\n" + "=" * 80)
    print("🎓 步骤2: 训练买点特征模型")
    print("=" * 80)
    
    train_result = analyzer.train_features()
    if train_result.get('success'):
        feature_count = len(train_result.get('common_features', {}))
        sample_count = train_result.get('sample_count', 0)
        print(f"\n✅ 买点特征模型训练完成")
        print(f"   - 特征数量: {feature_count}")
        print(f"   - 样本数量: {sample_count}")
        # 如果包含“8条件”选股大模型，也打印摘要
        if getattr(analyzer, 'trained_screener_model', None):
            cond_stats = analyzer.trained_screener_model.get('condition_stats', {})
            print(f"   - 选股大模型(8条件)统计项: {len(cond_stats)}")
    else:
        print(f"\n❌ 买点特征模型训练失败: {train_result.get('message', '')}")
        return
    
    # 步骤3: 训练卖点特征模型
    print("\n" + "=" * 80)
    print("💰 步骤3: 训练卖点特征模型")
    print("=" * 80)
    
    sell_train_result = analyzer.train_sell_point_features()
    if sell_train_result.get('success'):
        sell_feature_count = len(sell_train_result.get('common_features', {}))
        sell_sample_count = sell_train_result.get('sample_count', 0)
        print(f"\n✅ 卖点特征模型训练完成")
        print(f"   - 特征数量: {sell_feature_count}")
        print(f"   - 样本数量: {sell_sample_count}")
    else:
        print(f"\n⚠️ 卖点特征模型训练失败: {sell_train_result.get('message', '')}")
    
    # 步骤4: 验证匹配度
    print("\n" + "=" * 80)
    print("🔍 步骤4: 验证匹配度（确保买点100%符合要求）")
    print("=" * 80)
    
    is_ready, max_score = analyzer._check_match_score()
    print(f"\n匹配度检查结果:")
    print(f"   - 最高匹配度: {max_score:.3f}")
    print(f"   - 是否达标 (>=0.95): {'✅ 是' if is_ready else '❌ 否'}")
    
    # 测试每只股票的买点匹配度，并收集结果用于最后展示
    name_by_code = {s['代码']: s['名称'] for s in analyzer.bull_stocks}
    match_results = []
    print(f"\n测试每只股票的买点匹配度:")
    for stock_code in analyzer.default_bull_stocks:
        name = name_by_code.get(stock_code, '-')
        if stock_code not in analyzer.analysis_results:
            match_results.append((stock_code, name, None, False))
            continue
        
        print(f"\n  {stock_code}:")
        result = analyzer.find_buy_points(stock_code, tolerance=0.3, search_years=5, match_threshold=0.95)
        if not result.get('success'):
            match_results.append((stock_code, name, None, False))
            print(f"    ❌ 查找失败: {result.get('message', '')}")
        elif not result.get('buy_points', []):
            match_results.append((stock_code, name, None, False))
            print(f"    ⚠️ 未找到买点（匹配度阈值0.95）")
        else:
            best_bp = result['buy_points'][0]
            ms = best_bp.get('匹配度', 0)
            ib = best_bp.get('是否最佳买点', False)
            match_results.append((stock_code, name, ms, ib))
            print(f"    最高匹配度: {ms:.3f}, 是否最佳买点: {'✅' if ib else '❌'}")
    
    def _print_match_table(rows, title="大牛股匹配度一览", threshold=0.95):
        print(f"\n{'='*80}")
        print(f"📋 {title}")
        print(f"{'='*80}")
        print(f"{'代码':<10} {'名称':<12} {'匹配度':<10} {'最佳买点':<10} {'达标(≥%.2f)' % threshold:<12}")
        print("-" * 60)
        for code, name, ms, ib in rows:
            ms_str = f"{ms:.3f}" if ms is not None else "-"
            ok = "✅" if (ms is not None and ms >= threshold) else "❌"
            ib_str = "✅" if ib else "❌"
            print(f"{code:<10} {name:<12} {ms_str:<10} {ib_str:<10} {ok:<12}")
        print(f"{'='*80}\n")
    
    _print_match_table(match_results, "大牛股匹配度一览", 0.95)
    
    # 步骤5: 保存模型
    print("\n" + "=" * 80)
    print("💾 步骤5: 保存模型到文件")
    print("=" * 80)
    
    if analyzer.save_model('trained_model.json'):
        print("\n✅ 所有步骤完成！")
        print("=" * 80)
        print("📝 模型文件: trained_model.json")
        print("📝 Web应用启动时会自动加载此模型")
        print("=" * 80)
        _print_match_table(match_results, "模型已更新 · 大牛股匹配度一览", 0.95)
    else:
        print("\n❌ 保存模型失败")

if __name__ == '__main__':
    main()

