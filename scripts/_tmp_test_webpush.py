"""临时测试 - 验证 pywebpush 真实走得通."""
import sys
from pathlib import Path

# 强制 reload utils 模块
vapid_file = Path("data/.vapid.json")
if vapid_file.exists():
    vapid_file.unlink()
sys.path.insert(0, "src")
for mod in list(sys.modules):
    if mod.startswith("utils"):
        del sys.modules[mod]

import base64
import os
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

# 客户端密钥对 (合法的 65 字节 uncompressed point)
client_sk = ec.generate_private_key(ec.SECP256R1())
client_pk_bytes = client_sk.public_key().public_bytes(
    encoding=serialization.Encoding.X962,
    format=serialization.PublicFormat.UncompressedPoint,
)
client_pk_b64 = base64.urlsafe_b64encode(client_pk_bytes).rstrip(b"=").decode()
auth_b64 = base64.urlsafe_b64encode(os.urandom(16)).rstrip(b"=").decode()

from utils.vapid import get_or_create_vapid_keys
from py_vapid import Vapid
import pywebpush

keys = get_or_create_vapid_keys()
v = Vapid.from_string(private_key=keys.private_key_b64url)

out = pywebpush.webpush(
    subscription_info={
        "endpoint": "https://fcm.googleapis.com/fcm/send/abc",
        "keys": {"p256dh": client_pk_b64, "auth": auth_b64},
    },
    data='{"title":"test","body":"hi"}',
    vapid_private_key=v,
    vapid_claims={"sub": "mailto:test@example.com"},
    curl=True,
)
print("SUCCESS - VAPID + payload 加密全走通")
print(out[:500])