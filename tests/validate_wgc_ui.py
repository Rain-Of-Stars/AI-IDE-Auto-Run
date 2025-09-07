# -*- coding: utf-8 -*-
"""
WGC配置界面UI优化验证脚本
"""
import sys
import os

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

def validate_wgc_ui_code():
    """验证WGC UI代码优化"""
    print("验证WGC配置界面UI优化...")
    
    # 读取设置对话框文件
    settings_file = os.path.join(project_root, 'auto_approve', 'settings_dialog.py')
    
    with open(settings_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 检查优化点
    optimizations = []
    
    # 1. 检查分组结构
    if 'QGroupBox("基础配置")' in content:
        optimizations.append("[OK] 添加了基础配置分组")
    
    if 'QGroupBox("窗口查找工具")' in content:
        optimizations.append("[OK] 添加了窗口查找工具分组")
    
    if 'QGroupBox("性能配置")' in content:
        optimizations.append("[OK] 添加了性能配置分组")
    
    if 'QGroupBox("捕获选项")' in content:
        optimizations.append("[OK] 添加了捕获选项分组")
    
    if 'QGroupBox("自动更新配置")' in content:
        optimizations.append("[OK] 添加了自动更新配置分组")
    
    # 2. 检查网格布局
    if 'QGridLayout' in content and 'layout_tools.addWidget' in content:
        optimizations.append("[OK] 使用网格布局优化工具按钮排列")
    
    # 3. 检查统一样式
    if 'tool_button_style' in content:
        optimizations.append("[OK] 统一了工具按钮样式")
    
    # 4. 检查间距优化
    if 'setSpacing(16)' in content and 'setContentsMargins(16, 16, 16, 16)' in content:
        optimizations.append("[OK] 优化了布局间距和边距")
    
    # 5. 检查滚动区域
    if 'QScrollArea' in content and 'setWidgetResizable(True)' in content:
        optimizations.append("[OK] 优化了滚动区域设置")
    
    print("\n优化验证结果:")
    for opt in optimizations:
        print(f"  {opt}")
    
    print(f"\n总共实现了 {len(optimizations)} 项优化")
    
    # 检查是否移除了旧的布局代码
    old_patterns = [
        'form_wgc.addRow("捕获模式"',
        'vb_w.addLayout(hb_w1)',
        'sep = QtWidgets.QFrame()'
    ]
    
    removed_old = True
    for pattern in old_patterns:
        if pattern in content:
            print(f"[WARN] 仍然包含旧代码模式: {pattern}")
            removed_old = False
    
    if removed_old:
        print("[OK] 已清理所有旧布局代码")
    
    print("\nWGC配置界面UI优化验证完成!")

if __name__ == "__main__":
    validate_wgc_ui_code()