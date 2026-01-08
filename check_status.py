#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查系统运行状态
"""
import requests
import json
import sys

def check_status():
    """检查系统运行状态"""
    print("=" * 80)
    print("🔍 系统运行状态检查")
    print("=" * 80)
    print()
    
    # 1. 检查Web服务
    print("1️⃣  Web服务状态:")
    try:
        response = requests.get("http://localhost:5002/api/get_stocks", timeout=3)
        if response.status_code == 200:
            data = response.json()
            stock_count = data.get('count', 0)
            print(f"   ✅ 服务正在运行")
            print(f"   📊 已加载股票数: {stock_count}")
            print(f"   🌐 访问地址: http://localhost:5002")
        else:
            print(f"   ⚠️  服务响应异常 (状态码: {response.status_code})")
    except requests.exceptions.ConnectionError:
        print("   ❌ 服务未运行（无法连接）")
        print("   💡 提示: 运行 './restart_service.sh' 启动服务")
    except Exception as e:
        print(f"   ❌ 检查失败: {e}")
    
    print()
    
    # 2. 检查特征模型
    print("2️⃣  特征模型状态:")
    try:
        response = requests.get("http://localhost:5002/api/get_features", timeout=3)
        if response.status_code == 200:
            data = response.json()
            if data.get('success') and data.get('features'):
                feature_count = len(data.get('features', {}).get('common_features', {}))
                print(f"   ✅ 特征模型已训练")
                print(f"   📊 特征数量: {feature_count}")
            else:
                print("   ⚠️  特征模型未训练")
                print("   💡 提示: 需要先添加大牛股、分析股票并训练特征模型")
        else:
            print("   ⚠️  无法获取特征模型信息")
    except Exception as e:
        print(f"   ⚠️  检查特征模型失败: {e}")
    
    print()
    
    # 3. 检查大牛股列表
    print("3️⃣  大牛股列表:")
    try:
        response = requests.get("http://localhost:5002/api/get_stocks", timeout=3)
        if response.status_code == 200:
            data = response.json()
            stocks = data.get('stocks', [])
            if stocks:
                print(f"   ✅ 已加载 {len(stocks)} 只大牛股:")
                for i, stock in enumerate(stocks[:5], 1):
                    code = stock.get('代码', 'N/A')
                    name = stock.get('名称', 'N/A')
                    print(f"      {i}. {code} {name}")
                if len(stocks) > 5:
                    print(f"      ... 还有 {len(stocks) - 5} 只")
            else:
                print("   ⚠️  大牛股列表为空")
                print("   💡 提示: 需要先添加大牛股")
    except Exception as e:
        print(f"   ⚠️  检查失败: {e}")
    
    print()
    print("=" * 80)
    print("💡 使用说明:")
    print("   - Web界面: http://localhost:5002")
    print("   - 启动服务: ./restart_service.sh")
    print("   - 停止服务: pkill -f 'python.*bull_stock_web'")
    print("=" * 80)

if __name__ == '__main__':
    check_status()





