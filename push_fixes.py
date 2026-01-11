#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
推送修复到 GitHub
"""
import subprocess
import os
import sys

def run_command(cmd, cwd=None):
    """执行命令并返回输出"""
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=60
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "命令执行超时"
    except Exception as e:
        return -1, "", str(e)

def main():
    repo_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(repo_dir)
    
    print("=" * 60)
    print("推送修复到 GitHub")
    print("=" * 60)
    print(f"工作目录: {repo_dir}")
    print()
    
    # 1. 检查git状态
    print("1. 检查git状态...")
    code, stdout, stderr = run_command("git status --short")
    if code == 0:
        if stdout.strip():
            print(f"   发现未提交的更改:\n{stdout}")
        else:
            print("   ✅ 没有未提交的更改")
    
    # 2. 添加修改的文件
    print("\n2. 添加修改的文件...")
    files = [
        "templates/bull_stock_web.html",
        "vercel_scan_helper.py",
        "data_fetcher.py",
        "bull_stock_web.py",
        "bull_stock_analyzer.py",
        "煜邦电力诊断报告.md"
    ]
    
    for file in files:
        if os.path.exists(file):
            code, stdout, stderr = run_command(f"git add {file}")
            if code == 0:
                print(f"   ✅ 已添加: {file}")
            else:
                print(f"   ⚠️  添加失败: {file} - {stderr}")
        else:
            print(f"   ⚠️  文件不存在: {file}")
    
    # 3. 提交更改
    print("\n3. 提交更改...")
    commit_message = """修复网络版扫描问题：煜邦电力案例分析

主要修复：
1. 修复 vercel_scan_helper.py 中 get_weekly_kline 参数错误（weeks=100 -> period='2y'）
2. 添加超时机制（5秒）和详细日志，追踪数据获取失败原因
3. 修复股票代码格式处理，去除 .SZ/.SH 后缀
4. 修复匹配阈值默认值（VIP用户从0.97改为0.93）
5. 优化扫描结果提示，显示扫描总数和找到数量
6. 修复本地版本参数读取逻辑，优先检查本地环境
7. 优化 Vercel 环境超时设置和错误处理
8. 修复市值筛选功能，两个版本都正确实现市值筛选

特别针对煜邦电力（603597）添加详细日志，便于分析扫描失败原因"""
    
    code, stdout, stderr = run_command(f'git commit -m "{commit_message}"')
    if code == 0:
        print("   ✅ 已提交更改")
        if stdout.strip():
            print(f"   输出: {stdout}")
    else:
        if "nothing to commit" in stderr.lower() or "nothing to commit" in stdout.lower():
            print("   ⚠️  没有需要提交的更改")
        else:
            print(f"   ⚠️  提交失败: {stderr}")
            print(f"   输出: {stdout}")
    
    # 4. 获取当前分支
    print("\n4. 获取当前分支...")
    code, stdout, stderr = run_command("git branch --show-current")
    if code == 0:
        current_branch = stdout.strip()
        print(f"   当前分支: {current_branch}")
    else:
        print(f"   ⚠️  获取分支失败，使用默认分支 'main'")
        current_branch = "main"
    
    # 5. 推送到 GitHub
    print(f"\n5. 推送分支 {current_branch} 到GitHub...")
    code, stdout, stderr = run_command(f"git push origin {current_branch}")
    if code == 0:
        print(f"   ✅ 已推送分支 {current_branch}")
        if stdout.strip():
            print(f"   输出: {stdout}")
    else:
        print(f"   ❌ 推送失败")
        print(f"   错误: {stderr}")
        print(f"   输出: {stdout}")
        print("\n   可能的原因:")
        print("   1. 需要配置GitHub认证（Personal Access Token或SSH密钥）")
        print("   2. 网络连接问题")
        print("   3. 权限不足")
        print("   4. 需要先拉取远程更改")
        return
    
    print("\n" + "=" * 60)
    print("✅ 推送完成！")
    print("=" * 60)
    print(f"\nGitHub仓库: https://github.com/jet20002025-hash/daniugu")
    print(f"分支: {current_branch}")
    print("\nVercel 将自动检测 main 分支的更新并重新部署")

if __name__ == "__main__":
    main()



