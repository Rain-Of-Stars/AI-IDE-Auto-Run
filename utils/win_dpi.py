# -*- coding: utf-8 -*-
"""
Windows DPI 感知和坐标转换工具

提供 Per Monitor V2 DPI 感知设置和像素坐标与 DIP (Device Independent Pixels) 
之间的转换功能，确保在不同 DPI 缩放下的坐标一致性。
此外，提供基于系统DPI/分辨率的早期屏幕缩放因子计算与环境变量注入，
用于在创建Qt应用之前设置 QT_SCREEN_SCALE_FACTORS，以尽量保持物理观感一致。
"""

from __future__ import annotations
import os
import ctypes
from typing import Tuple, Optional
from ctypes import wintypes

# Windows API
user32 = ctypes.windll.user32
shcore = ctypes.windll.shcore
kernel32 = ctypes.windll.kernel32

from auto_approve.logger_manager import get_logger

# DPI 感知级别常量
DPI_AWARENESS_INVALID = -1
DPI_AWARENESS_UNAWARE = 0
DPI_AWARENESS_SYSTEM_AWARE = 1
DPI_AWARENESS_PER_MONITOR_AWARE = 2

# Process DPI Awareness Context 常量
DPI_AWARENESS_CONTEXT_UNAWARE = -1
DPI_AWARENESS_CONTEXT_SYSTEM_AWARE = -2
DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE = -3
DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = -4
DPI_AWARENESS_CONTEXT_UNAWARE_GDISCALED = -5

# Monitor DPI Type
MDT_EFFECTIVE_DPI = 0
MDT_ANGULAR_DPI = 1
MDT_RAW_DPI = 2

# 标准 DPI 值
STANDARD_DPI = 96


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long)
    ]


# MONITORINFOEX 结构体，用于枚举显示器并获取其矩形与设备名
# 参考 Win32 API: GetMonitorInfoW
class MONITORINFOEXW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("rcMonitor", RECT),
        ("rcWork", RECT),
        ("dwFlags", wintypes.DWORD),
        ("szDevice", wintypes.WCHAR * 32),  # CCHDEVICENAME = 32
    ]


def set_process_dpi_awareness() -> bool:
    """
    设置进程为 Per Monitor V2 DPI 感知
    
    应在程序启动早期调用，最好在导入 Qt 之前。
    
    Returns:
        bool: 设置是否成功
    """
    logger = get_logger()
    
    try:
        # 尝试设置 Per Monitor V2 (Windows 10 1703+)
        if hasattr(user32, 'SetProcessDpiAwarenessContext'):
            result = user32.SetProcessDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2)
            if result:
                logger.info("已设置 Per Monitor V2 DPI 感知")
                return True
            else:
                logger.warning("Per Monitor V2 DPI 感知设置失败，尝试 Per Monitor V1")
                
        # 回退到 Per Monitor V1 (Windows 8.1+)
        if hasattr(shcore, 'SetProcessDpiAwareness'):
            try:
                shcore.SetProcessDpiAwareness(DPI_AWARENESS_PER_MONITOR_AWARE)
                logger.info("已设置 Per Monitor V1 DPI 感知")
                return True
            except OSError as e:
                if e.winerror == -2147024891:  # E_ACCESSDENIED
                    logger.info("DPI 感知已被设置（可能由其他组件设置）")
                    return True
                logger.warning(f"Per Monitor V1 DPI 感知设置失败: {e}")
                
        # 最后回退到系统 DPI 感知
        if hasattr(user32, 'SetProcessDPIAware'):
            result = user32.SetProcessDPIAware()
            if result:
                logger.info("已设置系统 DPI 感知")
                return True
            else:
                logger.warning("系统 DPI 感知设置失败")
                
    except Exception as e:
        logger.error(f"DPI 感知设置异常: {e}")
        
    logger.warning("所有 DPI 感知设置方法都失败，将使用默认设置")
    return False


