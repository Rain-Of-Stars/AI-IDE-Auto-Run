# AI IDE 自动化工具

## 项目简介

这是一个基于 PySide6 开发的 AI IDE 自动化工具，主要功能是自动检测和点击特定界面元素，实现自动化操作。该工具支持多显示器、高性能图像识别、智能窗口定位等功能。

## 主要特性

- **智能图像识别**: 基于 OpenCV 的高性能模板匹配算法
- **多显示器支持**: 支持多屏幕环境下的窗口捕获和操作
- **高性能架构**: 多线程设计，IO密集型任务使用QThreadPool，CPU密集型任务使用multiprocessing
- **智能窗口定位**: 支持多种窗口查找策略，包括进程名、窗口标题、类名等
- **自动恢复机制**: 具备窗口丢失后的自动恢复功能
- **配置化**: 支持通过配置文件灵活调整各种参数
- **内存优化**: 内置内存管理和性能监控
- **高DPI支持**: 完整的高DPI显示器适配

## 系统要求

- **操作系统**: Windows 10/11
- **Python版本**: 3.12.11
- **内存**: 推荐4GB以上
- **显示器**: 支持多显示器配置

## 安装说明

1. 克隆项目到本地
2. 安装依赖包：
```bash
pip install -r requirements.txt
```

## 项目结构

```
AI_IDE_Auto_Run_github_main_V4.2/
├── main_auto_approve_refactored.py    # 主程序入口
├── config.json                        # 配置文件
├── requirements.txt                   # 依赖包列表
├── assets/                            # 资源文件
│   ├── icons/                         # 图标文件
│   ├── images/                        # 模板图片
│   └── styles/                        # 样式文件
├── auto_approve/                      # 核心功能模块
├── capture/                           # 屏幕捕获模块
├── tools/                             # 工具模块
├── utils/                             # 工具类
│   ├── memory/                        # 内存管理
│   └── windows/                       # Windows系统工具
├── workers/                           # 工作线程
└── tests/                             # 测试文件
```

## 配置说明
### 基础配置

#### 模板图片配置
- `template_path`: 当前使用的模板图片路径
- `template_paths`: 模板图片路径列表，支持多模板切换
- `monitor_index`: 指定监视器索引（0为主显示器，1为副显示器等）

#### 感兴趣区域（ROI）
- `roi`: 感兴趣区域设置，格式为 `{"x": 0, "y": 0, "w": 0, "h": 0}`
  - `x`: 区域左上角X坐标
  - `y`: 区域左上角Y坐标  
  - `w`: 区域宽度
  - `h`: 区域高度
  - 当w和h为0时，表示全屏检测

#### 检测参数
- `interval_ms`: 检测间隔时间（毫秒），默认500ms
- `threshold`: 匹配阈值（0-1），值越高要求匹配越精确，默认0.8
- `cooldown_s`: 操作冷却时间（秒），防止重复点击，默认3.0秒
- `min_detections`: 最小检测次数，用于提高检测准确性

### 图像处理配置

#### 图像预处理
- `grayscale`: 是否启用灰度处理，默认true（可提高匹配速度）
- `multi_scale`: 是否启用多尺度匹配，默认true（提高匹配成功率）
- `scales`: 多尺度匹配的缩放比例列表，默认[1.0]

#### 点击配置
- `click_offset`: 点击偏移量，格式为[x_offset, y_offset]
- `click_method`: 点击方式，可选值：
  - "message": 使用消息发送点击
  - "sendmessage": 使用SendMessage API
  - "postmessage": 使用PostMessage API

### 窗口管理配置

#### 目标窗口
- `target_hwnd`: 目标窗口句柄（自动更新）
- `target_process`: 目标进程名，如"Code.exe"
- `process_partial_match`: 是否启用进程名部分匹配，默认true

#### 窗口查找策略
- `finder_strategies`: 窗口查找策略配置
  - `process_name`: 使用进程名查找
  - `process_path`: 使用进程路径查找
  - `window_title`: 使用窗口标题查找
  - `class_name`: 使用窗口类名查找
  - `fuzzy_match`: 启用模糊匹配

#### 窗口状态管理
- `verify_window_before_click`: 点击前是否验证窗口，默认false
- `restore_minimized_noactivate`: 恢复最小化窗口但不激活，默认true
- `restore_minimized_after_capture`: 捕获后恢复最小化窗口，默认false

