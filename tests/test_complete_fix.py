# -*- coding: utf-8 -*-
"""
完整测试修复后的自动HWND更新功能
"""

import sys
import os
import time
import json

# 添加项目路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from auto_approve.config_manager import load_config, CONFIG_FILE
from auto_approve.auto_hwnd_updater import AutoHWNDUpdater
from auto_approve.settings_dialog import SettingsDialog
from PySide6 import QtWidgets, QtCore


def test_complete_fixed_functionality():
    """测试完整修复后的功能"""
    print("=== 测试完整修复后的自动HWND更新功能 ===")
    
    try:
        # 创建应用实例
        app = QtWidgets.QApplication.instance()
        if app is None:
            app = QtWidgets.QApplication(sys.argv)
        
        # 模拟完整的主程序
        class FixedTestApp:
            def __init__(self):
                self.cfg = load_config()
                self.settings_dlg = None
                self.worker = None
                self.auto_hwnd_updater = AutoHWNDUpdater()
                self.auto_hwnd_updater.set_config(self.cfg)
                self.auto_hwnd_updater.hwnd_updated.connect(self._on_hwnd_auto_updated)
                
            def _on_hwnd_auto_updated(self, hwnd: int, process_name: str):
                """修复后的自动HWND更新处理"""
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
        
        # 创建测试应用
        test_app = FixedTestApp()
        
        # 显示初始状态
        initial_config = load_config()
        initial_hwnd = initial_config.target_hwnd
        print(f"1. 初始配置HWND: {initial_hwnd}")
        
        # 创建设置对话框
        test_app.settings_dlg = SettingsDialog()
        dialog_initial_hwnd = test_app.settings_dlg.sb_target_hwnd.value()
        print(f"2. 对话框初始HWND: {dialog_initial_hwnd}")
        
        # 启动自动更新器
        test_app.auto_hwnd_updater.start()
        print("3. 自动更新器已启动")
        
        # 等待智能查找器自动工作
        print("4. 等待智能查找器自动工作...")
        time.sleep(10)
        
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
        
        # 验证成功条件
        success_criteria = []
        
        # 检查是否找到了真实的窗口
        if final_updater_hwnd > 0 and final_updater_hwnd != initial_hwnd:
            print("✓ 智能查找器成功找到并更新目标窗口")
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
        if (final_config.target_hwnd == final_dialog_hwnd == final_updater_hwnd and 
            final_updater_hwnd > 0):
            print("✓ 所有组件HWND值一致")
            success_criteria.append(True)
        else:
            print("✗ 组件间HWND值不一致")
            success_criteria.append(False)
        
        overall_success = all(success_criteria)
        
        if overall_success:
            print("\n🎉 完整自动HWND更新功能修复成功！")
            print("\n用户现在可以享受完全自动化的体验：")
            print("1. 启动应用后自动查找目标进程窗口")
            print("2. 找到窗口后自动更新内存中的配置")
            print("3. 自动保存配置到文件")
            print("4. 自动更新UI界面显示")
            print("5. 下次启动应用时保持正确的HWND")
            print("6. 完全无需用户手动干预")
        else:
            print("\n❌ 部分功能仍需修复")
        
        return overall_success
        
    except Exception as e:
        print(f"完整测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主函数"""
    print("完整测试修复后的自动HWND更新功能\n")
    
    success = test_complete_fixed_functionality()
    
    print(f"\n=== 修复总结 ===")
    if success:
        print("✅ 所有问题已修复")
        print("\n修复内容：")
        print("1. ✅ 修复了SmartProcessFinder策略名称不匹配问题")
        print("2. ✅ 修复了智能查找器信号线程问题")
        print("3. ✅ 添加了配置文件同步保存功能")
        print("4. ✅ 添加了设置对话框自动更新功能")
        print("5. ✅ 完善了自动HWND更新的完整流程")
    else:
        print("❌ 仍有问题需要解决")
    
    return success


if __name__ == "__main__":
    success = main()
    print(f"\n测试完成，结果: {'成功' if success else '失败'}")