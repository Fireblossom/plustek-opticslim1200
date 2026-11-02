# Plustek OpticSlim 1200 兼容项目

目标：USB 扫描仪无需 XP 虚拟机，在 Windows 10 的系统扫描应用、Apple Silicon Mac 的“图像捕捉”中扫描。

当前是开发与验证版本。代码、构建成功、协议测试成功、实机扫描成功、系统应用识别成功是不同的验收项；以 `VALIDATION.md` 中的实际记录为准。项目不声称已经实现原生 WIA/ICA 插件，也不声称通过 Mopria 认证。

**已验证：Windows 10 22H2 的系统发现、添加及原生 WIA 2.0 实机扫描。待验证：Apple Silicon Mac 的“图像捕捉”。**

公开仓库包含源码、Mac 安装脚本和 Windows 源码构建补丁。原厂固件、扫描文档、虚拟磁盘、运行日志和本地构建产物不发布。

## 实现方式

```text
Windows 扫描 / macOS 图像捕捉
             │ 系统自带 eSCL/AirScan 客户端
       airscan_bridge.py + Bonjour/mDNS
             │ 独立 scanimage 进程
       SANE 1.4.0 gt68xx 驱动
             │ libusb / Windows 上的 WinUSB
       OpticSlim 1200 (07b3:0413)
```

系统把它作为 Bonjour / 网络扫描仪显示。桥接服务运行在本机，不需要 XP 虚拟机。必须保持桥接进程运行；退出后扫描服务消失。默认绑定 `127.0.0.1:8090`，不将扫描接口开放给其他电脑。各系统是否接受本机回环地址的扫描仪，须在对应版本上验证。

Microsoft 的 KB5014666 在 2022 年为 Windows 10 加入 eSCL Mopria Scan。目标建议为已更新的 Windows 10 22H2。更早且未更新的 Windows 10 不能保证支持此方案。

## 固件

已从用户自己的关机状态 VirtualBox `xp.vdi` 中，只读提取 `Program Files/ScannerU/Cism216.fw`，未启动或修改虚拟机。

- 大小：8192 字节。
- SHA-256：`70ce066ed6c3dc34733bd43a32a9b670ae89c99203c0bb49aac1639af96d0884`。
- 本机副本：`.runtime/firmware/cism216.fw`。
- 原始来源记录：`.runtime/firmware/provenance.json`。

固件不属于本项目原创代码。个人使用的迁移包可以保留自己的副本；项目公开源码排除 `.runtime`。M12 同名固件不能作为此型号的替代品。

在其他副本中导入固件：

```sh
python3 opticslim.py import-firmware /path/to/Cism216.fw --source-info "来自本人的 OpticSlim 1200 XP 驱动"
```

该命令只检查文件基本形态并记录来源，不会证明任意文件与硬件兼容。

## Apple Silicon Mac

已安装 Homebrew 并准备好自己的固件文件后，可在 Mac 终端执行：

```sh
git clone https://github.com/Fireblossom/plustek-opticslim1200.git
cd plustek-opticslim1200
bash macos/setup.sh
bash macos/Start-AirScan.command
```

安装时选择固件，连接扫描仪，保持最后一个命令运行，再打开“图像捕捉”。Mac 端仍为待实测版本。

1. 从本 GitHub 仓库克隆源码，或点击 Code → Download ZIP 并解压。
2. 从 https://brew.sh 安装原生 ARM Homebrew（已有则跳过）。
3. 将自己持有的 OpticSlim 1200 `Cism216.fw` 固件复制到 Mac。原厂固件不包含在公开仓库或公开发布包内。
4. 在项目目录运行 `bash macos/setup.sh`，安装 SANE、Python 3.12 与本项目局部 Python 依赖；文件选择框出现时选取上述固件。也可运行 `bash macos/setup.sh /path/to/Cism216.fw` 明确传入路径。
5. 连接扫描仪，运行 `/opt/homebrew/bin/python3.12 opticslim.py list`，核对出现的设备。
6. 首次实机验证可运行 `/opt/homebrew/bin/python3.12 opticslim.py scan first-test.png`，默认 150 dpi、50 × 50 mm。
7. 运行 `bash macos/Start-AirScan.command`，再打开“图像捕捉”，检查“共享”扫描仪。保持命令窗口运行；Ctrl+C 退出服务。

可先用 `sw_vers` 记录具体 macOS 版本。这里只确认用户的 Mac 为 ARM，尚未获知版本，也没有在 Mac 上实际编译或运行。Homebrew 的可安装版本支持以其官方页面为准。

## Windows 10 x64

需要 Python 3.10+，以及 `dist/win64/bin/scanimage.exe` 和同目录的运行库。

必须先为 **USB VID 07B3 / PID 0413** 绑定 WinUSB。官方 Zadig 是 libusb 推荐的安装工具，操作前核对设备 ID 与当前驱动。只为这台设备安装，不更改其他 USB 设备。保留 XP 虚拟机与本项目中的原驱动信息，便于排查；不要通过关闭系统驱动签名校验来安装本项目。

