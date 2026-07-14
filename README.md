# Codex Quota Bar

A tiny macOS **menu bar** widget that shows your Codex (ChatGPT desktop app) usage limits at a glance — so you don't have to click into Settings every time.

一个 macOS **菜单栏**小工具，扫一眼就知道 Codex（ChatGPT 桌面 App）还剩多少额度，不用每次点进设置里翻。

```
🟢 5h 88% · 🟠 7d 46%
```

- Colored text = how much you have **left**: 🟢 green > 50% · 🟠 orange 20–50% · 🔴 red < 20% (or limit reached). Each window is colored independently.
- `5h` = the 5‑hour window, `7d` = the 7‑day (weekly) window.
- Click to open a dropdown: per‑window remaining %, a progress bar, reset countdown, plan type, last refresh, and a **Refresh now** button.

> The 5‑hour window only appears when you've used Codex recently; when idle you may see just the weekly window. That's normal.

## How it works

It reads your limits through the official `codex` binary's app‑server RPC method `account/rateLimits/read` (the same data the Settings page shows).

- **Costs no quota** — it's a metadata read, not a generation request.
- **Never touches your credentials** — token refresh is handled by the official binary; this tool writes zero auth code.

它通过官方 `codex` 二进制的 app‑server 接口 `account/rateLimits/read` 读额度（和设置页同一条路）：**不消耗额度**（元数据读取，非生成请求），**不碰你的登录凭证**（token 刷新全交给官方程序）。

## Requirements / 依赖

- macOS with the **ChatGPT desktop app** installed at `/Applications/ChatGPT.app` and logged in.
- Uses the system `/usr/bin/python3`; `install.sh` installs the only dependency (`rumps`) for you.

## Install / 安装

```bash
git clone <your-repo-url> codex-quota-bar
cd codex-quota-bar
./install.sh
```

That's it — the menu bar icon appears and auto‑starts on login.
装完即出现在菜单栏，并会开机自启。

Uninstall / 卸载：

```bash
./uninstall.sh
```

## Run without auto‑start / 只想临时试跑（不装自启）

```bash
/usr/bin/python3 codex_quota_bar.py
```

Debug the fetch alone / 单独调试取数（打印 JSON）：

```bash
/usr/bin/python3 fetch_quota.py
```

## Files / 文件

| File | Purpose |
|---|---|
| `fetch_quota.py` | Drives `codex app-server`, returns a normalized quota dict |
| `codex_quota_bar.py` | The menu bar app (rumps); display logic is pure & unit‑testable |
| `com.user.codexquota.plist.template` | LaunchAgent template (paths filled in by `install.sh`) |
| `install.sh` / `uninstall.sh` | One‑command setup / teardown |

Background refresh runs every 3 minutes; you can also hit **Refresh now** anytime.
后台每 3 分钟自动刷新，也可随时点「立即刷新」。

## Notes

- Auto‑start only relaunches on a crash (non‑zero exit); if you click **Quit** it stays quit.
- Crash logs: `/tmp/codexbar.err.log`, `/tmp/codexbar.out.log`.
- macOS only. Tested on the ChatGPT desktop app (bundle id `com.openai.codex`).

## Compatibility / 兼容性

Verified on: macOS 26 (Apple Silicon), ChatGPT desktop app bundle `com.openai.codex`,
`codex` 0.144.2, **Plus** plan.

- Reads limits through the **experimental** `codex app-server` RPC (`account/rateLimits/read`).
  OpenAI may change this interface in future codex versions; if a release breaks it, the fetch
  layer in `fetch_quota.py` needs a small update. `install.sh` runs a self‑test so you'll know
  immediately whether the interface works on your machine.
- Only tested on a Plus account. Other plans (Free/Pro/Team) return windows generically and
  should work, but are untested.
- Requires Xcode Command Line Tools for `/usr/bin/python3` (`xcode-select --install` if missing).

通过**实验性**接口 `codex app-server`（`account/rateLimits/read`）读额度，官方后续改版可能需要
同步更新 `fetch_quota.py`。仅在 Plus 账户上实测；`install.sh` 会先自检、当场告诉你能不能读到。

## License

MIT

