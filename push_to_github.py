#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
推送代码到GitHub
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
            timeout=30
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "命令执行超时"
    except Exception as e:
        return -1, "", str(e)

def main():
    repo_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(repo_dir)
    
    print("=" * 50)
    print("推送代码到GitHub")
    print("=" * 50)
    print(f"工作目录: {repo_dir}")
    print()
    
    # 1. 检查git状态
    print("1. 检查git状态...")
    code, stdout, stderr = run_command("git status --short")
    if code == 0:
        if stdout.strip():
            print(f"   发现未提交的更改:\n{stdout}")
            print("\n2. 添加所有更改...")
            code, _, _ = run_command("git add -A")
            if code == 0:
                print("   ✅ 已添加所有更改")
                print("\n3. 提交更改...")
                code, _, _ = run_command(
                    'git commit -m "完成功能按钮按环境和用户等级显示：本地版显示所有功能，网络版免费用户只能查看结果，VIP用户每天只能扫描一次"'
                )
                if code == 0:
                    print("   ✅ 已提交更改")
                else:
                    print("   ⚠️  提交失败或没有新更改")
            else:
                print("   ❌ 添加更改失败")
        else:
            print("   ✅ 没有未提交的更改")
    else:
        print(f"   ❌ 检查状态失败: {stderr}")
        return
    
    # 2. 获取当前分支
    print("\n4. 获取当前分支...")
    code, stdout, stderr = run_command("git branch --show-current")
    if code == 0:
        current_branch = stdout.strip()
        print(f"   当前分支: {current_branch}")
    else:
        print(f"   ❌ 获取分支失败: {stderr}")
        return
    
    # 3. 推送分支
    print(f"\n5. 推送分支 {current_branch} 到GitHub...")
    code, stdout, stderr = run_command(f"git push origin {current_branch}")
    if code == 0:
        print(f"   ✅ 已推送分支 {current_branch}")
        print(f"\n   输出: {stdout}")
    else:
        print(f"   ❌ 推送失败")
        print(f"   错误: {stderr}")
        print(f"   输出: {stdout}")
        print("\n   可能的原因:")
        print("   1. 需要配置GitHub认证（Personal Access Token或SSH密钥）")
        print("   2. 网络连接问题")
        print("   3. 权限不足")
        return
    
    # 4. 询问是否合并到main
    if current_branch != "main":
        print(f"\n6. 是否合并到main分支？")
        print("   提示: 如果需要合并到main分支，请手动执行:")
        print(f"   git checkout main")
        print(f"   git merge {current_branch}")
        print(f"   git push origin main")
    
    print("\n" + "=" * 50)
    print("✅ 推送完成！")
    print("=" * 50)
    print(f"\nGitHub仓库: https://github.com/jet20002025-hash/daniugu")
    print(f"分支: {current_branch}")

if __name__ == "__main__":
    main()

