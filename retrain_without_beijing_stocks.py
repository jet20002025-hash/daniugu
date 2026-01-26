#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
移除训练模型中的北交所股票，重新训练模型
"""
from bull_stock_analyzer import BullStockAnalyzer
import json
import os

def is_beijing_stock(stock_code):
    """判断是否为北交所股票"""
    stock_code = str(stock_code).strip()
    # 北交所股票代码判断：以8、43、83、87、88、89、92开头（6位数字）
    return (stock_code.startswith('8') or 
            stock_code.startswith('43') or 
            stock_code.startswith('83') or 
            stock_code.startswith('87') or 
            stock_code.startswith('88') or 
            stock_code.startswith('89') or
            stock_code.startswith('92'))

def main():
    print("=" * 80)
    print("🚀 移除北交所股票并重新训练模型")
    print("=" * 80)
    
    # 1. 读取当前训练模型，获取股票列表
    print("\n📖 读取当前训练模型...")
    trained_model_path = 'trained_model.json'
    if not os.path.exists(trained_model_path):
        print(f"❌ 错误：找不到模型文件 {trained_model_path}")
        return
    
    with open(trained_model_path, 'r', encoding='utf-8') as f:
        model_data = json.load(f)
    
    buy_features = model_data.get('buy_features', {})
    sample_stocks = buy_features.get('sample_stocks', [])
    
    print(f"当前训练样本数: {len(sample_stocks)}")
    
    # 2. 识别并移除北交所股票
    beijing_stocks = []
    filtered_stocks = []
    
    for stock in sample_stocks:
        if is_beijing_stock(stock):
            beijing_stocks.append(stock)
        else:
            filtered_stocks.append(stock)
    
    print(f"\n📊 识别结果:")
    print(f"  北交所股票: {len(beijing_stocks)} 只")
    if beijing_stocks:
        print(f"  {', '.join(beijing_stocks)}")
    print(f"  非北交所股票: {len(filtered_stocks)} 只")
    print(f"  过滤后剩余: {len(filtered_stocks)} 只")
    
    if len(filtered_stocks) == 0:
        print("❌ 错误：过滤后没有剩余股票，无法训练模型")
        return
    
    # 3. 创建分析器
    print("\n🔧 初始化分析器...")
    analyzer = BullStockAnalyzer(auto_load_default_stocks=False, auto_analyze_and_train=False)
    
    # 清空现有数据
    analyzer.analysis_results = {}
    analyzer.trained_features = None
    analyzer.bull_stocks = []
    
    # 4. 添加过滤后的股票
    print(f"\n📝 添加 {len(filtered_stocks)} 只股票...")
    added_count = 0
    for stock_code in filtered_stocks:
        result = analyzer.add_bull_stock(stock_code)
        if result.get('success'):
            added_count += 1
            if added_count % 10 == 0 or added_count == len(filtered_stocks):
                print(f"  ✅ 已添加: {added_count}/{len(filtered_stocks)} - {stock_code} {result.get('stock', {}).get('名称', '')}")
        else:
            print(f"  ⚠️ 添加失败: {stock_code} - {result.get('message', '')}")
    
    print(f"\n✅ 已加载 {len(analyzer.bull_stocks)} 只大牛股")
    
    # 5. 分析所有股票
    print("\n" + "=" * 80)
    print("📊 步骤1: 分析所有大牛股（找到涨幅最大区间）")
    print("=" * 80)
    
    analyzed_count = 0
    for i, stock in enumerate(analyzer.bull_stocks, 1):
        stock_code = stock.get('代码', '')
        stock_name = stock.get('名称', '')
        print(f"\n[{i}/{len(analyzer.bull_stocks)}] 分析 {stock_code} {stock_name}...")
        
        try:
            # 获取周K线数据
            import pandas as pd
            from datetime import datetime
            weekly_df = analyzer.fetcher.get_weekly_kline(stock_code, period="3y")
            if weekly_df is None or len(weekly_df) == 0:
                print(f"  ⚠️ 无法获取 {stock_code} 的周线数据，跳过")
                continue
            
            # 过滤未来日期
            today = datetime.now().date()
            weekly_df['日期'] = pd.to_datetime(weekly_df['日期'])
            weekly_df = weekly_df[weekly_df['日期'].dt.date <= today].reset_index(drop=True)
            
            if len(weekly_df) < 8:
                print(f"  ⚠️ 数据不足（{len(weekly_df)} 周），跳过")
                continue
            
            # 使用 find_buy_points 方法找到买点（简化版：8周内涨幅300%）
            result = analyzer.find_buy_points(stock_code, search_years=3)
            if result.get('success') and result.get('buy_points'):
                buy_points = result.get('buy_points', [])
                if buy_points:
                    # 使用第一个买点（最佳买点）
                    best_buy_point = buy_points[0]
                    buy_date = best_buy_point.get('日期', '')
                    
                    # 找到买点对应的索引
                    start_idx = None
                    if buy_date:
                        buy_date_dt = pd.to_datetime(buy_date).date()
                        for idx, row in weekly_df.iterrows():
                            row_date = pd.to_datetime(row['日期']).date()
                            if row_date >= buy_date_dt:
                                start_idx = weekly_df.index.get_loc(idx)
                                break
                    
                    if start_idx is not None:
                        # 记录分析结果（train_features方法需要这个）
                        analyzer.analysis_results[stock_code] = {
                            'success': True,
                            'interval': {
                                '起点索引': int(start_idx),
                                '起点日期': weekly_df.iloc[start_idx]['日期'].strftime('%Y-%m-%d') if isinstance(weekly_df.iloc[start_idx]['日期'], pd.Timestamp) else str(weekly_df.iloc[start_idx]['日期']),
                                '起点价格': float(weekly_df.iloc[start_idx]['收盘'])
                            }
                        }
                        analyzed_count += 1
                        print(f"  ✅ 找到买点: 索引 {start_idx}, 日期 {analyzer.analysis_results[stock_code]['interval']['起点日期']}")
                    else:
                        print(f"  ⚠️ 未找到买点索引")
                else:
                    print(f"  ⚠️ 未找到买点")
            else:
                print(f"  ⚠️ 未找到符合条件的买点，跳过")
                continue
            if result.get('success') and result.get('interval'):
                start_idx = result['interval']['start_idx']
                
                # 记录分析结果（train_features方法需要这个）
                analyzer.analysis_results[stock_code] = {
                    'success': True,
                    'interval': {
                        '起点索引': int(start_idx),
                        '起点日期': weekly_df.iloc[start_idx]['日期'].strftime('%Y-%m-%d') if isinstance(weekly_df.iloc[start_idx]['日期'], pd.Timestamp) else str(weekly_df.iloc[start_idx]['日期']),
                        '起点价格': float(weekly_df.iloc[start_idx]['收盘'])
                    }
                }
                analyzed_count += 1
                print(f"  ✅ 找到买点: 索引 {start_idx}, 日期 {analyzer.analysis_results[stock_code]['interval']['起点日期']}")
            else:
                print(f"  ⚠️ 未找到符合条件的买点，跳过")
        except Exception as e:
            print(f"  ❌ 分析异常: {e}")
            import traceback
            traceback.print_exc()
    
    print(f"\n✅ 分析完成，成功分析 {analyzed_count}/{len(analyzer.bull_stocks)} 只股票")
    
    # 6. 训练模型
    print("\n" + "=" * 80)
    print("🎯 步骤2: 训练特征模型（匹配度目标 >= 0.95）")
    print("=" * 80)
    
    try:
        train_result = analyzer.train_features()
        if train_result.get('success'):
            print("\n✅ 模型训练成功！")
            
            # 显示训练结果
            trained = analyzer.get_trained_features()
            if trained:
                print(f"\n📊 训练结果:")
                print(f"  特征数: {len(trained.get('common_features', {}))}")
                print(f"  样本数: {trained.get('sample_count', 0)}")
                print(f"  训练时间: {trained.get('trained_at', '未知')}")
        else:
            print(f"\n❌ 模型训练失败: {train_result.get('message', '')}")
            return
    except Exception as e:
        print(f"\n❌ 训练异常: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # 7. 保存模型
    print("\n" + "=" * 80)
    print("💾 步骤3: 保存模型")
    print("=" * 80)
    
    save_path = 'trained_model.json'
    success = analyzer.save_model(save_path)
    if success:
        print(f"✅ 模型已保存到: {save_path}")
        
        # 显示保存的模型信息
        if os.path.exists(save_path):
            stat = os.stat(save_path)
            from datetime import datetime
            mtime = datetime.fromtimestamp(stat.st_mtime)
            print(f"   修改时间: {mtime.strftime('%Y-%m-%d %H:%M:%S')}")
    else:
        print(f"❌ 保存模型失败")
        return
    
    # 8. 验证训练结果
    print("\n" + "=" * 80)
    print("✅ 验证训练结果")
    print("=" * 80)
    
    print(f"\n📋 训练样本股票列表 ({len(filtered_stocks)} 只):")
    for i, stock_code in enumerate(filtered_stocks, 1):
        print(f"  {i}. {stock_code}")
    
    print("\n✅ 重新训练完成！")
    print(f"   - 移除了 {len(beijing_stocks)} 只北交所股票")
    print(f"   - 使用 {len(filtered_stocks)} 只股票重新训练")
    print(f"   - 模型已保存到: {save_path}")

if __name__ == '__main__':
    main()
