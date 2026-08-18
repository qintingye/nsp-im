#!/usr/bin/env bash
# ============================================================
# NSP-IM · W1-D5 End-to-End Demo
# ============================================================
# Stages:
#   1) deploy_precheck     →  验证环境/依赖/单测/JSON schema
#   2) pytest 全套         →  50 测试全部通过
#   3) main_fetcher --demo →  离线生成 5 条 demo policy
#   4) docs/preview/ 完整性  →  index/manifest/sw/data 三件套
#
# 退出码:
#   0 = 全部通过
#   1 = 任一 Stage 失败
# ============================================================
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT" || { echo "❌ 无法进入仓库根: $REPO_ROOT"; exit 1; }

# 选择 Python 解释器
if [ -x ".venv-d5/Scripts/python.exe" ]; then
    PY=".venv-d5/Scripts/python.exe"
elif command -v python3 >/dev/null 2>&1; then
    PY="python3"
else
    PY="python"
fi

# ---------- 颜色 ----------
if [ -t 1 ]; then RED=$'\033[0;31m'; GREEN=$'\033[0;32m'; YELLOW=$'\033[0;33m'; BLUE=$'\033[0;34m'; RESET=$'\033[0m'
else              RED='';         GREEN='';          YELLOW='';           BLUE='';           RESET=''; fi

stage() { echo -e "\n${BLUE}━━━ Stage $1: $2 ━━━${RESET}"; }
pass()  { echo -e "${GREEN}✅ $1${RESET}"; }
fail()  { echo -e "${RED}❌ $1${RESET}"; FAILED=1; }

FAILED=0

# ============================================================
# Stage 1: deploy_precheck
# ============================================================
stage "1" "deploy_precheck"
if bash scripts/deploy_precheck.sh 2>&1 | tail -25 ; then
    RC=${PIPESTATUS[0]}
    if [ "$RC" -eq 0 ]; then
        pass "[Stage 1] deploy_precheck → PASSED"
    else
        fail "[Stage 1] deploy_precheck → FAILED (rc=$RC)"
    fi
else
    fail "[Stage 1] deploy_precheck 执行异常"
fi

# ============================================================
# Stage 2: pytest 全套
# ============================================================
stage "2" "pytest (full suite)"
PYTEST_OUT=$("$PY" -m pytest tests/ -v 2>&1)
PYTEST_RC=$?
echo "$PYTEST_OUT" | tail -30
PYTEST_SUMMARY=$(echo "$PYTEST_OUT" | grep -E "passed|failed" | tail -1)
if [ "$PYTEST_RC" -eq 0 ]; then
    pass "[Stage 2] pytest → ${PYTEST_SUMMARY:-all green}"
else
    fail "[Stage 2] pytest → ${PYTEST_SUMMARY} (rc=$PYTEST_RC)"
fi

# ============================================================
# Stage 3: main_fetcher --demo
# ============================================================
stage "3" "main_fetcher --demo"
BEFORE_TOTAL=$("$PY" -c "import json; d=json.load(open('data/policies.json',encoding='utf-8')); print(len(d.get('policies',[])))")
DEMO_OUT=$("$PY" -m src.main_fetcher --demo 2>&1)
DEMO_RC=$?
echo "$DEMO_OUT" | tail -10
AFTER_TOTAL=$("$PY" -c "import json; d=json.load(open('data/policies.json',encoding='utf-8')); print(len(d.get('policies',[])))")
DEMO_LOG_LINE=$(echo "$DEMO_OUT" | grep -E "demo 完成|✅" | tail -1)
if [ "$DEMO_RC" -eq 0 ] && [ -n "$DEMO_LOG_LINE" ]; then
    pass "[Stage 3] demo fetch → total=${AFTER_TOTAL} (log: ${DEMO_LOG_LINE##*INFO } )"
else
    fail "[Stage 3] demo fetch 异常 (rc=$DEMO_RC, before=$BEFORE_TOTAL, after=$AFTER_TOTAL)"
fi

# ============================================================
# Stage 4: docs/preview/ 完整性
# ============================================================
stage "4" "docs/preview/ 完整性"
PREVIEW_FILES=0
PREVIEW_MISSING=()
for f in index.html manifest.json sw.js README.md; do
    if [ -f "docs/preview/$f" ]; then
        PREVIEW_FILES=$((PREVIEW_FILES+1))
    else
        PREVIEW_MISSING+=("$f")
    fi
done
# data 目录快照
for f in policies.json health.json; do
    if [ -f "docs/preview/data/$f" ]; then
        PREVIEW_FILES=$((PREVIEW_FILES+1))
    else
        PREVIEW_MISSING+=("data/$f")
    fi
done
echo "预览文件清单:"
ls -la docs/preview/ docs/preview/data/ 2>&1 | sed 's/^/  /'
if [ "${#PREVIEW_MISSING[@]}" -eq 0 ]; then
    pass "[Stage 4] deploy preview → ${PREVIEW_FILES} files 就绪"
else
    fail "[Stage 4] deploy preview 缺: ${PREVIEW_MISSING[*]}"
fi

# ============================================================
# 最终判定
# ============================================================
echo ""
echo -e "${BLUE}━━━ Final ━━━${RESET}"
if [ "$FAILED" -eq 0 ]; then
    echo -e "${GREEN}✅ E2E PASSED${RESET}"
    exit 0
else
    echo -e "${RED}❌ E2E FAILED${RESET}"
    exit 1
fi
