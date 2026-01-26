#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
显示扫描结果：使用模型23扫描所有股票的结果
匹配度阈值: 0.93
市值限制: ≤ 100亿
"""
import json
import os
from datetime import datetime

def main():
    # 查找最新的结果文件
    result_files = [f for f in os.listdir('.') if f.startswith('scan_result_model23_') and f.endswith('.json')]
    if not result_files:
        print("❌ 未找到扫描结果文件")
        return
    
    # 按修改时间排序，获取最新的
    result_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
    latest_file = result_files[0]
    
    print("=" * 80)
    print(f"显示扫描结果: {latest_file}")
    print("=" * 80)
    
    with open(latest_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    candidates = data.get('candidates', [])
    total_scanned = data.get('total_scanned', 0)
    found_count = data.get('found_count', 0)
    
    print(f"\n📊 扫描统计:")
    print(f"   - 总扫描股票数: {total_scanned}")
    print(f"   - 找到符合条件的股票: {found_count} 只")
    print(f"   - 返回的候选股票数: {len(candidates)} 只")
    print()
    
    # 统计市值情况
    none_count = sum(1 for s in candidates if s.get('市值') is None)
    valid_count = sum(1 for s in candidates if s.get('市值') is not None and s.get('市值', 0) > 0)
    over_limit_count = sum(1 for s in candidates if s.get('市值') is not None and s.get('市值', 0) > 100.0)
    under_limit_count = sum(1 for s in candidates if s.get('市值') is not None and 0 < s.get('市值', 0) <= 100.0)
    
    print(f"📈 市值统计:")
    print(f"   - 市值未知(None): {none_count} 只")
    print(f"   - 市值有效: {valid_count} 只")
    print(f"   - 市值≤100亿: {under_limit_count} 只")
    print(f"   - 市值>100亿: {over_limit_count} 只")
    print()
    
    if found_count > 0:
        print("=" * 80)
        print("符合条件的股票列表:")
        print("=" * 80)
        print(f"{'序号':<6} {'股票代码':<12} {'股票名称':<20} {'匹配度':<10} {'市值(亿)':<12} {'买点日期':<15}")
        print("-" * 80)
        
        # 按匹配度排序
        sorted_candidates = sorted(candidates, key=lambda x: x.get('匹配度', 0), reverse=True)
        
        for idx, stock in enumerate(sorted_candidates, 1):
            code = stock.get('股票代码', 'N/A')
            name = stock.get('股票名称', 'N/A')
            match_score = stock.get('匹配度', 0)
            market_cap = stock.get('市值', None)
            buy_point = stock.get('买点日期', 'N/A')
            
            if market_cap is not None and market_cap > 0:
                market_cap_str = f"{market_cap:.2f}"
                # 如果市值超过100亿，标记
                if market_cap > 100.0:
                    market_cap_str = f"{market_cap:.2f} ⚠️"
            else:
                market_cap_str = "未知"
            
            match_score_str = f"{match_score:.3f}"
            
            print(f"{idx:<6} {code:<12} {name:<20} {match_score_str:<10} {market_cap_str:<12} {buy_point}")
        
        print("=" * 80)
        print(f"\n✅ 共显示 {len(sorted_candidates)} 只符合条件的股票")
    else:
        print("⚠️ 未找到符合条件的股票")

if __name__ == '__main__':
    main()
