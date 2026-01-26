#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""查询恒宝股份(002104)在最新模型、近5年数据下的最高匹配度"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bull_stock_analyzer import BullStockAnalyzer

def main():
    analyzer = BullStockAnalyzer(auto_load_default_stocks=False, auto_analyze_and_train=False)
    if not analyzer.load_model('trained_model.json', skip_network=True):
        print('加载 trained_model.json 失败')
        return
    
    code, name = '002104', '恒宝股份'
    # 近5年，匹配度阈值设为0，返回所有买点以便取最高匹配度
    result = analyzer.find_buy_points(
        code,
        tolerance=0.3,
        search_years=5,
        match_threshold=0.0
    )
    
    if not result.get('success') or not result.get('buy_points'):
        print(f'{name}({code}) 近5年未找到买点，或查询失败: {result.get("message", "未知")}')
        return
    
    pts = result['buy_points']
    max_match = max(p['匹配度'] for p in pts)
    best = next(p for p in pts if p['匹配度'] == max_match)
    
    print(f'恒宝股份(002104) | 最新模型 | 近5年')
    print(f'最高匹配度: {max_match:.3f}')
    print(f'对应买点: 日期 {best["日期"]}, 价格 {best["价格"]}')

if __name__ == '__main__':
    main()
