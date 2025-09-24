# -*- coding: utf-8 -*-
"""
测试配置保存功能
"""

import sys
import os
import json

# 添加项目路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from auto_approve.config_manager import load_config, AppConfig, CONFIG_FILE


def save_config_sync(cfg: AppConfig, path: str = None) -> str:
    """同步保存配置到JSON文件"""
    try:
        from dataclasses import asdict
        
        data = asdict(cfg)
        data["roi"] = asdict(cfg.roi)
        data["scales"] = list(cfg.scales)
        data["click_offset"] = list(cfg.click_offset)
        
        # 兼容处理：若存在多模板列表，则保留 template_path 为列表首元素
        if isinstance(data.get("template_paths"), list):
            if data["template_paths"]:
                data["template_path"] = data["template_paths"][0]
            else:
                data["template_paths"] = []
        
        data["coordinate_offset"] = list(cfg.coordinate_offset)
        
        config_path = os.path.abspath(path or CONFIG_FILE)
        
        # 确保目录存在
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        
        # 同步保存
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        return config_path
        
    except Exception as e:
        print(f"同步保存配置失败: {e}")
        return None


def test_sync_save():
    """测试同步保存功能"""
    print("=== 测试同步配置保存 ===")
    
    try:
        # 加载原始配置
        config = load_config()
        original_hwnd = config.target_hwnd
        print(f"1. 原始HWND: {original_hwnd}")
        
        # 修改HWND
        test_hwnd = 777777777
        config.target_hwnd = test_hwnd
        print(f"2. 修改HWND为: {test_hwnd}")
        
        # 同步保存
        saved_path = save_config_sync(config)
        print(f"3. 保存到: {saved_path}")
        
        # 重新加载
        new_config = load_config()
        final_hwnd = new_config.target_hwnd
        print(f"4. 重新加载HWND: {final_hwnd}")
        
        # 验证
        if final_hwnd == test_hwnd:
            print("✓ 同步保存测试通过")
            return True
        else:
            print("✗ 同步保存测试失败")
            return False
            
    except Exception as e:
        print(f"同步保存测试失败: {e}")
        return False


def test_auto_hwnd_update_with_sync_save():
    """测试使用同步保存的自动HWND更新"""
    print("\n=== 测试自动HWND更新（同步保存）===")
    
    try:
        from auto_approve.auto_hwnd_updater import AutoHWNDUpdater
        from PySide6 import QtWidgets, QtCore
        
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
                """自动HWND更新处理（使用同步保存）"""
                try:
                    print(f"收到HWND更新信号: {hwnd}")
                    
                    # 更新配置中的目标HWND
                    self.cfg.target_hwnd = hwnd
                    
                    # 使用同步保存到文件
                    saved_path = save_config_sync(self.cfg)
                    print(f"配置已同步保存到文件: {saved_path}")
                    
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
        print(f"1. 原始HWND: {original_hwnd}")
        
        # 创建设置对话框
        from auto_approve.settings_dialog import SettingsDialog
        test_app.settings_dlg = SettingsDialog()
        dialog_original_hwnd = test_app.settings_dlg.sb_target_hwnd.value()
        print(f"2. 对话框原始HWND: {dialog_original_hwnd}")
        
        # 启动自动更新器
        test_app.auto_hwnd_updater.start()
        
        # 模拟智能查找器找到窗口
        test_hwnd = 888888888
        print(f"3. 模拟找到窗口: {test_hwnd}")
        test_app.auto_hwnd_updater._on_smart_process_found(test_hwnd, "Code.exe", "Test Window")
        
        # 等待处理
        import time
        time.sleep(0.5)
        
        # 检查结果
        final_config = load_config()
        final_dialog_hwnd = test_app.settings_dlg.sb_target_hwnd.value()
        
        print(f"4. 最终结果:")
        print(f"   - 配置文件HWND: {final_config.target_hwnd}")
        print(f"   - 对话框HWND: {final_dialog_hwnd}")
        
        # 停止
        test_app.auto_hwnd_updater.stop()
        test_app.settings_dlg.close()
        
        # 验证
        success = (final_config.target_hwnd == test_hwnd and 
                 final_dialog_hwnd == test_hwnd)
        
        if success:
            print("✓ 自动HWND更新测试通过")
        else:
            print("✗ 自动HWND更新测试失败")
            
        return success
        
    except Exception as e:
        print(f"自动HWND更新测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主测试函数"""
    print("测试配置保存和自动HWND更新\n")
    
    try:
        # 运行测试
        test_results = []
        
        test_results.append(test_sync_save())
        test_results.append(test_auto_hwnd_update_with_sync_save())
        
        # 汇总结果
        print(f"\n=== 测试结果汇总 ===")
        passed = sum(test_results)
        total = len(test_results)
        print(f"通过测试: {passed}/{total}")
        
        if passed == total:
            print("\n🎉 所有测试通过！")
            print("自动HWND更新功能修复成功：")
            print("1. 配置文件正确保存")
            print("2. 自动更新器正确更新配置")
            print("3. 设置对话框正确显示更新")
        else:
            print("\n❌ 部分测试失败")
            
    except Exception as e:
        print(f"测试过程中发生异常: {e}")
        return False
    
    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)