#!/bin/bash
# 卸载：停止并移除开机自启，关闭正在运行的菜单栏工具。
set -euo pipefail

LABEL=com.user.codexquota
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

launchctl unload "$PLIST" 2>/dev/null || true
rm -f "$PLIST"
pkill -f codex_quota_bar.py 2>/dev/null || true
rm -rf "$HOME/Library/Application Support/CodexQuotaBar"

echo "✅ 已卸载（依赖 rumps 未删除，如需清理：/usr/bin/python3 -m pip uninstall rumps）。"
