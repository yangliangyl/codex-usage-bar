#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import math
import os
from pathlib import Path
import stat
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import fetch_quota as quota


FAKE_CODEX = r'''#!__PYTHON__
import json
import os
import sys
import time

mode = os.environ.get("FAKE_CODEX_MODE", "normal")
pid_file = os.environ.get("FAKE_CODEX_PID_FILE")
trace_file = os.environ.get("FAKE_CODEX_TRACE_FILE")
if pid_file:
    with open(pid_file, "w", encoding="utf-8") as handle:
        handle.write(str(os.getpid()))

def trace(value):
    if trace_file:
        with open(trace_file, "a", encoding="utf-8") as handle:
            handle.write(value + "\n")

def reply(value):
    sys.stdout.write(json.dumps(value) + "\n")
    sys.stdout.flush()

if mode == "early_exit":
    sys.stderr.write("fake app-server exited early\n")
    sys.stderr.flush()
    raise SystemExit(3)

if mode == "stderr_flood":
    credential_fixture = "token" + "=fixture-sensitive-value"
    path_fixture = "/" + "Users" + "/fixture-user/example"
    payload = credential_fixture + " " + path_fixture + " " + ("x" * 4096)
    while True:
        sys.stderr.write(payload)
        sys.stderr.flush()
        time.sleep(0.001)

for raw in sys.stdin:
    try:
        message = json.loads(raw)
    except ValueError:
        continue
    method = message.get("method", "")
    trace(method)
    if message.get("id") == 1:
        if mode == "no_response":
            while True:
                time.sleep(1)
        if mode == "malformed":
            sys.stdout.write("not-json\n")
            sys.stdout.flush()
            while True:
                time.sleep(1)
        if mode == "initialize_error":
            reply({"id": 1, "error": {"code": -32000, "message": "fixture init rejected"}})
            continue
        reply({"id": 1, "result": {"serverInfo": {"name": "fixture"}}})
        continue
    if message.get("id") != 2:
        continue
    if mode == "read_no_response":
        while True:
            time.sleep(1)
    if mode == "read_error":
        reply({"id": 2, "error": {"code": -32001, "message": "fixture read rejected"}})
        while True:
            time.sleep(1)
    response = {
        "id": 2,
        "result": {
            "rateLimits": {
                "planType": "test",
                "primary": {
                    "usedPercent": 25,
                    "windowDurationMins": 300,
                    "resetsAt": 1234567890,
                },
                "secondary": None,
            }
        },
    }
    reply(response)
    while True:
        time.sleep(1)
'''


class FetchQuotaProcessTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.fake_codex = Path(self.temp_dir.name) / "fake-codex"
        script = FAKE_CODEX.replace("__PYTHON__", sys.executable)
        self.fake_codex.write_text(script, encoding="utf-8")
        self.fake_codex.chmod(self.fake_codex.stat().st_mode | stat.S_IXUSR)

    def tearDown(self):
        self.temp_dir.cleanup()

    def _fetch(self, mode, timeout=1.3):
        pid_file = Path(self.temp_dir.name) / f"{mode}.pid"
        trace_file = Path(self.temp_dir.name) / f"{mode}.trace"
        env = {
            "FAKE_CODEX_MODE": mode,
            "FAKE_CODEX_PID_FILE": str(pid_file),
            "FAKE_CODEX_TRACE_FILE": str(trace_file),
        }
        started = time.monotonic()
        with mock.patch.object(quota, "_find_codex", return_value=str(self.fake_codex)):
            with mock.patch.dict(os.environ, env, clear=False):
                result = quota.fetch_quota(timeout=timeout)
        elapsed = time.monotonic() - started
        self.assertLess(elapsed, timeout + quota._CLEANUP_GRACE_SECONDS + 0.8)
        self._assert_child_reaped(pid_file)
        leaked = [
            thread.name
            for thread in threading.enumerate()
            if thread.name.startswith("codex-quota-")
        ]
        self.assertEqual([], leaked, f"reader threads leaked: {leaked}")
        trace = trace_file.read_text(encoding="utf-8").splitlines() if trace_file.exists() else []
        return result, elapsed, trace

    def _assert_child_reaped(self, pid_file):
        start_deadline = time.monotonic() + 0.5
        while not pid_file.exists() and time.monotonic() < start_deadline:
            time.sleep(0.02)
        self.assertTrue(pid_file.exists(), "fake app-server did not start")
        pid = int(pid_file.read_text(encoding="utf-8"))
        deadline = time.monotonic() + 0.5
        while time.monotonic() < deadline:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                return
            time.sleep(0.02)
        self.fail(f"fake app-server process {pid} was not reaped")

    def test_normal_response_uses_required_handshake_order(self):
        result, _, trace = self._fetch("normal", timeout=1.5)
        self.assertTrue(result["ok"])
        self.assertEqual(result["plan_type"], "test")
        self.assertEqual(result["windows"][0]["label"], "5h")
        self.assertEqual(result["windows"][0]["remaining_percent"], 75)
        self.assertEqual(
            ["initialize", "initialized", "account/rateLimits/read"], trace
        )

    def test_initialize_error_stops_before_initialized_or_read(self):
        result, _, trace = self._fetch("initialize_error")
        self.assertFalse(result["ok"])
        self.assertIn("初始化失败", result["error"])
        self.assertEqual(["initialize"], trace)

    def test_initialize_timeout_cleans_up(self):
        result, _, trace = self._fetch("no_response")
        self.assertFalse(result["ok"])
        self.assertIn("初始化 app-server 超时", result["error"])
        self.assertEqual(["initialize"], trace)

    def test_read_timeout_happens_after_successful_handshake(self):
        result, _, trace = self._fetch("read_no_response")
        self.assertFalse(result["ok"])
        self.assertIn("读取额度超时", result["error"])
        self.assertEqual(
            ["initialize", "initialized", "account/rateLimits/read"], trace
        )

    def test_continuous_stderr_is_bounded_and_redacted(self):
        result, _, _ = self._fetch("stderr_flood")
        self.assertFalse(result["ok"])
        self.assertLess(len(result["error"]), 800)
        self.assertNotIn("fixture-sensitive-value", result["error"])
        self.assertNotIn("/" + "Users" + "/fixture-user", result["error"])

    def test_malformed_json_times_out_and_cleans_up(self):
        result, _, _ = self._fetch("malformed")
        self.assertFalse(result["ok"])
        self.assertIn("超时", result["error"])

    def test_early_exit_returns_without_waiting_for_full_timeout(self):
        result, elapsed, _ = self._fetch("early_exit", timeout=2.0)
        self.assertFalse(result["ok"])
        self.assertLess(elapsed, 1.8)
        self.assertTrue(
            "通信失败" in result["error"] or "已退出" in result["error"],
            result["error"],
        )

    def test_read_error_is_explicit(self):
        result, _, _ = self._fetch("read_error")
        self.assertFalse(result["ok"])
        self.assertIn("fixture read rejected", result["error"])

    def test_missing_binary_is_explicit(self):
        with mock.patch.object(quota, "_find_codex", return_value=None):
            result = quota.fetch_quota(timeout=0.1)
        self.assertFalse(result["ok"])
        self.assertIn("找不到 codex", result["error"])


