# -*- coding: utf-8 -*-
"""
WGC实时预览对话框
提供实时窗口捕获预览功能，方便用户验证WGC配置效果
"""

import time
from pathlib import Path
import numpy as np
import cv2
from PySide6 import QtWidgets, QtCore, QtGui
from typing import Optional


class WGCPreviewDialog(QtWidgets.QDialog):
    """WGC实时预览对话框"""
    
    def __init__(self, hwnd: int, parent=None, *, fps: int = 15, include_cursor: bool = False, border_required: bool = False):
        super().__init__(parent)
        self.hwnd = hwnd
        self.capture_manager = None
        self.timer = None
        self.is_capturing = False
        # 预览配置（从外部传入，确保与设置面板一致）
        self.preview_fps = max(1, min(int(fps), 60))
        self.include_cursor = bool(include_cursor)
        self.border_required = bool(border_required)

        # 共享帧缓存用户ID
        self.user_id = f"wgc_preview_{hwnd}_{int(time.time())}"
        
        self.setWindowTitle(f"WGC实时预览 - HWND: {hwnd}")
        self.resize(800, 600)
        self.setModal(True)
        
        self._setup_ui()
        self._setup_capture()
        
    def _setup_ui(self):
        """设置UI界面"""
        layout = QtWidgets.QVBoxLayout(self)
        
        # 顶部信息栏
        info_layout = QtWidgets.QHBoxLayout()
        
        self.info_label = QtWidgets.QLabel(f"目标窗口: HWND {self.hwnd}")
        self.info_label.setStyleSheet("font-weight: bold; color: #2F80ED;")
        info_layout.addWidget(self.info_label)
        
        info_layout.addStretch()
        
        self.fps_label = QtWidgets.QLabel("FPS: --")
        info_layout.addWidget(self.fps_label)
        
        self.size_label = QtWidgets.QLabel("尺寸: --")
        info_layout.addWidget(self.size_label)
        
        layout.addLayout(info_layout)
        
        # 预览区域
        self.preview_label = QtWidgets.QLabel()
        self.preview_label.setAlignment(QtCore.Qt.AlignCenter)
        self.preview_label.setMinimumSize(400, 300)
        self.preview_label.setStyleSheet("""
            QLabel {
                border: 2px solid #E0E0E0;
                background-color: #F5F5F5;
                border-radius: 4px;
            }
        """)
        self.preview_label.setText("正在初始化预览...")
        
        # 将预览标签放在滚动区域中
        scroll_area = QtWidgets.QScrollArea()
        scroll_area.setWidget(self.preview_label)
        scroll_area.setWidgetResizable(True)
        scroll_area.setAlignment(QtCore.Qt.AlignCenter)
        
        layout.addWidget(scroll_area, 1)
        
        # 控制按钮
        control_layout = QtWidgets.QHBoxLayout()
        
        self.start_btn = QtWidgets.QPushButton("开始预览")
        self.start_btn.clicked.connect(self._start_preview)
        control_layout.addWidget(self.start_btn)
        
        self.stop_btn = QtWidgets.QPushButton("停止预览")
        self.stop_btn.clicked.connect(self._stop_preview)
        self.stop_btn.setEnabled(False)
        control_layout.addWidget(self.stop_btn)
        
        control_layout.addStretch()
        
        self.save_btn = QtWidgets.QPushButton("保存当前帧")
        self.save_btn.clicked.connect(self._save_current_frame)
        self.save_btn.setEnabled(False)
        control_layout.addWidget(self.save_btn)
        
        close_btn = QtWidgets.QPushButton("关闭")
        close_btn.clicked.connect(self.accept)
        control_layout.addWidget(close_btn)
        
        layout.addLayout(control_layout)
        
        # 状态栏
        self.status_label = QtWidgets.QLabel("就绪")
        self.status_label.setStyleSheet("color: #666; font-size: 12px;")
        layout.addWidget(self.status_label)
        
        # 用于FPS计算
        self.frame_count = 0
        self.last_fps_time = time.time()
        self.current_frame = None
        
    def _setup_capture(self):
        """设置捕获管理器"""
        try:
            from capture import CaptureManager
            self.capture_manager = CaptureManager()
            
            # 配置参数：使用外部传入的光标/边框开关，确保与设置勾选一致
            self.capture_manager.configure(
                fps=self.preview_fps,  # 预览使用较低帧率
                include_cursor=self.include_cursor,
                border_required=self.border_required,
                restore_minimized=True
            )
            
            self.status_label.setText("捕获管理器初始化成功")
            
        except Exception as e:
            self.status_label.setText(f"初始化失败: {e}")
            QtWidgets.QMessageBox.critical(self, "错误", f"初始化捕获管理器失败: {e}")
    
    def _start_preview(self):
        """开始预览"""
        if not self.capture_manager:
            return

        # 禁用开始按钮，防止重复点击
        self.start_btn.setEnabled(False)
        self.status_label.setText("正在启动...")
        QtWidgets.QApplication.processEvents()

        try:
            # 打开窗口捕获 - 使用异步模式避免阻塞GUI
            success = self.capture_manager.open_window(self.hwnd, async_init=True, timeout=3.0)
            if not success:
                self.status_label.setText("启动失败")
                self.start_btn.setEnabled(True)
                QtWidgets.QMessageBox.warning(self, "失败", "无法启动窗口捕获，请检查窗口是否有效")
                return

            # 设置定时器
            self.timer = QtCore.QTimer()
            self.timer.timeout.connect(self._capture_frame)

            # 根据预览FPS设置定时器间隔
            interval = max(16, int(1000 / self.preview_fps))  # 最少16ms (约60FPS)
            self.timer.start(interval)

            self.is_capturing = True
            self.stop_btn.setEnabled(True)
            self.save_btn.setEnabled(True)

            self.status_label.setText("预览中...")

        except Exception as e:
            self.status_label.setText(f"启动失败: {e}")
            self.start_btn.setEnabled(True)
            QtWidgets.QMessageBox.critical(self, "错误", f"启动预览失败: {e}")
    
    def _stop_preview(self):
        """停止预览"""
        if self.timer:
            self.timer.stop()
            self.timer = None

        if self.capture_manager:
            # 释放共享帧缓存引用
            self.capture_manager.release_shared_frame(self.user_id)
            self.capture_manager.close()

        self.is_capturing = False
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.save_btn.setEnabled(False)

        self.status_label.setText("已停止")
        self.preview_label.setText("预览已停止")
    
    def _capture_frame(self):
        """捕获并显示一帧（使用共享帧缓存）"""
        if not self.capture_manager or not self.is_capturing:
            return

        try:
            # 添加超时保护，避免长时间阻塞
            import time
            start_time = time.time()

            # 优先使用共享帧缓存
            frame = self.capture_manager.get_shared_frame(self.user_id, "preview")
            if frame is None:
                # 如果共享缓存没有，尝试传统捕获（带超时）
                frame = self.capture_manager.capture_frame()
                if frame is None:
                    # 连续失败计数
                    if not hasattr(self, '_capture_fail_count'):
                        self._capture_fail_count = 0
                    self._capture_fail_count += 1

                    # 如果连续失败超过30次（约2秒），显示警告
                    if self._capture_fail_count > 30:
                        self.status_label.setText("捕获失败，请检查窗口状态")
                        self._capture_fail_count = 0  # 重置计数
                    return

            # 重置失败计数
            self._capture_fail_count = 0

            # 检查捕获耗时
            capture_time = (time.time() - start_time) * 1000
            if capture_time > 100:  # 超过100ms
                self.status_label.setText(f"捕获较慢: {capture_time:.1f}ms")

            self.current_frame = frame
            h, w = frame.shape[:2]

            # 更新尺寸信息
            self.size_label.setText(f"尺寸: {w}×{h}")

            # 计算FPS
            self.frame_count += 1
            current_time = time.time()
            if current_time - self.last_fps_time >= 1.0:
                fps = self.frame_count / (current_time - self.last_fps_time)
                self.fps_label.setText(f"FPS: {fps:.1f}")
                self.frame_count = 0
                self.last_fps_time = current_time

            # 转换为Qt图像并显示
            self._display_frame(frame)

        except Exception as e:
            self.status_label.setText(f"捕获错误: {e}")
            # 连续异常计数
            if not hasattr(self, '_exception_count'):
                self._exception_count = 0
            self._exception_count += 1

            # 如果连续异常超过10次，停止预览
            if self._exception_count > 10:
                self.status_label.setText("捕获异常过多，已停止预览")
                self._stop_preview()
    
    def _display_frame(self, frame):
        """显示帧到预览标签"""
        try:
            h, w = frame.shape[:2]
            
            # 确保图像数据连续
            if not frame.flags['C_CONTIGUOUS']:
                frame = np.ascontiguousarray(frame)
            
            # BGR转RGB
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # 创建QImage
            bytes_per_line = rgb.strides[0] if rgb.strides else w * 3
            qimg = QtGui.QImage(rgb.data, w, h, bytes_per_line, QtGui.QImage.Format_RGB888)
            
            if qimg.isNull():
                return
            
            # 创建像素图并缩放到合适大小
            pixmap = QtGui.QPixmap.fromImage(qimg)
            if pixmap.isNull():
                return
            
            # 缩放到预览标签大小，保持宽高比
            label_size = self.preview_label.size()
            scaled_pixmap = pixmap.scaled(
                label_size, 
                QtCore.Qt.KeepAspectRatio, 
                QtCore.Qt.SmoothTransformation
            )
            
            self.preview_label.setPixmap(scaled_pixmap)
            
        except Exception as e:
            self.status_label.setText(f"显示错误: {e}")
    
    def _save_current_frame(self):
        """保存当前帧 - 使用非阻塞I/O"""
        if self.current_frame is None:
            QtWidgets.QMessageBox.warning(self, "提示", "没有可保存的帧")
            return
        
        # 生成默认名称（不再写入磁盘，仅用于数据库键名）
        timestamp = int(time.time())
        default_filename = f"wgc_preview_capture_{timestamp}.png"
        filename = default_filename
        
        # 禁用保存按钮，防止重复点击
        self.save_btn.setEnabled(False)
        self.status_label.setText("正在保存图像...")
        QtWidgets.QApplication.processEvents()
        
        try:
            # 使用非阻塞I/O线程池保存图像（仅数据库）
            from workers.io_tasks import submit_image_save
            
            # 获取“扩展名”来确定质量设置（仅影响编码质量）
            file_extension = Path(filename).suffix.lower()
            quality = 95 if file_extension in ['.jpg', '.jpeg'] else 100
            
            def on_save_success(task_id, result):
                """保存成功的回调"""
                # 在主线程中更新UI
                QtCore.QTimer.singleShot(0, lambda: self._on_save_complete(True, result))
                
            def on_save_error(task_id, error_message, exception):
                """保存失败的回调"""  
                # 在主线程中更新UI
                QtCore.QTimer.singleShot(0, lambda: self._on_save_complete(False, error_message))
            
            # 提交非阻塞保存任务（保存到SQLite的images表）
            self.save_task_id = submit_image_save(
                self.current_frame,
                filename,
                quality,
                on_save_success,
                on_save_error
            )
            
        except Exception as e:
            # 回退：直接提示失败（不再进行磁盘写入）
            self.status_label.setText("保存失败")
            QtWidgets.QMessageBox.critical(self, "错误", f"保存失败: {e}")
    
    def _on_save_complete(self, success, result):
        """保存完成后的UI更新"""
        self.save_btn.setEnabled(True)
        
        if success:
            file_info = result
            file_size_mb = file_info['file_size'] / (1024 * 1024)
            dimensions = file_info['dimensions']
            self.status_label.setText(f"保存成功: {Path(default_filename).name}")
            QtWidgets.QMessageBox.information(
                self,
                "保存成功",
                f"图像已保存到数据库:\n{file_info['file_path']}\n\n"
                f"尺寸: {dimensions[0]}×{dimensions[1]}\n"
                f"大小: {file_size_mb:.2f} MB\n"
                f"质量: {file_info['quality']}\n"
                f"image_id: {file_info.get('image_id')}"
            )
        else:
            self.status_label.setText("保存失败")
            QtWidgets.QMessageBox.critical(self, "保存失败", f"保存图像时出错:\n{result}")
    
    # 取消磁盘回退保存逻辑
    
    def closeEvent(self, event):
        """关闭事件"""
        self._stop_preview()
        # 确保释放共享帧缓存引用
        if self.capture_manager:
            self.capture_manager.release_shared_frame(self.user_id)
        super().closeEvent(event)
    
    def resizeEvent(self, event):
        """窗口大小改变事件"""
        super().resizeEvent(event)
        # 如果有当前帧，重新显示以适应新尺寸
        if self.current_frame is not None:
            self._display_frame(self.current_frame)
