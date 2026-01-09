#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查 Vercel 部署版本是否是最新的
"""

import subprocess
import json
import sys
import os

def run_command(cmd):
    """执行命令并返回结果"""
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            cwd=os.path.dirname(os.path.abspath(__file__))
        )
        return result.returncode == 0, result.stdout.strip(), result.stderr.strip()
    except Exception as e:
        return False, "", str(e)

def get_latest_github_commit():
    """获取 GitHub 最新 commit"""
    print("📦 正在获取 GitHub 最新提交...")
    success, output, error = run_command("git log --oneline -1")
    if not success:
        print(f"❌ 获取 GitHub 提交失败: {error}")
        return None
    
    # 获取完整 commit SHA
    success, sha, _ = run_command("git rev-parse HEAD")
    if not success:
        return None
    
    # 获取 commit 信息
    success, message, _ = run_command("git log -1 --pretty=format:'%s'")
    if not success:
        message = output.split(' ', 1)[1] if ' ' in output else output
    
    return {
        'sha': sha,
        'short_sha': sha[:7],
        'message': message,
        'output': output
    }

def check_vercel_deployment():
    """检查 Vercel 部署信息"""
    print("\n🌐 检查 Vercel 部署版本的方法：")
    print("=" * 60)
    
    print("\n方法 1: 通过 Vercel Dashboard 查看")
    print("-" * 60)
    print("1. 访问 https://vercel.com/dashboard")
    print("2. 选择你的项目")
    print("3. 进入 'Deployments' 标签页")
    print("4. 查看最新部署的 commit SHA")
    print("5. 对比 GitHub 上的最新 commit")
    
    print("\n方法 2: 通过 Vercel CLI 查看（需要安装 Vercel CLI）")
    print("-" * 60)
    print("安装: npm install -g vercel")
    print("登录: vercel login")
    print("查看: vercel ls")
    print("详情: vercel inspect <deployment-url>")
    
    print("\n方法 3: 通过 API 查询（需要 Vercel Token）")
    print("-" * 60)
    print("1. 在 Vercel Dashboard → Settings → Tokens 创建 token")
    print("2. 使用以下命令查询：")
    print("   curl -H 'Authorization: Bearer YOUR_TOKEN' \\")
    print("        https://api.vercel.com/v6/deployments")
    
    print("\n方法 4: 在网页上显示版本信息（推荐）")
    print("-" * 60)
    print("可以在网页底部或控制台显示当前部署的 commit SHA")
    print("这样可以直接在浏览器中查看版本信息")

def main():
    print("=" * 60)
    print("🔍 Vercel 部署版本检查工具")
    print("=" * 60)
    
    # 获取 GitHub 最新 commit
    github_commit = get_latest_github_commit()
    
    if github_commit:
        print(f"\n✅ GitHub 最新提交:")
        print(f"   Commit SHA: {github_commit['sha']}")
        print(f"   简短 SHA: {github_commit['short_sha']}")
        print(f"   提交信息: {github_commit['message']}")
        print(f"   完整信息: {github_commit['output']}")
    else:
        print("\n❌ 无法获取 GitHub 提交信息")
        return
    
    # 检查 Vercel 部署
    check_vercel_deployment()
    
    print("\n" + "=" * 60)
    print("📝 对比步骤：")
    print("=" * 60)
    print(f"1. 在 Vercel Dashboard 查看最新部署的 commit SHA")
    print(f"2. 对比上面的 GitHub commit SHA: {github_commit['short_sha']}")
    print(f"3. 如果 SHA 一致，说明已部署最新版本")
    print(f"4. 如果 SHA 不一致，需要等待自动部署或手动触发部署")
    
    print("\n💡 提示：")
    print("- Vercel 会在你推送代码到 GitHub 后自动部署")
    print("- 如果自动部署失败，可以在 Vercel Dashboard 手动触发")
    print("- 部署通常需要 2-5 分钟完成")

if __name__ == "__main__":
    main()

