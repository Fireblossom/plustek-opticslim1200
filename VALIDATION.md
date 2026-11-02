# 验证记录

日期：2026-11-02，Europe/Berlin。

## 已通过

- 实机 USB：Plustek OpticSlim 1200，VID `07b3`，PID `0413`，固件版本描述 `0501`。
- 从用户的关机状态 VirtualBox `xp.vdi` 只读提取原固件；大小 8192 字节，SHA-256 为 `70ce066ed6c3dc34733bd43a32a9b670ae89c99203c0bb49aac1639af96d0884`。虚拟磁盘未修改。
- Windows 环境：Windows 10 Enterprise 22H2，构建 19045.6456，x64。
- 用户使用 Zadig 安装 WinUSB；首次启动超时，拔插后设备正常，设备服务为 `WinUSB`。
- SANE 1.4.0 的 `gt68xx` USB 扫描引擎已编译并实际运行。
- 修复 Cygwin 下缺少共享内存服务导致的扫描失败，使用同步读取路径，未安装 cygserver 系统服务。
- PNG 实机扫描：150 dpi，50 × 50 mm，295 × 295 像素，170104 字节。首张为深色内容，不能用来验收图像质量。
- 白纸实机测试：通过 eSCL 创建任务（HTTP 201）、读取 JPEG（HTTP 200）、清理任务（HTTP 200）；295 × 295 像素，7382 字节。已视觉检查，能看到白纸及边缘。
- Windows 系统发现与注册：用户已在设置中发现并添加 `Plustek OpticSlim 1200`；WIA 枚举独立确认设备类型为扫描仪、WIA 2.0、Microsoft 驱动 10.0.19041.5794，PnP 状态正常。
- Windows 原生 WIA 扫描：通过 `WIA.DeviceManager` 连接系统设备，设置 150 dpi 和 295 × 295 像素范围，用微软 eSCL 类驱动实际采集 BMP；输出 `.runtime/native-wia-test.bmp`，262014 字节。日志明确记录请求方 `Escl Scan Client` 完成状态查询、任务创建、取图与结束。已视觉检查输出中的白纸与边缘。
- 独立 mDNS 发布端和发现端成功解析 `127.0.0.1` 的临时 `_uscan._tcp` 服务，测试后撤销广播。此测试在完整主机权限下通过；受限执行环境下未通过，不能将后者归因于驱动故障。
- 4 项自动测试通过：真实 SANE 模拟后端经 HTTP 返回 PNG 并校验 CRC 与压缩数据；任务忙与完成状态；不支持设置拒绝；网页伪装固件拒绝。没有用模拟图片冒充实机结果。
- 补丁对固定上游源码的 dry-run 通过，Mac 和 Windows 的 Bash 脚本语法检查通过。

## 尚未通过的验收

- Windows Scan / Windows 传真和扫描的具体 GUI 操作尚未自动化验证；已确认设备可被系统识别并通过原生 WIA 2.0 接口实际扫描，不能将这两项混为一谈。
- Apple Silicon Mac 上的安装、USB 识别、Bonjour 发现以及“图像捕捉”扫描。已知芯片为 ARM，具体 macOS 版本未提供，也没有可访问的 Mac 测试环境。
- 有文字/色标的成像质量、300/600 dpi、整页、灰度、取消后的物理扫描终止与热插拔完整恢复。

## 已发现并修复的实现问题

- 上游 Windows SCSI 路径的旧句柄类型不适合当前 64 位编译器：USB 专用构建禁用该路径，修正关闭句柄条件。
- 预加载后端函数表需要显式函数指针类型转换。
- 上游模拟后端在设备数量为零时访问未初始化指针：添加零设备保护，生产运行配置禁用模拟设备。
- Cygwin 的 SysV 共享内存接口依赖额外服务：本项目在 Cygwin 下使用驱动现有的同步读取实现。
- USB 插拔后 libusb 设备地址可能改变：桥接在每次真实扫描前重新按厂商和型号枚举。

## 当前文件与进程

- 实机样图：`.runtime/first-hardware-test.png`、`.runtime/white-paper-test.jpg`、`.runtime/native-wia-test.bmp`。
- 固件及来源：`.runtime/firmware/`。
- Windows 可执行文件及依赖：`dist/win64/bin/`，共 7 个文件；摘要见 `dist/win64/SHA256.json`。
- 桥接只监听 `127.0.0.1:8090`。进程 ID 记录在 `.runtime/bridge.pid`，日志在 `.runtime/bridge.stdout.log` 和 `.runtime/bridge.stderr.log`。没有安装自动启动服务。

结论：Windows 上实机 USB 扫描、eSCL 图像传输、系统发现注册和 Microsoft 原生 WIA 采集均已通过。ARM Mac“图像捕捉”尚无实机验证，当前不应标为两平台最终驱动均已完成。
