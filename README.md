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

- **Costs no quota** — it's a metadata read, not a generation request.
- **Never touches your credentials** — token refresh is handled by the official binary; this tool writes zero auth code.

## Requirements

- macOS with the **ChatGPT desktop app** installed at `/Applications/ChatGPT.app` and logged in.
- Uses the system `/usr/bin/python3`; `install.sh` installs the only dependency (`rumps`) for you.

## Install

### Easiest — let Codex do it (no terminal needed)

You already have Codex. Just tell it:

> Clone `github.com/yangliangyl/codex-usage-bar` locally and run its `install.sh` to set up this menu bar tool for me.

Codex clones the repo and runs the installer for you — you don't type a single command.

### Manual — two commands

```bash
git clone https://github.com/yangliangyl/codex-usage-bar.git
cd codex-usage-bar
./install.sh
```

That's it — the menu bar icon appears and auto‑starts on login.

Uninstall:

```bash
./uninstall.sh
```

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
| `com.user.codexquota.plist.template` | LaunchAgent template (paths filled in by `install.sh`) |
| `install.sh` / `uninstall.sh` | One‑command setup / teardown |

Background refresh runs every 3 minutes; you can also hit **Refresh now** anytime.

## Compatibility

Verified on: macOS 26 (Apple Silicon), ChatGPT desktop app bundle `com.openai.codex`,
`codex` 0.144.2, **Plus** plan.

- Reads limits through the **experimental** `codex app-server` RPC (`account/rateLimits/read`).
  OpenAI may change this interface in future codex versions; if a release breaks it, the fetch
  layer in `fetch_quota.py` needs a small update. `install.sh` runs a self‑test so you'll know
  immediately whether the interface works on your machine.
- Only tested on a Plus account. Other plans (Free/Pro/Team) return windows generically and
  should work, but are untested.
- Requires Xcode Command Line Tools for `/usr/bin/python3` (`xcode-select --install` if missing).

## Notes

- Auto‑start only relaunches on a crash (non‑zero exit); if you click **Quit** it stays quit.
- Crash logs: `/tmp/codexbar.err.log`, `/tmp/codexbar.out.log`.
- macOS only.

## License

[MIT](LICENSE)
