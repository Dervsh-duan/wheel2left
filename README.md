# Wheel2Left · 滚轮变左键

**Turn your mouse wheel into a left click — at the driver level, so it works inside full-screen games.**

给 galgame、视觉小说和任何"只需要一直点左键"的场景用的。也为单手操作、手部劳损、躺床上推剧情的人设计。

> 前几版都是用户层方案（`WH_MOUSE_LL` + `SendInput`），在浏览器里能跑，一进游戏就失灵。
> 原因和修复见 [为什么必须走驱动层](#为什么必须走驱动层)。

---

## 目录

- [为什么必须走驱动层](#为什么必须走驱动层)
- [特性](#特性)
- [安装](#安装)
- [使用](#使用)
- [兼容性](#兼容性)
- [不适用的情况](#不适用的情况)
- [卸载](#卸载)
- [从源码构建](#从源码构建)
- [常见问题](#常见问题)
- [许可证](#许可证)

## 为什么必须走驱动层

用户层的工作方式是：系统先把滚轮事件算完，程序再"补发"一个左键。这个补发的点击在系统里带着**注入标记**（`SendInput` 的 `LLMHF_INJECTED`、RawInput 的 injected 标志），而游戏读的是硬件原始数据（RawInput / DirectInput），一看是模拟的直接丢掉。所以无论换成 `SendInput` 还是 `PostMessage`，在游戏里都注定无效——不是参数没调对。

Wheel2Left 换了个位置：它挂在鼠标类过滤驱动（`mouse.sys`）上，在滚轮事件进入系统**之前**就把它拦下来，左键也从同一层发出去。对上层来说这是设备本身产生的事件，没有任何标记可以区分。代价是需要安装一个内核驱动，并且要管理员权限。

## 特性

- **驱动层拦截**：全屏独占、无边框全屏、窗口化都有效，与真人按左键无法区分
- **默认只对锁定的程序生效**：桌面、浏览器、文件管理器的滚轮完全不受影响
- **三档生效范围**：全部窗口 / 仅全屏 / 指定程序（默认）
- **自动锁定**：第一次在全屏程序里滚一下就自动记住它，不用手动配置
- **热键随时开关**：`Ctrl + Alt + Shift + R`
- **关闭即恢复**：退出程序滚轮立刻恢复正常，驱动本身不常驻、不常开
- **单文件、无安装、无联网**

## 安装

要求：Windows 10 / 11，64 位。需要管理员权限。

### 1. 安装过滤驱动（只需一次）

1. 从 [Release](releases) 下载 `Wheel2Left-v1.0.0-win64.zip` 并解压
2. 右键 `install_driver.bat` → **以管理员身份运行**
3. **重启电脑**（让驱动真正挂到鼠标设备栈上，这一步不能省）

驱动本体是 [Interception](https://github.com/oblitum/Interception) v1.0.1，压缩包里的 `Interception/` 目录是它的原始发布包，未做任何修改。

### 2. 启动

双击 `Wheel2Left.exe`，UAC 弹窗点「是」。程序要管理员权限才能打开驱动设备。

> `Wheel2Left.exe` 和 `interception.dll` 必须放在同一个目录里。

## 使用

启动后界面顶部显示「已开启 · 点击关闭」，此时滚轮已经等于左键。

**第一次用推荐这样**：

1. 启动程序（它会停在桌面右下角，不抢焦点）
2. 切到游戏窗口，**滚一下滚轮**
3. 程序自动锁定这个游戏，界面上出现 `锁定：Game.exe`
4. 之后再滚就是在点左键了

如果自动锁定没触发（比如游戏是窗口化的），点界面上的 **「锁定前台程序」** 按钮——它会记住你刚才待过的那个窗口的进程。

**三档范围**：

| 范围 | 行为 | 适合 |
|---|---|---|
| 指定程序 | 只对锁定的 exe 生效 | 默认，最安全 |
| 仅全屏 | 前台窗口铺满屏幕时才转换 | 懒得配置、又怕误点桌面 |
| 全部窗口 | 任何地方滚轮都是左键 | 临时用，桌面上会误点图标 |

**计数含义**：`已触发 N 次` 是成功发出的左键数量，`放行 N` 是因为不在范围内而没被转换的滚轮次数。滚轮滚了但两个数都不涨，说明驱动没拦到（看下方日志框）。

配置存在 `%LOCALAPPDATA%\Wheel2Left\config.json`，删掉它会恢复默认。

## 兼容性

判定标准很简单：**只要这个游戏能接受真人按的左键，它就能接受这里的左键**，因为事件在设备栈里产生，没有任何可识别标记。

已知适用于这些 galgame / 视觉小说引擎（它们在 Windows 上都走标准鼠标输入路径）：

| 引擎 | 备注 |
|---|---|
| KiriKiri 2 / KrKrZ | 汉化作品里最常见 |
| NScripter / ONScripter | |
| Ren'Py | SDL2 |
| RPG Maker MV / MZ | NW.js（Chromium），窗口必须处于激活状态 |
| SiglusEngine | Key 系作品 |
| YU-RIS | 柚子社等 |
| Artemis Engine | |
| Majiro | |
| BGI / Ethornell | |
| CatSystem2 | |
| CMVS | |
| Unity（部分移植作） | |

"适用"指输入路径层面。实际体验还取决于游戏本身怎么用滚轮（见下）。

## 不适用的情况

- **带反作弊的在线游戏**（EAC / BattlEye / Vanguard 等）。这类反作弊会检测非白名单的过滤驱动，轻则拒绝启动，重则封号。**不要用**。
- **滚轮本身有功能的场景**。很多 galgame 用滚轮回看历史对话（backlog）、快进、缩放 CG。转换之后这些功能就用不了了——这时候用「指定程序」+ 热键关掉，或者干脆别开。
- **macOS / Linux**。本项目只做 Windows。
- 极少数把输入绑定到具体物理设备（按 VID/PID 校验）的程序，理论上仍可能失败。欢迎用 [issue](issues) 反馈具体游戏。

## 卸载

1. 关闭 `Wheel2Left.exe` —— 滚轮立刻恢复正常，不关驱动也能用回滚轮
2. 如果不再需要这个工具，右键 `install_driver.bat` 同目录的 `uninstall_driver.bat` → 以管理员身份运行，然后重启

手动卸载（如果脚本不管用）：

```bat
:: 管理员命令提示符
sc stop mouse
sc delete mouse
:: 然后到注册表删掉 UpperFilters 里的 mouse 项，重启
```

驱动服务名是 `mouse` / `keyboard`，`ImagePath` 指向 `%SystemRoot%\System32\drivers\mouse.sys`。**不要直接删 `mouse.sys` 文件**，先删服务再重启。

## 从源码构建

需要 Python 3.11+。

```bat
:: 1. 下载 Interception 并解压到 driver\Interception\
::    https://github.com/oblitum/Interception/releases/download/v1.0.1/Interception.zip
:: 2. 安装打包工具
pip install pyinstaller
:: 3. 构建
build.bat
```

产物在 `dist\Wheel2Left.exe` 和 `dist\interception.dll`。

源码结构：

```
src/
├── main.py      入口、单实例检查、崩溃兜底
├── app.py       界面（纯 Win32 自绘，不依赖 tkinter）
├── engine.py    驱动引擎：拦滚轮、发左键、范围判定
├── icpt.py      Interception 的 ctypes 封装
├── config.py    配置持久化
└── w32.py       Win32 API 绑定与常量
tools/
├── install_driver.bat    驱动安装（辅助修正上游 installer 的已知问题）
├── ui_probe.py           不开引擎、只渲染界面并截图，用来检查排版
└── smoke.py              端到端冒烟测试（需管理员）
```

`tools/install_driver.bat` 里做了两件上游安装器没做好的事：补全驱动服务的 `ImagePath`（否则 SCM 认不出服务），以及提示重启以重新枚举鼠标设备（否则过滤驱动不会插进设备栈）。

## 常见问题

**界面里计数不涨，滚轮也没反应**
驱动没挂上。先确认装完驱动后**重启过**；再检查 Windows 的「内核隔离 / 内存完整性」是否开启——开启时系统会拒绝加载这类过滤驱动，需要关掉再重启。

**计数在涨，但游戏里没反应**
说明驱动拦到了，但前台不是你以为的那个窗口。把游戏切到前台再滚；或者点「锁定前台程序」确认锁的是 `Game.exe` 而不是启动器。日志框会显示实际转换了几次。

**每次启动都弹 UAC**
正常，打开驱动设备需要管理员权限。介意的话可以给 exe 建一个任务计划程序项，勾选"以最高权限运行"。

**游戏里滚轮原来是回看对话的**
这套工具会把滚轮彻底换成左键。用「指定程序」模式，需要回看对话时按 `Ctrl+Alt+Shift+R` 临时关掉。

## 许可证

本项目代码：[MIT](LICENSE)。

第三方：`interception.dll` 与驱动来自 [Interception](https://github.com/oblitum/Interception) v1.0.1，采用**双许可**——非商业用途 LGPL-3.0，商业用途需另行购买授权。本项目以动态链接方式使用未经修改的库，`interception.dll` 独立放在 exe 同目录，你可以自行替换成自编译版本。详见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

**商业使用请注意**：MIT 只覆盖本项目的代码，不覆盖 Interception。要在商业产品里用，需要向 Interception 作者购买商业许可。

## 免责声明

本项目通过内核过滤驱动改写鼠标输入，属于系统级操作。仅建议用于**单机游戏和个人辅助场景**。不要在带反作弊的在线游戏中使用，不要用于自动化脚本、挂机或其他违反游戏服务条款的行为。使用风险自负。
