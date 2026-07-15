#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Codex 额度菜单栏悬浮工具（rumps 版）。

菜单栏：颜色圆点 + 各窗口剩余额度%（扫一眼就知道紧张程度）。
下拉：每个窗口的剩余%/进度条/重置倒计时、账户 plan、上次刷新、手动刷新。

必须用 /usr/bin/python3 运行（rumps 装在系统 python 上；默认 PATH 的 python3 无 rumps）：
    /usr/bin/python3 codex_quota_bar.py

取数走 fetch_quota.py（官方 app-server 元数据接口，零额度消耗）。
"""

import os
import subprocess
import threading
import time

import rumps
from AppKit import (NSColor, NSFont, NSForegroundColorAttributeName,
                    NSFontAttributeName, NSApplication,
                    NSApplicationActivationPolicyAccessory)
from Foundation import NSMutableAttributedString

from fetch_quota import fetch_quota

REFRESH_INTERVAL = 180  # 后台自动刷新间隔（秒）
BAR_WIDTH = 10          # 下拉里进度条宽度


def fmt_countdown(resets_at):
    if not resets_at:
        return "—"
    delta = int(resets_at - time.time())
    if delta <= 0:
        return "即将重置"
    d, rem = divmod(delta, 86400)
    h, rem = divmod(rem, 3600)
    m, _ = divmod(rem, 60)
    if d > 0:
        return f"{d}天{h}小时"
    if h > 0:
        return f"{h}小时{m}分"
    return f"{m}分"


def bar(remaining_percent):
    filled = round(remaining_percent / 100 * BAR_WIDTH)
    filled = max(0, min(BAR_WIDTH, filled))
    return "█" * filled + "░" * (BAR_WIDTH - filled)


def dot(remaining_percent):
    if remaining_percent > 50:
        return "🟢"
    if remaining_percent >= 20:
        return "🟡"
    return "🔴"


# 菜单栏文字颜色：鲜艳、深浅色菜单栏都清晰
def ns_color(remaining_percent, reached=False):
    if reached or remaining_percent < 20:
        return NSColor.colorWithSRGBRed_green_blue_alpha_(1.00, 0.27, 0.23, 1.0)  # 鲜红
    if remaining_percent <= 50:
        return NSColor.colorWithSRGBRed_green_blue_alpha_(1.00, 0.60, 0.00, 1.0)  # 亮橙
    return NSColor.colorWithSRGBRed_green_blue_alpha_(0.16, 0.86, 0.28, 1.0)      # 鲜绿


# ---------- 纯函数：把取数结果转成要显示的文案（便于单测，App 也复用）----------
def compute_title(r):
    """菜单栏标题字符串。"""
    if not r.get("ok"):
        return "Codex ⚠️"
    windows = r.get("windows", [])
    if not windows:
        return "Codex ⚠️"
    reached = r.get("rate_limit_reached_type")
    worst = min(w["remaining_percent"] for w in windows)
    segs = " · ".join(f'{w["label"]} {w["remaining_percent"]}%' for w in windows)
    marker = "🔴" if reached else dot(worst)
    return f"{marker} {segs}"


def compute_menu_lines(r):
    """下拉里的信息项文案列表（None 表示分隔线）；不含「立即刷新/打开/退出」动作项。"""
    lines = []
    reached = r.get("rate_limit_reached_type")
    if reached:
        lines.append(f"🔴 已触达限额（{reached}）")
        lines.append(None)
    if not r.get("ok") or not r.get("windows"):
        lines.append(f'⚠️ {r.get("error") or "获取失败"}')
    else:
        for w in r["windows"]:
            name = {"5h": "五小时额度", "7d": "七日额度"}.get(
                w["label"], f'{w["label"]} 额度')
            lines.append(
                f'{name}：剩余 {w["remaining_percent"]}%（已用 {w["used_percent"]}%）')
            lines.append(f'    {bar(w["remaining_percent"])}')
            lines.append(f'    重置还需 {fmt_countdown(w["resets_at"])}')
            lines.append(None)
    if r.get("plan_type"):
        lines.append(f'账户：{r["plan_type"].capitalize()}')
    fetched_at = r.get("fetched_at")
    stamp = time.strftime("%H:%M:%S", time.localtime(fetched_at)) if fetched_at else "—"
    lines.append(f"上次刷新：{stamp}")
    return lines


class CodexQuotaBar(rumps.App):
    def __init__(self):
        super().__init__("Codex", title="Codex …", quit_button="退出")
        self._pending = None          # 后台线程放最新结果
        self._displayed_at = None     # 已应用到 UI 的结果时间戳
        self._wake = threading.Event()  # set 时立即重新取数
        self._fetching = False

        # 后台取数循环
        threading.Thread(target=self._loop, daemon=True).start()
        # 主线程定时器：把后台结果应用到 UI（保证 UI 更新都在主线程）
        self._timer = rumps.Timer(self._tick, 1)
        self._timer.start()

    # ---------- 后台取数 ----------
    def _loop(self):
        while True:
            self._fetching = True
            try:
                r = fetch_quota()
            except Exception as e:
                r = {"ok": False, "error": f"取数异常：{e}",
                     "fetched_at": int(time.time()), "windows": [],
                     "plan_type": None, "rate_limit_reached_type": None}
            self._pending = r
            self._fetching = False
            # 等待间隔；手动刷新会提前唤醒
            self._wake.wait(timeout=REFRESH_INTERVAL)
            self._wake.clear()

    # ---------- 主线程应用结果 ----------
    def _tick(self, _):
        r = self._pending
        if r is None:
            return
        if r["fetched_at"] == self._displayed_at:
            return
        self._displayed_at = r["fetched_at"]
        self._render(r)

    def _render(self, r):
        self._apply_colored_title(r)
        items = []
        for line in compute_menu_lines(r):
            items.append(None if line is None else rumps.MenuItem(line))
        items.append(None)
        items.append(rumps.MenuItem("立即刷新", callback=self.on_refresh))
        items.append(rumps.MenuItem("打开 ChatGPT", callback=self.on_open))
        self.menu.clear()
        self.menu = items  # rumps 会自动补上「退出」

    def _apply_colored_title(self, r):
        """给菜单栏文字上鲜艳颜色；每个窗口按自身剩余额度独立配色。"""
        try:
            item = self._nsapp.nsstatusitem
        except AttributeError:
            self.title = compute_title(r)  # 尚未启动完成时的兜底
            return

        reached = bool(r.get("rate_limit_reached_type"))
        segments = []  # [(文本, NSColor)]
        if not r.get("ok") or not r.get("windows"):
            segments.append(("Codex ⚠️", ns_color(0, reached=True)))
        else:
            for i, w in enumerate(r["windows"]):
                if i > 0:
                    segments.append((" · ", NSColor.labelColor()))
                segments.append((f'{w["label"]} {w["remaining_percent"]}%',
                                 ns_color(w["remaining_percent"], reached)))

        font = NSFont.menuBarFontOfSize_(0.0)
        full = NSMutableAttributedString.alloc().init()
        for text, color in segments:
            attrs = {NSFontAttributeName: font, NSForegroundColorAttributeName: color}
            full.appendAttributedString_(
                NSMutableAttributedString.alloc().initWithString_attributes_(text, attrs))
        item.setAttributedTitle_(full)

    # ---------- 菜单动作 ----------
    def on_refresh(self, _):
        try:
            self._nsapp.nsstatusitem.setTitle_("刷新中…")
        except Exception:
            pass
        self._wake.set()

    def on_open(self, _):
        try:
            subprocess.Popen(["open", "-a", "ChatGPT"])
        except Exception:
            pass


if __name__ == "__main__":
    # 仅菜单栏模式：不在程序坞(Dock)显示图标、也不占顶部应用菜单。
    # 在 run() 前对真正的 NSApplication 设置，启动时不会有 Dock 图标一闪。
    NSApplication.sharedApplication().setActivationPolicy_(
        NSApplicationActivationPolicyAccessory)
    CodexQuotaBar().run()
