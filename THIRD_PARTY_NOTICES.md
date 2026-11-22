# 第三方组件说明

本项目自身的代码（`src/`、`tools/`、脚本与文档）采用 [MIT 许可证](LICENSE)。

它依赖下面这个第三方组件，**其许可条件与本项目不同**。

---

## Interception

- 项目主页：https://github.com/oblitum/Interception
- 本项目使用的版本：**v1.0.1**
- 使用的文件：`interception.dll`（x64）、`mouse.sys`、`keyboard.sys`、`install-interception.exe`
- 修改情况：**未做任何修改**

### 许可证

Interception 采用**双许可**，两个分支的条款完全不同：

| 用途 | 许可 | 说明 |
|---|---|---|
| 非商业用途 | **LGPL-3.0** | 上游发布包中 `licenses/non-commercial-usage/LGPL 3.0.txt` |
| 商业用途 | **商业许可（付费）** | 需向作者购买，条款见 `licenses/commercial-usage/` 下的 PDF |

**如果你要把 Wheel2Left 用在商业产品里，MIT 许可证并不覆盖 Interception 部分**，你需要自行向上游取得商业授权。

### 本项目如何遵守 LGPL-3.0

- `interception.dll` 以**动态链接**方式加载（`ctypes.WinDLL`），不做静态链接、不加壳、不修改
- `interception.dll` **独立存放在 `Wheel2Left.exe` 同目录**，没有被打包进 exe，用户可以直接用自己编译的版本替换它
- 上游完整发布包（含许可证文件）放在 Release 压缩包的 `Interception/` 目录中，原样未改
- 内核驱动 `mouse.sys` / `keyboard.sys` 由上游 `install-interception.exe` 安装，本项目不重新签名、不修改驱动文件

### 获取源代码

Interception 的源代码在其上游仓库公开：https://github.com/oblitum/Interception

---

## Python 运行时与打包工具

构建产物包含 Python 解释器与标准库（由 PyInstaller 打包），采用 PSF License。
PyInstaller 本身采用 GPL-2.0-or-later，并带有允许分发打包产物的例外条款。