### 捕获配置

#### 捕获方式
- `capture_backend`: 捕获后端，可选值：
  - "window": 窗口捕获
  - "screen": 屏幕捕获
- `use_monitor`: 是否使用监视器模式，默认false
- `fps_max`: 最大帧率，默认1
- `capture_timeout_ms`: 捕获超时时间，默认2000ms

#### 多显示器支持
- `enable_multi_screen_polling`: 启用多屏幕轮询，默认true
- `screen_polling_interval_ms`: 屏幕轮询间隔，默认5000ms

#### 捕获优化
- `include_cursor`: 是否包含鼠标光标，默认false
- `border_required`: 是否需要边框，默认true
- `window_border_required`: 是否需要窗口边框，默认true
- `screen_border_required`: 是否需要屏幕边框，默认false

### 性能优化配置

#### 智能查找器
- `enable_smart_finder`: 启用智能查找器，默认true
- `smart_finder_base_interval`: 基础查找间隔，默认1.0秒
- `smart_finder_max_interval`: 最大查找间隔，默认30.0秒
- `smart_finder_min_interval`: 最小查找间隔，默认0.5秒

#### 自动恢复
- `enable_auto_recovery`: 启用自动恢复，默认true
- `max_recovery_attempts`: 最大恢复尝试次数，默认5次
- `recovery_cooldown`: 恢复冷却时间，默认10.0秒

#### 坐标转换
- `enable_coordinate_correction`: 启用坐标修正，默认true
- `coordinate_offset`: 坐标偏移量，格式为[x, y]
- `coordinate_transform_mode`: 坐标转换模式，默认"auto"

### 系统集成配置

#### Electron应用优化
- `enable_electron_optimization`: 启用Electron应用优化，默认false
- `dirty_region_mode`: 脏区域模式，默认为空

#### 自动更新
- `auto_update_hwnd_by_process`: 自动根据进程更新窗口句柄，默认true
- `auto_update_hwnd_interval_ms`: 自动更新间隔，默认5000ms

### 调试配置

#### 调试选项
- `enable_logging`: 启用日志记录，默认false
- `enable_notifications`: 启用通知，默认true
- `debug_mode`: 调试模式，默认false
- `save_debug_images`: 保存调试图片，默认false
- `debug_image_dir`: 调试图片保存目录，默认"debug_images"

#### 高级选项
- `enhanced_window_finding`: 增强窗口查找，默认false
- `auto_start_scan`: 自动开始扫描，默认true

## 使用方法

1. 运行主程序：
```bash
python main_auto_approve_refactored.py
```

2. 程序启动后会自动最小化到系统托盘
3. 右键点击托盘图标可以打开设置菜单
4. 在设置中可以调整各项参数和选择模板图片

## 核心功能模块

### 图像识别
- 支持灰度匹配和多尺度匹配
- 可配置匹配阈值和感兴趣区域
- 支持多种图像预处理选项

### 窗口管理
- 智能窗口查找和定位
- 支持窗口状态恢复
- 自动更新窗口句柄

### 性能优化
- 内存使用监控和优化
- GUI响应性管理
- 性能分析和调优

### 错误处理
- 自动错误恢复机制
- 详细的日志记录
- 用户友好的错误提示

## 开发说明

### 代码结构
- 采用模块化设计，各功能模块分离
- 使用信号槽机制进行线程间通信
- 配置管理支持热重载

### 扩展开发
- 新增功能模块请放在相应目录
- 遵循现有的命名规范
- 添加相应的测试用例

## 注意事项

1. 使用前请确保目标程序已启动
2. 建议先在测试环境中验证配置
3. 长时间运行时注意内存使用情况
4. 多显示器环境下请正确配置监视器索引

## 故障排除

### 常见问题
- 窗口无法找到：检查进程名和窗口标题配置
- 识别率低：调整匹配阈值或更新模板图片
- 性能问题：检查检测间隔和内存使用情况

### 日志分析
程序运行时会生成详细日志，可通过日志分析问题原因。

## 许可证

本项目仅供学习和研究使用。

## 贡献指南

欢迎提交Issue和Pull Request来改进项目。

## 更新日志

### V5.0
- 重构多线程架构
- 优化性能和内存使用
- 增强窗口定位功能
- 改进错误处理机制