def get_dpi_for_window(hwnd: int) -> Tuple[int, int]:
    """
    获取窗口的 DPI 值
    
    Args:
        hwnd: 窗口句柄
        
    Returns:
        Tuple[int, int]: (dpi_x, dpi_y)，失败返回 (96, 96)
    """
    try:
        # Windows 10 1607+ 方法
        if hasattr(user32, 'GetDpiForWindow'):
            dpi = user32.GetDpiForWindow(hwnd)
            if dpi > 0:
                return (dpi, dpi)
                
        # Windows 8.1+ 方法
        if hasattr(shcore, 'GetDpiForMonitor'):
            hmonitor = user32.MonitorFromWindow(hwnd, 2)  # MONITOR_DEFAULTTONEAREST
            if hmonitor:
                dpi_x = wintypes.UINT()
                dpi_y = wintypes.UINT()
                if shcore.GetDpiForMonitor(hmonitor, MDT_EFFECTIVE_DPI, 
                                         ctypes.byref(dpi_x), ctypes.byref(dpi_y)) == 0:
                    return (dpi_x.value, dpi_y.value)
                    
        # 回退到系统 DPI
        hdc = user32.GetDC(hwnd)
        if hdc:
            try:
                dpi_x = ctypes.windll.gdi32.GetDeviceCaps(hdc, 88)  # LOGPIXELSX
                dpi_y = ctypes.windll.gdi32.GetDeviceCaps(hdc, 90)  # LOGPIXELSY
                return (dpi_x, dpi_y)
            finally:
                user32.ReleaseDC(hwnd, hdc)
                
    except Exception as e:
        get_logger().warning(f"获取窗口 DPI 失败: {e}")
        
    return (STANDARD_DPI, STANDARD_DPI)


def get_dpi_for_monitor(hmonitor: int) -> Tuple[int, int]:
    """
    获取显示器的 DPI 值
    
    Args:
        hmonitor: 显示器句柄
        
    Returns:
        Tuple[int, int]: (dpi_x, dpi_y)，失败返回 (96, 96)
    """
    try:
        if hasattr(shcore, 'GetDpiForMonitor'):
            dpi_x = wintypes.UINT()
            dpi_y = wintypes.UINT()
            if shcore.GetDpiForMonitor(hmonitor, MDT_EFFECTIVE_DPI,
                                     ctypes.byref(dpi_x), ctypes.byref(dpi_y)) == 0:
                return (dpi_x.value, dpi_y.value)
    except Exception as e:
        get_logger().warning(f"获取显示器 DPI 失败: {e}")
        
    return (STANDARD_DPI, STANDARD_DPI)


def get_system_dpi() -> Tuple[int, int]:
    """
    获取系统 DPI 值
    
    Returns:
        Tuple[int, int]: (dpi_x, dpi_y)
    """
    try:
        hdc = user32.GetDC(0)
        if hdc:
            try:
                dpi_x = ctypes.windll.gdi32.GetDeviceCaps(hdc, 88)  # LOGPIXELSX
                dpi_y = ctypes.windll.gdi32.GetDeviceCaps(hdc, 90)  # LOGPIXELSY
                return (dpi_x, dpi_y)
            finally:
                user32.ReleaseDC(0, hdc)
    except Exception:
        pass
        
    return (STANDARD_DPI, STANDARD_DPI)


def pixels_to_dip(pixels: int, dpi: int) -> int:
    """
    像素转换为 DIP (Device Independent Pixels)
    
    Args:
        pixels: 像素值
        dpi: DPI 值
        
    Returns:
        int: DIP 值
    """
    return round(pixels * STANDARD_DPI / dpi)


def dip_to_pixels(dip: int, dpi: int) -> int:
    """
    DIP 转换为像素
    
    Args:
        dip: DIP 值
        dpi: DPI 值
        
    Returns:
        int: 像素值
    """
    return round(dip * dpi / STANDARD_DPI)


