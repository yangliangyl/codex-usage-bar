<!-- 语言切换 -->
[English](README.md) · **简体中文**

# Codex Quota Bar · 额度菜单栏

一个 macOS **菜单栏**小工具，扫一眼就知道 Codex（ChatGPT 桌面 App）还剩多少额度，不用每次点进设置里翻。

```
🟢 5h 88% · 🟠 7d 46%
```

- 彩色文字 = 还**剩**多少：🟢 绿 > 50% · 🟠 橙 20–50% · 🔴 红 < 20%（或已触达限额）。每个窗口按自己的紧张度独立配色。
- `5h` = 5 小时窗口，`7d` = 7 天（周）窗口。
- 点开下拉：每个窗口的剩余%、进度条、重置倒计时、账户 plan、上次刷新，以及「立即刷新」按钮。

> 5 小时窗口只有在近期用过 Codex 时才出现；空闲时可能只显示周窗口，属正常。

## 原理

通过官方 `codex` 二进制的 app‑server 接口 `account/rateLimits/read` 读额度（和设置页显示用量同一条路）。

- **不消耗额度**——这是元数据读取，不是生成请求。
- **不碰你的登录凭证**——token 刷新全交给官方程序，本工具一行认证代码都没写。

## 依赖

- macOS，装了 **ChatGPT 桌面 App**（`/Applications/ChatGPT.app`）并已登录。
- 用系统自带的 `/usr/bin/python3`；`install.sh` 会帮你装唯一的依赖 `rumps`。

## 安装

### 最简单——让 Codex 帮你装（不用开终端）

你既然在用 Codex，把下面这一段整段发给它（仅 macOS）：

> 帮我安装这个 macOS 菜单栏工具：**github.com/yangliangyl/codex-usage-bar**。步骤：`git clone` 到本地文件夹，`cd` 进去，运行 `./install.sh`。脚本会装依赖（rumps）、把运行文件复制到 `~/Library/Application Support/CodexQuotaBar`、配置开机自启的 LaunchAgent，并读一次我的额度做自检。请执行这些命令，需要我确认的地方告诉我。如果没有 `/usr/bin/python3`，先让我运行 `xcode-select --install`。

Codex 会自动克隆仓库、运行安装脚本——你一条命令都不用敲（它问的时候点确认即可）。装完工具就在菜单栏（不占程序坞），每次开机自动启动。

**前提：** macOS，装了 ChatGPT 桌面 App 并已登录。

### 手动——两条命令

```bash
git clone https://github.com/yangliangyl/codex-usage-bar.git
cd codex-usage-bar
./install.sh
```

装完即出现在菜单栏，并开机自启。

卸载：

```bash
./uninstall.sh
```

## 只想临时试跑（不装自启）

```bash
/usr/bin/python3 codex_quota_bar.py
```

单独调试取数（打印 JSON）：

```bash
/usr/bin/python3 fetch_quota.py
```

## 文件说明

| 文件 | 作用 |
|---|---|
| `fetch_quota.py` | 驱动 `codex app-server`，返回统一结构的额度数据 |
| `codex_quota_bar.py` | 菜单栏 App（rumps）；展示逻辑是纯函数、可单测 |
| `com.user.codexquota.plist.template` | 开机自启模板（路径由 `install.sh` 填充） |
| `install.sh` / `uninstall.sh` | 一条命令安装 / 卸载 |

后台每 3 分钟自动刷新，也可随时点「立即刷新」。

## 兼容性

已验证环境：macOS 26（Apple Silicon）、ChatGPT 桌面 App（bundle `com.openai.codex`）、`codex` 0.144.2、**Plus** 账户。

- 走的是 Codex 一个**实验性**接口 `account/rateLimits/read`，官方后续改版可能需要同步更新 `fetch_quota.py`。`install.sh` 会先自检、当场告诉你能不能读到额度。
- 仅在 Plus 账户上实测；其他 plan（Free/Pro/Team）为通用写法，大概率可用但未验证。
- 需要 Xcode 命令行工具提供 `/usr/bin/python3`（缺失则 `xcode-select --install`）。

## 说明

- 只在右上角菜单栏显示——**不在程序坞（Dock）出现图标**，也不占顶部应用菜单。
- 自启只在崩溃（非零退出）时自动拉起；你主动点「退出」不会被强行复活。
- 崩溃日志：`/tmp/codexbar.err.log`、`/tmp/codexbar.out.log`。
- 仅支持 macOS。

## 许可

[MIT](LICENSE)
