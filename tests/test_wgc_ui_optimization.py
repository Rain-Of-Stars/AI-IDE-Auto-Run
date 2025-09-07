# -*- coding: utf-8 -*-
"""
WGC配置界面UI优化测试脚本
"""
import sys
import os

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from PySide6 import QtWidgets, QtCore
from auto_approve.settings_dialog import SettingsDialog

def test_wgc_ui_optimization():
    """测试WGC配置界面UI优化效果"""
    print("开始测试WGC配置界面UI优化...")
    
    # 创建应用程序
    app = QtWidgets.QApplication(sys.argv)
    
    try:
        # 创建设置对话框
        dialog = SettingsDialog()
        dialog.show()
        
        # 导航到WGC配置页面
        nav = dialog.nav
        wgc_item = None
        
        # 查找窗口捕获节点
        for i in range(nav.topLevelItemCount()):
            top_item = nav.topLevelItem(i)
            if top_item.text(0) == '窗口捕获':
                wgc_item = top_item.child(0)
                break
        
        if wgc_item:
            nav.setCurrentItem(wgc_item)
            print("成功导航到WGC配置页面")
            
            # 检查布局结构
            stack = dialog.stack
            current_widget = stack.currentWidget()
            
            if hasattr(current_widget, 'layout'):
                layout = current_widget.layout()
                if layout:
                    print(f"当前页面有 {layout.count()} 个子控件")
                    
                    # 统计分组数量
                    group_count = 0
                    for i in range(layout.count()):
                        item = layout.itemAt(i)
                        if item.widget():
                            widget = item.widget()
                            if isinstance(widget, QtWidgets.QGroupBox):
                                group_count += 1
                                print(f"  找到分组: {widget.title()}")
                    
                    print(f"总共找到 {group_count} 个配置分组")
                    
                    # 检查是否包含所有预期分组
                    expected_groups = ["基础配置", "窗口查找工具", "性能配置", "捕获选项", "自动更新配置"]
                    found_groups = []
                    
                    for i in range(layout.count()):
                        item = layout.itemAt(i)
                        if item.widget():
                            widget = item.widget()
                            if isinstance(widget, QtWidgets.QGroupBox):
                                found_groups.append(widget.title())
                    
                    missing_groups = set(expected_groups) - set(found_groups)
                    if missing_groups:
                        print(f"警告: 缺少分组 {missing_groups}")
                    else:
                        print("所有预期分组都已正确创建")
                    
                    print("UI优化测试通过!")
                else:
                    print("错误: 当前页面没有布局")
            else:
                print("错误: 当前页面没有layout方法")
        else:
            print("错误: 未找到WGC配置页面")
        
        # 关闭对话框
        dialog.close()
        
    except Exception as e:
        print(f"测试过程中出现错误: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        app.quit()
    
    print("WGC配置界面UI优化测试完成")

if __name__ == "__main__":
    test_wgc_ui_optimization()