# -*- coding: utf-8 -*-
"""
测试自动HWND更新功能

验证AutoHWNDUpdater是否能正确更新UI和配置文件
"""

import sys
import os
import time
import json

# 添加项目路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from auto_approve.config_manager import load_config, save_config
from auto_approve.auto_hwnd_updater import AutoHWNDUpdater
from auto_approve.settings_dialog import SettingsDialog
from PySide6 import QtWidgets, QtCore


def test_config_persistence():
    """测试配置持久化"""
    print("=== 测试配置持久化 ===")
    
    try:
        # 加载原始配置
        config = load_config()
        original_hwnd = config.target_hwnd
        print(f"1. 原始配置HWND: {original_hwnd}")
        
        # 修改HWND
        new_hwnd = 123456789
        config.target_hwnd = new_hwnd
        
        # 保存配置
        save_config(config)
        print(f"2. 保存新HWND: {new_hwnd}")
        
        # 重新加载配置
        reloaded_config = load_config()
        print(f"3. 重新加载HWND: {reloaded_config.target_hwnd}")
        
        # 验证
        if reloaded_config.target_hwnd == new_hwnd:
            print("✓ 配置持久化测试通过")
            return True
        else:
            print("✗ 配置持久化测试失败")
            return False
            
    except Exception as e:
        print(f"配置持久化测试失败: {e}")
        return False


def test_auto_updater_with_config():
    """测试自动更新器与配置同步"""
    print("\n=== 测试自动更新器与配置同步 ===")
    
    try:
        # 创建应用实例（如果需要）
        app = QtWidgets.QApplication.instance()
        if app is None:
            app = QtWidgets.QApplication(sys.argv)
        
        # 加载配置
        config = load_config()
        original_hwnd = config.target_hwnd
        print(f"1. 原始配置HWND: {original_hwnd}")
        
        # 创建自动更新器
        updater = AutoHWNDUpdater()
        updater.set_config(config)
        
        # 模拟找到新窗口
        new_hwnd = 987654321
        print(f"2. 模拟找到新HWND: {new_hwnd}")
        
        # 手动触发更新（模拟智能查找器找到窗口）
        updater._current_hwnd = new_hwnd
        updater.hwnd_updated.emit(new_hwnd, config.target_process)
        
        # 检查配置是否更新
        time.sleep(0.1)  # 等待信号处理
        updated_config = load_config()
        print(f"3. 更新后配置HWND: {updated_config.target_hwnd}")
        
        # 验证
        if updated_config.target_hwnd == new_hwnd:
            print("✓ 自动更新器配置同步测试通过")
            updater.stop()
            return True
        else:
            print("✗ 自动更新器配置同步测试失败")
            updater.stop()
            return False
            
    except Exception as e:
        print(f"自动更新器配置同步测试失败: {e}")
        return False


def test_settings_dialog_update():
    """测试设置对话框更新"""
    print("\n=== 测试设置对话框更新 ===")
    
    try:
        # 创建应用实例
        app = QtWidgets.QApplication.instance()
        if app is None:
            app = QtWidgets.QApplication(sys.argv)
        
        # 创建设置对话框
        dialog = SettingsDialog()
        original_hwnd = dialog.sb_target_hwnd.value()
        print(f"1. 对话框原始HWND: {original_hwnd}")
        
        # 测试更新方法
        new_hwnd = 555666777
        dialog.update_target_hwnd(new_hwnd)
        updated_hwnd = dialog.sb_target_hwnd.value()
        print(f"2. 更新后对话框HWND: {updated_hwnd}")
        
        # 验证
        if updated_hwnd == new_hwnd:
            print("✓ 设置对话框更新测试通过")
            dialog.close()
            return True
        else:
            print("✗ 设置对话框更新测试失败")
            dialog.close()
            return False
            
    except Exception as e:
        print(f"设置对话框更新测试失败: {e}")
        return False


