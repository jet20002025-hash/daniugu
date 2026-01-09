#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自动推送网络版代码到GitHub
"""
import subprocess
import os
import sys

def run_command(cmd, cwd=None, check=True):
    """执行命令并返回结果"""
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=60
        )
        if check and result.returncode != 0:
            print(f"❌ 命令失败: {cmd}")
            print(f"   错误: {result.stderr}")
            return False, result.stdout, result.stderr
        return True, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        print(f"⏱️  命令超时: {cmd}")
        return False, "", "命令执行超时"
    except Exception as e:
        print(f"❌ 执行命令出错: {e}")
        return False, "", str(e)

def main():
    repo_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(repo_dir)
    
    print("=" * 60)
    print("自动推送网络版代码到GitHub")
    print("=" * 60)
    print(f"工作目录: {repo_dir}")
    print()
    
    # 1. 检查当前分支
    print("1. 检查当前分支...")
    success, stdout, _ = run_command("git branch --show-current", check=False)
    if success:
        current_branch = stdout.strip()
        print(f"   当前分支: {current_branch}")
    else:
        print("   ⚠️  无法获取当前分支，继续...")
        current_branch = None
    
    # 2. 切换到 local-dev-stock-search 分支
    print()
    print("2. 切换到 local-dev-stock-search 分支...")
    if current_branch != "local-dev-stock-search":
        success, stdout, stderr = run_command("git checkout local-dev-stock-search", check=False)
        if success:
            print("   ✅ 已切换到 local-dev-stock-search 分支")
        else:
            print(f"   ⚠️  切换分支失败: {stderr}")
            print("   尝试继续...")
    else:
        print("   ✅ 已在 local-dev-stock-search 分支")
    
    # 3. 拉取最新更改
    print()
    print("3. 拉取最新更改...")
    success, stdout, stderr = run_command("git pull origin local-dev-stock-search", check=False)
    if success:
        print("   ✅ 已拉取最新更改")
    else:
        print("   ⚠️  拉取失败（可能远程分支不存在），继续...")
    
    # 4. 检查是否有未提交的更改
    print()
    print("4. 检查未提交的更改...")
    success, stdout, _ = run_command("git status --porcelain", check=False)
    if success and stdout.strip():
        print("   发现未提交的更改:")
        print(f"   {stdout.strip()}")
        print()
        print("   提交更改...")
        run_command("git add -A", check=False)
        run_command(
            'git commit -m "完成功能按钮按环境和用户等级显示：本地版显示所有功能，网络版免费用户只能查看结果，VIP用户每天只能扫描一次"',
            check=False
        )
        print("   ✅ 已提交更改")
    else:
        print("   ✅ 没有未提交的更改")
    
    # 5. 切换到 main 分支
    print()
    print("5. 切换到 main 分支...")
    success, stdout, stderr = run_command("git checkout main", check=False)
    if success:
        print("   ✅ 已切换到 main 分支")
    else:
        print(f"   ❌ 切换分支失败: {stderr}")
        return False
    
    # 6. 拉取 main 分支最新更改
    print()
    print("6. 拉取 main 分支最新更改...")
    success, stdout, stderr = run_command("git pull origin main", check=False)
    if success:
        print("   ✅ 已拉取 main 分支最新更改")
    else:
        print("   ⚠️  拉取失败，继续...")
    
    # 7. 合并 local-dev-stock-search 到 main
    print()
    print("7. 合并 local-dev-stock-search 到 main...")
    success, stdout, stderr = run_command("git merge local-dev-stock-search --no-edit", check=False)
    if success:
        print("   ✅ 合并成功")
        if stdout.strip():
            print(f"   {stdout.strip()}")
    else:
        if "Already up to date" in stderr or "Already up to date" in stdout:
            print("   ℹ️  main 分支已经是最新的，无需合并")
        else:
            print(f"   ⚠️  合并失败: {stderr}")
            print("   可能需要手动解决冲突")
            return False
    
    # 8. 推送到GitHub
    print()
    print("8. 推送到GitHub...")
    success, stdout, stderr = run_command("git push origin main", check=False)
    if success:
        print("   ✅ 推送成功")
        if stdout.strip():
            print(f"   {stdout.strip()}")
    else:
        print(f"   ❌ 推送失败")
        print(f"   错误: {stderr}")
        print()
        print("   可能的原因：")
        print("   1. 需要配置GitHub认证（Personal Access Token或SSH密钥）")
        print("   2. 网络连接问题")
        print("   3. 权限不足")
        print()
        print("   请手动执行: git push origin main")
        return False
    
    print()
    print("=" * 60)
    print("✅ 完成！")
    print("=" * 60)
    print()
    print("Vercel 将自动检测 main 分支的更新并重新部署")
    print("GitHub: https://github.com/jet20002025-hash/daniugu")
    print()
    return True

if __name__ == '__main__':
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  操作被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ 发生错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

