"""
NSP-IM VAPID (Voluntary Application Server Identification) utilities
====================================================================

W3-D3 BE 改动:
  - VAPID 密钥对生成 (P-256 ECDSA)
  - 持久化到 data/.vapid.json (umask 0o600, base64url 编码)
  - 启动时 lazy 加载 (首次调用才读文件, 避免 IO 阻塞)
  - 同时输出 applicationServerKey (公钥 base64url) 给前端订阅用
  - 路径锚定仓库根 (与 base.py 一致), 不依赖 CWD

VAPID 协议参考: RFC 8292 (Message Encryption for Web Push)
"""

from __future__ import annotations

import base64
import json
import logging
import os
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from cryptography.hazmat.primitives.asymmetric import ec

LOG = logging.getLogger("nspim.push.vapid")

# ----- 路径锚定: 与 src/fetchers/base.py 保持一致 -----
_THIS = Path(__file__).resolve()
# src/utils/vapid.py → parents[0]=src/utils, parents[1]=src, parents[2]=nsp-im
REPO_ROOT = _THIS.parents[2]
DEFAULT_VAPID_FILE = REPO_ROOT / "data" / ".vapid.json"

# VAPID 私钥序列化格式 (PKCS8 / PEM)
_PKCS8_PEM_HEADER = b"-----BEGIN PRIVATE KEY-----"
_PKCS8_PEM_FOOTER = b"-----END PRIVATE KEY-----"


@dataclass(frozen=True)
class VAPIDKeys:
    """VAPID 密钥对 - 公钥给前端订阅, 私钥服务端签名用."""

    public_key_b64url: str   # 应用服务器公钥 (前端订阅时传入)
    private_key_b64url: str  # 应用服务器私钥 (服务端签名)
    subject: str             # VAPID 主题 (mailto:... 或 https://...)

    def to_dict(self) -> dict:
        return {
            "public_key": self.public_key_b64url,
            "private_key": self.private_key_b64url,
            "subject": self.subject,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "VAPIDKeys":
        return cls(
            public_key_b64url=d["public_key"],
            private_key_b64url=d["private_key"],
            subject=d.get("subject", "mailto:nspim@example.com"),
        )


def _b64url_decode(data: str) -> bytes:
    """base64url 解码 (容错: 缺失 padding 自动补齐)."""
    pad = 4 - len(data) % 4
    if pad != 4:
        data += "=" * pad
    return base64.urlsafe_b64decode(data)


def _b64url_encode(data: bytes) -> str:
    """base64url 编码 (去 padding, 与 Web Crypto 兼容)."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def generate_vapid_keys(subject: str = "mailto:nspim@example.com") -> VAPIDKeys:
    """生成新的 VAPID 密钥对 (P-256 ECDSA).

    RFC 8292 要求: P-256 曲线, 私钥长度 32 字节, 公钥长度 65 字节 (uncompressed).
    """
    sk = ec.generate_private_key(ec.SECP256R1())
    pk = sk.public_key()

    # 私钥: 提取 32 字节原始 scalar (用于 VAPID 签名, RFC 8292 §2)
    sk_numbers = sk.private_numbers()
    sk_raw = sk_numbers.private_value.to_bytes(32, "big")

    # 公钥: uncompressed point (0x04 || x || y), 65 字节
    pk_numbers = pk.public_numbers()
    pk_raw = b"\x04" + pk_numbers.x.to_bytes(32, "big") + pk_numbers.y.to_bytes(32, "big")

    return VAPIDKeys(
        public_key_b64url=_b64url_encode(pk_raw),
        private_key_b64url=_b64url_encode(sk_raw),
        subject=subject,
    )


def _load_private_key_for_pywebpush(vapid_private_b64url: str):
    """把 VAPID 私钥 base64url 转 cryptography EC key 对象 (pywebpush 内部需要).

    注意: 实现已迁移到 utils/webpush.py._load_private_key_for_pywebpush.
    保留此符号向后兼容.
    """
    from utils.webpush import _load_private_key_for_pywebpush as _impl

    return _impl(vapid_private_b64url)


def save_vapid_keys(vapid: VAPIDKeys, path: Optional[Path] = None) -> Path:
    """保存到 .vapid.json (敏感文件, 0o600 权限)."""
    target = path or DEFAULT_VAPID_FILE
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(
        json.dumps(vapid.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    # Windows 下没有 POSIX 0o600 语义, 但 os.chmod 在 NTFS 上仍生效 (只读位)
    try:
        os.chmod(tmp, 0o600)
    except OSError:
        pass
    os.replace(tmp, target)
    LOG.info("VAPID 密钥已保存到 %s", target)
    return target


def load_vapid_keys(path: Optional[Path] = None) -> Optional[VAPIDKeys]:
    """读取已保存的 VAPID 密钥. 不存在返回 None."""
    target = path or DEFAULT_VAPID_FILE
    if not target.exists():
        return None
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
        return VAPIDKeys.from_dict(data)
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        LOG.error("VAPID 密钥文件 %s 损坏: %s", target, e)
        return None


# ----- 单例 lazy load (进程级, 线程安全) -----
_cached: Optional[VAPIDKeys] = None
_lock = threading.Lock()


def get_or_create_vapid_keys(
    subject: Optional[str] = None,
    path: Optional[Path] = None,
    regenerate: bool = False,
) -> VAPIDKeys:
    """获取 VAPID 密钥 (lazy + cached).

    优先级:
      1. 进程内缓存 (避免每次都 IO)
      2. 文件缓存 (data/.vapid.json)
      3. 现场生成 (写回文件)
    """
    global _cached
    with _lock:
        if _cached is not None and not regenerate:
            return _cached

        if not regenerate:
            loaded = load_vapid_keys(path)
            if loaded is not None:
                _cached = loaded
                return loaded

        subj = subject or os.environ.get("VAPID_SUBJECT", "mailto:nspim@example.com")
        keys = generate_vapid_keys(subj)
        save_vapid_keys(keys, path)
        _cached = keys
        return keys


def get_vapid_private_pem_for_pywebpush(path: Optional[Path] = None) -> tuple[str, str]:
    """便捷函数: 返回 (private_pem, public_b64url) 给 pywebpush 用.

    保留旧签名, 但实际上新版 pywebpush 用 EC key 对象而非 PEM.
    """
    keys = get_or_create_vapid_keys(path=path)
    return keys.public_key_b64url, keys.public_key_b64url