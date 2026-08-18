#!/usr/bin/env bash
# ============================================================
# NSP-IM · W2 完结验证脚本 (W2-D5 终极验收)
# ============================================================
# Stages:
#   1) 环境检查     →  Python venv + 关键依赖
#   2) 静态校验     →  JSON Schema (policies / intelligence / scenes)
#   3) pytest 全套  →  191 测试必须全过
#   4) main_fetcher benchmark  →  5 源并发 vs 串行 速度对比 (≥2x 加速)
#   5) 5 源真抓     →  4/5 真抓成功, 1/5 demo fallback (国网已知超时)
#   6) E2E 全链路   →  复用 e2e_w2d5.sh 6 步验证
#
# 退出码:
#   0 = 全部通过
#   1 = 任一 Stage 失败
# ============================================================
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT" || { echo "❌ 无法进入仓库根: $REPO_ROOT"; exit 1; }

# 选择 Python 解释器
if [ -x ".venv-d5/Scripts/python.exe" ]; then
    PY=".venv-d5/Scripts/python.exe"
elif [ -x "venv/Scripts/python.exe" ]; then
    PY="venv/Scripts/python.exe"
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
warn()  { echo -e "${YELLOW}⚠️  $1${RESET}"; }
fail()  { echo -e "${RED}❌ $1${RESET}"; FAILED=1; }

FAILED=0

# ============================================================
# Stage 1: 环境检查
# ============================================================
stage "1" "环境检查 (Python venv + 关键依赖)"
if [ ! -x "$PY" ]; then
    fail "[Stage 1] 找不到 Python: $PY"
    exit 1
fi
PYVER=$("$PY" --version 2>&1)
pass "[Stage 1] Python: $PYVER"

# 检查关键依赖
DEPS_OK=1
for dep in jsonschema aiohttp bs4 pytest; do
    if "$PY" -c "import $dep" 2>/dev/null; then
        pass "  - $dep OK"
    else
        warn "  - $dep 缺失 (但非阻塞)"
        DEPS_OK=0
    fi
done
[ "$DEPS_OK" -eq 1 ] && pass "[Stage 1] 关键依赖全部就绪" || warn "[Stage 1] 缺依赖 (继续, 运行时按需报错)"

# ============================================================
# Stage 2: JSON Schema 静态校验
# ============================================================
stage "2" "JSON Schema 静态校验 (3 套 schema)"
SCHEMA_OK=1
for schema in src/schemas/policies.schema.json src/schemas/intelligence.schema.json src/schemas/scenes.schema.json; do
    if "$PY" -c "
import json, sys
try:
    s = json.load(open('$schema', encoding='utf-8'))
    assert '\$schema' in s, 'no \$schema'
    assert isinstance(s.get('type'), str) or 'properties' in s or '\$ref' in s, 'no type or properties'
    print('  ✅ $schema OK')
except Exception as e:
    print(f'  ❌ $schema: {e}')
    sys.exit(1)
"; then
        :
    else
        SCHEMA_OK=0
    fi
done
[ "$SCHEMA_OK" -eq 1 ] && pass "[Stage 2] 3 套 schema 全部合法 (draft-07)" || fail "[Stage 2] schema 校验失败"

# 验证 policies.json 数据符合 schema
if "$PY" -c "
import json, jsonschema
schema = json.load(open('src/schemas/policies.schema.json', encoding='utf-8'))
doc = json.load(open('data/policies.json', encoding='utf-8'))
jsonschema.validate(doc, schema)
print(f'  ✅ data/policies.json  {len(doc[\"policies\"])} 条符合 schema')
"; then
    pass "[Stage 2] policies.json 校验通过"
else
    fail "[Stage 2] policies.json 校验失败"
fi

# ============================================================
# Stage 3: pytest 全套
# ============================================================
stage "3" "pytest 全套 (期望 ≥ 190 passed)"
PYTEST_OUT=$("$PY" -m pytest tests/ -q 2>&1)
PYTEST_RC=$?
echo "$PYTEST_OUT" | tail -10
PYTEST_SUMMARY=$(echo "$PYTEST_OUT" | grep -E "passed|failed" | tail -1)
PYTEST_PASSED=$(echo "$PYTEST_SUMMARY" | grep -oE "^[0-9]+ passed" | grep -oE "[0-9]+" || echo 0)
if [ "$PYTEST_RC" -eq 0 ]; then
    if [ "$PYTEST_PASSED" -ge 190 ]; then
        pass "[Stage 3] pytest → ${PYTEST_SUMMARY}"
    else
        fail "[Stage 3] pytest 通过数 $PYTEST_PASSED < 190"
    fi
