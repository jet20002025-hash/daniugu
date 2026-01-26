#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
列出所有22只训练股票的最佳买点和匹配度
"""
import sys
sys.path.insert(0, '.')
from bull_stock_analyzer import BullStockAnalyzer
import json
import os
from datetime import datetime
import pandas as pd

def main():
    print("=" * 80)
    print("📊 列出所有22只训练股票的最佳买点和匹配度")
    print("=" * 80)
    
    # 初始化分析器
    analyzer = BullStockAnalyzer(auto_load_default_stocks=False, auto_analyze_and_train=False)
    
    # 加载训练模型
    model_file = 'trained_model.json'
    if not os.path.exists(model_file):
        print(f"❌ 未找到模型文件: {model_file}")
        return
    
    with open(model_file, 'r', encoding='utf-8') as f:
        model_data = json.load(f)
    
    buy_features = model_data.get('buy_features', {})
    training_stocks = buy_features.get('training_stocks', [])
    common_features = buy_features.get('common_features', {})
    
    print(f"\n📋 模型信息:")
    print(f"   - 训练股票数: {len(training_stocks)} 只")
    print(f"   - 特征数量: {len(common_features)} 个")
    
    # 加载模型到分析器
    analyzer.trained_features = buy_features
    
    print(f"\n📊 计算 {len(training_stocks)} 只训练股票的最佳买点和匹配度...")
    print("=" * 80)
    
    results = []
    
    for i, stock_code in enumerate(training_stocks, 1):
        try:
            print(f"[{i}/{len(training_stocks)}] {stock_code}...", end=' ', flush=True)
            
            # 获取股票名称（从股票列表或使用代码）
            stock_name = stock_code  # 默认使用代码
            try:
                all_stocks = analyzer.fetcher.get_all_stocks()
                for stock in all_stocks:
                    if stock.get('code') == stock_code or stock.get('股票代码') == stock_code:
                        stock_name = stock.get('name', stock.get('股票名称', stock_code))
                        break
            except:
                pass
            
            # 获取周线数据
            weekly_df = analyzer.fetcher.get_weekly_kline(stock_code, period="3y")
            if weekly_df is None or len(weekly_df) < 8:
                print("⚠️ 数据不足")
                continue
            
            # 过滤未来日期
            today = datetime.now().date()
            if '日期' in weekly_df.columns:
                weekly_df['日期'] = pd.to_datetime(weekly_df['日期'])
                weekly_df = weekly_df[weekly_df['日期'].dt.date <= today].copy()
                weekly_df = weekly_df.sort_values('日期').reset_index(drop=True)
            
            if len(weekly_df) < 8:
                print("⚠️ 数据不足")
                continue
            
            # 查找最佳买点（8周内涨幅达到300%）
            valid_intervals = []
            for start_idx in range(len(weekly_df) - 8):
                for end_idx in range(start_idx + 1, min(start_idx + 9, len(weekly_df))):
                    start_price = float(weekly_df.iloc[start_idx]['收盘'])
                    interval_df = weekly_df.iloc[start_idx:end_idx]
                    max_price = float(interval_df['最高'].max())
                    gain = (max_price - start_price) / start_price * 100
                    
                    if gain >= 300.0:
                        start_date = weekly_df.iloc[start_idx]['日期']
                        if isinstance(start_date, pd.Timestamp):
                            start_date_str = start_date.strftime('%Y-%m-%d')
                        else:
                            start_date_str = str(start_date)
                        
                        valid_intervals.append({
                            '起点索引': start_idx,
                            '终点索引': end_idx,
                            '涨幅': gain,
                            '周数': end_idx - start_idx,
                            '买点日期': start_date_str,
                            '买点价格': start_price
                        })
            
            if not valid_intervals:
                print("⚠️ 未找到买点")
                continue
            
            # 找到涨幅最大的区间（最佳买点）
            best_interval = max(valid_intervals, key=lambda x: x['涨幅'])
            best_start_idx = best_interval['起点索引']
            
            # 使用成交量突增点作为特征提取起点（与训练时一致）
            volume_surge_idx = analyzer.find_volume_surge_point(
                weekly_df, best_start_idx, min_volume_ratio=2.0, lookback_weeks=40
            )
            if volume_surge_idx is None:
                volume_surge_idx = max(0, best_start_idx - 20)
            
            # 提取特征
            features = analyzer.extract_features_at_start_point(
                stock_code, volume_surge_idx, lookback_weeks=40, weekly_df=weekly_df
            )
            
            if not features:
                print("⚠️ 无法提取特征")
                continue
            
            # 计算匹配度
            match_score = analyzer._calculate_match_score(
                features, common_features, tolerance=0.3, stock_code=stock_code
            )
            
            total_match = match_score.get('总匹配度', 0)
            core_match = match_score.get('核心特征匹配度', 0)
            profit_chips = features.get('盈利筹码比例', None)
            chip_concentration_90 = features.get('90%成本集中度', None)
            
            results.append({
                '股票代码': stock_code,
                '股票名称': stock_name,
                '最佳买点日期': best_interval['买点日期'],
                '最佳买点价格': round(best_interval['买点价格'], 2),
                '涨幅': round(best_interval['涨幅'], 2),
                '周数': best_interval['周数'],
                '匹配度': round(total_match, 3),
                '核心特征匹配度': round(core_match, 3),
                '盈利筹码比例': round(profit_chips, 2) if profit_chips is not None else None,
                '90%成本集中度': round(chip_concentration_90, 2) if chip_concentration_90 is not None else None
            })
            
            status = "✅" if total_match >= 0.95 else "⚠️"
            print(f"{status} {total_match:.3f} ({best_interval['买点日期']})")
            
        except Exception as e:
            print(f"❌ 失败: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "=" * 80)
    print("📊 所有训练股票的最佳买点和匹配度")
    print("=" * 80)
    
    if results:
        # 按匹配度排序
        results.sort(key=lambda x: x['匹配度'], reverse=True)
        
        print(f"\n{'排名':<6} {'股票代码':<10} {'股票名称':<20} {'最佳买点日期':<14} {'买点价格':<10} {'涨幅':<10} {'周数':<6} {'匹配度':<10} {'核心匹配度':<12} {'盈利筹码':<10} {'90%集中度':<12}")
        print("-" * 140)
        for i, r in enumerate(results, 1):
            profit = f"{r['盈利筹码比例']:.2f}%" if r['盈利筹码比例'] is not None else "N/A"
            chip_90 = f"{r['90%成本集中度']:.2f}" if r['90%成本集中度'] is not None else "N/A"
            print(f"{i:<6} {r['股票代码']:<10} {r['股票名称']:<20} {r['最佳买点日期']:<14} {r['最佳买点价格']:>8.2f} {r['涨幅']:>8.2f}% {r['周数']:>4} {r['匹配度']:>8.3f} {r['核心特征匹配度']:>10.3f} {profit:>10} {chip_90:>12}")
        
        # 统计信息
        match_scores = [r['匹配度'] for r in results]
        core_scores = [r['核心特征匹配度'] for r in results]
        pass_count = len([s for s in match_scores if s >= 0.95])
        
        print(f"\n📈 统计信息:")
        print(f"   平均匹配度: {sum(match_scores) / len(match_scores):.3f}")
        print(f"   最低匹配度: {min(match_scores):.3f}")
        print(f"   最高匹配度: {max(match_scores):.3f}")
        print(f"   平均核心特征匹配度: {sum(core_scores) / len(core_scores):.3f}")
        print(f"   达标数量（>=0.95）: {pass_count}/{len(match_scores)}")
        
        if pass_count == len(match_scores):
            print(f"\n✅ 所有 {len(match_scores)} 只股票的匹配度都 >= 0.95！")
        else:
            print(f"\n⚠️ 有 {len(match_scores) - pass_count} 只股票的匹配度 < 0.95")
        
        # 保存结果
        output_file = 'training_stocks_buy_points_list.json'
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump({
                '计算时间': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                '模型文件': model_file,
                '训练股票数': len(training_stocks),
                '成功计算数': len(results),
                '结果': results
            }, f, ensure_ascii=False, indent=2)
        print(f"\n✅ 结果已保存到: {output_file}")
    else:
        print("❌ 没有成功计算的结果")

if __name__ == '__main__':
    main()
