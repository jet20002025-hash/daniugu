#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
移除本地版本代码，只保留网络版功能
"""
import re
import os

def remove_local_version_code():
    """移除HTML中的本地版本代码"""
    html_file = 'templates/bull_stock_web.html'
    
    if not os.path.exists(html_file):
        print(f"❌ 文件不存在: {html_file}")
        return False
    
    # 备份原文件
    backup_file = html_file + '.backup'
    with open(html_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    with open(backup_file, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"✅ 已备份原文件: {backup_file}")
    
    # 移除本地版本的按钮组
    # 匹配从 "<!-- 本地版本：显示所有功能 -->" 到对应的 </div> 结束
    pattern1 = r'<!-- 本地版本：显示所有功能 -->.*?</div>\s*</div>\s*'
    content = re.sub(pattern1, '', content, flags=re.DOTALL)
    
    # 移除搜索反转个股功能（仅本地版本）
    pattern2 = r'<!-- 反转个股筛选条件（仅本地版本显示） -->.*?<!-- 反转个股扫描结果区域 -->'
    content = re.sub(pattern2, '', content, flags=re.DOTALL)
    
    # 简化 isLocalEnvironment 函数，使其始终返回 False（网络环境）
    pattern3 = r'function isLocalEnvironment\(\) \{[^}]*return[^}]*\}'
    replacement3 = '''function isLocalEnvironment() {
            // 网络版：始终返回 false（不显示本地版本功能）
            return false;
        }'''
    content = re.sub(pattern3, replacement3, content, flags=re.DOTALL)
    
    # 简化 updateFunctionButtonsVisibility 函数，移除本地版本的逻辑
    # 找到函数开始
    func_start = content.find('async function updateFunctionButtonsVisibility()')
    if func_start != -1:
        # 找到函数结束（下一个函数开始或文件结束）
        func_end = content.find('async function', func_start + 1)
        if func_end == -1:
            func_end = len(content)
        
        func_content = content[func_start:func_end]
        
        # 移除本地版本的显示逻辑，只保留网络版逻辑
        new_func = '''        // 根据环境和用户等级显示/隐藏功能按钮（网络版）
        async function updateFunctionButtonsVisibility() {
            // 网络环境：根据用户等级显示
            const webButtons = document.getElementById('webVersionButtons');
            const vipButtons = document.getElementById('vipUserButtons');
            const freeButtons = document.getElementById('freeUserButtons');
            const superButtons = document.getElementById('superUserButtons');
            
            if (webButtons) webButtons.style.display = 'block';
            
            // 获取用户信息
            try {
                const user = await getUserInfo();
                if (user) {
                    const tier = user.tier || 'free';
                    const isSuper = user.is_super || false;
                    
                    if (isSuper || tier === 'super') {
                        // 超级用户：显示所有功能
                        if (superButtons) superButtons.style.display = 'block';
                        if (vipButtons) vipButtons.style.display = 'none';
                        if (freeButtons) freeButtons.style.display = 'none';
                    } else if (tier === 'premium') {
                        // VIP用户：显示扫描全市场（每天一次）
                        if (vipButtons) vipButtons.style.display = 'block';
                        if (freeButtons) freeButtons.style.display = 'none';
                        if (superButtons) superButtons.style.display = 'none';
                    } else {
                        // 免费用户：只显示查看结果按钮
                        if (freeButtons) freeButtons.style.display = 'block';
                        if (vipButtons) vipButtons.style.display = 'none';
                        if (superButtons) superButtons.style.display = 'none';
                    }
                } else {
                    // 无法获取用户信息，默认显示免费用户按钮
                    if (freeButtons) freeButtons.style.display = 'block';
                    if (vipButtons) vipButtons.style.display = 'none';
                    if (superButtons) superButtons.style.display = 'none';
                }
            } catch (error) {
                console.error('获取用户信息失败:', error);
                // 出错时默认显示免费用户按钮
                if (freeButtons) freeButtons.style.display = 'block';
                if (vipButtons) vipButtons.style.display = 'none';
                if (superButtons) superButtons.style.display = 'none';
            }
        }'''
        
        content = content[:func_start] + new_func + content[func_end:]
    
    # 移除 initPageLoad 中对本地版本的检查
    pattern4 = r'// 根据环境显示/隐藏"搜索反转个股"功能.*?console\.log\(`\[initPageLoad\] 搜索反转个股功能.*?\);'
    content = re.sub(pattern4, '', content, flags=re.DOTALL)
    
    # 保存修改后的文件
    with open(html_file, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"✅ 已移除本地版本代码: {html_file}")
    return True

if __name__ == '__main__':
    print("=" * 50)
    print("移除本地版本代码（仅保留网络版）")
    print("=" * 50)
    print()
    
    if remove_local_version_code():
        print()
        print("=" * 50)
        print("✅ 完成！")
        print("=" * 50)
        print()
        print("文件已修改，本地版本功能已移除")
        print("请检查 templates/bull_stock_web.html 确认修改正确")
        print("如需恢复，可使用备份文件: templates/bull_stock_web.html.backup")
    else:
        print()
        print("=" * 50)
        print("❌ 失败！")
        print("=" * 50)

