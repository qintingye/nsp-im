"""临时测试 - send_push 完整路径."""
import sys
from pathlib import Path

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

client_sk = ec.generate_private_key(ec.SECP256R1())
client_pk_bytes = client_sk.public_key().public_bytes(
    encoding=serialization.Encoding.X962,
    format=serialization.PublicFormat.UncompressedPoint,
)
client_pk_b64 = base64.urlsafe_b64encode(client_pk_bytes).rstrip(b"=").decode()
auth_b64 = base64.urlsafe_b64encode(os.urandom(16)).rstrip(b"=").decode()

from utils.webpush import PushSubscription, PushPayload, send_push, PushError

sub = PushSubscription(
    endpoint="https://fcm.googleapis.com/fcm/send/abc-not-real",
    keys_p256dh=client_pk_b64,
    keys_auth=auth_b64,
)
payload = PushPayload(title="NSP-IM", body="新增 3 条政策", url="/p/test")

try:
    send_push(sub, payload, timeout=3)
    print("UNEXPECTED success")
except PushError as e:
    print(f"got expected: {type(e).__name__} status={e.status_code}")
    print(f"message: {str(e)[:300]}")