class NormalizeTests(unittest.TestCase):
    def test_single_and_dual_windows_are_normalized_and_sorted(self):
        single = quota._normalize({
            "primary": {"usedPercent": 30, "windowDurationMins": 300, "resetsAt": 10},
            "secondary": None,
        })
        self.assertEqual(["5h"], [window["label"] for window in single])

        dual = quota._normalize({
            "primary": {"usedPercent": 10, "windowDurationMins": 10080, "resetsAt": 20},
            "secondary": {"usedPercent": 20, "windowDurationMins": 300, "resetsAt": 10},
        })
        self.assertEqual(["5h", "7d"], [window["label"] for window in dual])

    def test_null_unknown_and_invalid_fields_do_not_crash(self):
        self.assertEqual([], quota._normalize(None))
        self.assertEqual([], quota._normalize({"primary": None, "futureField": {"x": 1}}))
        windows = quota._normalize({
            "primary": {
                "usedPercent": "25",
                "windowDurationMins": 300,
                "resetsAt": 10,
            },
            "secondary": {
                "usedPercent": 50,
                "windowDurationMins": "300",
                "resetsAt": "later",
                "unknown": True,
            },
        })
        self.assertEqual(1, len(windows))
        self.assertEqual("?", windows[0]["label"])
        self.assertIsNone(windows[0]["resets_at"])

    def test_percentages_are_clamped_and_nonfinite_values_are_dropped(self):
        windows = quota._normalize({
            "primary": {"usedPercent": -4, "windowDurationMins": 300},
            "secondary": {"usedPercent": 125, "windowDurationMins": 10080},
        })
        self.assertEqual([0, 100], [window["used_percent"] for window in windows])
        self.assertEqual([100, 0], [window["remaining_percent"] for window in windows])
        self.assertEqual([], quota._normalize({
            "primary": {"usedPercent": math.nan, "windowDurationMins": 300}
        }))

    def test_multi_bucket_codex_is_preferred_and_shape_errors_are_explicit(self):
        codex = {"primary": {"usedPercent": 1, "windowDurationMins": 300}}
        fallback = {"primary": {"usedPercent": 99, "windowDurationMins": 300}}
        selected, error = quota._select_snapshot({
            "rateLimits": fallback,
            "rateLimitsByLimitId": {"codex": codex, "other": {}},
            "future": "ignored",
        })
        self.assertIs(codex, selected)
        self.assertIsNone(error)

        selected, error = quota._select_snapshot({"rateLimitsByLimitId": {"other": {}}})
        self.assertIsNone(selected)
        self.assertIn("缺少", error)


if __name__ == "__main__":
    unittest.main()
