"""
NSP-IM 原子写入工具 (B4 - W1-D4)
================================

目标:
    防止 "抓取中途崩溃 → 半写文件污染下游消费" 这类 P0 问题。

设计原则（contract）:
    - 写入目标文件全过程**对消费者要么"看到旧版本"、要么"看到完整新版本"，绝看不到"半写"**。
    - 同一进程/多进程并发原子写 → 结果是"最后完成写入者全量覆盖"，不出现文件错乱。
    - 任何环节抛异常 → 临时文件一定清理 / 不污染目录。

实现要点（POSIX & Windows 通用）:
    1. 写入目标: `<target>.tmp.<pid>.<rand>` （同目录下，rename 跨目录的 atomicity 才能保证）
    2. 写入方式: 文本模式 + `fsync()` 确保数据落盘
       - Windows 上 `os.fsync` 行为与 POSIX 一致（落到底层存储介质）
    3. 落盘后 `Path.replace()` 替换目标
       - POSIX: rename(2) 原子
       - Windows: Python 3.3+ Path.replace 等价于 os.replace → MoveFileExW(..., MOVEFILE_REPLACE_EXISTING) 原子
    4. 临时文件清理: try/finally + 注册 atexit 兜底
"""
from __future__ import annotations

import atexit
import errno
import os
import random
import tempfile
from pathlib import Path
from typing import Any, Optional

# ---------- 全局清扫 ----------
# 进程生命周期内所有由本进程创建的 .tmp 残留，进程退出时一律清理，
# 避免"抓取脚本 ctrl-C 留下半写 .tmp"污染 data 目录。
_TMP_TRACKER: set[Path] = set()
_TMP_TRACKER_LOCK = False  # 简单保护 (Python GIL 保障 list/set 基本操作原子)


def _track(path: Path) -> None:
    _TMP_TRACKER.add(path)
    if len(_TMP_TRACKER) == 1:
        atexit.register(_cleanup_tracked)


def _cleanup_tracked() -> None:
    """进程退出前清扫遗留临时文件。"""
    for p in list(_TMP_TRACKER):
        try:
            if p.exists():
                p.unlink()
        except OSError:
            pass  # best-effort
    _TMP_TRACKER.clear()


def _new_tmp(target: Path) -> Path:
    """在 target 同目录下生成唯一临时文件名。

    跨目录 rename 在 POSIX 上可能不再是 atomic 的，所以必须同目录。
    Windows 上同理（MoveFileEx 在同卷上原子）。
    """
    parent = target.parent
    parent.mkdir(parents=True, exist_ok=True)
    pid = os.getpid()
    rand = random.randint(0, 1_000_000)
    return parent / f".{target.name}.tmp.{pid}.{rand}"


def _retry_replace(tmp: Path, target: Path, *, attempts: int = 5, base_delay: float = 0.02) -> None:
    """带退避的 os.replace。

    为什么需要 retry:
      - Windows 上并发 rename 同一目标, 偶发出现 PermissionError(13)
        （即使 .tmp 文件名不同, NTFS 的目标文件锁会拒绝并行 rename）
      - 防病毒/索引服务短暂持有文件句柄也会触发
      - 退避 20ms→40ms→80ms... 覆盖掉毫秒级争用
    """
    last_err: Optional[OSError] = None
    for i in range(attempts):
        try:
            os.replace(tmp, target)
            return
        except OSError as e:  # noqa: PERF203
            last_err = e
            if e.errno not in (errno.EACCES, errno.EPERM, errno.EBUSY, errno.ETXTBSY):
                # 非"文件被锁/无权限"类型，不值得重试
                raise
            if i < attempts - 1:
                import time
                time.sleep(base_delay * (2 ** i))
    assert last_err is not None
    raise last_err


def atomic_write_text(path: str | Path, content: str, encoding: str = "utf-8") -> Path:
    """以文本模式原子写入字符串。返回最终目标 Path。"""
    target = Path(path)
    tmp = _new_tmp(target)
    _track(tmp)
    try:
        with open(tmp, "w", encoding=encoding, newline="") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        _retry_replace(tmp, target)
    finally:
        # 成功 → tmp 已被 rename 走，不存在；失败 → 清理残留
        try:
            if tmp.exists():
                tmp.unlink()
        except OSError:
            pass
        _TMP_TRACKER.discard(tmp)
    return target


def atomic_write_bytes(path: str | Path, data: bytes) -> Path:
    """以二进制模式原子写入字节。返回最终目标 Path。"""
    target = Path(path)
    tmp = _new_tmp(target)
    _track(tmp)
    try:
        with open(tmp, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        _retry_replace(tmp, target)
    finally:
        try:
            if tmp.exists():
                tmp.unlink()
        except OSError:
            pass
        _TMP_TRACKER.discard(tmp)
    return target


def atomic_write_json(path: str | Path, obj: Any, *, ensure_ascii: bool = False, indent: int = 2, sort_keys: bool = False) -> Path:
    """原子写入 JSON。默认 ensure_ascii=False（中文可读）、indent=2（diff 友好）。"""
    import json
    text = json.dumps(obj, ensure_ascii=ensure_ascii, indent=indent, sort_keys=sort_keys)
    return atomic_write_text(path, text, encoding="utf-8")


def safe_read_json(path: str | Path, default: Any = None) -> Any:
    """读取 JSON；文件不存在/格式错误时返回 default 而不是抛异常。

    用于 fetcher.save() 这种"读旧数据 → 合并 → 写新数据"的合并场景：
    任何解析异常都不能阻塞新数据写入。
    """
    import json
    p = Path(path)
    if not p.exists():
        return default
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        # 留痕但不让 writer 崩
        import sys
        print(f"[atomic_write] safe_read_json {p} 失败: {e}", file=sys.stderr)
        return default


__all__ = [
    "atomic_write_text",
    "atomic_write_bytes",
    "atomic_write_json",
    "safe_read_json",
]