def test_full_integration():
    """完整集成测试"""
    print("\n=== 完整集成测试 ===")
    
    try:
        # 创建应用实例
        app = QtWidgets.QApplication.instance()
        if app is None:
            app = QtWidgets.QApplication(sys.argv)
        
        # 模拟主程序
        class MockMainApp:
            def __init__(self):
                self.cfg = load_config()
                self.settings_dlg = None
                self.auto_hwnd_updater = AutoHWNDUpdater()
                self.auto_hwnd_updater.set_config(self.cfg)
                self.auto_hwnd_updater.hwnd_updated.connect(self._on_hwnd_auto_updated)
                
            def _on_hwnd_auto_updated(self, hwnd: int, process_name: str):
                """模拟主程序的自动HWND更新处理"""
                try:
                    # 更新配置中的目标HWND
                    self.cfg.target_hwnd = hwnd
                    
                    # 保存配置到文件
                    from auto_approve.config_manager import save_config
                    save_config(self.cfg)
                    
                    # 更新设置对话框的显示
                    if self.settings_dlg and hasattr(self.settings_dlg, 'update_target_hwnd'):
                        self.settings_dlg.update_target_hwnd(hwnd)
                        
                except Exception as e:
                    print(f"自动HWND更新处理失败: {e}")
        
        # 创建模拟主程序
        main_app = MockMainApp()
        original_hwnd = main_app.cfg.target_hwnd
        print(f"1. 原始HWND: {original_hwnd}")
        
        # 创建设置对话框
        main_app.settings_dlg = SettingsDialog()
        dialog_original_hwnd = main_app.settings_dlg.sb_target_hwnd.value()
        print(f"2. 对话框原始HWND: {dialog_original_hwnd}")
        
        # 启动自动更新器
        main_app.auto_hwnd_updater.start()
        
        # 模拟智能查找器找到窗口
        test_hwnd = 111222333
        print(f"3. 模拟找到新HWND: {test_hwnd}")
        
        # 模拟智能查找器信号
        main_app.auto_hwnd_updater._on_smart_process_found(test_hwnd, "Code.exe", "Visual Studio Code")
        
        # 等待处理
        time.sleep(0.5)
        
        # 检查结果
        final_config = load_config()
        final_dialog_hwnd = main_app.settings_dlg.sb_target_hwnd.value()
        print(f"4. 最终配置HWND: {final_config.target_hwnd}")
        print(f"5. 最终对话框HWND: {final_dialog_hwnd}")
        
        # 停止
        main_app.auto_hwnd_updater.stop()
        main_app.settings_dlg.close()
        
        # 验证
        success = (final_config.target_hwnd == test_hwnd and 
                 final_dialog_hwnd == test_hwnd)
        
        if success:
            print("✓ 完整集成测试通过")
        else:
            print("✗ 完整集成测试失败")
            
        return success
        
    except Exception as e:
        print(f"完整集成测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主测试函数"""
    print("测试自动HWND更新功能\n")
    
    try:
        # 运行测试
        test_results = []
        
        test_results.append(test_config_persistence())
        test_results.append(test_auto_updater_with_config())
        test_results.append(test_settings_dialog_update())
        test_results.append(test_full_integration())
        
        # 汇总结果
        print(f"\n=== 测试结果汇总 ===")
        passed = sum(test_results)
        total = len(test_results)
        print(f"通过测试: {passed}/{total}")
        
        if passed == total:
            print("\n🎉 所有测试通过！")
            print("自动HWND更新功能完全正常：")
            print("1. 配置文件正确保存和加载")
            print("2. AutoHWNDUpdater正确更新配置")
            print("3. 设置对话框正确显示更新")
            print("4. 完整集成流程正常工作")
            print("\n现在用户会看到：")
            print("- 自动查找找到窗口后，配置文件自动更新")
            print("- 设置对话框中的HWND值自动更新")
            print("- 下次启动应用时保持正确的HWND")
        else:
            print("\n❌ 部分测试失败，请检查实现。")
            
    except Exception as e:
        print(f"测试过程中发生异常: {e}")
        return False
    
    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)