```powershell
python opticslim.py doctor
python opticslim.py list
python opticslim.py scan first-test.png
python -m pip install --target .runtime/python -r requirements.txt
python airscan_bridge.py
```

随后在 Windows“设置 → 设备 → 打印机和扫描仪 → 添加打印机或扫描仪”中查找 `Plustek OpticSlim 1200`，完成添加后打开系统扫描应用。还须验证 Windows 接受回环地址的设备发现；不能以 HTTP 接口测试成功代替此项验收。

本机已完成系统发现、添加与 Microsoft WIA 2.0 实际采集验证，见 `VALIDATION.md`。当前桥接已在后台运行。重启电脑后，运行 `windows/Start-AirScan.cmd`，再使用系统扫描应用。此版本尚未设置开机启动。后台测试进程可用 `windows/Stop-AirScan.ps1` 停止；命令窗口启动的进程用 Ctrl+C 退出。

开发者本机生成的 `dist/OpticSlim1200-personal-test-kit.zip` 是个人迁移测试包，含源码、Windows 引擎、Mac 脚本与用户自己的固件，排除构建缓存和扫描文档。该个人包不上传 GitHub；公开仓库的安装方式如上。Mac 运行安装脚本获取对应 ARM 依赖。Windows 新副本先按上面命令安装 Python 依赖；包内不包含 Python 安装程序。

## 构建 Windows 扫描引擎

官方源码固定为 SANE 1.4.0，下载地址：

`https://gitlab.com/sane-project/backends/-/archive/1.4.0/backends-1.4.0.tar.gz`

下载文件 SHA-256：`9c50ee76e35d98d7ae0cbb97d4c2a3c15663a78fdd74b0ed2bf2fe8e1a73f63a`。这是本次下载后记录的固定摘要，用于复现，并非另行验证的上游签名。

本项目 `.cache/cygwin` 是局部 Cygwin 环境。工具从官方签名的 setup 下载，使用 `--no-admin --no-shortcuts --no-write-registry`，未建立全局 Cygwin 安装。依赖：gcc-core、gcc-g++、make、autoconf、automake、autoconf-archive、libtool、pkg-config、patch、diffutils、gettext-devel、python3、libusb1.0-devel、libpng-devel、libjpeg-devel、libtiff-devel。

在该 Cygwin 环境运行：

```sh
bash windows/build-cygwin.sh /path/to/backends-1.4.0.tar.gz
```

仅构建 `gt68xx` 和用于协议测试的 `test` 后端，并静态预加载。运行时将模拟设备数量设为零，桥接只发布真实的 OpticSlim 1200。`windows/compat.patch` 修正旧 SCSI 关闭句柄的条件编译、预加载函数表的显式函数指针转换、模拟后端零设备时的空指针访问，以及 Cygwin 缺少共享内存服务时的读取路径；USB 专用构建关闭不需要的 Windows SCSI 检测。

## 测试与限制

```powershell
$env:SCAN_TEST_BINARY = (Resolve-Path .\dist\win64\bin\scanimage.exe).Path
python -m unittest discover -s tests -v
```

协议测试使用 SANE 的 `test:0` 模拟后端，不启动实际 USB 扫描。覆盖完整 PNG 传输及 CRC/压缩数据、重复任务忙状态、文档取完后的 404、HEAD 无副作用，以及不支持的设置与伪固件拒绝。

当前桥接支持单设备、平板、75/150/300/600 dpi、RGB24/灰度8、JPEG/PNG。不支持 ADF、硬件按钮、OCR、48 位颜色。取消任务立即停止传输，但底层正在进行的物理扫描可能继续到完成，期间保持设备忙；这是需继续完善的行为。第一次扫描应有人在设备旁观察机械运行。

## 主要资料

- [SANE 支持表](https://sane-project.gitlab.io/website/sane-backends.html)：型号、USB ID、gt68xx、固件要求。
- [gt68xx 手册](https://sane-project.gitlab.io/website/man/sane-gt68xx.5.html)：固件加载和配置语法。
- [SANE 1.4.0 源码](https://gitlab.com/sane-project/backends/-/tree/1.4.0)：命令实现、型号参数、校准与数据读取。
- [Microsoft KB5014666](https://support.microsoft.com/en-us/servicing/os/windows-10/2022/06/june-28-2022-kb5014666-os-builds-19042-1806-19043-1806-and-19044-1806-preview)：Windows 10 eSCL 支持。
- [AirSane](https://github.com/SimulPiscator/AirSane)：用系统扫描应用访问 SANE 的已存在桥接路径；本项目未声称是 AirSane 发行版。
- [libusb Windows 指南](https://github.com/libusb/libusb/wiki/Windows)：WinUSB 要求。
- [VueScan 型号页面](https://www.hamrick.com/vuescan/plustek_opticslim_1200.html)：已有商业扫描软件支持；并不代表能替代本项目的系统应用接入验收。

各第三方代码和二进制仍受各自许可证约束。不得把本项目的胶水代码标为原厂 Plustek 驱动。

本项目原创代码以 GPL-3.0-or-later 发布；SANE 补丁保留上游 GPL-2.0-or-later 及例外声明，详见 [第三方说明](THIRD_PARTY.md)。