def convert_point_to_dip(x: int, y: int, hwnd: int) -> Tuple[int, int]:
    """
    将屏幕像素坐标转换为 DIP 坐标
    
    Args:
        x, y: 屏幕像素坐标
        hwnd: 参考窗口句柄
        
    Returns:
        Tuple[int, int]: DIP 坐标
    """
    dpi_x, dpi_y = get_dpi_for_window(hwnd)
    return (pixels_to_dip(x, dpi_x), pixels_to_dip(y, dpi_y))


def convert_point_to_pixels(x: int, y: int, hwnd: int) -> Tuple[int, int]:
    """
    将 DIP 坐标转换为屏幕像素坐标
    
    Args:
        x, y: DIP 坐标
        hwnd: 参考窗口句柄
        
    Returns:
        Tuple[int, int]: 屏幕像素坐标
    """
    dpi_x, dpi_y = get_dpi_for_window(hwnd)
    return (dip_to_pixels(x, dpi_x), dip_to_pixels(y, dpi_y))


def get_scaling_factor(hwnd: int) -> Tuple[float, float]:
    """
    获取窗口的缩放因子
    
    Args:
        hwnd: 窗口句柄
        
    Returns:
        Tuple[float, float]: (scale_x, scale_y)
    """
    dpi_x, dpi_y = get_dpi_for_window(hwnd)
    return (dpi_x / STANDARD_DPI, dpi_y / STANDARD_DPI)


def logical_to_physical_point(hwnd: int, x: int, y: int) -> Tuple[int, int]:
    """
    逻辑坐标转物理坐标（考虑 DPI 缩放）
    
    Args:
        hwnd: 窗口句柄
        x, y: 逻辑坐标
        
    Returns:
        Tuple[int, int]: 物理坐标
    """
    try:
        if hasattr(user32, 'LogicalToPhysicalPointForPerMonitorDPI'):
            point = POINT(x, y)
            if user32.LogicalToPhysicalPointForPerMonitorDPI(hwnd, ctypes.byref(point)):
                return (point.x, point.y)
    except Exception:
        pass
        
    # 回退到手动计算
    scale_x, scale_y = get_scaling_factor(hwnd)
    return (round(x * scale_x), round(y * scale_y))


def physical_to_logical_point(hwnd: int, x: int, y: int) -> Tuple[int, int]:
    """
    物理坐标转逻辑坐标（考虑 DPI 缩放）
    
    Args:
        hwnd: 窗口句柄
        x, y: 物理坐标
        
    Returns:
        Tuple[int, int]: 逻辑坐标
    """
    try:
        if hasattr(user32, 'PhysicalToLogicalPointForPerMonitorDPI'):
            point = POINT(x, y)
            if user32.PhysicalToLogicalPointForPerMonitorDPI(hwnd, ctypes.byref(point)):
                return (point.x, point.y)
    except Exception:
        pass
        
    # 回退到手动计算
    scale_x, scale_y = get_scaling_factor(hwnd)
    return (round(x / scale_x), round(y / scale_y))


def get_dpi_info_summary() -> dict:
    """
    获取 DPI 信息摘要，用于调试
    
    Returns:
        dict: DPI 信息摘要
    """
    system_dpi = get_system_dpi()
    
    # 获取当前进程的 DPI 感知级别
    awareness = "未知"
    try:
        if hasattr(user32, 'GetProcessDpiAwarenessContext'):
            context = user32.GetProcessDpiAwarenessContext(kernel32.GetCurrentProcess())
            if context == DPI_AWARENESS_CONTEXT_UNAWARE:
                awareness = "不感知"
            elif context == DPI_AWARENESS_CONTEXT_SYSTEM_AWARE:
                awareness = "系统感知"
            elif context == DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE:
                awareness = "Per Monitor V1"
            elif context == DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2:
                awareness = "Per Monitor V2"
    except Exception:
        pass
        
    return {
        'system_dpi': system_dpi,
        'system_scaling': (system_dpi[0] / STANDARD_DPI, system_dpi[1] / STANDARD_DPI),
        'dpi_awareness': awareness,
        'standard_dpi': STANDARD_DPI
    }


