#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Vercel Serverless Function 入口
将 Flask 应用适配为 Vercel 的 serverless 函数格式
"""
import sys
import os

# 添加项目根目录到路径
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

from bull_stock_web import app

# Vercel 的 Python serverless 函数需要这个格式
# 直接导出 app，Vercel 会自动处理
