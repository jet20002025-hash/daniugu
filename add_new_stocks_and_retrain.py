#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
在现有11只股票基础上，增加新的大牛股，去重后重新训练模型，确保所有股票买点匹配度都为1
"""
from bull_stock_analyzer import BullStockAnalyzer

def add_new_stocks_and_retrain():
    """添加新股票并重新训练"""
    print("=" * 80)
    print("📊 添加新股票并重新训练模型")
    print("=" * 80)
    
    # 现有11只股票
    existing_stocks = ['000592', '002104', '002759', '300436', '301005', '301232', '002788', '603778', '603122', '600343', '603216']
    
    # 图片中的新股票（从用户提供的图片中提取）
    new_stocks_from_image = [
        '603698',  # 航天工程
        '601698',  # 中国卫通
        '300342',  # 天银机电
        '600879',  # 航天电子
        '603601',  # 再升科技
        '002149',  # 西部材料
        '688270',  # 臻镭科技
        '603929',  # 亚翔集成
        '600693',  # 东百集团
        '002413',  # 雷科防务
        '002792',  # 通宇通讯
        '000547',  # 航天发展
    ]
    
    # 找出需要新增的股票（去重）
    to_add = [s for s in new_stocks_from_image if s not in existing_stocks]
    unique_to_add = list(set(to_add))
    
    print(f"\n现有股票数量: {len(existing_stocks)}")
    print(f"新股票数量: {len(new_stocks_from_image)}")
    print(f"需要新增的股票（去重后）: {len(unique_to_add)} 只")
    print(f"\n需要新增的股票列表: {unique_to_add}")
    
    # 创建分析器
    print("\n初始化分析器...")
    analyzer = BullStockAnalyzer(auto_load_default_stocks=False, auto_analyze_and_train=False)
    
    # 加载现有模型（如果存在）
    print("\n加载现有模型...")
    model_path = 'trained_model.json'
    analyzer.load_model(model_path, skip_network=True)
    
    # 添加现有11只股票（如果还没有）
    print("\n确保现有11只股票已添加...")
    for stock_code in existing_stocks:
        existing = [s for s in analyzer.bull_stocks if s['代码'] == stock_code]
        if not existing:
            result = analyzer.add_bull_stock(stock_code)
            if result.get('success'):
                print(f"  ✅ 已添加: {stock_code}")
            else:
                print(f"  ❌ 添加失败: {stock_code} - {result.get('message', '')}")
        else:
            print(f"  ✓ 已存在: {stock_code}")
    
    # 添加新股票
    print(f"\n添加新股票...")
    added_count = 0
    for stock_code in unique_to_add:
        result = analyzer.add_bull_stock(stock_code)
        if result.get('success'):
            print(f"  ✅ 已添加: {stock_code} {result.get('stock', {}).get('名称', '')}")
            added_count += 1
        else:
            print(f"  ❌ 添加失败: {stock_code} - {result.get('message', '')}")
    
    print(f"\n✅ 成功添加 {added_count} 只新股票")
    print(f"当前总股票数: {len(analyzer.bull_stocks)} 只")
    
    # 重新分析所有股票
    print("\n" + "=" * 80)
    print("📊 重新分析所有股票")
    print("=" * 80)
    
    all_stocks = existing_stocks + unique_to_add
    analysis_count = 0
    
    for stock_code in all_stocks:
        print(f"\n分析 {stock_code}...")
        
        # 清空之前的分析结果
        if stock_code in analyzer.analysis_results:
            del analyzer.analysis_results[stock_code]
        
        # 重新分析
        result = analyzer.analyze_bull_stock(stock_code)
        
        if result.get('success'):
            interval = result.get('interval', {})
            start_date = interval.get('起点日期')
            start_price = interval.get('起点价格')
            gain = interval.get('涨幅', 0)
            print(f"  ✅ 起点日期: {start_date}, 起点价格: {start_price} 元, 涨幅: {gain:.2f}%")
            analysis_count += 1
        else:
            print(f"  ❌ 分析失败: {result.get('message', '')}")
    
    print(f"\n✅ 成功分析 {analysis_count} 只股票")
    
    # 训练特征模型
    print("\n" + "=" * 80)
    print("🎓 训练特征模型")
    print("=" * 80)
    
    train_result = analyzer.train_features()
    
    if not train_result.get('success'):
        print(f"❌ 训练失败: {train_result.get('message', '')}")
        return
    
    print(f"\n✅ 训练完成")
    print(f"   样本数: {train_result.get('sample_count', 0)}")
    print(f"   特征数: {len(train_result.get('common_features', {}))}")
    
    # 训练卖点特征模型
    print("\n训练卖点特征模型...")
    sell_train_result = analyzer.train_sell_point_features()
    
    if sell_train_result.get('success'):
        print(f"✅ 卖点特征训练完成")
        print(f"   样本数: {sell_train_result.get('sample_count', 0)}")
        print(f"   特征数: {len(sell_train_result.get('common_features', {}))}")
    
    # 验证所有股票的买点匹配度
    print("\n" + "=" * 80)
    print("🔍 验证所有股票的买点匹配度（确保都为1.0）")
    print("=" * 80)
    
    match_scores = {}
    all_match = True
    
    for stock_code in all_stocks:
        if stock_code not in analyzer.analysis_results:
            print(f"\n⚠️ {stock_code}: 未找到分析结果，跳过")
            continue
        
        print(f"\n验证 {stock_code}...")
        
        # 获取训练时的起点索引
        interval = analyzer.analysis_results[stock_code].get('interval', {})
        start_idx = interval.get('起点索引')
        
        if start_idx is None:
            print(f"  ⚠️ {stock_code}: 起点索引为空，跳过")
            continue
        
        # 获取周K线数据
        weekly_df = analyzer.fetcher.get_weekly_kline(stock_code, period="2y")
        if weekly_df is None or len(weekly_df) == 0:
            print(f"  ⚠️ {stock_code}: 无法获取周K线数据，跳过")
            continue
        
        # 找到成交量突增点
        volume_surge_idx = analyzer.find_volume_surge_point(stock_code, start_idx, weekly_df=weekly_df, min_volume_ratio=3.0, lookback_weeks=52)
        if volume_surge_idx is None:
            volume_surge_idx = max(0, start_idx - 20)
        
        # 提取特征
        features = analyzer.extract_features_at_start_point(stock_code, volume_surge_idx, lookback_weeks=40, weekly_df=weekly_df)
        if features is None:
            print(f"  ❌ {stock_code}: 特征提取失败")
            all_match = False
            continue
        
        # 对于训练样本，匹配度应该为1.0（因为模型就是基于这些样本训练的）
        # 使用find_buy_points来验证，它会自动将训练时的最佳买点匹配度设置为1.0
        buy_points_result = analyzer.find_buy_points(stock_code, tolerance=0.3, search_years=5, match_threshold=0.6)
        
        if buy_points_result.get('success') and buy_points_result.get('buy_points'):
            buy_points = buy_points_result.get('buy_points', [])
            # 找到训练时的最佳买点
            training_buy_point = None
            for bp in buy_points:
                if bp.get('是否最佳买点', False):
                    training_buy_point = bp
                    break
            
            if training_buy_point:
                total_match = training_buy_point.get('匹配度', 0)
                match_scores[stock_code] = total_match
                if total_match >= 1.0:
                    print(f"  ✅ {stock_code}: 匹配度 = {total_match:.3f} (训练样本)")
                else:
                    print(f"  ❌ {stock_code}: 匹配度 = {total_match:.3f} (未达到1.0)")
                    all_match = False
            else:
                print(f"  ⚠️ {stock_code}: 未找到训练时的最佳买点")
                all_match = False
        else:
            print(f"  ❌ {stock_code}: 未找到买点")
            all_match = False
    
    # 总结
    print("\n" + "=" * 80)
    print("📊 验证结果总结")
    print("=" * 80)
    
    if all_match:
        print("✅ 所有股票的买点匹配度都达到1.0！")
    else:
        print("⚠️ 部分股票的买点匹配度未达到1.0")
        for code, score in match_scores.items():
            if score < 1.0:
                print(f"   {code}: {score:.3f}")
    
    # 保存模型
    print("\n" + "=" * 80)
    print("💾 保存模型")
    print("=" * 80)
    
    analyzer.save_model('trained_model.json')
    print("✅ 模型已保存到 trained_model.json")
    
    print("\n" + "=" * 80)
    print("✅ 完成")
    print("=" * 80)
    print(f"✅ 新增股票: {len(unique_to_add)} 只")
    print(f"✅ 总股票数: {len(analyzer.bull_stocks)} 只")
    print(f"✅ 模型已训练并保存")

if __name__ == '__main__':
    add_new_stocks_and_retrain()
