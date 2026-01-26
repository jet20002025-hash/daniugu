#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
删除股票数量为0的模型文件
"""
import os
import json
import sys

def check_and_delete_zero_stock_models():
    """检查并删除股票数量为0的模型"""
    project_root = os.path.dirname(os.path.abspath(__file__))
    deleted_files = []
    kept_files = []
    
    print("="*80)
    print("检查模型文件，删除股票数量为0的模型")
    print("="*80)
    
    # 查找所有 trained_model*.json 文件
    for filename in os.listdir(project_root):
        if filename.startswith('trained_model') and filename.endswith('.json'):
            filepath = os.path.join(project_root, filename)
            try:
                # 读取模型文件
                with open(filepath, 'r', encoding='utf-8') as f:
                    model_data = json.load(f)
                
                # 检查股票数量
                bull_stocks = model_data.get('bull_stocks', [])
                stock_count = len(bull_stocks)
                
                # 如果股票数为0，直接删除
                if stock_count == 0:
                    # 获取其他信息用于日志
                    sample_count = model_data.get('sample_count', 0)
                    buy_features = model_data.get('buy_features', {})
                    common_features = buy_features.get('common_features', {})
                    feature_count = len(common_features)
                    
                    print(f"❌ {filename}: 股票数=0 (样本数={sample_count}, 特征数={feature_count}) - 删除")
                    os.remove(filepath)
                    deleted_files.append(filename)
                else:
                    print(f"✅ {filename}: 股票数={stock_count} - 保留")
                    kept_files.append((filename, f"股票数={stock_count}"))
                    
            except Exception as e:
                print(f"⚠️  {filename}: 读取失败 - {e} - 保留（可能是格式问题）")
                kept_files.append((filename, f"读取失败: {str(e)}"))
    
    print("\n" + "="*80)
    print("删除结果统计")
    print("="*80)
    print(f"删除文件数: {len(deleted_files)}")
    print(f"保留文件数: {len(kept_files)}")
    
    if deleted_files:
        print("\n已删除的文件:")
        for f in deleted_files:
            print(f"  - {f}")
    
    if kept_files:
        print("\n保留的文件:")
        for f, reason in kept_files:
            print(f"  - {f} ({reason})")
    
    print("\n" + "="*80)
    print("完成")
    print("="*80)

if __name__ == '__main__':
    try:
        check_and_delete_zero_stock_models()
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
