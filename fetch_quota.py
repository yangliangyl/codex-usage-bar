#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
取数模块：通过官方 codex app-server 的 JSON-RPC 读取 Codex 账户额度。

关键点：
- 走 `account/rateLimits/read` —— 这是元数据读取，不消耗你的 Codex 额度。
- token 过期刷新、接口细节都交给官方二进制处理，我们不碰认证。
- 返回统一结构；失败显式带 error，不静默吞掉。

也可单独运行做调试： python3 fetch_quota.py   （打印 JSON）
"""

import json
import os
import subprocess
import threading
import time

# codex 二进制：优先桌面 App 内置，其次 PATH 上的 codex
_APP_CODEX = "/Applications/ChatGPT.app/Contents/Resources/codex"


def _find_codex():
    if os.path.exists(_APP_CODEX):
        return _APP_CODEX
    from shutil import which
    p = which("codex")
    return p  # 可能为 None


def _label_window(mins):
    """把窗口时长（分钟）转成人类可读标签：300->5h, 10080->7d, 1440->1d。"""
    if not mins:
        return "?"
    if mins % 1440 == 0:
        return f"{mins // 1440}d"
    if mins % 60 == 0:
        return f"{mins // 60}h"
    return f"{mins}m"


def _normalize(snapshot):
    """把 RateLimitSnapshot 里存在的窗口抽成列表，按时长排序（短窗口在前）。"""
    windows = []
    for w in (snapshot.get("primary"), snapshot.get("secondary")):
        if not w:
            continue
        used = w.get("usedPercent")
        if used is None:
            continue
        windows.append({
            "label": _label_window(w.get("windowDurationMins")),
            "window_mins": w.get("windowDurationMins"),
            "used_percent": used,
            "remaining_percent": max(0, 100 - used),
            "resets_at": w.get("resetsAt"),
        })
    # 去重（primary/secondary 偶尔重复同一窗口）+ 按时长升序
    seen = set()
    uniq = []
    for w in sorted(windows, key=lambda x: (x["window_mins"] or 0)):
        key = (w["window_mins"], w["used_percent"])
        if key in seen:
            continue
        seen.add(key)
        uniq.append(w)
    return uniq


def fetch_quota(timeout=25):
    """
    返回：
    {
      "ok": bool,
      "error": str | None,
      "fetched_at": int (unix秒),
      "plan_type": str | None,
      "rate_limit_reached_type": str | None,
      "windows": [ {label, window_mins, used_percent, remaining_percent, resets_at}, ... ],
    }
    """
    result = {
        "ok": False, "error": None, "fetched_at": int(time.time()),
        "plan_type": None, "rate_limit_reached_type": None, "windows": [],
    }

    codex = _find_codex()
    if not codex:
        result["error"] = "找不到 codex 二进制（ChatGPT.app 未安装？）"
        return result

    try:
        proc = subprocess.Popen(
            [codex, "app-server"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, bufsize=1,
        )
    except Exception as e:
        result["error"] = f"启动 app-server 失败：{e}"
        return result

    responses = {}
    got_read = threading.Event()

    def reader():
        try:
            for line in proc.stdout:
                line = line.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                except ValueError:
                    continue
                rid = msg.get("id")
                if rid is not None and ("result" in msg or "error" in msg):
                    responses[rid] = msg
                    if rid == 2:
                        got_read.set()
        except Exception:
            pass

    t = threading.Thread(target=reader, daemon=True)
    t.start()

    def send(obj):
        proc.stdin.write(json.dumps(obj) + "\n")
        proc.stdin.flush()

    try:
        send({"id": 1, "method": "initialize",
              "params": {"clientInfo": {"name": "codex-quota-bar", "version": "0.1.0"}}})
        time.sleep(0.4)
        send({"method": "initialized"})
        time.sleep(0.2)
        send({"id": 2, "method": "account/rateLimits/read"})
    except Exception as e:
        result["error"] = f"与 app-server 通信失败：{e}"
        _kill(proc)
        return result

    ok = got_read.wait(timeout=timeout)
    stderr_tail = ""
    if not ok:
        try:
            stderr_tail = (proc.stderr.read() or "")[-500:]
        except Exception:
            pass
    _kill(proc)

    if not ok:
        result["error"] = "读取额度超时（可能未登录 ChatGPT）。" + (
            f" 详情：{stderr_tail.strip()}" if stderr_tail.strip() else "")
        return result

    resp = responses.get(2, {})
    if "error" in resp:
        err = resp["error"]
        msg = err.get("message", str(err)) if isinstance(err, dict) else str(err)
        result["error"] = f"app-server 返回错误：{msg}（可能需要在 ChatGPT App 里重新登录）"
        return result

    data = resp.get("result", {})
    snap = data.get("rateLimits") or {}
    # 优先用 codex 桶（多桶视图更明确）
    by_id = data.get("rateLimitsByLimitId") or {}
    if "codex" in by_id and by_id["codex"]:
        snap = by_id["codex"]

    result["plan_type"] = snap.get("planType")
    result["rate_limit_reached_type"] = snap.get("rateLimitReachedType")
    result["windows"] = _normalize(snap)
    result["ok"] = True
    if not result["windows"]:
        # 拿到响应但没有任何窗口数据（例如刚重置、全新账户）
        result["error"] = "暂无额度窗口数据（可能近期无使用记录）"
    return result


def _kill(proc):
    try:
        proc.terminate()
        proc.wait(timeout=3)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


if __name__ == "__main__":
    print(json.dumps(fetch_quota(), ensure_ascii=False, indent=2))
