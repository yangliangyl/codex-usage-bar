#!/bin/bash
# 卸载：停止并移除开机自启，关闭正在运行的菜单栏工具。
set -euo pipefail

LABEL=com.user.codexquota
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
APP_DIR="$HOME/Library/Application Support/CodexQuotaBar"

usage() {
    echo "用法：./uninstall.sh [--plan]"
    echo "  --plan  只显示拟删除内容；不停止进程、不卸载服务、不删除文件"
}

case "${1:-}" in
    "") ;;
    --plan)
        echo "卸载计划（只读，不执行）："
        echo "- 卸载并删除登录项：$PLIST"
        echo "- 停止从此运行目录启动的菜单栏进程：$APP_DIR/codex_quota_bar.py"
        echo "- 删除运行目录：$APP_DIR"
        echo "- 保留 rumps 和 /tmp/codexbar.*.log"
        exit 0
        ;;
    -h|--help)
        usage
        exit 0
        ;;
    *)
        usage >&2
        exit 2
        ;;
esac

if [ -L "$APP_DIR" ]; then
    echo "❌ 运行目录是符号链接，拒绝自动删除：$APP_DIR" >&2
    exit 1
fi

launchctl unload "$PLIST" 2>/dev/null || true
rm -f "$PLIST"
pkill -f "$APP_DIR/codex_quota_bar.py" 2>/dev/null || true
rm -rf "$APP_DIR"

echo "✅ 已卸载（依赖 rumps 未删除，如需清理：/usr/bin/python3 -m pip uninstall rumps）。"
