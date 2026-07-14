#!/bin/bash
# 一键安装：装依赖 + 生成开机自启配置 + 启动菜单栏工具。
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY=/usr/bin/python3          # 用系统自带 python（framework build，菜单栏 App 需要）
LABEL=com.user.codexquota
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

echo "==> 1/4 检查 ChatGPT 桌面 App ..."
if [ ! -e "/Applications/ChatGPT.app" ]; then
    echo "   ⚠️  未检测到 /Applications/ChatGPT.app —— 请先安装并登录 ChatGPT/Codex 桌面 App，否则读不到额度。"
fi

echo "==> 2/4 安装依赖 rumps ..."
if ! "$PY" -c 'import rumps' 2>/dev/null; then
    "$PY" -m pip install --user rumps
fi

echo "==> 3/4 生成开机自启配置 ..."
mkdir -p "$HOME/Library/LaunchAgents"
sed -e "s|__PYTHON__|$PY|g" \
    -e "s|__SCRIPT__|$DIR/codex_quota_bar.py|g" \
    -e "s|__WORKDIR__|$DIR|g" \
    "$DIR/com.user.codexquota.plist.template" > "$PLIST"

echo "==> 4/4 启动 ..."
launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"

echo "✅ 安装完成。菜单栏右上角应出现 Codex 额度图标（首次拉取约 1–2 秒）。"
echo "   卸载：运行 ./uninstall.sh"
