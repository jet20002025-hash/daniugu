#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查11只训练股票在使用优化模型v2时的匹配度
"""
import sys
sys.path.insert(0, '.')
from bull_stock_analyzer import BullStockAnalyzer
from datetime import datetime
import pandas as pd
import numpy as np

# 11只训练股票
TRAINING_STOCKS = {
    '000592': '平潭发展',
    '002104': '恒宝股份',
    '002759': '天际股份',
    '300436': '广生堂',
    '301005': '超捷股份',
    '301232': '飞沃科技',
    '002788': '鹭燕医药',
    '603778': '国晟科技',
    '603122': '合富中国',
    '600343': '航天动力',
    '603216': '梦天家居'
}

def check_training_stocks_match_v2():
    """检查训练股票在优化模型v2下的匹配度"""
    print("=" * 80)
    print("📊 检查11只训练股票在优化模型v2下的匹配度")
    print("=" * 80)
    print()
    
    # 加载优化后的模型
    analyzer = BullStockAnalyzer(auto_load_default_stocks=False, auto_analyze_and_train=False)
    if not analyzer.load_model('models/模型11_优化_v2.json', skip_network=True):
        print("❌ 模型加载失败")
        return
    
    if not analyzer.trained_features or 'common_features' not in analyzer.trained_features:
        print("❌ 模型特征未加载")
        return
    
    print("✅ 优化模型v2加载成功")
    print()
    
    results = []
    
    # 对每只训练股票，使用其买点日期提取特征并计算匹配度
    for stock_code, stock_name in TRAINING_STOCKS.items():
        print(f"📈 处理 {stock_code} {stock_name}...")
        
        try:
            # 获取该股票的最佳买点（通过查找8周内涨幅300%的区间）
            buy_points_result = analyzer.find_buy_points(stock_code, search_years=3)
            
            if not buy_points_result.get('success') or not buy_points_result.get('buy_points'):
                print(f"  ❌ 未找到买点")
                results.append({
                    '股票代码': stock_code,
                    '股票名称': stock_name,
                    '买点日期': 'N/A',
                    '匹配度': 0.0,
                    '状态': '未找到买点'
                })
                continue
            
            # 取第一个买点（最佳买点）
            best_buy_point = buy_points_result['buy_points'][0]
            buy_date = best_buy_point.get('日期')
            buy_price = best_buy_point.get('价格')
            
            if not buy_date:
                print(f"  ❌ 买点日期为空")
                results.append({
                    '股票代码': stock_code,
                    '股票名称': stock_name,
                    '买点日期': 'N/A',
                    '匹配度': 0.0,
                    '状态': '买点日期为空'
                })
                continue
            
            buy_date_obj = datetime.strptime(buy_date, '%Y-%m-%d').date()
            print(f"  最佳买点: {buy_date}, 价格: {buy_price:.2f}")
            
            # 使用买点日期作为结束日期获取周K线数据
            weekly_df = analyzer.fetcher.get_weekly_kline(
                stock_code, 
                period="2y", 
                end_date=buy_date_obj
            )
            
            if weekly_df is None or len(weekly_df) < 40:
                print(f"  ❌ 数据不足（{len(weekly_df) if weekly_df is not None else 0} 周）")
                results.append({
                    '股票代码': stock_code,
                    '股票名称': stock_name,
                    '买点日期': buy_date,
                    '匹配度': 0.0,
                    '状态': f'数据不足（{len(weekly_df) if weekly_df is not None else 0} 周）'
                })
                continue
            
            # 确保只使用到买点日期的数据
            if '日期' in weekly_df.columns:
                weekly_df['日期'] = pd.to_datetime(weekly_df['日期']).dt.date
                original_len = len(weekly_df)
                weekly_df = weekly_df[weekly_df['日期'] <= buy_date_obj].copy()
                weekly_df = weekly_df.sort_values('日期').reset_index(drop=True)
            
            if len(weekly_df) < 40:
                print(f"  ❌ 数据不足（过滤后 {len(weekly_df)} 周）")
                results.append({
                    '股票代码': stock_code,
                    '股票名称': stock_name,
                    '买点日期': buy_date,
                    '匹配度': 0.0,
                    '状态': f'数据不足（过滤后 {len(weekly_df)} 周）'
                })
                continue
            
            # 找到买点对应的周K线索引
            buy_idx = None
            for i in range(len(weekly_df)):
                week_date = weekly_df.iloc[i]['日期']
                if isinstance(week_date, pd.Timestamp):
                    week_date = week_date.date()
                
                # 买点应该在这一周或之前
                if week_date >= buy_date_obj:
                    buy_idx = i
                    break
            
            if buy_idx is None:
                buy_idx = len(weekly_df) - 1
            
            # 找到成交量突增点（作为特征提取的起点）
            volume_surge_idx = analyzer.find_volume_surge_point(
                stock_code, 
                buy_idx, 
                weekly_df=weekly_df, 
                min_volume_ratio=2.0, 
                lookback_weeks=52
            )
            
            if volume_surge_idx is None:
                # 如果找不到突增点，使用买点前40周的位置
                volume_surge_idx = max(0, buy_idx - 40)
            
            print(f"  买点索引: {buy_idx}, 成交量突增点索引: {volume_surge_idx}")
            
            # 提取特征（使用成交量突增点作为起点）
            features = analyzer.extract_features_at_start_point(
                stock_code, 
                volume_surge_idx, 
                lookback_weeks=40, 
                weekly_df=weekly_df
            )
            
            if features is None:
                print(f"  ❌ 特征提取失败")
                results.append({
                    '股票代码': stock_code,
                    '股票名称': stock_name,
                    '买点日期': buy_date,
                    '匹配度': 0.0,
                    '状态': '特征提取失败'
                })
                continue
            
            # 计算匹配度
            match_score_result = analyzer._calculate_match_score(
                features, 
                analyzer.trained_features['common_features'], 
                tolerance=0.3
            )
            match_score = match_score_result.get('总匹配度', 0)
            
            print(f"  ✅ 匹配度: {match_score:.4f}")
            print()
            
            results.append({
                '股票代码': stock_code,
                '股票名称': stock_name,
                '买点日期': buy_date,
                '匹配度': match_score,
                '状态': '成功'
            })
            
        except Exception as e:
            print(f"  ❌ 错误: {str(e)[:200]}")
            import traceback
            traceback.print_exc()
            results.append({
                '股票代码': stock_code,
                '股票名称': stock_name,
                '买点日期': 'N/A',
                '匹配度': 0.0,
                '状态': f'错误: {str(e)[:50]}'
            })
            print()
    
    # 显示结果
    print("=" * 80)
    print("📊 结果汇总")
    print("=" * 80)
    print()
    
    df = pd.DataFrame(results)
    
    # 按匹配度排序
    df_sorted = df[df['状态'] == '成功'].copy()
    if len(df_sorted) > 0:
        df_sorted = df_sorted.sort_values('匹配度', ascending=False)
        
        print("训练股票匹配度（按匹配度排序）:")
        print()
        for idx, row in df_sorted.iterrows():
            match_score = row['匹配度']
            status_icon = "✅" if match_score >= 0.83 else "⚠️" if match_score >= 0.70 else "❌"
            print(f"{status_icon} {row['股票代码']} {row['股票名称']:12s} - 匹配度: {match_score:.4f} (买点: {row['买点日期']})")
        
        print()
        print(f"平均匹配度: {df_sorted['匹配度'].mean():.4f}")
        print(f"最高匹配度: {df_sorted['匹配度'].max():.4f}")
        print(f"最低匹配度: {df_sorted['匹配度'].min():.4f}")
        print(f"≥0.83的股票数: {len(df_sorted[df_sorted['匹配度'] >= 0.83])}/{len(df_sorted)}")
        print(f"≥0.70的股票数: {len(df_sorted[df_sorted['匹配度'] >= 0.70])}/{len(df_sorted)}")
    else:
        print("❌ 没有成功计算匹配度的股票")
    
    print()
    
    # 显示失败的股票
    failed_df = df[df['状态'] != '成功']
    if len(failed_df) > 0:
        print("失败的股票:")
        for idx, row in failed_df.iterrows():
            print(f"  ❌ {row['股票代码']} {row['股票名称']} - {row['状态']}")
        print()
    
    # 保存结果
    csv_file = 'training_stocks_match_v2.csv'
    df.to_csv(csv_file, index=False, encoding='utf-8-sig')
    print(f"✅ 结果已保存到: {csv_file}")

if __name__ == '__main__':
    try:
        check_training_stocks_match_v2()
    except KeyboardInterrupt:
        print("\n⚠️ 用户中断")
    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
        import traceback
        traceback.print_exc()
