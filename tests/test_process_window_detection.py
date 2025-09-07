# -*- coding: utf-8 -*-
"""
测试基于进程名称的窗口检测功能
验证移除窗口标题检测后，进程检测功能是否正常工作
"""
import sys
import os
import unittest
from unittest.mock import patch, MagicMock

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from capture.monitor_utils import find_window_by_process
from auto_approve.auto_hwnd_updater import AutoHWNDUpdater
from auto_approve.config_manager import AppConfig


class TestProcessWindowDetection(unittest.TestCase):
    """测试基于进程的窗口检测功能"""
    
    def setUp(self):
        """测试前准备"""
        self.config = AppConfig()
        self.config.target_process = "notepad.exe"
        self.config.process_partial_match = True
        self.config.auto_update_hwnd_by_process = True
        self.config.auto_update_hwnd_interval_ms = 1000
    
    def test_find_window_by_process_function_exists(self):
        """测试 find_window_by_process 函数是否存在"""
        self.assertTrue(callable(find_window_by_process))
    
    def test_find_window_by_process_with_valid_process(self):
        """测试使用有效进程名查找窗口"""
        # 模拟找到窗口的情况
        with patch('capture.monitor_utils.user32') as mock_user32, \
             patch('capture.monitor_utils.kernel32') as mock_kernel32, \
             patch('capture.monitor_utils.psapi') as mock_psapi:
            
            # 模拟枚举窗口
            mock_user32.EnumWindows.side_effect = lambda callback, param: callback(12345, param) and False
            mock_user32.IsWindowVisible.return_value = True
            mock_user32.GetWindowThreadProcessId.side_effect = lambda hwnd, pid_ptr: setattr(pid_ptr.contents, 'value', 1234)
            
            # 模拟打开进程和获取进程路径
            mock_kernel32.OpenProcess.return_value = 9999
            mock_psapi.GetModuleFileNameExW.side_effect = lambda proc, mod, buf, size: (
                setattr(buf, 'value', 'C:\\Windows\\System32\\notepad.exe'), True
            )[1]
            
            result = find_window_by_process("notepad.exe", True)
            
            # 验证结果
            self.assertIsNotNone(result)
            mock_user32.EnumWindows.assert_called_once()
    
    def test_find_window_by_process_not_found(self):
        """测试查找不存在的进程"""
        with patch('capture.monitor_utils.user32') as mock_user32:
            # 模拟没有找到匹配窗口
            mock_user32.EnumWindows.side_effect = lambda callback, param: True
            
            result = find_window_by_process("nonexistent.exe", True)
            
            # 验证返回 None
            self.assertIsNone(result)
    
    def test_auto_hwnd_updater_initialization(self):
        """测试自动HWND更新器初始化"""
        updater = AutoHWNDUpdater()
        
        # 验证初始状态
        self.assertFalse(updater.is_running())
        self.assertEqual(updater.get_current_hwnd(), 0)
    
    def test_auto_hwnd_updater_config_setting(self):
        """测试设置配置到自动HWND更新器"""
        updater = AutoHWNDUpdater()
        updater.set_config(self.config)
        
        # 验证配置设置正确
        self.assertEqual(updater._config.target_process, "notepad.exe")
        self.assertTrue(updater._config.process_partial_match)
        self.assertTrue(updater._config.auto_update_hwnd_by_process)
    
    @patch('capture.monitor_utils.find_window_by_process')
    def test_auto_hwnd_updater_process_detection(self, mock_find_window):
        """测试自动HWND更新器的进程检测功能"""
        # 模拟找到窗口
        mock_find_window.return_value = 54321
        
        updater = AutoHWNDUpdater()
        updater.set_config(self.config)
        
        # 手动触发一次更新（模拟定时器触发）
        updater._perform_update()
        
        # 验证调用了进程检测函数
        mock_find_window.assert_called_with("notepad.exe", True)
        
        # 验证HWND被更新
        self.assertEqual(updater.get_current_hwnd(), 54321)
    
    def test_config_no_window_title_fields(self):
        """测试配置中不再包含窗口标题相关字段"""
        config = AppConfig()
        
        # 验证不再有窗口标题相关字段
        self.assertFalse(hasattr(config, 'target_window_title'))
        self.assertFalse(hasattr(config, 'window_title_partial_match'))
        
        # 验证仍有进程相关字段
        self.assertTrue(hasattr(config, 'target_process'))
        self.assertTrue(hasattr(config, 'process_partial_match'))
        self.assertTrue(hasattr(config, 'auto_update_hwnd_by_process'))
    
    def test_find_window_by_title_function_removed(self):
        """测试 find_window_by_title 函数已被移除"""
        try:
            from capture.monitor_utils import find_window_by_title
            self.fail("find_window_by_title 函数应该已被移除")
        except ImportError:
            # 正确的情况：函数已不存在
            pass


class TestProcessDetectionIntegration(unittest.TestCase):
    """集成测试：验证整个进程检测流程"""
    
    def setUp(self):
        """测试前准备"""
        self.config = AppConfig()
        self.config.target_process = "Code.exe"  # VS Code进程
        self.config.process_partial_match = True
        self.config.auto_update_hwnd_by_process = True
    
    @patch('capture.monitor_utils.find_window_by_process')
    def test_end_to_end_process_detection(self, mock_find_window):
        """端到端测试进程检测流程"""
        # 模拟找到VS Code窗口
        mock_find_window.return_value = 98765
        
        # 创建自动更新器并设置配置
        updater = AutoHWNDUpdater()
        updater.set_config(self.config)
        
        # 记录信号触发
        signal_received = []
        updater.hwnd_updated.connect(lambda hwnd, proc: signal_received.append((hwnd, proc)))
        
        # 执行更新
        updater._perform_update()
        
        # 验证结果
        self.assertEqual(updater.get_current_hwnd(), 98765)
        self.assertEqual(len(signal_received), 1)
        self.assertEqual(signal_received[0], (98765, "Code.exe"))
        
        # 验证调用参数正确
        mock_find_window.assert_called_with("Code.exe", True)


def run_process_detection_tests():
    """运行进程检测测试"""
    print("=" * 60)
    print("运行基于进程名称的窗口检测功能测试")
    print("=" * 60)
    
    # 创建测试套件
    suite = unittest.TestSuite()
    
    # 添加测试用例
    suite.addTest(unittest.makeSuite(TestProcessWindowDetection))
    suite.addTest(unittest.makeSuite(TestProcessDetectionIntegration))
    
    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # 输出结果摘要
    print("\n" + "=" * 60)
    print(f"测试结果摘要:")
    print(f"总测试数: {result.testsRun}")
    print(f"成功: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"失败: {len(result.failures)}")
    print(f"错误: {len(result.errors)}")
    print("=" * 60)
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_process_detection_tests()
    sys.exit(0 if success else 1)
