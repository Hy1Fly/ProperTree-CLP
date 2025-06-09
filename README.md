# 这是什么？

ProperTree 是一款跨平台的 GUI plist 编辑器，使用 Python（兼容 2.x 和 3.x 版本）和 Tkinter 编写。
由Hy1Fly加入中文,部分内容使用AI进行翻译
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

### 将存储库下载为 ZIP 文件

在任何系统上，您都可以选择绿色的“代码”按钮，然后选择“下载 ZIP”按钮以 zip 文件的形式下载整个存储库（请注意，这不允许您通过“git pull”更新，任何更新都需要您以相同的方式再次下载存储库。

### 通过 Git 克隆仓库

#### 在 *nix 系统上：

```
git clone https://github.com/corpnewt/ProperTree
python ./ProperTree/ProperTree.py
```
-或-
```
python3 ./ProperTree/ProperTree.py
```

* 在 macOS 上，您只需在克隆后双击 'ProperTree.command' 即可启动。

#### 在 Windows 上：

```
git clone https://github.com/corpnewt/ProperTree
./ProperTree/ProperTree.bat
```

***
FAQ见原项目主页

#### 截图
![image](https://github.com/user-attachments/assets/d48539f9-304e-4735-b5a7-0a276d596345)
![image](https://github.com/user-attachments/assets/2ec08666-3fd6-4e10-ba36-e77828dc9a67)
![image](https://github.com/user-attachments/assets/e8a65924-f4f4-40cf-8467-15f93635fb38)
设置等英文字符放于ProperTree.py中
其它而放于plistwindow.py中