# -------------------- 早期设置：为 Qt 计算并注入屏幕缩放因子 --------------------

def _enumerate_monitors() -> list[dict]:
    """枚举系统显示器，返回包含句柄、分辨率信息的列表。

    返回的每个元素包含：
    - hmonitor: 显示器句柄
    - width/height: 像素分辨率宽高
    - device: 设备名（可用于调试）

    说明：
    - 仅依赖 Win32 API，不依赖 Qt；适合在 QApplication 创建前调用。
    - 遇到异常时尽量返回已获取到的结果，保证鲁棒性。
    """
    results: list[dict] = []

    MonitorEnumProc = ctypes.WINFUNCTYPE(
        wintypes.BOOL,  # 返回值 BOOL
        wintypes.HMONITOR,  # HMONITOR
        wintypes.HDC,       # HDC
        ctypes.POINTER(RECT),  # LPRECT
        wintypes.LPARAM     # LPARAM
    )

    def _callback(hmon, hdc, lprc, lparam):
        try:
            info = MONITORINFOEXW()
            info.cbSize = ctypes.sizeof(MONITORINFOEXW)
            if user32.GetMonitorInfoW(hmon, ctypes.byref(info)):
                width = info.rcMonitor.right - info.rcMonitor.left
                height = info.rcMonitor.bottom - info.rcMonitor.top
                results.append({
                    'hmonitor': int(ctypes.cast(hmon, ctypes.c_void_p).value or 0),
                    'width': int(width),
                    'height': int(height),
                    'left': int(info.rcMonitor.left),
                    'top': int(info.rcMonitor.top),
                    'device': info.szDevice,
                })
        except Exception:
            # 忽略单个显示器的异常，继续枚举
            pass
        return True

    try:
        cb = MonitorEnumProc(_callback)
        user32.EnumDisplayMonitors(0, 0, cb, 0)
    except Exception:
        # 兼容性：不同系统/权限下可能失败，返回已采集的数据
        pass

    # 尝试按几何位置排序（左到右，上到下），更贴近Qt的常见枚举顺序
    try:
        results.sort(key=lambda m: (m.get('left', 0), m.get('top', 0)))
    except Exception:
        pass
    return results


def _compute_scale_from_dpi(dpi: int, base: int = STANDARD_DPI, min_scale: float = 1.0) -> float:
    """根据DPI计算缩放因子，带最小值约束（纯函数，便于测试）。"""
    try:
        dpi = int(dpi)
        base = int(base) if base else STANDARD_DPI
        if dpi <= 0:
            return max(1.0, min_scale)
        return max(dpi / float(base), float(min_scale))
    except Exception:
        return max(1.0, float(min_scale))


def _compute_scale_from_height(height: int, base_height: int = 1080, min_scale: float = 1.0) -> float:
    """根据分辨率高度计算缩放因子，带最小值约束（纯函数，便于测试）。"""
    try:
        height = int(height)
        base_height = int(base_height) if base_height else 1080
        if height <= 0:
            return max(1.0, float(min_scale))
        return max(height / float(base_height), float(min_scale))
    except Exception:
        return max(1.0, float(min_scale))


