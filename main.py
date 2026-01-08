"""
A股量价分析选股软件 - 主程序
"""
from stock_screener import StockScreener
import time
import argparse
import sys


def main():
    """主函数"""
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='A股量价分析选股软件')
    parser.add_argument('--test', '-t', action='store_true', help='测试模式（仅分析前50只股票）')
    parser.add_argument('--all', '-a', action='store_true', help='分析全部A股（约5000只）')
    parser.add_argument('--limit', '-l', type=int, default=None, help='限制分析股票数量')
    parser.add_argument('--export', '-e', type=str, default=None, help='自动导出结果到Excel文件')
    parser.add_argument('--no-export', action='store_true', help='不询问是否导出，直接跳过')
    
    args = parser.parse_args()
    
    print("=" * 80)
    print("A股量价分析选股软件")
    print("=" * 80)
    print("\n选股条件：")
    print("1. 过去一年内出现过历史最大成交量")
    print("2. 股价持续运行在年线（250日均线）之上，重心稳步上移")
    print("3. 找到启动价（连续下跌不超过2个月，不跌破20月均线，月线反转）")
    print("4. 当前价在启动价±3%范围内，且不跌破反转日最低价")
    print("5. 最近一个交易日成交量 ≥ 上一个交易日的2倍")
    print("6. 最近10个交易日内出现过涨停")
    print("7. 过去一年内有最大月成交量")
    print("8. 月线级别股价稳步上升")
    print("\n" + "=" * 80)
    
    # 创建选股器
    screener = StockScreener()
    
    # 确定分析数量限制
    if args.all:
        limit = None
        print("\n完整分析模式：将分析全部A股（约5000只）")
        print("预计耗时：2-4小时")
    elif args.limit:
        limit = args.limit
        print(f"\n限制分析数量: {limit} 只股票")
    elif args.test:
        limit = 50
        print("\n测试模式：仅分析前50只股票")
    else:
        # 交互式询问（如果是在交互式终端）
        if sys.stdin.isatty():
            print("\n提示：完整分析所有A股需要较长时间，建议先测试少量股票")
            try:
                test_mode = input("是否进入测试模式（仅分析前50只股票）？(y/n): ").strip().lower()
                limit = 50 if test_mode == 'y' else None
            except (EOFError, KeyboardInterrupt):
                print("\n使用默认测试模式（50只股票）")
                limit = 50
        else:
            # 非交互式环境，默认分析全部
            print("\n非交互式环境，将分析全部A股")
            limit = None
    
    # 开始选股
    start_time = time.time()
    results = screener.screen_all_stocks(limit=limit, exclude_st=True, save_interval=100)
    end_time = time.time()
    
    # 显示结果
    if results:
        print("\n符合条件的股票：")
        print("-" * 80)
        for i, result in enumerate(results, 1):
            print(f"\n{i}. {result['股票代码']} {result['股票名称']}")
            print(f"   当前价格: {result['当前价格']:.2f}")
            if result['启动价']:
                print(f"   启动价: {result['启动价']:.2f}")
                print(f"   反转日期: {result['反转日期']}")
            if result['涨停日期']:
                print(f"   涨停日期: {result['涨停日期']}")
            print(f"   历史最大量日期: {result['历史最大量日期']}")
            print(f"   月成交量最大日期: {result['月成交量最大日期']}")
        
        # 导出结果
        if args.export:
            # 命令行指定了导出文件
            screener.export_results(args.export)
        elif not args.no_export:
            # 交互式询问（如果是在交互式终端）
            if sys.stdin.isatty():
                try:
                    export = input("\n是否导出结果到Excel？(y/n): ").strip().lower()
                    if export == 'y':
                        filename = input("请输入文件名（默认：选股结果.xlsx）: ").strip()
                        if not filename:
                            filename = '选股结果.xlsx'
                        screener.export_results(filename)
                except (EOFError, KeyboardInterrupt):
                    print("\n跳过导出")
            else:
                # 非交互式环境，自动导出
                filename = args.export if args.export else '选股结果.xlsx'
                screener.export_results(filename)
    else:
        print("\n未找到符合条件的股票")
    
    print(f"\n总耗时: {end_time - start_time:.2f} 秒")
    print("=" * 80)


if __name__ == "__main__":
    main()

