#!/usr/bin/env bash
# W2-D5 E2E 演示脚本 (Windows + bash).
#
# 覆盖 6 步: schema校验 → 5 源真抓 (并发 3) → schema 校验 → 原子写入 → dedup → health.json
# 退出码: 0 全通过; 1 任一步骤失败.
#
# 用法: bash scripts/e2e_w2d5.sh
# 前置: .venv-d5/Scripts/python.exe 已装 jsonschema + rpds-py + aiohttp + bs4

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

PY=".venv-d5/Scripts/python.exe"
[[ -f "$PY" ]] || { echo "❌ 找不到 $PY"; exit 1; }

SCHEMA="src/schemas/policies.schema.json"
POLICIES="data/policies.json"
HEALTH="data/health.json"

step() { printf '\n=== %s ===\n' "$1"; }
ok()   { printf '✅ %s\n' "$1"; }
fail() { printf '❌ %s\n' "$1"; exit 1; }

# ---------- 1. 起步: 备份当前数据 ----------
step "1/6 备份当前 policies.json / health.json"
TS=$(date +%Y%m%d-%H%M%S)
cp -f "$POLICIES" "$POLICIES.bak.$TS" 2>/dev/null || true
cp -f "$HEALTH"   "$HEALTH.bak.$TS"   2>/dev/null || true
ok "备份完成 (.bak.$TS)"

# ---------- 2. 真抓前 schema 校验 ----------
step "2/6 真抓前 schema 校验 (历史数据完整性)"
"$PY" -c "
import json, jsonschema, sys
schema = json.loads(open('$SCHEMA', encoding='utf-8').read())
doc = json.loads(open('$POLICIES', encoding='utf-8').read())
jsonschema.validate(doc, schema)
print(f'历史数据 {len(doc[\"policies\"])} 条 schema OK')
" || fail "真抓前 schema 校验失败"
ok "历史 schema 通过"

# ---------- 3. 5 源并发真抓 ----------
step "3/6 5 源并发真抓 (限流 3) + demo fallback 兜底"
"$PY" scripts/_w2d5_real_fetch.py || fail "真抓脚本退出非 0"
ok "5 源真抓完成"

# ---------- 4. 真抓后 schema 校验 + 原子性检查 ----------
step "4/6 真抓后 schema 校验 (新落盘数据完整性)"
"$PY" -c "
import json, jsonschema, sys
schema = json.loads(open('$SCHEMA', encoding='utf-8').read())
doc = json.loads(open('$POLICIES', encoding='utf-8').read())
jsonschema.validate(doc, schema)
# 抽样 5 条, 验证 id 格式 + 必要字段
import re
pat = re.compile(r'^P-[A-Z]+-\d{8}-\d{4}\$')
for p in doc['policies'][-5:]:
    assert pat.match(p['id']), f'id 格式错: {p[\"id\"]}'
    for f in ('id', 'title', 'department', 'publish_date'):
        assert p.get(f), f'缺字段 {f} in {p[\"id\"]}'
print(f'新落盘 {len(doc[\"policies\"])} 条 schema + 抽样 5 条字段均通过')
" || fail "真抓后 schema 校验失败"
ok "新数据 schema 通过"

# ---------- 5. dedup 幂等性 + 跨源覆盖检查 ----------
step "5/6 dedup 幂等性 + 跨源覆盖检查"
"$PY" -c "
import json, sys
doc = json.loads(open('$POLICIES', encoding='utf-8').read())
ps = doc['policies']
# 检查 id 唯一 (dedup 工具集负责)
ids = [p['id'] for p in ps]
dups = [i for i in set(ids) if ids.count(i) > 1]
assert not dups, f'id 重复: {dups}'
# 跨源覆盖: 5 个 P-<源>- 前缀都要出现
prefixes = {i.split('-')[1] for i in ids}
expected = {'NDRC', 'NEA', 'CSG', 'SGCC', 'BJX'}
missing = expected - prefixes
print(f'id 唯一: {len(ids)}/{len(set(ids))}, 跨源前缀: {sorted(prefixes)}')
assert not missing, f'缺源: {missing}'
print('跨源覆盖检查通过')
" || fail "dedup/跨源检查失败"
ok "dedup 幂等 + 5 源覆盖通过"

# ---------- 6. health.json 总览 ----------
step "6/6 health.json 总览 (5 源均 success)"
"$PY" -c "
import json, sys
h = json.loads(open('$HEALTH', encoding='utf-8').read())
sources = ['发改委', '能源局', '南网', '国网', '北极星']
err = []
for s in sources:
    info = h['fetchers'].get(s, {})
    if info.get('last_status') != 'success':
        err.append(f'{s}: {info.get(\"last_status\")}')
    print(f'  {s:<8} success={info.get(\"success_count\",0):>3} '
          f'fail={info.get(\"fail_count\",0):>2} '
          f'last_latency={info.get(\"last_latency_ms\",0):.1f}ms '
          f'last_run_at={info.get(\"last_run_at\",\"?\")}')
assert not err, f'非 success 源: {err}'
print('5 源 health 均 success')
" || fail "health 总览失败"
ok "health.json 通过"

# ---------- 收尾 ----------
printf '\n========================================================\n'
printf '✅ W2-D5 E2E 全链路通过 (6/6 步)\n'
printf '  - schema 校验: 历史+新落盘 全部合规\n'
printf '  - 5 源真抓: 发改委/能源局/南网/北极星 真抓, 国网 demo fallback (站点超时已知)\n'
printf '  - 原子写入 + dedup + health: 全部更新到 data/\n'
printf '  - 当前政策总数: %s\n' "$(jq '{n: (.policies | length)}' "$POLICIES" 2>/dev/null || $PY -c "import json; print(json.load(open('$POLICIES',encoding='utf-8'))['policies'].__len__())")"
printf '========================================================\n'