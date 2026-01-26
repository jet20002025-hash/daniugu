#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
上传本地股票数据到外部存储
支持多种存储方案：GitHub Releases、AWS S3、Google Cloud Storage等
"""
import os
import sys
import json
import tarfile
import gzip
from pathlib import Path
from datetime import datetime

# 配置
CACHE_DIR = 'cache'
STOCK_DATA_DIR = 'stock_data'
UPLOAD_CONFIG_FILE = 'upload_config.json'

def get_data_size_mb(directory):
    """获取目录大小（MB）"""
    total_size = 0
    file_count = 0
    for dirpath, dirnames, filenames in os.walk(directory):
        for filename in filenames:
            filepath = os.path.join(dirpath, filename)
            if os.path.exists(filepath):
                total_size += os.path.getsize(filepath)
                file_count += 1
    return total_size / (1024 * 1024), file_count

def create_upload_package():
    """创建上传包"""
    print("=" * 60)
    print("📦 创建数据上传包")
    print("=" * 60)
    
    # 检查目录是否存在
    if not os.path.exists(CACHE_DIR):
        print(f"❌ 目录不存在: {CACHE_DIR}")
        return None
    
    if not os.path.exists(STOCK_DATA_DIR):
        print(f"⚠️  目录不存在: {STOCK_DATA_DIR}，跳过")
        stock_data_exists = False
    else:
        stock_data_exists = True
    
    # 获取数据大小
    cache_size_mb, cache_files = get_data_size_mb(CACHE_DIR)
    print(f"📊 cache 目录: {cache_size_mb:.2f} MB, {cache_files} 个文件")
    
    if stock_data_exists:
        stock_size_mb, stock_files = get_data_size_mb(STOCK_DATA_DIR)
        print(f"📊 stock_data 目录: {stock_size_mb:.2f} MB, {stock_files} 个文件")
        total_size_mb = cache_size_mb + stock_size_mb
        total_files = cache_files + stock_files
    else:
        total_size_mb = cache_size_mb
        total_files = cache_files
    
    print(f"📊 总计: {total_size_mb:.2f} MB, {total_files} 个文件")
    
    # 创建压缩包
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    package_name = f'stock_data_{timestamp}.tar.gz'
    
    print(f"\n📦 正在创建压缩包: {package_name}")
    print("   这可能需要几分钟时间...")
    
    try:
        with tarfile.open(package_name, 'w:gz') as tar:
            # 添加 cache 目录
            print("   添加 cache 目录...")
            tar.add(CACHE_DIR, arcname='cache', filter=lambda info: info if info.size < 100 * 1024 * 1024 else None)  # 跳过大于100MB的文件
            
            # 添加 stock_data 目录（如果存在）
            if stock_data_exists:
                print("   添加 stock_data 目录...")
                tar.add(STOCK_DATA_DIR, arcname='stock_data', filter=lambda info: info if info.size < 100 * 1024 * 1024 else None)
        
        package_size_mb = os.path.getsize(package_name) / (1024 * 1024)
        print(f"✅ 压缩包创建成功: {package_name}")
        print(f"   压缩后大小: {package_size_mb:.2f} MB")
        print(f"   压缩率: {(1 - package_size_mb / total_size_mb) * 100:.1f}%")
        
        return package_name
    except Exception as e:
        print(f"❌ 创建压缩包失败: {e}")
        import traceback
        traceback.print_exc()
        return None

def upload_to_github_release(package_name, github_token=None, repo=None):
    """上传到 GitHub Releases（需要安装 PyGithub）"""
    try:
        from github import Github
    except ImportError:
        print("❌ 需要安装 PyGithub: pip install PyGithub")
        return False
    
    if not github_token:
        github_token = os.environ.get('GITHUB_TOKEN')
    
    if not github_token:
        print("❌ 需要设置 GITHUB_TOKEN 环境变量")
        return False
    
    if not repo:
        repo = os.environ.get('GITHUB_REPO', 'jet20002025-hash/daniugu')
    
    try:
        g = Github(github_token)
        repo_obj = g.get_repo(repo)
        
        # 创建或获取 release
        tag_name = f"data-{datetime.now().strftime('%Y%m%d')}"
        try:
            release = repo_obj.get_release(tag_name)
            print(f"📌 使用现有 Release: {tag_name}")
        except:
            release = repo_obj.create_git_release(
                tag=tag_name,
                name=f"股票数据包 - {datetime.now().strftime('%Y-%m-%d')}",
                message=f"自动上传的股票数据包\n上传时间: {datetime.now().isoformat()}\n文件: {package_name}",
                draft=False,
                prerelease=False
            )
            print(f"✅ 创建新 Release: {tag_name}")
        
        # 上传文件
        print(f"📤 正在上传 {package_name} 到 GitHub Releases...")
        with open(package_name, 'rb') as f:
            release.upload_asset(
                path=package_name,
                label=package_name,
                content_type='application/gzip'
            )
        
        print(f"✅ 上传成功！")
        print(f"   Release URL: {release.html_url}")
        return True
    except Exception as e:
        print(f"❌ 上传到 GitHub Releases 失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def save_upload_info(package_name, upload_method='manual'):
    """保存上传信息"""
    info = {
        'package_name': package_name,
        'upload_time': datetime.now().isoformat(),
        'upload_method': upload_method,
        'package_size_mb': os.path.getsize(package_name) / (1024 * 1024) if os.path.exists(package_name) else 0
    }
    
    with open(UPLOAD_CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(info, f, ensure_ascii=False, indent=2)
    
    print(f"✅ 上传信息已保存到: {UPLOAD_CONFIG_FILE}")

def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("🚀 股票数据上传工具")
    print("=" * 60 + "\n")
    
    # 创建压缩包
    package_name = create_upload_package()
    if not package_name:
        print("\n❌ 创建压缩包失败，退出")
        sys.exit(1)
    
    # 保存上传信息
    save_upload_info(package_name)
    
    # 询问上传方式
    print("\n" + "=" * 60)
    print("📤 上传选项")
    print("=" * 60)
    print("1. GitHub Releases（需要 GITHUB_TOKEN）")
    print("2. 手动上传（稍后手动上传压缩包）")
    print("3. 跳过上传（仅创建压缩包）")
    
    choice = input("\n请选择上传方式 (1/2/3，默认3): ").strip() or '3'
    
    if choice == '1':
        # 上传到 GitHub Releases
        github_token = os.environ.get('GITHUB_TOKEN') or input("请输入 GitHub Token: ").strip()
        if github_token:
            upload_to_github_release(package_name, github_token)
        else:
            print("❌ 未提供 GitHub Token，跳过上传")
    elif choice == '2':
        print(f"\n✅ 压缩包已创建: {package_name}")
        print("   请手动上传到云存储服务（如：")
        print("   - GitHub Releases")
        print("   - AWS S3")
        print("   - Google Cloud Storage")
        print("   - 阿里云 OSS")
        print("   - 其他云存储服务")
    else:
        print(f"\n✅ 压缩包已创建: {package_name}")
        print("   可以稍后手动上传")
    
    print("\n" + "=" * 60)
    print("✅ 完成！")
    print("=" * 60)
    print(f"📦 压缩包: {package_name}")
    print(f"📊 大小: {os.path.getsize(package_name) / (1024 * 1024):.2f} MB")
    print(f"📝 上传信息: {UPLOAD_CONFIG_FILE}")

if __name__ == '__main__':
    main()
