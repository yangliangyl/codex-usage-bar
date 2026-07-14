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

echo "==> 2/5 检查 /usr/bin/python3 ..."
if [ ! -x "$PY" ]; then
    echo "   ❌ 未找到 $PY —— 请先运行：xcode-select --install"
    exit 1
fi

echo "==> 3/5 安装依赖 rumps ..."
if ! "$PY" -c 'import rumps' 2>/dev/null; then
    "$PY" -m pip install --user rumps
fi

echo "==> 4/5 自检：真读一次额度 ..."
SELFTEST="$("$PY" "$DIR/fetch_quota.py" 2>&1 || true)"
if printf '%s' "$SELFTEST" | grep -q '"ok": true'; then
    echo "   ✅ 成功读到额度："
    printf '%s\n' "$SELFTEST" | grep -E 'label|remaining_percent|plan_type' | sed 's/^/      /'
else
    echo "   ⚠️  暂时没读到额度。常见原因：ChatGPT App 未登录，或 codex 版本不兼容此接口。"
    echo "      工具仍会安装；菜单栏会显示 ⚠️ 并给出具体原因。诊断输出："
    printf '%s\n' "$SELFTEST" | grep -E 'error|ok' | sed 's/^/      /'
fi

echo "==> 5/5 生成开机自启配置 ..."
mkdir -p "$HOME/Library/LaunchAgents"
sed -e "s|__PYTHON__|$PY|g" \
    -e "s|__SCRIPT__|$DIR/codex_quota_bar.py|g" \
    -e "s|__WORKDIR__|$DIR|g" \
    "$DIR/com.user.codexquota.plist.template" > "$PLIST"

echo "==> 启动 ..."
launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"

echo "✅ 安装完成。菜单栏右上角应出现 Codex 额度图标（首次拉取约 1–2 秒）。"
echo "   卸载：运行 ./uninstall.sh"
