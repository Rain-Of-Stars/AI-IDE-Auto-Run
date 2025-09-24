# -*- coding: utf-8 -*-
"""
最终验证测试：自动HWND更新功能完整测试
"""

import sys
import os
import time

# 添加项目路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from auto_approve.config_manager import load_config
from auto_approve.auto_hwnd_updater import AutoHWNDUpdater
from auto_approve.smart_process_finder import SmartProcessFinder
from PySide6 import QtWidgets, QtCore


def test_complete_auto_hwnd_update():
    """完整的自动HWND更新测试"""
    print("=== 完整自动HWND更新功能测试 ===")
    
    try:
        # 创建应用实例
        app = QtWidgets.QApplication.instance()
        if app is None:
            app = QtWidgets.QApplication(sys.argv)
        
        # 模拟完整的主程序
        class CompleteTestApp:
            def __init__(self):
                self.cfg = load_config()
                self.settings_dlg = None
                self.worker = None  # 模拟扫描器
                self.auto_hwnd_updater = AutoHWNDUpdater()
                self.auto_hwnd_updater.set_config(self.cfg)
                self.auto_hwnd_updater.hwnd_updated.connect(self._on_hwnd_auto_updated)
                
            def _on_hwnd_auto_updated(self, hwnd: int, process_name: str):
                """完整的自动HWND更新处理（修复版）"""
                try:
                    print(f"收到HWND更新信号: {hwnd}")
                    
                    # 更新配置中的目标HWND
                    self.cfg.target_hwnd = hwnd
                    
                    # 如果扫描器正在运行，更新其配置
                    if self.worker and self.worker.isRunning():
                        self.worker.update_config(self.cfg)
                        print(f"自动更新扫描器HWND：{hwnd} (进程: {process_name})")
                    else:
                        print(f"自动更新目标窗口HWND：{hwnd} (进程: {process_name})")
                    
                    # 使用同步保存确保配置立即更新
                    import json
                    from dataclasses import asdict
                    from auto_approve.config_manager import CONFIG_FILE
                    
                    config_data = asdict(self.cfg)
                    config_data["roi"] = asdict(self.cfg.roi)
                    config_data["scales"] = list(self.cfg.scales)
                    config_data["click_offset"] = list(self.cfg.click_offset)
                    config_data["coordinate_offset"] = list(self.cfg.coordinate_offset)
                    
                    # 兼容处理
                    if isinstance(config_data.get("template_paths"), list):
                        if config_data["template_paths"]:
                            config_data["template_path"] = config_data["template_paths"][0]
                    
                    config_path = os.path.abspath(CONFIG_FILE)
                    os.makedirs(os.path.dirname(config_path), exist_ok=True)
                    
                    with open(config_path, 'w', encoding='utf-8') as f:
                        json.dump(config_data, f, indent=2, ensure_ascii=False)
                    
                    print(f"配置已同步保存到文件: {hwnd}")
                    
                    # 更新设置对话框的显示
                    if self.settings_dlg and hasattr(self.settings_dlg, 'update_target_hwnd'):
                        self.settings_dlg.update_target_hwnd(hwnd)
                        print(f"设置对话框已更新: {hwnd}")
                        
                except Exception as e:
                    print(f"自动HWND更新处理失败: {e}")
        
        # 创建完整测试应用
        test_app = CompleteTestApp()
        
        # 显示初始状态
        initial_config = load_config()
        initial_hwnd = initial_config.target_hwnd
        print(f"1. 初始配置HWND: {initial_hwnd}")
        
        # 创建设置对话框
        from auto_approve.settings_dialog import SettingsDialog
        test_app.settings_dlg = SettingsDialog()
        dialog_initial_hwnd = test_app.settings_dlg.sb_target_hwnd.value()
        print(f"2. 对话框初始HWND: {dialog_initial_hwnd}")
        
        # 启动自动更新器
        test_app.auto_hwnd_updater.start()
        print("3. 自动更新器已启动")
        
        # 等待智能查找器自动工作
        print("4. 等待智能查找器自动工作...")
        time.sleep(5)
        
        # 检查自动查找结果
        auto_found_hwnd = test_app.auto_hwnd_updater.get_current_hwnd()
        print(f"5. 自动查找结果: {auto_found_hwnd}")
        
        # 等待更长时间以确保更新完成
        print("6. 等待更新完成...")
        time.sleep(2)
        
        # 检查最终结果
        final_config = load_config()
        final_dialog_hwnd = test_app.settings_dlg.sb_target_hwnd.value()
        
        print(f"7. 最终结果:")
        print(f"   - 配置文件HWND: {final_config.target_hwnd}")
        print(f"   - 对话框HWND: {final_dialog_hwnd}")
        print(f"   - 更新器HWND: {auto_found_hwnd}")
        
        # 停止
        test_app.auto_hwnd_updater.stop()
        test_app.settings_dlg.close()
        
        # 验证成功条件
        success_criteria = []
        
        # 检查是否找到了真实的窗口
        if auto_found_hwnd > 0:
            print("✓ 智能查找器成功找到目标窗口")
            success_criteria.append(True)
        else:
            print("✗ 智能查找器未找到目标窗口")
            success_criteria.append(False)
        
        # 检查配置文件是否更新
        if final_config.target_hwnd != initial_hwnd:
            print("✓ 配置文件已自动更新")
            success_criteria.append(True)
        else:
            print("✗ 配置文件未更新")
            success_criteria.append(False)
        
        # 检查对话框是否更新
        if final_dialog_hwnd != dialog_initial_hwnd:
            print("✓ 设置对话框已自动更新")
            success_criteria.append(True)
        else:
            print("✗ 设置对话框未更新")
            success_criteria.append(False)
        
        # 检查三者是否一致
        if (final_config.target_hwnd == final_dialog_hwnd == auto_found_hwnd and 
            auto_found_hwnd > 0):
            print("✓ 所有组件HWND值一致")
            success_criteria.append(True)
        else:
            print("✗ 组件间HWND值不一致")
            success_criteria.append(False)
        
        overall_success = all(success_criteria)
        
        if overall_success:
            print("\n🎉 完整自动HWND更新功能测试通过！")
            print("用户现在可以享受：")
            print("- 启动应用后自动查找目标进程窗口")
            print("- 找到窗口后自动更新配置文件")
            print("- UI界面显示自动更新")
            print("- 完全无需手动干预的自动化体验")
        else:
            print("\n❌ 部分功能未正常工作")
        
        return overall_success
        
    except Exception as e:
        print(f"完整测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主函数"""
    print("最终验证：自动HWND更新功能\n")
    
    success = test_complete_auto_hwnd_update()
    
    print(f"\n=== 最终测试结果 ===")
    if success:
        print("✅ 所有功能正常工作")
        print("自动HWND更新功能修复完成！")
    else:
        print("❌ 仍有问题需要解决")
    
    return success


if __name__ == "__main__":
    success = main()
    print(f"\n测试完成，结果: {'成功' if success else '失败'}")