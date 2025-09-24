# -*- coding: utf-8 -*-
"""测试图标加载功能"""
import os
import sys
from PySide6 import QtWidgets, QtGui, QtCore
from auto_approve.path_utils import get_app_base_dir

def test_icon_loading():
    """测试图标加载"""
    app = QtWidgets.QApplication(sys.argv)
    
    # 获取应用基准目录
    base_dir = get_app_base_dir()
    print(f"应用基准目录: {base_dir}")
    
    # 构建图标路径
    icon_path = os.path.join(base_dir, "assets", "icons", "icons", "custom_icon.ico")
    print(f"图标路径: {icon_path}")
    print(f"图标文件是否存在: {os.path.exists(icon_path)}")
    
    if os.path.exists(icon_path):
        # 尝试加载图标
        try:
            icon = QtGui.QIcon(icon_path)
            print(f"图标加载成功: {not icon.isNull()}")
            print(f"图标可用尺寸: {icon.availableSizes()}")
            
            # 创建系统托盘图标测试
            tray_icon = QtWidgets.QSystemTrayIcon()
            tray_icon.setIcon(icon)
            tray_icon.setToolTip("测试图标加载")
            tray_icon.show()
            
            # 测试不同尺寸的图标
            sizes = [16, 24, 32, 48, 64]
            for size in sizes:
                pixmap = icon.pixmap(size, size)
                print(f"尺寸 {size}x{size}: {'成功' if not pixmap.isNull() else '失败'}")
            
            print("图标测试完成，将在3秒后退出...")
            QtCore.QTimer.singleShot(3000, app.quit)
            
        except Exception as e:
            print(f"图标加载失败: {e}")
            import traceback
            traceback.print_exc()
    else:
        print("图标文件不存在，无法测试加载")
    
    sys.exit(app.exec())

if __name__ == "__main__":
    test_icon_loading()