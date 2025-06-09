# 这是什么？

ProperTree 是一款跨平台的 GUI plist 编辑器，使用 Python（兼容 2.x 和 3.x 版本）和 Tkinter 编写。

## 功能特性

- [x] 跨平台 - 只要支持 Python 和 Tkinter 的环境均可运行
- [x] 支持多窗口的文档式编辑
- [x] 通过拖放节点重新排序
- [x] 复制粘贴功能
- [x] 查找/替换 - 支持搜索键名或键值
- [x] 有序/无序字典支持
- [x] 完整的撤销-重做栈
- [x] 在 Python 2 中提供二进制属性列表和 Unicode 的后向兼容支持
- [x] 扩展整数转换功能，支持在 XML `<integer>` 标签中使用十六进制整数（如 `0xFFFF`）
- [x] 上下文感知右键菜单，包含针对 OpenCore 或 Clover 配置文件 config.plist 的模板信息
- [x] OC (纯净)快照 - 扫描 OpenCore 配置文件中 ACPI、Drivers、Kexts 和 Tools 目录的内容
- [x] 支持 Base64、十六进制、ASCII 和十进制的数值转换器

***

## 获取 ProperTree

### 下载 ZIP 压缩包

在任何系统上，点击绿色的 `Code` 按钮，选择 `Download ZIP`（或直接点击[此处](https://github.com/corpnewt/ProperTree/archive/refs/heads/master.zip)）下载整个仓库。注意：此方式无法通过 `git pull` 更新，更新需重新下载。

### 通过 Git 克隆仓库

#### *nix 系统：
```bash
git clone https://github.com/corpnewt/ProperTree
python ./ProperTree/ProperTree.py
# 或
python3 ./ProperTree/ProperTree.py

* macOS 用户克隆后双击 ProperTree.command 即可启动。

Windows 系统：
batch
git clone https://github.com/corpnewt/ProperTree
./ProperTree/ProperTree.bat
常见问题解答
OC 快照功能是什么？
该功能会提示您选择 OpenCore (OC) 文件夹，扫描其 ACPI、Kexts、Tools 和 Drivers 目录内容，并与当前配置文件的 ACPI -> Add, Kernel -> Add, Misc -> Tools, UEFI -> Drivers 进行对比。自动增删条目，并通过比对 kext 的 CFBundleIdentifier 和 OSBundleLibraries 确保依赖加载顺序。会检测重复的 CFBundleIdentifiers（支持 MinKernel/MaxKernel/MatchKernel 重叠检查），并提供禁用选项。同时检查"已禁用父 kext 但启用子 kext"的情况。默认通过比对 OpenCore.efi 的 MD5 哈希确定架构版本，未匹配则使用脚本中 snapshot.plist 的最新架构。可在设置菜单的 OC Snapshot Target Version 自定义。

OC 快照和 OC 纯净快照有何区别？
两者功能相同，但起点不同：

纯净快照会清空配置中的四个相关模块，然后重新添加所有内容

普通快照基于当前配置内容增量更新，仅增删必要条目

何时使用纯净快照？
首次快照建议使用纯净快照清除示例条目，后续更新使用普通快照以保留自定义设置。

Sonoma (14.x+) 系统点击无响应
Python 3.11.x 及更早版本在 macOS 上与 tk 存在兼容性问题。升级至 Python 3.12.0+（下载）可修复。如无法升级，可尝试拖动窗口后再点击树形视图。

macOS Monterey (12.x+) 显示黑窗
系统自带的 tk 版本不兼容。解决方案：

从 python.org 安装最新 Python

运行 ProperTree/Scripts 中的 buildapp-select.command

使用生成的 ProperTree.app 启动

macOS Monterey 无法读写 plist 文件
tk 内置版本问题。需安装 Python 3.10.2+ 的通用版本（下载），再通过 buildapp-select.command 创建应用。

关联 .plist 文件双击打开

macOS：运行 Scripts/buildapp-select.command 生成应用后关联

Windows：运行 Scripts/AssociatePlistFiles.bat 关联（移动目录需重新运行）

报错 ModuleNotFoundError: No module name 'tkinter'
缺少图形库依赖。Ubuntu 系统修复命令：

bash
sudo apt-get install python3-tk -y
权限不足无法运行
确保来源可信后授予权限：

bash
chmod +x ProperTree.command
非美式键盘布局导致崩溃
macOS 的 Tcl/Tk Cocoa 实现存在缺陷（详情）。解决方案：

安装 Python 2.7.18+（下载）

使用 buildapp-select.command 绑定该 Python 路径

macOS Big Sur (11.x) 崩溃问题
* macOS 11.2+ 已修复系统 tk 问题
旧版解决方案：

安装 python.org 的 Python 3.9.1+（避免使用"通用"安装包）

通过 buildapp-select.command 创建应用

buildapp-select.command 使用示例
该脚本自动检测可用 Python 版本（示例输出）：

text
- 当前可用 Python 版本 -
1. /usr/bin/python 2.7.16 - tk 8.5 (推荐8.6+)
2. /usr/bin/python3 3.8.2 - tk 8.5 (推荐8.6+)
3. /Library/Frameworks/.../python3 3.9.1 - tk 8.6
4. /usr/bin/env python
5. /usr/bin/env python3
C. 当前版本 (/Library/Frameworks/.../python3)
Q. 退出
请选择要使用的 Python 版本：
