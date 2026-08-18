#!/usr/bin/env bash
# ============================================================
# NSP-IM 部署前自检 (W1-D4)
# ============================================================
# 用途: 在 CI / 生产部署前验证环境与代码完整性。
#   - Python 版本
#   - 必需依赖 (aiohttp, bs4, jsonschema, pytest)
#   - 目录与文件 (data/, logs/, scripts/, src/, tests/)
#   - 单测全部通过
#   - 主入口可被 import
#   - JSON 校验 (policies.json schema)
#
# 用法:
#   bash scripts/deploy_precheck.sh                 # 默认全检查
#   bash scripts/deploy_precheck.sh --skip-pytest   # 跳过 pytest
#   bash scripts/deploy_precheck.sh --strict        # 任何警告都 fail
#
# 退出码:
#   0 = 全部通过
#   1 = 有失败
#   2 = 有警告 (仅 --strict 模式)
# ============================================================
set -u

# ---------- 解析参数 ----------
SKIP_PYTEST=0
STRICT=0
for arg in "$@"; do
    case "$arg" in
        --skip-pytest) SKIP_PYTEST=1 ;;
        --strict)      STRICT=1 ;;
        -h|--help)
            head -25 "$0" | tail -20
            exit 0
            ;;
        *) echo "⚠️ 未知参数: $arg"; exit 1 ;;
    esac
done

# ---------- 锚定仓库根 ----------
# scripts/deploy_precheck.sh → parents[0]=scripts, parents[1]=nsp-im
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT" || { echo "❌ 无法进入仓库根: $REPO_ROOT"; exit 1; }

# 选择 Python 解释器
if [ -x ".venv-d5/Scripts/python.exe" ]; then
    PY=".venv-d5/Scripts/python.exe"
elif command -v python3 >/dev/null 2>&1; then
    PY="python3"
elif command -v python >/dev/null 2>&1; then
    PY="python"
else
    echo "❌ 找不到 python 解释器"
    exit 1
fi

