#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查训练股票在回测期间的匹配度
"""
import sys
sys.path.insert(0, '.')
from bull_stock_analyzer import BullStockAnalyzer
from datetime import datetime, timedelta
import pandas as pd

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

def check_training_stocks_match_score():
    """检查训练股票在回测期间的匹配度"""
    print("=" * 80)
    print("📊 检查训练股票在回测期间的匹配度")
    print("=" * 80)
    print()
    
    # 加载模型
    analyzer = BullStockAnalyzer(auto_load_default_stocks=False, auto_analyze_and_train=False)
    if not analyzer.load_model('models/模型11.json', skip_network=True):
        print("❌ 模型加载失败")
        return
    
    if not analyzer.trained_features or 'common_features' not in analyzer.trained_features:
        print("❌ 模型特征未加载")
        return
    
    print("✅ 模型加载成功")
    print()
    
    # 回测日期范围：每周扫描一次（选择几个关键日期测试）
    test_dates = [
        '2025-01-02',  # 回测开始
        '2025-02-05',  # 2月初
        '2025-03-05',  # 3月初
        '2025-06-05',  # 6月初（002104的买点附近）
        '2025-09-01',  # 9月初
        '2025-12-29',  # 回测结束
    ]
    
    print(f"测试日期: {', '.join(test_dates)}")
    print()
    
    results = []
    
    for scan_date_str in test_dates:
        scan_date = datetime.strptime(scan_date_str, '%Y-%m-%d').date()
        print(f"📅 扫描日期: {scan_date_str}")
        print("-" * 80)
        
        for stock_code, stock_name in TRAINING_STOCKS.items():
            try:
                # 获取周K线数据（只使用到扫描日期的数据）
                weekly_df = analyzer.fetcher.get_weekly_kline(
                    stock_code, 
                    period="2y", 
                    use_cache=True,
                    end_date=scan_date
                )
                
                if weekly_df is None or len(weekly_df) < 40:
                    results.append({
                        '股票代码': stock_code,
                        '股票名称': stock_name,
                        '扫描日期': scan_date_str,
                        '匹配度': 0,
                        '市值(亿)': 'N/A',
                        '原因': '数据不足'
                    })
                    print(f"  ❌ {stock_code} {stock_name}: 数据不足（{len(weekly_df) if weekly_df is not None else 0} 周）")
                    continue
                
                # 确保只使用到扫描日期的数据
                if '日期' in weekly_df.columns:
                    weekly_df['日期'] = pd.to_datetime(weekly_df['日期']).dt.date
                    weekly_df = weekly_df[weekly_df['日期'] <= scan_date].copy()
                    weekly_df = weekly_df.sort_values('日期').reset_index(drop=True)
                
                if len(weekly_df) < 40:
                    results.append({
                        '股票代码': stock_code,
                        '股票名称': stock_name,
                        '扫描日期': scan_date_str,
                        '匹配度': 0,
                        '市值(亿)': 'N/A',
                        '原因': f'数据不足（{len(weekly_df)} 周）'
                    })
                    print(f"  ❌ {stock_code} {stock_name}: 数据不足（{len(weekly_df)} 周）")
                    continue
                
                # 找到涨幅最大区间的起点（作为买点）
                # 使用最后一周作为潜在的买点
                current_idx = len(weekly_df) - 1
                
                # 找到成交量突增点
                volume_surge_idx = analyzer.find_volume_surge_point(
                    stock_code, 
                    current_idx, 
                    weekly_df=weekly_df, 
                    min_volume_ratio=3.0, 
                    lookback_weeks=52
                )
                if volume_surge_idx is None:
                    volume_surge_idx = max(0, current_idx - 20)
                
                # 提取特征
                features = analyzer.extract_features_at_start_point(
                    stock_code, 
                    volume_surge_idx, 
                    lookback_weeks=40, 
                    weekly_df=weekly_df
                )
                
                if features is None:
                    results.append({
                        '股票代码': stock_code,
                        '股票名称': stock_name,
                        '扫描日期': scan_date_str,
                        '匹配度': 0,
                        '市值(亿)': 'N/A',
                        '原因': '特征提取失败'
                    })
                    print(f"  ❌ {stock_code} {stock_name}: 特征提取失败")
                    continue
                
                # 计算匹配度
                match_score_result = analyzer._calculate_match_score(
                    features, 
                    analyzer.trained_features['common_features'], 
                    tolerance=0.3
                )
                match_score = match_score_result.get('总匹配度', 0)
                
                # 获取市值（使用扫描日期的价格）
                market_cap = None
                try:
                    if current_idx < len(weekly_df):
                        buy_price = float(weekly_df.iloc[current_idx]['收盘'])
                        market_cap = analyzer.fetcher.get_circulating_market_cap(
                            stock_code, 
                            target_date=scan_date
                        )
                        if market_cap is None:
                            # 尝试估算
                            try:
                                import akshare as ak
                                info_df = ak.stock_individual_info_em(symbol=stock_code)
                                if info_df is not None and len(info_df) > 0:
                                    circulating_shares = None
                                    for _, row in info_df.iterrows():
                                        if '流通股本' in str(row.iloc[0]) or '流通股' in str(row.iloc[0]):
                                            try:
                                                circulating_shares = float(str(row.iloc[1]).replace(',', '').replace('万', ''))
                                                if '万' in str(row.iloc[1]):
                                                    circulating_shares *= 10000
                                                break
                                            except:
                                                pass
                                    if circulating_shares:
                                        market_cap = (circulating_shares * buy_price) / 100000000
                            except:
                                pass
                except:
                    pass
                
                market_cap_str = f"{market_cap:.2f}" if market_cap is not None else "N/A"
                
                # 判断是否通过筛选
                passed = match_score >= 0.83
                if market_cap is not None:
                    passed = passed and market_cap <= 100.0
                
                reason = []
                if match_score < 0.83:
                    reason.append(f"匹配度{match_score:.3f}<0.83")
                if market_cap is not None and market_cap > 100.0:
                    reason.append(f"市值{market_cap:.2f}亿>100亿")
                if not reason:
                    reason.append("可能排名不够前5")
                
                results.append({
                    '股票代码': stock_code,
                    '股票名称': stock_name,
                    '扫描日期': scan_date_str,
                    '匹配度': match_score,
                    '市值(亿)': market_cap_str,
                    '是否通过': '是' if passed else '否',
                    '原因': '; '.join(reason)
                })
                
                status = "✅" if passed else "❌"
                print(f"  {status} {stock_code} {stock_name}: 匹配度 {match_score:.3f}, 市值 {market_cap_str}亿")
                if not passed:
                    print(f"     原因: {'; '.join(reason)}")
                
            except Exception as e:
                print(f"  ⚠️ {stock_code} {stock_name}: 错误 - {str(e)[:100]}")
                results.append({
                    '股票代码': stock_code,
                    '股票名称': stock_name,
                    '扫描日期': scan_date_str,
                    '匹配度': 0,
                    '市值(亿)': 'N/A',
                    '原因': f'错误: {str(e)[:50]}'
                })
        
        print()
    
    # 保存结果
    if results:
        df = pd.DataFrame(results)
        csv_file = 'training_stocks_match_score_check.csv'
        df.to_csv(csv_file, index=False, encoding='utf-8-sig')
        print("=" * 80)
        print("📊 统计摘要")
        print("=" * 80)
        print()
        
        # 按股票统计
        for stock_code, stock_name in TRAINING_STOCKS.items():
            stock_data = df[df['股票代码'] == stock_code]
            passed_count = len(stock_data[stock_data['是否通过'] == '是'])
            total_count = len(stock_data)
            
            if total_count > 0:
                avg_match = stock_data['匹配度'].mean()
                max_match = stock_data['匹配度'].max()
                min_match = stock_data['匹配度'].min()
                
                print(f"{stock_code} {stock_name}:")
                print(f"  通过次数: {passed_count}/{total_count}")
                print(f"  匹配度: 平均 {avg_match:.3f}, 最高 {max_match:.3f}, 最低 {min_match:.3f}")
                
                # 显示市值信息
                market_caps = stock_data[stock_data['市值(亿)'] != 'N/A']['市值(亿)']
                if len(market_caps) > 0:
                    try:
                        caps = [float(x) for x in market_caps]
                        print(f"  市值: 平均 {sum(caps)/len(caps):.2f}亿, 最高 {max(caps):.2f}亿, 最低 {min(caps):.2f}亿")
                    except:
                        pass
                print()
        
        print(f"✅ 详细结果已保存到: {csv_file}")

if __name__ == '__main__':
    check_training_stocks_match_score()
