#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
scripts/git_commit_data.py
=========================

W1-D4 BE 任务 - Git 自动提交脚本。

目的:
    主抓取器跑完后，自动把新增的 data/*.json 提交到 Git，给前端的"内网
    预览"和 CI 提供可回滚、可追溯的版本来源。

设计:
    - 只关注 data/ 下"有变化"的文件（用 git status --porcelain）
    - 不写死 commit message，每天自动拼一个【日期 + 简要摘要】
    - 失败时不留半成品 commit（no-verify + 自动 abort）
    - 强约束: 仓库必须"干净"或者只有 data/* 未提交版本，否则拒绝提交避免混淆

调用方式:
    # 1. main_fetcher.py 跑完后调用
    python scripts/git_commit_data.py --commit-msg "auto: W1-D4 数据更新"

    # 2. CI 每日 09:00 触发
    python scripts/git_commit_data.py --auto

    # 3. 干跑 (不实际 commit)，看会提交什么
    python scripts/git_commit_data.py --dry-run

退出码:
    0  - 提交成功（或无内容可提交，正常退出）
    1  - 仓库脏 / git 异常 / 用户中断
    2  - 参数错误

依赖: 仅 stdlib + 项目 .venv 里的 git CLI。
"""
from __future__ import annotations

import argparse
import datetime as dt
import logging
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Tuple

# ---------- 路径定位 ----------
SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parent.parent  # nsp-im/
DATA_DIR = REPO_ROOT / "data"

# ---------- 日志 ----------
logger = logging.getLogger("nsp-git-commit")
_handler = logging.StreamHandler(sys.stdout)
_handler.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s %(message)s",
                                       datefmt="%H:%M:%S"))
logger.addHandler(_handler)
logger.setLevel(logging.INFO)


# ---------- git 工具 ----------
class GitError(RuntimeError):
    """git 命令失败。"""


def _run_git(args: List[str], *, cwd: Path, check: bool = True) -> Tuple[int, str, str]:
    """运行 git 子命令。返回 (rc, stdout, stderr)。"""
    proc = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if check and proc.returncode != 0:
        raise GitError(
            f"git {' '.join(args)} failed (rc={proc.returncode}): {proc.stderr.strip()}"
        )
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def is_in_repo(cwd: Path = REPO_ROOT) -> bool:
    rc, _, _ = _run_git(["rev-parse", "--is-inside-work-tree"], cwd=cwd, check=False)
    return rc == 0


def current_branch(cwd: Path = REPO_ROOT) -> str:
    rc, out, _ = _run_git(["symbolic-ref", "--short", "HEAD"], cwd=cwd, check=False)
    if rc != 0:
        # detached HEAD 时返回 HEAD
        rc2, out2, _ = _run_git(["rev-parse", "--short", "HEAD"], cwd=cwd, check=False)
        return out2 if rc2 == 0 else "(unknown)"
    return out


# ---------- 状态检查 ----------
def list_changed_data_files(cwd: Path = REPO_ROOT) -> List[str]:
    """返回 data/ 下相对路径的状态变化文件 (added/modified/deleted)."""
    if not is_in_repo(cwd):
        return []
    _, out, _ = _run_git(["status", "--porcelain", "--untracked-files=all", "--", "data/"],
                         cwd=cwd, check=False)
    files: List[str] = []
    for line in out.splitlines():
        if len(line) < 4:
            continue
        # porcelain 格式: XY <path>
        # 第三个字符起是路径；如果是重命名 'R ' 则路径是 'old -> new'
        rest = line[3:]
        if "->" in rest:
            _, _, new = rest.partition("->")
            new = new.strip()
            files.append(new)
        else:
            files.append(rest.strip())
    return [f for f in files if f]


def is_repo_clean_except_data(cwd: Path = REPO_ROOT, *, allow_other_changes: bool = False) -> Tuple[bool, List[str]]:
    """仓库除 data/ 外必须干净；返回 (干净, 干扰文件列表)。

    allow_other_changes=True 时跳过校验 (允许 dirty 但只 commit data/)。
    """
    if allow_other_changes:
        return (True, [])
    _, out, _ = _run_git(["status", "--porcelain", "--untracked-files=all"], cwd=cwd, check=False)
    dirty: List[str] = []
    for line in out.splitlines():
        if not line:
            continue
        path_part = line[3:]
        # 排除 data/ 开头
        if not path_part.startswith("data/"):
            dirty.append(line)
    return (len(dirty) == 0, dirty)


# ---------- 提交主流程 ----------
def make_commit_message(template: str, files: List[str], auto: bool) -> str:
    """生成 commit message。模板里 {date} {count} {files} 是占位符。"""
    today = dt.date.today().isoformat()
    return (template
            .replace("{date}", today)
            .replace("{count}", str(len(files)))
            .replace("{files}", ", ".join(f.replace("data/", "") for f in files[:5]))
            .replace("{auto_suffix}", " [auto]" if auto else ""))


def commit_data(commit_message: str, *, cwd: Path = REPO_ROOT,
                author_name: str = "NSP-IM Bot",
                author_email: str = "nsp-im-bot@hermes.local",
                dry_run: bool = False,
                allow_other_changes: bool = False) -> int:
    """执行 add+commit。可以被 main_fetcher 在抓完后直接调用。

    返回:
        0 - 提交成功 (或无变更)
        1 - 有未提交冲突 (dirty)
        2 - 未指定 message
        3 - git 操作失败
    """
    if not is_in_repo(cwd):
        logger.error(f"❌ {cwd} 不是 git 仓库")
        return 1

    if not commit_message:
        logger.error("❌ commit message 不能为空")
        return 2

    # 1. 拦截其他脏文件 (除非显式放行)
    clean, dirty = is_repo_clean_except_data(cwd, allow_other_changes=allow_other_changes)
    if not clean:
        logger.error("❌ 仓库除 data/ 外还有未提交变更，请先处理:")
        for d in dirty:
            logger.error(f"   {d}")
        return 1

    # 2. 收集要提交的文件
    files = list_changed_data_files(cwd)
    if not files:
        logger.info("ℹ️  data/ 无变更，跳过提交")
        return 0

    logger.info(f"📝 待提交 {len(files)} 个文件:")
    for f in files:
        logger.info(f"   - {f}")

    if dry_run:
        logger.info("🔍 DRY-RUN: 不实际执行 git add/commit")
        return 0

    # 3. 配 bot 身份（仅本次进程，不污染全局 gitconfig）
    bot_env = {
        "GIT_AUTHOR_NAME": author_name,
        "GIT_AUTHOR_EMAIL": author_email,
        "GIT_COMMITTER_NAME": author_name,
        "GIT_COMMITTER_EMAIL": author_email,
    }
    import os
    saved_env = {k: os.environ.get(k) for k in bot_env}
    os.environ.update(bot_env)

    try:
        # 4. add
        rc, _, err = _run_git(["add", "--", "data/"], cwd=cwd, check=False)
        if rc != 0:
            logger.error(f"❌ git add 失败: {err}")
            return 3

        # 5. commit
        rc, _, err = _run_git(["commit", "-m", commit_message], cwd=cwd, check=False)
        if rc != 0:
            logger.error(f"❌ git commit 失败: {err}")
            return 3

        # 6. 显示结果
        rc, sha, _ = _run_git(["rev-parse", "--short", "HEAD"], cwd=cwd, check=False)
        rc2, msg, _ = _run_git(["log", "-1", "--pretty=format:%s"], cwd=cwd, check=False)
        branch = current_branch(cwd)
        logger.info(f"✅ 提交成功 [{sha}] on {branch}: {msg}")

        return 0

    finally:
        for k, v in saved_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


# ---------- CLI ----------
def parse_args(argv=None) -> argparse.Namespace:
    today = dt.date.today().isoformat()
    p = argparse.ArgumentParser(
        description="NSP-IM 自动提交 data/ 到 Git (W1-D4)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument(
        "-m", "--commit-msg",
        default=f"auto: 数据更新 {today}",
        help="commit message。模板占位符: {date} {count} {files} {auto_suffix}",
    )
    p.add_argument(
        "--auto",
        action="store_true",
        help="自动模式 (被 CI 或 main_fetcher 调用)",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="只列出待提交文件，不实际 commit",
    )
    p.add_argument(
        "--allow-dirty",
        action="store_true",
        help="允许 data/ 外也有未提交变更 (不推荐)",
    )
    p.add_argument(
        "--repo",
        type=Path,
        default=REPO_ROOT,
        help="git 仓库根目录 (默认: 项目根)",
    )
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    repo = args.repo.resolve()
    if not is_in_repo(repo):
        logger.error(f"❌ {repo} 不是 git 仓库 (或 git 不可用)")
        return 1

    # 先 list files，再用真实数字生成 commit message
    files = list_changed_data_files(repo)
    msg = make_commit_message(args.commit_msg, files, args.auto)

    return commit_data(msg, cwd=repo, dry_run=args.dry_run,
                       allow_other_changes=args.allow_dirty)


if __name__ == "__main__":
    sys.exit(main())
