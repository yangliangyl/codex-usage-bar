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

- 本工具只发送额度元数据查询，不发起模型生成请求；服务端如何计量由 OpenAI 决定，不由本仓库保证。
- 本仓库的取数代码不直接读取或保存账户 token；认证、联网和可能发生的凭据刷新由官方 `codex` 二进制处理。

## 依赖

- macOS，装了 **ChatGPT 桌面 App**（`/Applications/ChatGPT.app`）并已登录。
- 用系统自带的 `/usr/bin/python3`；需要时，`install.sh` 会按 `requirements.txt` 把唯一依赖 `rumps>=0.4,<0.5` 安装到当前用户共享的 Python user site。

## 安装

### 安装器会改什么

`install.sh` 不是只读查看。它可能会：

- 缺少依赖时，把 `rumps` 安装到当前用户的系统 Python 环境；
- 把运行文件复制到 `~/Library/Application Support/CodexQuotaBar`；
- 执行一次真实额度查询作为自检；
- 写入并加载 `~/Library/LaunchAgents/com.user.codexquota.plist`，设置登录自启；
- 启动后把运行日志写到 `/tmp/codexbar.err.log` 和 `/tmp/codexbar.out.log`。

运行前请先查看脚本。安装过程不要求本仓库直接读取或保存 token，但官方 `codex` 进程会使用现有账户状态完成查询。

可以先只读预览准确路径和副作用；该模式不安装依赖、不读取账户、不写文件、不加载服务：

```bash
./install.sh --plan
```

### 最简单——让 Codex 帮你装（不用开终端）

你既然在用 Codex，把下面这一段整段发给它（仅 macOS）：

> 帮我安装这个 macOS 菜单栏工具：**github.com/yangliangyl/codex-usage-bar**。先 `git clone` 到本地文件夹并进入目录，运行 `./install.sh --plan`，把计划展示给我并等我确认，再运行 `./install.sh`。真实安装可能把兼容版本的 rumps 装进当前用户共享的 system-Python user site，把运行文件复制到 `~/Library/Application Support/CodexQuotaBar`，读取一次我的额度做自检，并加载登录自启的 LaunchAgent。如果没有 `/usr/bin/python3`，先让我运行 `xcode-select --install`。

Codex 会自动克隆仓库、运行安装脚本——你一条命令都不用敲（它问的时候点确认即可）。装完工具就在菜单栏（不占程序坞），每次开机自动启动。

**前提：** macOS，装了 ChatGPT 桌面 App 并已登录。

### 手动——先预览，再安装

```bash
git clone https://github.com/yangliangyl/codex-usage-bar.git
cd codex-usage-bar
./install.sh --plan
./install.sh
```

依赖安装、自检和 LaunchAgent 加载成功后，菜单栏图标应出现，并在登录时自动启动。

卸载：

```bash
./uninstall.sh --plan
./uninstall.sh
```

卸载脚本会卸载并删除 LaunchAgent、停止菜单栏进程，并删除 `~/Library/Application Support/CodexQuotaBar`。它不会卸载 `rumps`，也不会删除已经存在的 `/tmp/codexbar.*.log` 日志。

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
| `requirements.txt` | system Python user site 使用的兼容依赖范围 |
| `com.user.codexquota.plist.template` | 开机自启模板（路径由 `install.sh` 填充） |
| `install.sh` / `uninstall.sh` | 一条命令安装 / 卸载 |

后台每 3 分钟自动刷新，也可随时点「立即刷新」。

## 兼容性

已验证环境：macOS 26（Apple Silicon）、ChatGPT 桌面 App（bundle `com.openai.codex`）、`codex` 0.144.2、**Plus** 账户。

- 走的是 OpenAI [已公开文档的 `codex app-server` 接口](https://developers.openai.com/zh-Hans/docs/app-server) `account/rateLimits/read`。客户端会先完成规定的初始化握手，再兼容读取单桶结构或 `rateLimitsByLimitId.codex` 多桶结构。app-server 返回结构仍可能随 codex 版本演进；`install.sh` 会先自检、当场告诉你能不能读到额度。
- 仅在 Plus 账户上实测；代码会按返回的窗口通用处理，但 Free、Pro、Team 和其他套餐均未验证。
- 需要 Xcode 命令行工具提供 `/usr/bin/python3`（缺失则 `xcode-select --install`）。

## 说明

- 只在右上角菜单栏显示——**不在程序坞（Dock）出现图标**，也不占顶部应用菜单。
- 自启只在崩溃（非零退出）时自动拉起；你主动点「退出」不会被强行复活。
- 崩溃日志：`/tmp/codexbar.err.log`、`/tmp/codexbar.out.log`。
- 卸载后仍会保留用户级 `rumps` 依赖和已有 `/tmp` 日志，除非另行清理。
- 仅支持 macOS。

## 许可

[MIT](LICENSE)
