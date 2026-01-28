#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (C) [2026] [晨曦微光]
# 移动端优化启动脚本

import os
import sys

# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def _add_path(p: str):
    if not p:
        return
    try:
        if os.path.isdir(p) and p not in sys.path:
            sys.path.insert(0, p)
    except Exception:
        pass

# python-for-android 环境下，应用源码通常位于：<filesDir>/app
private = os.environ.get('ANDROID_PRIVATE') or ''
argument = os.environ.get('ANDROID_ARGUMENT') or ''
_add_path(os.path.join(private, 'app'))
_add_path(os.path.join(argument, 'app'))

# Activity.getFilesDir() 兜底（在部分 ROM 上 ANDROID_PRIVATE 可能为空）
try:
    from jnius import autoclass
    PythonActivity = autoclass('org.kivy.android.PythonActivity')
    act = PythonActivity.mActivity
    files_dir = str(act.getFilesDir().getAbsolutePath())
    _add_path(os.path.join(files_dir, 'app'))
except Exception:
    pass



# 移动端环境变量设置
os.environ['KIVY_NO_CONSOLELOG'] = '1'
os.environ['KIVY_WINDOW'] = 'sdl2'
os.environ['KIVY_GRAPHICS'] = 'sdl2'

# 针对移动端的优化配置
os.environ['KIVY_DPI'] = '160'

# 禁用文件监控（移动端不需要）
os.environ['KIVY_NO_FILELOG'] = '1'

# 导入主应用
from app_main import AttendanceApp

if __name__ == '__main__':
    # 设置应用为移动端模式
    os.environ['APP_MOBILE_MODE'] = '1'
    
    # 启动应用
    app = AttendanceApp()
    app.run()