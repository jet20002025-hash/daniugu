#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
使用模型11进行回测验证
"""
from model_validator import ModelValidator
from datetime import datetime, timedelta
import os

def main():
    """主函数"""
    print("=" * 80)
    print("模型11回测验证")
    print("=" * 80)
    print()
    
    # 模型文件路径
    model_path = 'models/模型11.json'
    
    if not os.path.exists(model_path):
        print(f"❌ 模型文件不存在: {model_path}")
        return
    
    print(f"📁 模型文件: {model_path}")
    print()
    
    # 创建验证器并加载模型
    validator = ModelValidator(model_path=model_path)
    
    if not validator.analyzer.trained_features:
        print("❌ 模型加载失败")
        return
    
    # 设置回测参数
    print("📊 回测参数设置:")
    print("  - 时间范围: 2025-01-01 至 2025-12-31")
    print("  - 扫描模式: 每周扫描一次")
    print("  - 最小匹配度: 0.83")
    print("  - 最大流通市值: 100 亿元")
    print("  - 每周选择: 匹配度最高的5只股票")
    print("  - 收益周期: 1周、4周、8周、12周、20周")
    print("  - 数据来源: 优先从缓存获取（加快速度）")
    print()
    
    # 回测时间范围：2025年
    start_date = '2025-01-01'
    end_date = '2025-12-31'
    
    # 运行回测
    print("🚀 开始回测...")
    print("   这可能需要较长时间，请耐心等待...")
    print()
    
    try:
        result = validator.validate_backtest(
            start_date=start_date,
            end_date=end_date,
            min_match_score=0.83,
            max_market_cap=100.0,
            scan_mode='weekly',  # 每周扫描一次，加快速度
            max_stocks_per_day=5,  # 每周选择匹配度最高的5只股票
            periods=[7, 28, 56, 84, 140],  # 1周、4周、8周、12周、20周
            limit=None,  # 全市场扫描
            use_parallel=True,
            max_workers=10,
            save_report=True,
            output_dir='.',
            report_prefix='backtest_model11'
        )
        
        print()
        print("=" * 80)
        print("✅ 回测完成！")
        print("=" * 80)
        
        # 显示简要结果
        if result.get('success'):
            stats = result.get('statistics', {})
            print(f"\n📊 回测统计:")
            print(f"  总扫描次数: {stats.get('total_trades', 0)}")
            print(f"  有效交易数: {stats.get('valid_trades', 0)}")
            
            # 显示各周期收益
            for period_key in ['1周', '4周', '8周', '12周', '20周']:
                if period_key in stats:
                    period_stats = stats[period_key]
                    avg_return = period_stats.get('average_return', 0)
                    win_rate = period_stats.get('win_rate', 0)
                    print(f"  {period_key}收益: 平均 {avg_return:.2f}%, 胜率 {win_rate:.1f}%")
            
            print(f"\n📄 详细报告已保存到:")
            print(f"  - {result.get('text_report_path', 'N/A')}")
            print(f"  - {result.get('json_report_path', 'N/A')}")
        else:
            print(f"❌ 回测失败: {result.get('message', '未知错误')}")
            
    except KeyboardInterrupt:
        print("\n⚠️ 用户中断回测")
    except Exception as e:
        print(f"\n❌ 回测过程出错: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