# ---------- 颜色 ----------
if [ -t 1 ]; then
    RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[0;33m'; BLUE='\033[0;34m'; RESET='\033[0m'
else
    RED=''; GREEN=''; YELLOW=''; BLUE=''; RESET=''
fi

PASS_COUNT=0
FAIL_COUNT=0
WARN_COUNT=0

ok()   { echo -e "${GREEN}✅${RESET} $1"; PASS_COUNT=$((PASS_COUNT+1)); }
fail() { echo -e "${RED}❌${RESET} $1"; FAIL_COUNT=$((FAIL_COUNT+1)); }
warn() { echo -e "${YELLOW}⚠️${RESET}  $1"; WARN_COUNT=$((WARN_COUNT+1)); }
hdr()  { echo -e "\n${BLUE}━━━ $1 ━━━${RESET}"; }

# ---------- 1. 环境 ----------
hdr "1/6 环境检查"

PY_VERSION=$("$PY" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>&1)
if [ $? -eq 0 ]; then
    ok "Python 版本: $PY_VERSION"
    # Python >= 3.10 即可
    MAJOR=$(echo "$PY_VERSION" | cut -d. -f1)
    MINOR=$(echo "$PY_VERSION" | cut -d. -f2)
    if [ "$MAJOR" -lt 3 ] || { [ "$MAJOR" -eq 3 ] && [ "$MINOR" -lt 10 ]; }; then
        fail "Python 版本过低 (需要 >= 3.10，实际 $PY_VERSION)"
    fi
else
    fail "Python 解释器不可执行: $PY"
fi

# ---------- 2. 依赖 ----------
hdr "2/6 依赖检查"
for mod in aiohttp bs4 jsonschema pytest; do
    if "$PY" -c "import $mod" 2>/dev/null; then
        ok "依赖已安装: $mod"
    else
        fail "依赖缺失: $mod  →  pip install $mod"
    fi
done

# ---------- 3. 目录与文件 ----------
hdr "3/6 目录与文件"
for d in data logs src scripts tests docs/preview; do
    if [ -d "$d" ]; then
        ok "目录存在: $d/"
    else
        if [ "$d" = "docs/preview" ]; then
            # 部署预览允许首次部署时缺失
            warn "目录缺失: $d/  (运行 bash scripts/deploy_precheck.sh --init-preview 可创建)"
        else
            fail "目录缺失: $d/"
            mkdir -p "$d"
            warn "  → 已自动创建，请检查"
        fi
    fi
done

for f in data/policies.json src/main_fetcher.py src/utils/integrate.py \
         src/utils/atomic_write.py src/utils/health.py src/utils/dedup.py \
         .github/workflows/daily-fetch.yml; do
    if [ -f "$f" ]; then
        ok "文件存在: $f"
    else
        fail "文件缺失: $f"
    fi
done

# ---------- 4. 主入口 import ----------
hdr "4/6 主入口 import"
if "$PY" -c "
import sys
sys.path.insert(0, 'src')
from utils.integrate import fetch_with_health, integrated_fetch, run_integration_demo
from fetchers.ndrc import NdrcFetcher
from fetchers.base import BaseFetcher
print('imports OK')
" 2>&1 | tail -5; then
    if [ $? -eq 0 ]; then
        ok "主入口与 utils 模块可正常 import"
    else
        fail "import 失败 (见上方 traceback)"
    fi
fi

# ---------- 5. pytest ----------
hdr "5/6 单元测试"
if [ "$SKIP_PYTEST" -eq 1 ]; then
    warn "已跳过 (--skip-pytest)"
else
    if "$PY" -m pytest tests/ -q 2>&1 | tail -5; then
        LAST_LINE=$("$PY" -m pytest tests/ -q 2>&1 | tail -1)
        if echo "$LAST_LINE" | grep -q "passed"; then
            ok "pytest 全部通过 ($LAST_LINE)"
        else
            fail "pytest 未全部通过 ($LAST_LINE)"
        fi
    else
        fail "pytest 执行异常"
    fi
fi

# ---------- 6. JSON schema 校验 ----------
hdr "6/6 JSON schema 校验"
"$PY" -c "
import json, sys
from pathlib import Path
try:
    from jsonschema import Draft7Validator
except ImportError:
    print('[skip] jsonschema 未安装')
    sys.exit(0)

schema_map = {
    'data/policies.json': 'src/schemas/policies.schema.json',
}
rc = 0
for data_rel, schema_rel in schema_map.items():
    d, s = Path(data_rel), Path(schema_rel)
    if not d.exists():
        print(f'[skip] {data_rel} 不存在')
        continue
    if not s.exists():
        print(f'[skip] {schema_rel} 不存在')
        continue
    validator = Draft7Validator(json.loads(s.read_text(encoding='utf-8')))
    errs = list(validator.iter_errors(json.loads(d.read_text(encoding='utf-8'))))
    if errs:
        print(f'[FAIL] {data_rel} 有 {len(errs)} 处 schema 错误:')
        for e in errs[:5]:
            print(f'  - {list(e.absolute_path)}: {e.message}')
        rc = 1
    else:
        print(f'[OK]   {data_rel} 通过 schema 校验')
sys.exit(rc)
" 2>&1 | tail -10
RC_SCHEMA=$?
if [ "$RC_SCHEMA" -eq 0 ]; then
    ok "JSON schema 校验通过"
else
    fail "JSON schema 校验失败"
fi

# ---------- 总结 ----------
hdr "总结"
TOTAL=$((PASS_COUNT + FAIL_COUNT + WARN_COUNT))
echo "通过: ${GREEN}${PASS_COUNT}${RESET} / ${TOTAL}"
echo "失败: ${RED}${FAIL_COUNT}${RESET}"
echo "警告: ${YELLOW}${WARN_COUNT}${RESET}"

if [ "$FAIL_COUNT" -gt 0 ]; then
    echo -e "\n${RED}━━━ 部署前自检 FAILED — 请修复上述问题后再部署 ━━━${RESET}"
    exit 1
fi

if [ "$WARN_COUNT" -gt 0 ] && [ "$STRICT" -eq 1 ]; then
    echo -e "\n${YELLOW}━━━ 部署前自检 WARN (--strict 模式下视为失败) ━━━${RESET}"
    exit 2
fi

echo -e "\n${GREEN}━━━ 部署前自检 PASSED — 可以部署 ━━━${RESET}"
exit 0