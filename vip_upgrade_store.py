#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VIP升级申请存储模块
存储用户的VIP升级申请，等待手动审核和开通
"""
import os
import json
from datetime import datetime
from typing import Dict, List, Optional

# 申请数据文件
APPLICATIONS_FILE = 'vip_applications.json'

def _load_applications() -> Dict:
    """加载申请数据"""
    try:
        if os.path.exists(APPLICATIONS_FILE):
            with open(APPLICATIONS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    except Exception as e:
        print(f"⚠️ 加载VIP申请数据失败: {e}")
        return {}

def _save_applications(applications: Dict):
    """保存申请数据"""
    try:
        with open(APPLICATIONS_FILE, 'w', encoding='utf-8') as f:
            json.dump(applications, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"⚠️ 保存VIP申请数据失败: {e}")
        return False

def save_vip_application(username: str, email: str, plan: str, contact: str, note: str = '') -> bool:
    """
    保存VIP升级申请
    :param username: 用户名
    :param email: 邮箱
    :param plan: 套餐（'monthly' 或 'yearly'）
    :param contact: 联系方式（微信/QQ/手机号）
    :param note: 备注信息
    :return: 是否保存成功
    """
    try:
        applications = _load_applications()
        
        # 创建申请ID（基于时间和用户名）
        application_id = f"{username}_{int(datetime.now().timestamp())}"
        
        # 检查是否已有未处理的申请
        for app_id, app_data in applications.items():
            if app_data.get('username') == username and app_data.get('status') == 'pending':
                # 更新现有申请
                app_data['plan'] = plan
                app_data['contact'] = contact
                app_data['note'] = note
                app_data['updated_at'] = datetime.now().isoformat()
                applications[app_id] = app_data
                _save_applications(applications)
                return True
        
        # 创建新申请
        application = {
            'application_id': application_id,
            'username': username,
            'email': email,
            'plan': plan,  # 'monthly' 或 'yearly'
            'plan_name': '月费（99元/月）' if plan == 'monthly' else '年费（999元/年）',
            'amount': 99 if plan == 'monthly' else 999,
            'contact': contact,
            'note': note,
            'status': 'pending',  # 'pending', 'approved', 'rejected', 'completed'
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat(),
            'processed_at': None,
            'processed_by': None
        }
        
        applications[application_id] = application
        return _save_applications(applications)
        
    except Exception as e:
        print(f"⚠️ 保存VIP申请失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def get_vip_applications(status: Optional[str] = None) -> List[Dict]:
    """
    获取VIP升级申请列表
    :param status: 筛选状态（'pending', 'approved', 'rejected', 'completed'），None表示全部
    :return: 申请列表
    """
    try:
        applications = _load_applications()
        result = []
        
        for app_id, app_data in applications.items():
            if status is None or app_data.get('status') == status:
                result.append(app_data)
        
        # 按创建时间倒序排列（最新的在前）
        result.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        return result
        
    except Exception as e:
        print(f"⚠️ 获取VIP申请列表失败: {e}")
        return []

def update_application_status(application_id: str, status: str, processed_by: str = None) -> bool:
    """
    更新申请状态
    :param application_id: 申请ID
    :param status: 新状态（'pending', 'approved', 'rejected', 'completed'）
    :param processed_by: 处理人
    :return: 是否更新成功
    """
    try:
        applications = _load_applications()
        
        if application_id not in applications:
            return False
        
        applications[application_id]['status'] = status
        applications[application_id]['processed_at'] = datetime.now().isoformat()
        if processed_by:
            applications[application_id]['processed_by'] = processed_by
        applications[application_id]['updated_at'] = datetime.now().isoformat()
        
        return _save_applications(applications)
        
    except Exception as e:
        print(f"⚠️ 更新申请状态失败: {e}")
        return False

def get_user_application(username: str) -> Optional[Dict]:
    """
    获取用户的申请（最新的）
    :param username: 用户名
    :return: 申请信息，如果不存在返回None
    """
    try:
        applications = _load_applications()
        
        user_apps = []
        for app_id, app_data in applications.items():
            if app_data.get('username') == username:
                user_apps.append(app_data)
        
        if not user_apps:
            return None
        
        # 返回最新的申请
        user_apps.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        return user_apps[0]
        
    except Exception as e:
        print(f"⚠️ 获取用户申请失败: {e}")
        return None

