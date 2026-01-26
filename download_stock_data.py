#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
在 Render 环境中下载并解压股票数据
"""
import os
import sys
import json
import tarfile
import requests
from pathlib import Path

# 配置
DATA_PACKAGE_URL = os.environ.get('STOCK_DATA_URL', '')
CACHE_DIR = 'cache'
STOCK_DATA_DIR = 'stock_data'

def download_file(url, local_path, chunk_size=8192):
    """下载文件"""
    print(f"📥 正在下载: {url}")
    print(f"   保存到: {local_path}")
    
    try:
        response = requests.get(url, stream=True, timeout=300)
        response.raise_for_status()
        
        total_size = int(response.headers.get('content-length', 0))
        downloaded = 0
        
        with open(local_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=chunk_size):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        percent = (downloaded / total_size) * 100
                        print(f"\r   进度: {percent:.1f}% ({downloaded / (1024*1024):.1f} MB / {total_size / (1024*1024):.1f} MB)", end='', flush=True)
        
        print("\n✅ 下载完成")
        return True
    except Exception as e:
        print(f"\n❌ 下载失败: {e}")
        return False

def extract_package(package_path):
    """解压数据包"""
    print(f"\n📦 正在解压: {package_path}")
    
    try:
        with tarfile.open(package_path, 'r:gz') as tar:
            # 获取文件列表
            members = tar.getmembers()
            print(f"   包含 {len(members)} 个文件/目录")
            
            # 解压
            tar.extractall('.')
        
        print("✅ 解压完成")
        return True
    except Exception as e:
        print(f"❌ 解压失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def check_data_exists():
    """检查数据是否已存在"""
    cache_exists = os.path.exists(CACHE_DIR) and os.listdir(CACHE_DIR)
    stock_exists = os.path.exists(STOCK_DATA_DIR) and os.listdir(STOCK_DATA_DIR)
    
    if cache_exists:
        cache_files = sum(len(files) for _, _, files in os.walk(CACHE_DIR))
        print(f"✅ cache 目录已存在: {cache_files} 个文件")
    else:
        print(f"⚠️  cache 目录不存在或为空")
    
    if stock_exists:
        stock_files = sum(len(files) for _, _, files in os.walk(STOCK_DATA_DIR))
        print(f"✅ stock_data 目录已存在: {stock_files} 个文件")
    else:
        print(f"⚠️  stock_data 目录不存在或为空")
    
    return cache_exists or stock_exists

def main():
    """主函数"""
    print("=" * 60)
    print("📥 Render 数据下载工具")
    print("=" * 60)
    
    # 检查数据是否已存在
    if check_data_exists():
        print("\n✅ 数据已存在，跳过下载")
        return
    
    # 检查是否有下载 URL
    if not DATA_PACKAGE_URL:
        print("\n⚠️  未设置 STOCK_DATA_URL 环境变量")
        print("   数据将从网络实时获取（较慢）")
        return
    
    # 下载数据包
    package_name = 'stock_data.tar.gz'
    if download_file(DATA_PACKAGE_URL, package_name):
        # 解压
        if extract_package(package_name):
            # 删除压缩包（节省空间）
            try:
                os.remove(package_name)
                print(f"✅ 已删除压缩包: {package_name}")
            except:
                pass
            
            # 验证数据
            if check_data_exists():
                print("\n✅ 数据下载并解压成功！")
            else:
                print("\n⚠️  数据解压后验证失败")
        else:
            print("\n❌ 解压失败")
    else:
        print("\n❌ 下载失败，将使用网络实时获取数据")

if __name__ == '__main__':
    main()
