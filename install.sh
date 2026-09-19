#!/bin/bash
# 一键安装：装依赖 + 把运行文件装到不受保护目录 + 生成开机自启 + 启动菜单栏工具。
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"   # 仓库/克隆目录（源）
PY=/usr/bin/python3          # 用系统自带 python（framework build，菜单栏 App 需要）
LABEL=com.user.codexquota
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
# 运行目录：放到 ~/Library/Application Support（不受 macOS 隐私保护 TCC 限制）。
# 否则若克隆在 ~/Desktop、~/Documents、~/Downloads，launchd 自启进程会因 TCC
# 报「Operation not permitted」读不到脚本。
APP_DIR="$HOME/Library/Application Support/CodexQuotaBar"
REQUIREMENTS="$DIR/requirements.txt"

usage() {
    echo "用法：./install.sh [--plan]"
    echo "  --plan  只显示检查结果和拟执行操作；不安装、不取数、不写文件、不加载服务"
}

validate_sources() {
    for required in \
        "$DIR/codex_quota_bar.py" \
        "$DIR/fetch_quota.py" \
        "$DIR/com.user.codexquota.plist.template" \
        "$REQUIREMENTS"; do
        if [ ! -f "$required" ]; then
            echo "❌ 缺少安装源文件：$required" >&2
            return 1
        fi
    done
    /usr/bin/plutil -lint "$DIR/com.user.codexquota.plist.template" >/dev/null
}

case "${1:-}" in
    "") ;;
    --plan)
        validate_sources
        echo "安装计划（只读，不执行）："
        echo "- Python：$PY"
        echo "- 依赖：${REQUIREMENTS}（安装到当前用户的 system-Python user site）"
        echo "- 运行文件：$APP_DIR"
        echo "- 登录项：$PLIST"
        echo "- 安装时会读取一次真实额度做自检，并加载 LaunchAgent"
        echo "- 卸载默认保留 rumps 和 /tmp/codexbar.*.log"
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

validate_sources

if [ -L "$APP_DIR" ]; then
    echo "❌ 运行目录是符号链接，拒绝安装以免写入意外位置：$APP_DIR" >&2
    exit 1
fi

echo "==> 1/6 检查 ChatGPT 桌面 App ..."
if [ ! -e "/Applications/ChatGPT.app" ]; then
    echo "   ⚠️  未检测到 /Applications/ChatGPT.app —— 请先安装并登录 ChatGPT/Codex 桌面 App，否则读不到额度。"
fi

echo "==> 2/6 检查 /usr/bin/python3 ..."
if [ ! -x "$PY" ]; then
    echo "   ❌ 未找到 $PY —— 请先运行：xcode-select --install"
    exit 1
fi

echo "==> 3/6 安装依赖 rumps ..."
if ! "$PY" -c '
from importlib.metadata import version
parts = version("rumps").split(".")
raise SystemExit(0 if len(parts) >= 2 and parts[0] == "0" and parts[1] == "4" else 1)
' 2>/dev/null; then
    if ! "$PY" -m pip --version >/dev/null 2>&1; then
        echo "   ❌ $PY 没有可用的 pip，未安装任何依赖。" >&2
        exit 1
    fi
    "$PY" -m pip install --user --requirement "$REQUIREMENTS"
fi
if ! "$PY" -c 'import rumps' 2>/dev/null; then
    echo "   ❌ rumps 安装后仍无法由 $PY 导入，停止安装。" >&2
    exit 1
fi

echo "==> 4/6 安装运行文件到 $APP_DIR ..."
mkdir -p "$APP_DIR"
cp "$DIR/codex_quota_bar.py" "$DIR/fetch_quota.py" "$APP_DIR/"

echo "==> 5/6 自检：真读一次额度 ..."
SELFTEST="$("$PY" "$APP_DIR/fetch_quota.py" 2>&1 || true)"
if printf '%s' "$SELFTEST" | grep -q '"ok": true'; then
    echo "   ✅ 成功读到额度："
    printf '%s\n' "$SELFTEST" | grep -E 'label|remaining_percent|plan_type' | sed 's/^/      /'
else
    echo "   ⚠️  暂时没读到额度。常见原因：ChatGPT App 未登录，或 codex 版本不兼容此接口。"
    echo "      工具仍会安装；菜单栏会显示 ⚠️ 并给出具体原因。诊断输出："
    printf '%s\n' "$SELFTEST" | grep -E 'error|ok' | sed 's/^/      /'
fi

echo "==> 6/6 生成开机自启配置并启动 ..."
mkdir -p "$HOME/Library/LaunchAgents"
PLIST_TMP="$PLIST.tmp.$$"
cleanup() {
    rm -f "$PLIST_TMP"
}
trap cleanup EXIT INT TERM
sed -e "s|__PYTHON__|$PY|g" \
    -e "s|__SCRIPT__|$APP_DIR/codex_quota_bar.py|g" \
    -e "s|__WORKDIR__|$APP_DIR|g" \
    "$DIR/com.user.codexquota.plist.template" > "$PLIST_TMP"
/usr/bin/plutil -lint "$PLIST_TMP" >/dev/null
chmod 644 "$PLIST_TMP"
mv -f "$PLIST_TMP" "$PLIST"
trap - EXIT INT TERM
launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"

echo "✅ 安装完成。菜单栏右上角应出现 Codex 额度图标（首次拉取约 1–2 秒）。"
echo "   只在菜单栏显示，不在程序坞(Dock)出现。卸载：运行 ./uninstall.sh"
