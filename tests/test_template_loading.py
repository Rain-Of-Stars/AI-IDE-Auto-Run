#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试模板立即保存和加载功能
验证模板保存后能够立即被扫描器识别和使用
"""

import os
import sys
import time
import json
import tempfile
import shutil
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from PySide6 import QtWidgets, QtCore
from auto_approve.config_manager import AppConfig, ROI
from utils.memory_template_manager import get_template_manager
from workers.scanner_process import _load_templates_from_paths


class TemplateLoadingTest:
    """模板加载测试类"""
    
    def __init__(self):
        self.test_passed = 0
        self.test_failed = 0
        self.template_manager = get_template_manager()
        
    def log(self, message: str, level: str = "INFO"):
        """日志输出"""
        print(f"[{level}] {message}")
        
    def create_test_template(self, size: tuple = (50, 50), color: tuple = (255, 0, 0)) -> str:
        """创建测试模板图片"""
        import numpy as np
        from PIL import Image
        
        # 创建纯色图片
        img_array = np.full((*size, 3), color, dtype=np.uint8)
        img = Image.fromarray(img_array)
        
        # 保存到临时文件
        temp_file = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
        img.save(temp_file.name)
        temp_file.close()
        
        return temp_file.name
        
    def test_memory_template_loading(self):
        """测试内存模板管理器加载功能"""
        self.log("开始测试内存模板管理器加载功能")
        
        try:
            # 创建测试模板
            template_path = self.create_test_template()
            self.log(f"创建测试模板: {template_path}")
            
            # 测试加载到内存
            loaded_count = self.template_manager.load_templates([template_path], force_reload=True)
            
            if loaded_count > 0:
                self.log(f"成功加载 {loaded_count} 个模板到内存")
                
                # 验证可以从内存获取
                templates = self.template_manager.get_templates([template_path])
                if templates and len(templates) > 0:
                    self.log("模板成功从内存获取")
                    self.test_passed += 1
                else:
                    self.log("无法从内存获取模板", "ERROR")
                    self.test_failed += 1
            else:
                self.log("模板加载失败", "ERROR")
                self.test_failed += 1
                
        except Exception as e:
            self.log(f"内存模板加载测试失败: {e}", "ERROR")
            self.test_failed += 1
        finally:
            # 清理临时文件
            if 'template_path' in locals() and os.path.exists(template_path):
                os.unlink(template_path)
                
    def test_scanner_template_loading(self):
        """测试扫描器模板加载功能"""
        self.log("开始测试扫描器模板加载功能")
        
        try:
            # 创建测试模板
            template_path = self.create_test_template(color=(0, 255, 0))
            self.log(f"创建测试模板: {template_path}")
            
            # 测试扫描器加载
            templates = _load_templates_from_paths([template_path])
            
            if templates and len(templates) > 0:
                self.log(f"扫描器成功加载 {len(templates)} 个模板")
                
                # 验证模板数据格式
                template_data, template_size = templates[0]
                import numpy as np
                if isinstance(template_data, np.ndarray) and len(template_size) == 2:
                    self.log("模板数据格式正确")
                    self.test_passed += 1
                else:
                    self.log("模板数据格式错误", "ERROR")
                    self.test_failed += 1
            else:
                self.log("扫描器模板加载失败", "ERROR")
                self.test_failed += 1
                
        except Exception as e:
            self.log(f"扫描器模板加载测试失败: {e}", "ERROR")
            self.test_failed += 1
        finally:
            # 清理临时文件
            if 'template_path' in locals() and os.path.exists(template_path):
                os.unlink(template_path)
                
    def test_template_reload_after_save(self):
        """测试模板保存后立即重新加载功能"""
        self.log("开始测试模板保存后立即重新加载功能")
        
        try:
            # 模拟设置对话框中的模板保存流程
            import tempfile
            import shutil
            from datetime import datetime
            
            # 创建测试模板
            template_path = self.create_test_template(color=(0, 0, 255))
            
            # 模拟 assets/images 目录
            assets_dir = project_root / "assets" / "images"
            assets_dir.mkdir(parents=True, exist_ok=True)
            
            # 生成模板文件名（模仿 settings_dialog.py 的逻辑）
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')[:-3]
            template_name = f"template_{timestamp}.png"
            target_path = assets_dir / template_name
            
            self.log(f"模拟保存模板到: {target_path}")
            
            # 复制模板文件到 assets 目录
            shutil.copy2(template_path, target_path)
            
            # 模拟立即加载到内存（模仿 settings_dialog.py 的逻辑）
            loaded_count = self.template_manager.load_templates([str(target_path)], force_reload=True)
            
            if loaded_count > 0:
                self.log(f"模板保存后立即加载成功: {loaded_count} 个模板")
                
                # 验证扫描器可以使用新模板
                templates = _load_templates_from_paths([str(target_path)])
                if templates and len(templates) > 0:
                    self.log("扫描器可以立即使用新保存的模板")
                    self.test_passed += 1
                else:
                    self.log("扫描器无法使用新保存的模板", "ERROR")
                    self.test_failed += 1
            else:
                self.log("模板立即加载失败", "ERROR")
                self.test_failed += 1
                
        except Exception as e:
            self.log(f"模板立即重新加载测试失败: {e}", "ERROR")
            self.test_failed += 1
        finally:
            # 清理文件
            if 'template_path' in locals() and os.path.exists(template_path):
                os.unlink(template_path)
            if 'target_path' in locals() and target_path.exists():
                target_path.unlink()
                
    def test_config_update_mechanism(self):
        """测试配置更新机制"""
        self.log("开始测试配置更新机制")
        
        try:
            # 创建模拟配置
            config = AppConfig(
                template_path="test_template.png",
                template_paths=["test_template.png", "test_template2.png"],
                monitor_index=0,
                roi=ROI(x=0, y=0, w=100, h=100),
                interval_ms=1000,
                threshold=0.8,
                cooldown_s=1.0,
                enable_logging=True,
                enable_notifications=True,
                grayscale=False,
                multi_scale=False,
                scales=[1.0],
                click_offset=(0, 0),
                min_detections=1,
                auto_start_scan=False,
                debug_mode=False,
                save_debug_images=False,
                debug_image_dir="debug_images",
                enable_coordinate_correction=False,
                coordinate_offset=(0, 0),
                enhanced_window_finding=False,
                click_method="pyautogui",
                verify_window_before_click=False,
                coordinate_transform_mode="direct",
                enable_multi_screen_polling=False,
                screen_polling_interval_ms=1000,
                capture_backend="window",
                use_monitor=False,
                target_hwnd=0,
                target_process="",
                process_partial_match=False,
                fps_max=30,
                capture_timeout_ms=1000,
                restore_minimized_noactivate=False,
                restore_minimized_after_capture=False,
                enable_electron_optimization=False,
                include_cursor=False,
                window_border_required=False,
                screen_border_required=False,
                border_required=False,
                auto_update_hwnd_by_process=False,
                auto_update_hwnd_interval_ms=5000
            )
            
            # 创建测试模板文件
            template1_path = self.create_test_template(color=(255, 255, 0))
            template2_path = self.create_test_template(color=(255, 0, 255))
            
            # 更新配置中的模板路径
            config.template_path = template1_path
            config.template_paths = [template1_path, template2_path]
            
            self.log(f"测试配置更新，模板路径: {config.template_paths}")
            
            # 模拟配置更新流程
            templates = _load_templates_from_paths(config.template_paths)
            
            if templates and len(templates) == 2:
                self.log(f"配置更新后成功加载 {len(templates)} 个模板")
                self.test_passed += 1
            else:
                self.log(f"配置更新后模板加载失败，期望2个，实际{len(templates) if templates else 0}个", "ERROR")
                self.test_failed += 1
                
        except Exception as e:
            self.log(f"配置更新机制测试失败: {e}", "ERROR")
            self.test_failed += 1
        finally:
            # 清理临时文件
            if 'template1_path' in locals() and os.path.exists(template1_path):
                os.unlink(template1_path)
            if 'template2_path' in locals() and os.path.exists(template2_path):
                os.unlink(template2_path)
                
    def run_all_tests(self):
        """运行所有测试"""
        self.log("开始运行模板立即保存和加载功能测试")
        print("=" * 60)
        
        # 运行各个测试
        self.test_memory_template_loading()
        print()
        
        self.test_scanner_template_loading()
        print()
        
        self.test_template_reload_after_save()
        print()
        
        self.test_config_update_mechanism()
        print()
        
        # 输出测试结果
        print("=" * 60)
        self.log(f"测试完成: 通过 {self.test_passed}, 失败 {self.test_failed}")
        
        if self.test_failed == 0:
            self.log("所有测试通过！模板立即保存和加载功能正常", "SUCCESS")
            return 0
        else:
            self.log(f"有 {self.test_failed} 个测试失败", "ERROR")
            return 1


def main():
    """主函数"""
    # 设置UTF-8编码
    import locale
    locale.setlocale(locale.LC_ALL, '')
    
    # 创建Qt应用（某些测试可能需要Qt环境）
    app = QtWidgets.QApplication(sys.argv)
    
    # 运行测试
    tester = TemplateLoadingTest()
    exit_code = tester.run_all_tests()
    
    sys.exit(exit_code)


if __name__ == "__main__":
    main()