#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 training_stocks_buy_points_list.json 导出为 Excel/CSV。"""

import json
import os
from datetime import datetime

import pandas as pd


def main():
    src = 'training_stocks_buy_points_list.json'
    if not os.path.exists(src):
        raise SystemExit(f"❌ 未找到 {src}，请先生成买点列表")

    with open(src, 'r', encoding='utf-8') as f:
        data = json.load(f)

    rows = data.get('结果', [])
    if not rows:
        raise SystemExit('❌ JSON里没有结果可导出')

    df = pd.DataFrame(rows)

    # 列顺序（更像报表）
    preferred_cols = [
        '股票代码', '股票名称',
        '最佳买点日期', '最佳买点价格',
        '匹配度', '核心特征匹配度',
        '涨幅', '周数',
        '盈利筹码比例', '90%成本集中度'
    ]
    cols = [c for c in preferred_cols if c in df.columns] + [c for c in df.columns if c not in preferred_cols]
    df = df[cols]

    # 排序：匹配度降序
    if '匹配度' in df.columns:
        df = df.sort_values(by='匹配度', ascending=False)

    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    xlsx = f'training_stocks_buy_points_{ts}.xlsx'
    csv = f'training_stocks_buy_points_{ts}.csv'

    # Excel
    with pd.ExcelWriter(xlsx, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='训练股买点', index=False)
        ws = writer.sheets['训练股买点']

        # 简单美化：冻结首行，自动列宽
        ws.freeze_panes = 'A2'
        for col_cells in ws.columns:
            max_len = 0
            col_letter = col_cells[0].column_letter
            for cell in col_cells:
                v = cell.value
                if v is None:
                    continue
                max_len = max(max_len, len(str(v)))
            ws.column_dimensions[col_letter].width = min(max(10, max_len + 2), 40)

    # CSV（备份）
    df.to_csv(csv, index=False, encoding='utf-8-sig')

    print('✅ 已导出:')
    print('  -', xlsx)
    print('  -', csv)


if __name__ == '__main__':
    main()
