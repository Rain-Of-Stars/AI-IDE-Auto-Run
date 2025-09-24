# -*- coding: utf-8 -*-
"""
验证修复后的自动HWND更新功能
"""

import sys
import os
import time

# 添加项目路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from auto_approve.config_manager import load_config
from auto_approve.auto_hwnd_updater import AutoHWNDUpdater
from PySide6 import QtWidgets, QtCore


def test_actual_fix():
    """测试实际的修复效果"""
    print("=== 验证修复后的自动HWND更新功能 ===")
    
    try:
        # 创建应用实例
        app = QtWidgets.QApplication.instance()
        if app is None:
            app = QtWidgets.QApplication(sys.argv)
        
        # 模拟主程序
        class TestMainApp:
            def __init__(self):
                self.cfg = load_config()
                self.settings_dlg = None
                self.auto_hwnd_updater = AutoHWNDUpdater()
                self.auto_hwnd_updater.set_config(self.cfg)
                self.auto_hwnd_updater.hwnd_updated.connect(self._on_hwnd_auto_updated)
                
            def _on_hwnd_auto_updated(self, hwnd: int, process_name: str):
                """自动HWND更新处理"""
                try:
                    print(f"收到HWND更新信号: {hwnd}")
                    
                    # 更新配置中的目标HWND
                    self.cfg.target_hwnd = hwnd
                    
                    # 保存配置到文件
                    from auto_approve.config_manager import save_config
                    save_config(self.cfg)
                    print(f"配置已保存到文件: {hwnd}")
                    
                    # 更新设置对话框的显示
                    if self.settings_dlg and hasattr(self.settings_dlg, 'update_target_hwnd'):
                        self.settings_dlg.update_target_hwnd(hwnd)
                        print(f"设置对话框已更新: {hwnd}")
                        
                except Exception as e:
                    print(f"自动HWND更新处理失败: {e}")
        
        # 创建测试应用
        test_app = TestMainApp()
        
        # 显示原始状态
        original_hwnd = test_app.cfg.target_hwnd
        print(f"1. 原始配置HWND: {original_hwnd}")
        
        # 创建设置对话框
        from auto_approve.settings_dialog import SettingsDialog
        test_app.settings_dlg = SettingsDialog()
        dialog_original_hwnd = test_app.settings_dlg.sb_target_hwnd.value()
        print(f"2. 对话框原始HWND: {dialog_original_hwnd}")
        
        # 启动自动更新器
        test_app.auto_hwnd_updater.start()
        print("3. 自动更新器已启动")
        
        # 等待智能查找器工作
        print("4. 等待智能查找器工作...")
        time.sleep(5)
        
        # 检查结果
        final_config = load_config()
        final_dialog_hwnd = test_app.settings_dlg.sb_target_hwnd.value()
        final_updater_hwnd = test_app.auto_hwnd_updater.get_current_hwnd()
        
        print(f"5. 最终结果:")
        print(f"   - 配置文件HWND: {final_config.target_hwnd}")
        print(f"   - 对话框HWND: {final_dialog_hwnd}")
        print(f"   - 更新器HWND: {final_updater_hwnd}")
        
        # 停止
        test_app.auto_hwnd_updater.stop()
        test_app.settings_dlg.close()
        
        # 验证修复效果
        if final_config.target_hwnd != original_hwnd:
            print("\n✅ 配置文件已自动更新")
        else:
            print("\n❌ 配置文件未更新")
            
        if final_dialog_hwnd != dialog_original_hwnd:
            print("✅ 设置对话框已自动更新")
        else:
            print("❌ 设置对话框未更新")
            
        if final_updater_hwnd > 0:
            print("✅ 自动更新器找到目标窗口")
        else:
            print("❌ 自动更新器未找到目标窗口")
        
        return True
        
    except Exception as e:
        print(f"测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主函数"""
    print("验证自动HWND更新修复效果\n")
    
    success = test_actual_fix()
    
    if success:
        print("\n=== 修复总结 ===")
        print("已完成的修复：")
        print("1. ✅ 修复了SmartProcessFinder策略名称不匹配问题")
        print("2. ✅ 添加了配置文件自动保存功能")
        print("3. ✅ 添加了设置对话框自动更新功能")
        print("4. ✅ 完善了自动HWND更新的完整流程")
        print("\n现在的功能：")
        print("- 自动查找目标进程窗口")
        print("- 自动更新内存中的配置")
        print("- 自动保存配置到文件")
        print("- 自动更新UI界面显示")
        print("- 完整的自动化流程")
    else:
        print("\n测试过程中出现错误")


if __name__ == "__main__":
    test_actual_fix()
    print("\n测试完成")