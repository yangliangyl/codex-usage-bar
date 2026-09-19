<!-- Language switcher -->
**English** · [简体中文](README.zh-CN.md)

# Codex Quota Bar

A tiny macOS **menu bar** widget that shows your Codex (ChatGPT desktop app) usage limits at a glance — so you don't have to click into Settings every time.

```
🟢 5h 88% · 🟠 7d 46%
```

- Colored text = how much you have **left**: 🟢 green > 50% · 🟠 orange 20–50% · 🔴 red < 20% (or limit reached). Each window is colored independently.
- `5h` = the 5‑hour window, `7d` = the 7‑day (weekly) window.
- Click to open a dropdown: per‑window remaining %, a progress bar, reset countdown, plan type, last refresh, and a **Refresh now** button.

> The 5‑hour window only appears when you've used Codex recently; when idle you may see just the weekly window. That's normal.

## How it works

It reads your limits through the official `codex` binary's app‑server RPC method `account/rateLimits/read` (the same data the Settings page shows).

- The tool sends a rate-limit metadata query and does not send a model-generation request. Service-side metering policy is controlled by OpenAI, not by this repository.
- This repository's fetch code does not read or store account tokens directly. Authentication, network access, and any credential refresh are handled by the official `codex` binary.

## Requirements

- macOS with the **ChatGPT desktop app** installed at `/Applications/ChatGPT.app` and logged in.
- Uses the system `/usr/bin/python3`; `install.sh` installs the only dependency from `requirements.txt` (`rumps>=0.4,<0.5`) into the current user's shared Python user site when needed.

## Install

### What the installer changes

`install.sh` is not a read-only preview. It may:

- install `rumps` into the current user's system-Python environment if missing;
- copy runtime files to `~/Library/Application Support/CodexQuotaBar`;
- run one real quota query as a self-test;
- write `~/Library/LaunchAgents/com.user.codexquota.plist` and load it for login auto-start;
- write runtime logs to `/tmp/codexbar.err.log` and `/tmp/codexbar.out.log` after launch.

Review the script before running it. Installation does not require this repository to read or store your token directly, but the official `codex` process uses your existing account state to perform the query.

Preview the exact paths and side effects without installing, querying the account, writing files, or loading a service:

```bash
./install.sh --plan
```

### Easiest — let Codex install it (no terminal needed)

You already have Codex. Paste it this one instruction (macOS only):

> Install the macOS menu-bar tool at **github.com/yangliangyl/codex-usage-bar** for me. Clone the repo to a local folder, `cd` in, and first run `./install.sh --plan`. Show me that plan and wait for my confirmation before running `./install.sh`. The real install may add the compatible rumps dependency to my shared system-Python user site, copy runtime files to `~/Library/Application Support/CodexQuotaBar`, read my quota once for self-test, and load a LaunchAgent for autostart. If `/usr/bin/python3` is missing, tell me to run `xcode-select --install` first.

Codex clones the repo and runs the installer for you — you don't type any commands yourself (you just approve when it asks). Afterwards the tool lives in the menu bar (no Dock icon) and starts on every login.

**Prerequisites:** macOS, the ChatGPT desktop app installed and logged in.

### Manual — preview, then install

```bash
git clone https://github.com/yangliangyl/codex-usage-bar.git
cd codex-usage-bar
./install.sh --plan
./install.sh
```

The menu bar icon should appear and auto-start on login if the self-test, dependency install, and LaunchAgent load succeed.

Uninstall:

```bash
./uninstall.sh --plan
./uninstall.sh
```

The uninstaller unloads and removes the LaunchAgent, stops the menu-bar process, and removes `~/Library/Application Support/CodexQuotaBar`. It does not uninstall `rumps` or remove existing `/tmp/codexbar.*.log` files.

## Run without auto‑start

```bash
/usr/bin/python3 codex_quota_bar.py
```

Debug the fetch alone (prints JSON):

```bash
/usr/bin/python3 fetch_quota.py
```

## Files

| File | Purpose |
|---|---|
| `fetch_quota.py` | Drives `codex app-server`, returns a normalized quota dict |
| `codex_quota_bar.py` | The menu bar app (rumps); display logic is pure & unit‑testable |
| `requirements.txt` | Compatible runtime dependency range for the system Python user site |
| `com.user.codexquota.plist.template` | LaunchAgent template (paths filled in by `install.sh`) |
| `install.sh` / `uninstall.sh` | One‑command setup / teardown |

Background refresh runs every 3 minutes; you can also hit **Refresh now** anytime.

## Compatibility

Verified on: macOS 26 (Apple Silicon), ChatGPT desktop app bundle `com.openai.codex`,
`codex` 0.144.2, **Plus** plan.

- Reads limits through OpenAI's [documented `codex app-server` RPC](https://developers.openai.com/docs/app-server)
  (`account/rateLimits/read`). The client completes the required initialize handshake before
  reading either the backward-compatible single bucket or `rateLimitsByLimitId.codex`. App-server
  response shapes can evolve with codex releases; `install.sh` runs a self-test so you'll know
  immediately whether the interface works on your machine.
- Only tested on a Plus account. The code handles returned windows generically, but Free, Pro,
  Team, and other plans are unverified.
- Requires Xcode Command Line Tools for `/usr/bin/python3` (`xcode-select --install` if missing).

## Notes

- Lives only in the menu bar (top‑right) — **no Dock icon**, no app menu.
- Auto‑start only relaunches on a crash (non‑zero exit); if you click **Quit** it stays quit.
- Crash logs: `/tmp/codexbar.err.log`, `/tmp/codexbar.out.log`.
- Uninstall keeps the user-level `rumps` dependency and existing `/tmp` log files unless you remove them separately.
- macOS only.

## License

[MIT](LICENSE)
