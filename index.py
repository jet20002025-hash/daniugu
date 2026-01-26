#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Vercel Flask 应用入口点（根目录）
直接导入 api/index.py 中的 app
"""
from api.index import app

# 确保 app 对象在模块级别导出
# Vercel 会检测这个文件中的 'app' 变量
