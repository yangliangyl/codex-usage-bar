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
import math
import os
import re
import subprocess
import threading
import time
from collections import deque

# codex 二进制：优先桌面 App 内置，其次 PATH 上的 codex
_APP_CODEX = "/Applications/ChatGPT.app/Contents/Resources/codex"
_STDERR_TAIL_BYTES = 4096
_STDOUT_LINE_BYTES = 1024 * 1024
_CLEANUP_GRACE_SECONDS = 1.5


def _find_codex():
    if os.path.isfile(_APP_CODEX) and os.access(_APP_CODEX, os.X_OK):
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
    if not isinstance(snapshot, dict):
        return []
    windows = []
    for w in (snapshot.get("primary"), snapshot.get("secondary")):
        if not isinstance(w, dict):
            continue
        used = w.get("usedPercent")
        if isinstance(used, bool) or not isinstance(used, (int, float)):
            continue
        if not math.isfinite(used):
            continue
        used = min(100, max(0, used))
        if isinstance(used, float):
            used = int(used) if used.is_integer() else round(used, 2)
        mins = w.get("windowDurationMins")
        if (
            isinstance(mins, bool)
            or not isinstance(mins, (int, float))
            or not math.isfinite(mins)
            or mins <= 0
        ):
            mins = None
        elif isinstance(mins, float) and mins.is_integer():
            mins = int(mins)
        resets_at = w.get("resetsAt")
        if (
            isinstance(resets_at, bool)
            or not isinstance(resets_at, (int, float))
            or not math.isfinite(resets_at)
        ):
            resets_at = None
        elif isinstance(resets_at, float) and resets_at.is_integer():
            resets_at = int(resets_at)
        windows.append({
            "label": _label_window(mins),
            "window_mins": mins,
            "used_percent": used,
            "remaining_percent": max(0, 100 - used),
            "resets_at": resets_at,
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


def _remaining(deadline):
    return max(0.0, deadline - time.monotonic())


def _redact_stderr(text):
    """限长、压缩并脱敏 app-server 错误摘要。"""
    text = re.sub(r"/Users/[^/\s]+", "/Users/***", text)
    text = re.sub(r"/home/[^/\s]+", "/home/***", text)
    text = re.sub(
        r"(?i)\b(bearer\s+)([a-z0-9._~+/=-]+)",
        r"\1***",
        text,
    )
    text = re.sub(
        r"(?i)\b(token|api[_-]?key|secret|password|passwd)\b\s*[:=]\s*[^\s,;]+",
        r"\1=***",
        text,
    )
    text = re.sub(r"\b(?:sk-[A-Za-z0-9_-]{12,}|gh[opsu]_[A-Za-z0-9]{12,})\b", "***", text)
    return " ".join(text.split())[-500:]


def _read_stdout(stream, responses, response_events, done):
    """Consume stdout in one place; parse newline-delimited JSON responses."""
    pending = b""
    dropping_oversized_line = False
    try:
        while True:
            chunk = os.read(stream.fileno(), 4096)
            if not chunk:
                break
            pending += chunk
            while b"\n" in pending:
                raw_line, pending = pending.split(b"\n", 1)
                if dropping_oversized_line:
                    dropping_oversized_line = False
                    continue
                _record_response(raw_line, responses, response_events)
            if len(pending) > _STDOUT_LINE_BYTES:
                pending = b""
                dropping_oversized_line = True
        if pending and not dropping_oversized_line:
            _record_response(pending, responses, response_events)
    except (OSError, ValueError):
        pass
    finally:
        done.set()


def _record_response(raw_line, responses, response_events):
    raw_line = raw_line.strip()
    if not raw_line:
        return
    try:
        msg = json.loads(raw_line.decode("utf-8", errors="replace"))
    except (TypeError, ValueError):
        return
    rid = msg.get("id")
    if rid is not None and ("result" in msg or "error" in msg):
        responses[rid] = msg
        event = response_events.get(rid)
        if event:
            event.set()


def _read_stderr(stream, tail, done):
    """Continuously drain stderr into a bounded byte tail."""
    try:
        while True:
            chunk = os.read(stream.fileno(), 4096)
            if not chunk:
                break
            tail.extend(chunk)
    except (OSError, ValueError):
        pass
    finally:
        done.set()


def _wait_for_response(response_event, stdout_done, deadline):
    while True:
        if response_event.is_set():
            return "response"
        if stdout_done.is_set():
            return "exited"
        remaining = _remaining(deadline)
        if remaining <= 0:
            return "timeout"
        response_event.wait(min(0.05, remaining))


def _response_error(response):
    error = response.get("error") if isinstance(response, dict) else None
    if error is None:
        return None
    message = error.get("message", str(error)) if isinstance(error, dict) else str(error)
    return _redact_stderr(message)


def _select_snapshot(data):
    """Return (snapshot, error) while supporting current single/multi-bucket shapes."""
    if not isinstance(data, dict):
        return None, "app-server 返回的 result 不是对象"
    by_id = data.get("rateLimitsByLimitId")
    if isinstance(by_id, dict) and isinstance(by_id.get("codex"), dict):
        return by_id["codex"], None
    single = data.get("rateLimits")
    if isinstance(single, dict):
        return single, None
    return None, "app-server 响应缺少 Codex 额度快照"


def _cleanup_process(proc, threads):
    """Bound process termination and reader cleanup to a small grace period."""
    cleanup_deadline = time.monotonic() + _CLEANUP_GRACE_SECONDS

    try:
        if proc.stdin:
            proc.stdin.close()
    except (OSError, ValueError):
        pass

    if proc.poll() is None:
        try:
            proc.terminate()
        except OSError:
            pass
        try:
            proc.wait(timeout=min(0.75, _remaining(cleanup_deadline)))
        except subprocess.TimeoutExpired:
            try:
                proc.kill()
            except OSError:
                pass
            try:
                proc.wait(timeout=_remaining(cleanup_deadline))
            except subprocess.TimeoutExpired:
                pass

    for stream in (proc.stdout, proc.stderr):
        try:
            if stream:
                stream.close()
        except (OSError, ValueError):
            pass

    for thread in threads:
        remaining = _remaining(cleanup_deadline)
        if remaining <= 0:
            break
        thread.join(timeout=remaining)


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
    deadline = time.monotonic() + max(0.0, float(timeout))

    codex = _find_codex()
    if not codex:
        result["error"] = "找不到 codex 二进制（ChatGPT.app 未安装？）"
        return result

    try:
        proc = subprocess.Popen(
            [codex, "app-server"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            bufsize=0,
        )
    except Exception as e:
        result["error"] = f"启动 app-server 失败：{_redact_stderr(str(e))}"
        return result

    responses = {}
    response_events = {1: threading.Event(), 2: threading.Event()}
    stdout_done = threading.Event()
    stderr_done = threading.Event()
    stderr_tail = deque(maxlen=_STDERR_TAIL_BYTES)
    stdout_thread = threading.Thread(
        target=_read_stdout,
        args=(proc.stdout, responses, response_events, stdout_done),
        name="codex-quota-stdout",
        daemon=True,
    )
    stderr_thread = threading.Thread(
        target=_read_stderr,
        args=(proc.stderr, stderr_tail, stderr_done),
        name="codex-quota-stderr",
        daemon=True,
    )
    threads = (stdout_thread, stderr_thread)
    for thread in threads:
        thread.start()

    def send(obj):
        proc.stdin.write((json.dumps(obj) + "\n").encode("utf-8"))
        proc.stdin.flush()

    phase = "initialize"
    wait_status = "timeout"
    communication_error = None
    protocol_error = None
    try:
        send({"id": 1, "method": "initialize",
              "params": {"clientInfo": {"name": "codex-quota-bar", "version": "0.1.0"}}})
        wait_status = _wait_for_response(response_events[1], stdout_done, deadline)
        if wait_status == "response":
            protocol_error = _response_error(responses.get(1, {}))
        if wait_status == "response" and not protocol_error:
            send({"method": "initialized"})
            send({"id": 2, "method": "account/rateLimits/read"})
            phase = "read"
            wait_status = _wait_for_response(response_events[2], stdout_done, deadline)
    except Exception as e:
        communication_error = _redact_stderr(str(e))
    finally:
        _cleanup_process(proc, threads)

    stderr_detail = _redact_stderr(bytes(stderr_tail).decode("utf-8", errors="replace"))

    if communication_error:
        result["error"] = f"与 app-server 通信失败：{communication_error}"
        if stderr_detail:
            result["error"] += f" 详情：{stderr_detail}"
        return result

    if protocol_error:
        result["error"] = f"app-server 初始化失败：{protocol_error}"
        if stderr_detail:
            result["error"] += f" 详情：{stderr_detail}"
        return result

    if wait_status != "response":
        if wait_status == "exited":
            action = "初始化" if phase == "initialize" else "返回额度"
            result["error"] = f"app-server 在{action}前已退出。"
        else:
            if phase == "initialize":
                result["error"] = "初始化 app-server 超时。"
            else:
                result["error"] = "读取额度超时（可能未登录 ChatGPT）。"
        if stderr_detail:
            result["error"] += f" 详情：{stderr_detail}"
        return result

    resp = responses.get(2, {})
    read_error = _response_error(resp)
    if read_error:
        result["error"] = (
            f"app-server 返回错误：{read_error}（可能需要在 ChatGPT App 里重新登录）"
        )
        return result

    snap, shape_error = _select_snapshot(resp.get("result"))
    if shape_error:
        result["error"] = shape_error
        return result

    plan_type = snap.get("planType")
    reached_type = snap.get("rateLimitReachedType")
    result["plan_type"] = plan_type if isinstance(plan_type, str) else None
    result["rate_limit_reached_type"] = reached_type if isinstance(reached_type, str) else None
    result["windows"] = _normalize(snap)
    result["ok"] = True
    if not result["windows"]:
        # 拿到响应但没有任何窗口数据（例如刚重置、全新账户）
        result["error"] = "暂无额度窗口数据（可能近期无使用记录）"
    return result


if __name__ == "__main__":
    print(json.dumps(fetch_quota(), ensure_ascii=False, indent=2))