def build_qt_screen_scale_factors(
    prefer: str = "dpi",
    base_dpi: int = STANDARD_DPI,
    base_height: int = 1080,
    min_scale: float = 1.0,
    fallback_to_height: bool = True,
    monitors: Optional[list[dict]] = None,
) -> str:
    """构建 QT_SCREEN_SCALE_FACTORS 的分号分隔字符串（纯函数入口）。

    参数：
    - prefer: "dpi" 或 "height"，控制首选的计算方式
    - base_dpi: DPI基准，通常为96
    - base_height: 分辨率高度基准，通常为1080
    - min_scale: 最小缩放因子；避免缩放过小导致界面过密
    - fallback_to_height: 当按DPI计算失败或不可用时，是否回退到按高度计算
    - monitors: 可选的显示器信息列表（测试用）；若为空则自动枚举

    返回：类似 "1.0;1.5;2.0" 的字符串；若无法获取则返回空串。
    """
    prefer = (prefer or "").strip().lower() or "dpi"
    if monitors is not None:
        mons = list(monitors)
        try:
            mons.sort(key=lambda m: (m.get('left', 0), m.get('top', 0)))
        except Exception:
            pass
    else:
        mons = _enumerate_monitors()
    if not mons:
        return ""

    factors: list[str] = []
    for m in mons:
        scale = None
        if prefer == "dpi":
            try:
                dpi_x, dpi_y = get_dpi_for_monitor(m.get('hmonitor', 0))
                # 取Y方向更贴合字体渲染
                scale = _compute_scale_from_dpi(dpi_y, base=base_dpi, min_scale=min_scale)
            except Exception:
                scale = None
        if scale is None and (prefer == "height" or fallback_to_height):
            # 按高度回退
            scale = _compute_scale_from_height(m.get('height', 0), base_height=base_height, min_scale=min_scale)
        # 兜底
        if scale is None:
            scale = max(1.0, float(min_scale))
        # 保留一位小数，符合常见缩放因子格式；并将极近的常见刻度对齐
        # 常见刻度：1.0, 1.25, 1.5, 1.75, 2.0
        try:
            snaps = [1.0, 1.25, 1.5, 1.75, 2.0]
            for s in snaps:
                if abs(scale - s) < 0.06:  # 容差
                    scale = s
                    break
        except Exception:
            pass
        factors.append(f"{scale:.1f}")

    return ";".join(factors)


def apply_qt_screen_scale_factors_early(env: Optional[dict] = None) -> Optional[str]:
    """在创建 Qt QApplication 之前计算并设置 QT_SCREEN_SCALE_FACTORS 环境变量。

    受以下环境变量控制（全部可选）：
    - AIIDE_ENABLE_QT_SCREEN_SCALE_FACTORS=1|true 开启后才会注入（默认关闭，避免影响现有行为）
    - AIIDE_SCREEN_SCALE_MODE=dpi|height 首选模式（默认 dpi）
    - AIIDE_DPI_BASE=96 DPI基准（默认96）
    - AIIDE_SCALE_BASE_HEIGHT=1080 高度基准（默认1080）
    - AIIDE_MIN_SCALE=1.0 最小缩放因子（默认1.0）

    返回：成功设置时返回计算出的字符串；否则返回 None。
    """
    e = env or os.environ  # type: ignore[name-defined]
    try:
        # 若已设置，尊重外部配置
        if e.get("QT_SCREEN_SCALE_FACTORS"):
            return None

        enabled = str(e.get("AIIDE_ENABLE_QT_SCREEN_SCALE_FACTORS", "0")).strip().lower() in ("1", "true", "yes", "on")
        if not enabled:
            return None

        prefer = str(e.get("AIIDE_SCREEN_SCALE_MODE", "dpi")).strip().lower() or "dpi"
        base_dpi = int(str(e.get("AIIDE_DPI_BASE", str(STANDARD_DPI))))
        base_height = int(str(e.get("AIIDE_SCALE_BASE_HEIGHT", "1080")))
        min_scale = float(str(e.get("AIIDE_MIN_SCALE", "1.0")))

        factors = build_qt_screen_scale_factors(
            prefer=prefer,
            base_dpi=base_dpi,
            base_height=base_height,
            min_scale=min_scale,
            fallback_to_height=True,
            monitors=None,
        )

        if factors:
            e["QT_SCREEN_SCALE_FACTORS"] = factors
            get_logger().info(f"已计算并设置 QT_SCREEN_SCALE_FACTORS={factors}")
            return factors
    except Exception as ex:
        try:
            get_logger().warning(f"计算 QT_SCREEN_SCALE_FACTORS 失败: {ex}")
        except Exception:
            pass
    return None
