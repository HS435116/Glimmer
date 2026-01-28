#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (C) [2026] [晨曦微光]
# 项目配置脚本

import os
import sys
import json
import shutil
from pathlib import Path

def create_default_config():
    """创建默认配置文件"""
    print("创建默认配置...")
    
    # 检查必要的JSON文件是否存在
    required_files = ['users.json', 'attendance.json', 'settings.json']
    
    for file in required_files:
        if not os.path.exists(file):
            print(f"创建 {file}...")
            
            if file == 'users.json':
                default_data = {}
            elif file == 'attendance.json':
                default_data = {}
            elif file == 'settings.json':
                default_data = {
                    "__global__": {
                        "announcement_text": "欢迎使用晨曦智能打卡系统",
                        "announcement_time": "",
                        "company_name": "晨曦微光",
                        "work_start_time": "09:00",
                        "work_end_time": "18:00",
                        "location_required": True,
                        "auto_punch_enabled": False
                    }
                }
            
            with open(file, 'w', encoding='utf-8') as f:
                json.dump(default_data, f, ensure_ascii=False, indent=2)

def check_assets():
    """检查资源文件"""
    print("检查资源文件...")
    
    assets_dir = Path('assets')
    if not assets_dir.exists():
        assets_dir.mkdir(exist_ok=True)
        print("创建 assets 目录")
    
    # 检查必要资源
    required_assets = [
        'icon.png',
        'presplash.png',
        'fonts/simhei.ttf'
    ]
    
    missing_assets = []
    for asset in required_assets:
        if not (assets_dir / asset).exists():
            missing_assets.append(asset)
    
    if missing_assets:
        print(f"缺少资源文件: {', '.join(missing_assets)}")
        print("请确保以下文件存在:")
        for asset in missing_assets:
            print(f"  assets/{asset}")
        return False
    
    print("资源文件检查通过")
    return True

def optimize_python_files():
    """优化Python文件"""
    print("优化Python文件...")
    
    python_files = [
        'mobile_launcher.py',
        'main.py',
        'main_screen.py',
        'admin_screen.py',
        'settings_screen.py',
        'database.py',
        'app_main.py'
    ]
    
    for file in python_files:
        if os.path.exists(file):
            try:
                # 读取文件内容
                with open(file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # 移除调试信息（保留必要的日志）
                lines = content.split('\n')
                optimized_lines = []
                
                for line in lines:
                    # 保留文件头注释
                    if line.startswith('# Copyright') or line.startswith('# 此软件'):
                        optimized_lines.append(line)
                    # 跳过调试打印语句
                    elif 'print(' in line and 'debug' not in line.lower():
                        continue
                    # 跳过开发环境特定代码
                    elif 'APP_DEV_MODE' in line:
                        continue
                    else:
                        optimized_lines.append(line)
                
                # 写回优化后的内容
                with open(file, 'w', encoding='utf-8') as f:
                    f.write('\n'.join(optimized_lines))
                
                print(f"优化完成: {file}")
                
            except Exception as e:
                print(f"优化 {file} 时出错: {e}")

def create_build_info():
    """创建构建信息文件"""
    print("创建构建信息...")
    
    build_info = {
        "version": "1.1.0",
        "build_time": "",
        "build_environment": "mobile",
        "features": [
            "用户登录注册",
            "打卡记录",
            "位置验证",
            "自动打卡",
            "管理员功能",
            "设置管理",
            "公告通知"
        ],
        "permissions": [
            "INTERNET",
            "ACCESS_FINE_LOCATION",
            "ACCESS_COARSE_LOCATION", 
            "ACCESS_BACKGROUND_LOCATION",
            "WAKE_LOCK",
            "CAMERA",
            "WRITE_EXTERNAL_STORAGE",
            "READ_EXTERNAL_STORAGE",
            "VIBRATE"
        ]
    }
    
    with open('build_info.json', 'w', encoding='utf-8') as f:
        json.dump(build_info, f, ensure_ascii=False, indent=2)
    
    print("构建信息已保存到 build_info.json")

def main():
    """主函数"""
    print("晨曦智能打卡 - 项目配置")
    print("=" * 40)
    
    # 创建默认配置
    create_default_config()
    
    # 检查资源文件
    if not check_assets():
        print("资源文件检查失败，请补充必要文件后重试")
        sys.exit(1)
    
    # 优化Python文件
    optimize_python_files()
    
    # 创建构建信息
    create_build_info()
    
    print("\n配置完成！现在可以运行:")
    print("  python build.py debug     # 构建调试版本")
    print("  python build.py release   # 构建发布版本")

if __name__ == '__main__':
    main()