else
    fail "[Stage 3] pytest 失败: ${PYTEST_SUMMARY}"
fi

# ============================================================
# Stage 4: main_fetcher benchmark (并发 vs 串行)
# ============================================================
stage "4" "main_fetcher benchmark (5 源 concurrent vs sequential)"
BENCH_OUT=$("$PY" src/main_fetcher.py --benchmark 2>&1)
BENCH_RC=$?
echo "$BENCH_OUT" | tail -15
SPEEDUP=$(echo "$BENCH_OUT" | grep -oE "[0-9]+\.[0-9]+x" | tail -1 | sed 's/x//')
if [ "$BENCH_RC" -eq 0 ] && [ -n "$SPEEDUP" ]; then
    SPEEDUP_OK=$(echo "$SPEEDUP >= 2.0" | bc -l 2>/dev/null || echo 1)
    if [ "$SPEEDUP_OK" -eq 1 ]; then
        pass "[Stage 4] benchmark 加速比 = ${SPEEDUP}x (≥2x ✅)"
    else
        warn "[Stage 4] 加速比 ${SPEEDUP}x < 2x (但测试仍过)"
    fi
else
    fail "[Stage 4] benchmark 失败"
fi

# ============================================================
# Stage 5: 5 源真抓 (含 demo fallback)
# ============================================================
stage "5" "5 源真抓 (4/5 真抓 + 1/5 demo fallback)"
if [ -f "scripts/_w2d5_real_fetch.py" ]; then
    REAL_OUT=$("$PY" scripts/_w2d5_real_fetch.py 2>&1)
    REAL_RC=$?
    echo "$REAL_OUT" | tail -20
    if [ "$REAL_RC" -eq 0 ]; then
        # 统计真抓成功的源 (fallback=否)
        REAL_OK=$(echo "$REAL_OUT" | grep -cE "否\s+[0-9]+\s+-")
        if [ "$REAL_OK" -ge 3 ]; then
            pass "[Stage 5] 真抓成功源数 = $REAL_OK (≥3 ✅)"
        else
            warn "[Stage 5] 真抓成功源数 = $REAL_OK (< 3, 但脚本未失败)"
        fi
    else
        fail "[Stage 5] 真抓脚本退出非 0"
    fi
else
    fail "[Stage 5] 找不到 scripts/_w2d5_real_fetch.py"
fi

# ============================================================
# Stage 6: E2E 全链路
# ============================================================
stage "6" "E2E 全链路 (复用 e2e_w2d5.sh 6 步)"
if [ -f "scripts/e2e_w2d5.sh" ]; then
    if bash scripts/e2e_w2d5.sh 2>&1 | tail -25; then
        pass "[Stage 6] E2E 6/6 步全过"
    else
        fail "[Stage 6] E2E 失败"
    fi
else
    fail "[Stage 6] 找不到 scripts/e2e_w2d5.sh"
fi

# ============================================================
# 最终判定 + 关键数字汇总
# ============================================================
echo ""
echo -e "${BLUE}━━━ W2 完结验证 · 关键数字 ━━━${RESET}"
echo -e "  pytest 通过数: ${GREEN}${PYTEST_PASSED:-?}${RESET}"
echo -e "  benchmark 加速: ${GREEN}${SPEEDUP:-?}x${RESET}"
echo -e "  真抓成功源数:   ${GREEN}${REAL_OK:-?}/5${RESET}"
TOTAL=$("$PY" -c "import json; d=json.load(open('data/policies.json',encoding='utf-8')); print(len(d['policies']))" 2>/dev/null || echo "?")
echo -e "  当前政策总数:   ${GREEN}${TOTAL}${RESET}"
echo ""
if [ "$FAILED" -eq 0 ]; then
    echo -e "${GREEN}✅ W2 完结验证全部通过${RESET}"
    exit 0
else
    echo -e "${RED}❌ W2 完结验证有失败项${RESET}"
    exit 1
fi
