# -*- coding: utf-8 -*-
"""
捕获性能测试脚本
测试优化后的捕获性能
"""

import time
import sys
import os

# 添加项目路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from capture.capture_manager import CaptureManager
from auto_approve.logger_manager import get_logger

def test_capture_performance():
    """测试捕获性能"""
    logger = get_logger()
    
    # 创建捕获管理器
    capture_manager = CaptureManager()
    
    try:
        # 测试窗口捕获性能
        logger.info("开始测试窗口捕获性能...")
        
        # 使用当前窗口作为测试目标
        import ctypes
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        
        if hwnd:
            start_time = time.time()
            
            # 打开窗口捕获
            success = capture_manager.open_window(hwnd)
            if success:
                init_time = time.time() - start_time
                logger.info(f"窗口捕获初始化耗时: {init_time:.3f}秒")
                
                # 测试帧捕获性能
                frame_times = []
                for i in range(10):
                    frame_start = time.time()
                    frame = capture_manager.capture_frame()
                    frame_time = time.time() - frame_start
                    frame_times.append(frame_time)
                    
                    if frame is not None:
                        logger.info(f"第{i+1}帧捕获耗时: {frame_time:.3f}秒, 图像尺寸: {frame.shape}")
                    else:
                        logger.warning(f"第{i+1}帧捕获失败")
                    
                    # 短暂延迟，避免过快
                    time.sleep(0.1)
                
                # 计算平均性能
                avg_frame_time = sum(frame_times) / len(frame_times)
                successful_frames = sum(1 for t in frame_times if t < 1.0)  # 小于1秒认为成功
                
                logger.info(f"平均帧捕获耗时: {avg_frame_time:.3f}秒")
                logger.info(f"成功捕获帧数: {successful_frames}/{len(frame_times)}")
                logger.info(f"帧捕获成功率: {successful_frames/len(frame_times)*100:.1f}%")
                
                # 性能评估
                if avg_frame_time < 0.1:
                    logger.info("✅ 捕获性能优秀")
                elif avg_frame_time < 0.5:
                    logger.info("✅ 捕获性能良好")
                elif avg_frame_time < 1.0:
                    logger.info("⚠️  捕获性能一般")
                else:
                    logger.warning("❌ 捕获性能较差，需要进一步优化")
            else:
                logger.error("窗口捕获初始化失败")
        else:
            logger.error("无法获取前景窗口句柄")
            
    except Exception as e:
        logger.error(f"性能测试失败: {e}")
    finally:
        # 清理资源
        try:
            capture_manager.close()
        except:
            pass

if __name__ == "__main__":
    test_capture_performance()