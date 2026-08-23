#!/usr/bin/env python3
"""
NSP-IM v3.0 — Deploy Bundle Builder (D60)
========================================

把 liuwang-jiankong/ 的 index.html (D36 fetch 方案) + data/*.json 拼成一个
可部署到 CloudBase 静态托管的 bundle。

设计要点（与原任务书差异）：
  - index.html 已经用 fetch('./data/policies.json') / fetch('./data/projects.json') 加载数据
  - 因此**不需要**字符串替换 (没有 /*__TODAY__*/ 等占位符)
  - bundle 结构 = HTML 入口 + 静态资源 + data/ JSON 目录
  - 部署路径 = /liuwangqingbaozhan (固定)
  - 永久 URL  = https://liwangqingbaozhan-liuwang-jiankong-d2eatyj479b1861.webapps.tcloudbase.com/liuwangqingbaozhan/

用法：
  python scripts/build-deploy-bundle.py --validate-only
  python scripts/build-deploy-bundle.py --output deploy-bundle/liuwangqingbaozhan
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]
HTML_SRC = REPO_ROOT / "deploy-pkg" / "liuwang-jiankong"
DATA_SRC = REPO_ROOT / "data"

# HTML 必须的入口 + 静态资源（仅打包实际被 index.html 引用的文件 + 已验证无依赖的资源）
# D59 实际部署清单 = index.html + data/*.json，没有 fonts/icons/sw.js（HTML 未引用）
HTML_REQUIRED = ["index.html"]
HTML_OPTIONAL: list[str] = []  # 当前 index.html 不引用 manifest/sw/offline, 不打包
HTML_SUBDIRS_OPTIONAL: list[str] = []  # fonts/icons/auto-sync-fix 也未引用

# data/ 必需 + 可选 JSON
DATA_REQUIRED = ["policies.json", "projects.json", "today.json"]
DATA_OPTIONAL: list[str] = []  # health.json 当前 index.html 未引用 (与 D59 部署清单一致)


# ---------- validate ----------
def _validate_json(path: Path, label: str) -> int:
    """读取 JSON 并报告顶层结构。非致命错误返回非零。"""
    try:
        with path.open(encoding="utf-8") as f:
            obj = json.load(f)
    except json.JSONDecodeError as e:
        print(f"[FAIL] {label} JSON 解析失败: {e}", file=sys.stderr)
        return 1
    except Exception as e:  # pragma: no cover
        print(f"[FAIL] {label} 读取失败: {e}", file=sys.stderr)
        return 1

    n = len(obj) if hasattr(obj, "__len__") else 0
    print(f"[OK]   {label} (顶层条目数={n})")
    return 0


def validate_only() -> int:
    rc = 0
    print("===== 校验 HTML 入口 =====")
    for name in HTML_REQUIRED:
        p = HTML_SRC / name
        if p.exists():
            print(f"[OK]   {p.relative_to(REPO_ROOT)} ({p.stat().st_size:,} bytes)")
        else:
            print(f"[FAIL] {p.relative_to(REPO_ROOT)} 不存在", file=sys.stderr)
            rc = 1
    for name in HTML_OPTIONAL:
        p = HTML_SRC / name
        if p.exists():
            print(f"[OK]   {p.relative_to(REPO_ROOT)} ({p.stat().st_size:,} bytes)")
        else:
            print(f"[skip] {p.relative_to(REPO_ROOT)} (可选)")

    print("\n===== 校验 data/ =====")
    for name in DATA_REQUIRED:
        p = DATA_SRC / name
        if not p.exists():
            print(f"[FAIL] {p.relative_to(REPO_ROOT)} 不存在 (必需)", file=sys.stderr)
            rc = 1
            continue
        rc |= _validate_json(p, p.relative_to(REPO_ROOT).as_posix())
    for name in DATA_OPTIONAL:
        p = DATA_SRC / name
        if not p.exists():
            print(f"[skip] {name} (可选)")
            continue
        rc |= _validate_json(p, p.relative_to(REPO_ROOT).as_posix())

    # 大小预算（任意单文件 ≤ 500 KB，index.html ≤ 200 KB）
    print("\n===== 大小预算 =====")
    big = []
    for p in [HTML_SRC / "index.html", *(DATA_SRC / n for n in DATA_REQUIRED + DATA_OPTIONAL)]:
        if p.exists():
            sz = p.stat().st_size
            budget = 200_000 if p.name == "index.html" else 500_000
            flag = "[OK]  " if sz <= budget else "[WARN]"
            print(f"{flag} {p.relative_to(REPO_ROOT)} = {sz:,} bytes (预算 {budget:,})")
            if sz > budget:
                big.append(p)

    if big:
        print(f"\n[WARN] {len(big)} 个文件超出预算，部署可能仍成功但需评估", file=sys.stderr)

    print("\n✅ validate-only 完成" if rc == 0 else "\n❌ validate-only 失败")
    return rc


# ---------- build ----------
def _copy(src: Path, dst: Path) -> None:
    """copy 文件或目录到 dst（dst 不存在则建，存在则覆盖）。"""
    if src.is_dir():
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
    else:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def build(output: Path) -> int:
    print(f"===== 拼装 deploy bundle → {output} =====")
    output = output.resolve()
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)

    # 1) HTML + PWA 静态资源
    for name in HTML_REQUIRED + HTML_OPTIONAL:
        src = HTML_SRC / name
        if not src.exists():
            if name in HTML_REQUIRED:
                print(f"[FAIL] {src} 不存在 (必需)", file=sys.stderr)
                return 1
            print(f"[skip] {name} (可选缺失)")
            continue
        _copy(src, output / name)
        print(f"  + {name}")

    for sub in HTML_SUBDIRS_OPTIONAL:
        src = HTML_SRC / sub
        if not src.exists():
            print(f"[skip] {sub}/ (可选缺失)")
            continue
        _copy(src, output / sub)
        print(f"  + {sub}/")

    # 2) data/ JSON（fetch 入口）
    data_dst = output / "data"
    data_dst.mkdir(exist_ok=True)
    for name in DATA_REQUIRED:
        src = DATA_SRC / name
        if not src.exists():
            print(f"[FAIL] data/{name} 不存在 (必需)", file=sys.stderr)
            return 1
        _copy(src, data_dst / name)
        print(f"  + data/{name}")

    for name in DATA_OPTIONAL:
        src = DATA_SRC / name
        if not src.exists():
            print(f"[skip] data/{name} (可选)")
            continue
        _copy(src, data_dst / name)
        print(f"  + data/{name}")

    # 3) 校验生成的 bundle
    print("\n===== bundle 内容 =====")
    files = sorted(output.rglob("*"))
    total_size = 0
    for p in files:
        if p.is_file():
            sz = p.stat().st_size
            total_size += sz
            rel = p.relative_to(output).as_posix()
            print(f"  {rel:40s} {sz:>10,} bytes")
    print(f"\n总文件数 = {sum(1 for p in files if p.is_file())}, "
          f"总大小 = {total_size:,} bytes ({total_size/1024:.1f} KB)")

    print("\n✅ bundle 已就绪，可以执行：")
    print(f"   cd {output}")
    print(f"   tcb hosting deploy . /liuwangqingbaozhan -e liwang-jiankong-d2eatyj479b1861")
    return 0


# ---------- main ----------
def main(argv: Iterable[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="NSP-IM v3.0 deploy bundle builder")
    ap.add_argument("--validate-only", action="store_true", help="仅校验源数据完整性")
    ap.add_argument("--output", type=Path, help="bundle 输出目录")
    args = ap.parse_args(list(argv) if argv is not None else None)

    if args.validate_only:
        return validate_only()
    if args.output:
        return build(args.output)

    ap.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())