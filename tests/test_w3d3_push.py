"""
W3-D3: Web Push + VAPID + Subscription 存储 测试套件
=====================================================

覆盖:
    - VAPID 密钥生成 / 持久化 / 往返 (RFC 8292 §2 兼容)
    - Web Push 载荷编码 (PushPayload.to_json 字段裁剪)
    - 订阅管理 (add / list / mark_expired / cleanup / dedup / 鉴权)
    - OneSignal 配置 (env 检测 + 边界)

不真发推送 (mock pywebpush.webpush), 避免触发 FCM/Mozilla 真实推送造成 spam。
"""

from __future__ import annotations

import base64
import json
import os
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

# ---- 路径: src/ 加入 sys.path ----
REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


# ============================================================================
# VAPID 密钥生成
# ============================================================================

class TestVAPIDKeys(unittest.TestCase):
    """VAPID 密钥生成 / 编码 / 持久化."""

    def setUp(self) -> None:
        # 每个测试用独立临时目录, 避免污染 repo data/
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.vapid_path = Path(self.tmp.name) / "vapid_keys.json"

    def test_generate_vapid_keys_format(self):
        """生成的密钥对应当满足 RFC 8292 字节长度 + base64url 编码."""
        from utils.vapid import VAPIDKeys, generate_vapid_keys

        keys = generate_vapid_keys(subject="mailto:test@example.com")
        self.assertIsInstance(keys, VAPIDKeys)
        self.assertEqual(keys.subject, "mailto:test@example.com")

        # 解码验证字节长度
        # base64url 字符数 = ceil(65*4/3) = 87 (无 padding)
        pk_bytes = _b64url_decode(keys.public_key_b64url)
        sk_bytes = _b64url_decode(keys.private_key_b64url)
        # RFC 8292: 公钥 uncompressed point = 0x04 + 32 字节 x + 32 字节 y = 65 字节
        self.assertEqual(len(pk_bytes), 65, "公钥 uncompressed P-256 point 应当是 65 字节")
        self.assertEqual(pk_bytes[0], 0x04, "公钥首字节必须是 0x04 (uncompressed 标记)")
        # 私钥 scalar = 32 字节
        self.assertEqual(len(sk_bytes), 32, "私钥 scalar 应当是 32 字节")

    def test_save_and_load_roundtrip(self):
        """save → load 应能完整还原密钥对."""
        from utils.vapid import generate_vapid_keys, save_vapid_keys, load_vapid_keys

        keys = generate_vapid_keys(subject="mailto:rt@example.com")
        save_vapid_keys(keys, self.vapid_path)
        self.assertTrue(self.vapid_path.exists(), "保存后文件应存在")

        loaded = load_vapid_keys(self.vapid_path)
        self.assertIsNotNone(loaded, "读取不应返回 None")
        self.assertEqual(loaded.public_key_b64url, keys.public_key_b64url)
        self.assertEqual(loaded.private_key_b64url, keys.private_key_b64url)
        self.assertEqual(loaded.subject, keys.subject)

    def test_load_missing_returns_none(self):
        """读取不存在文件应返回 None (不抛异常)."""
        from utils.vapid import load_vapid_keys

        loaded = load_vapid_keys(self.vapid_path)  # 文件不存在
        self.assertIsNone(loaded)

    def test_load_corrupted_returns_none(self):
        """文件 JSON 损坏应优雅降级到 None."""
        from utils.vapid import load_vapid_keys

        self.vapid_path.write_text("{bad json", encoding="utf-8")
        loaded = load_vapid_keys(self.vapid_path)
        self.assertIsNone(loaded, "损坏文件不应抛异常, 应返回 None")

    def test_get_or_create_caches(self):
        """get_or_create 应复用已有文件 (幂级)."""
        from utils.vapid import (
            generate_vapid_keys,
            save_vapid_keys,
            get_or_create_vapid_keys,
        )

        first = generate_vapid_keys(subject="mailto:cached@example.com")
        save_vapid_keys(first, self.vapid_path)

        cached = get_or_create_vapid_keys(path=self.vapid_path)
        # 二次调用应返回文件里的同一对 (而非新生成)
        self.assertEqual(cached.public_key_b64url, first.public_key_b64url)
        self.assertEqual(cached.private_key_b64url, first.private_key_b64url)


# ============================================================================
# Web Push 载荷
# ============================================================================

class TestPushPayload(unittest.TestCase):
    """PushPayload 字段裁剪 + JSON 编码."""

    def test_basic_payload_json_shape(self):
        from utils.webpush import PushPayload

        p = PushPayload(title="新政策", body="今天发布新政策", url="/policy/123")
        js = p.to_json()
        d = json.loads(js)

        self.assertEqual(d["title"], "新政策")
        self.assertEqual(d["body"], "今天发布新政策")
        self.assertEqual(d["url"], "/policy/123")
        self.assertEqual(d["requireInteraction"], False)
        # 默认 icon / badge 应填充
        self.assertIn("icon", d)
        self.assertIn("badge", d)

    def test_title_truncated_to_64_chars(self):
        """title 必须 ≤ 64 字符 (OneSignal 也按此截断)."""
        from utils.webpush import PushPayload

        long_title = "x" * 200
        p = PushPayload(title=long_title, body="body")
        d = json.loads(p.to_json())
        self.assertEqual(len(d["title"]), 64)
        self.assertEqual(d["title"], "x" * 64)

    def test_body_truncated_to_200_chars(self):
        from utils.webpush import PushPayload

        long_body = "y" * 500
        p = PushPayload(title="t", body=long_body)
        d = json.loads(p.to_json())
        self.assertEqual(len(d["body"]), 200)

    def test_payload_supports_chinese(self):
        """中文载荷应正确往返 (ensure_ascii=False)."""
        from utils.webpush import PushPayload

        p = PushPayload(title="国家发改委新政策", body="关于 2026 年新型电力系统建设的指导意见")
        js = p.to_json()
        # 不应被转义为 \uXXXX
        self.assertIn("国家发改委", js)
        self.assertIn("2026", js)
        # 仍可解析回 dict
        d = json.loads(js)
        self.assertEqual(d["title"], "国家发改委新政策")


# ============================================================================
# 订阅管理
# ============================================================================

class TestSubscriptionStore(unittest.TestCase):
    """订阅存储: add / dedup / list / mark_expired / cleanup / increment_fail."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store_path = Path(self.tmp.name) / "subs.json"
        from api.subscriptions import SubscriptionStore
        self.store = SubscriptionStore(path=self.store_path)

    def _fake_sub(self, endpoint_suffix: str) -> dict:
        return {
            "endpoint": f"https://fcm.googleapis.com/fcm/send/{endpoint_suffix}",
            "keys": {
                "p256dh": "BNcRdreALRFXTkOOUHK1EtK2wtaz5Ry4_yf7uDAPe9omIj3lJ6gOdkpPy4GrInC2tF6BxIbKVBlRnF5-J1qY2q0",
                "auth": "tBHItJI5svbpez7KI4CCXg",
            },
        }

    def test_add_new_subscription(self):
        """新订阅应被记录, status=active."""
        ua = "Mozilla/5.0 TestBrowser"
        sub = self._fake_sub("abc123")
        rec = self.store.add(sub, ua=ua)

        self.assertEqual(rec["endpoint"], sub["endpoint"])
        self.assertEqual(rec["status"], "active")
        self.assertEqual(rec["fail_count"], 0)
        self.assertEqual(rec["ua"], ua)
        self.assertIn("created_at", rec)
        self.assertIn("last_seen_at", rec)

    def test_add_dedup_by_endpoint(self):
        """同一 endpoint 重复 add 应刷新而非新增."""
        sub = self._fake_sub("dup1")
        self.store.add(sub)
        self.store.add(sub)  # 第二次

        all_subs = self.store.list_all()
        self.assertEqual(len(all_subs), 1, "endpoint 应被去重")
        self.assertEqual(all_subs[0]["status"], "active")

    def test_list_active_filters_expired(self):
        """list_active 应排除 status=expired."""
        sub_a = self._fake_sub("alive")
        sub_b = self._fake_sub("dead")
        self.store.add(sub_a)
        self.store.add(sub_b)

        # 标记 B 失效
        self.store.mark_expired(sub_b["endpoint"])

        active = self.store.list_active()
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0]["endpoint"], sub_a["endpoint"])

    def test_mark_expired_idempotent(self):
        """重复 mark_expired 不报错, 也不丢失 expired_at."""
        sub = self._fake_sub("idem")
        self.store.add(sub)
        self.store.mark_expired(sub["endpoint"])
        first_expired = self.store.list_all()[0].get("expired_at")

        time.sleep(0.01)
        self.store.mark_expired(sub["endpoint"])  # 第二次
        second_expired = self.store.list_all()[0].get("expired_at")

        self.assertEqual(first_expired, second_expired, "重复标记不应更新时间戳")

    def test_increment_fail_threshold(self):
        """连续失败 ≥ 阈值应自动标记 expired."""
        sub = self._fake_sub("flaky")
        self.store.add(sub)

        # 阈值默认 3
        self.assertFalse(self.store.increment_fail(sub["endpoint"], threshold=3))
        self.assertFalse(self.store.increment_fail(sub["endpoint"], threshold=3))
        self.assertTrue(self.store.increment_fail(sub["endpoint"], threshold=3))

        # 现在应被自动失效
        active = self.store.list_active()
        self.assertEqual(len(active), 0)

    def test_cleanup_expired(self):
        """cleanup_expired 应物理删除 expired 记录."""
        sub_a = self._fake_sub("keep")
        sub_b = self._fake_sub("drop")
        self.store.add(sub_a)
        self.store.add(sub_b)
        self.store.mark_expired(sub_b["endpoint"])

        removed = self.store.cleanup_expired()
        self.assertEqual(removed, 1)

        all_subs = self.store.list_all()
        self.assertEqual(len(all_subs), 1)
        self.assertEqual(all_subs[0]["endpoint"], sub_a["endpoint"])

    def test_remove_returns_true_when_existed(self):
        sub = self._fake_sub("rm")
        self.store.add(sub)
        self.assertTrue(self.store.remove(sub["endpoint"]))
        self.assertEqual(self.store.count_active(), 0)

    def test_remove_returns_false_when_missing(self):
        self.assertFalse(self.store.remove("https://nope.example.com/x"))

    def test_has_endpoint(self):
        sub = self._fake_sub("exists")
        self.store.add(sub)
        self.assertTrue(self.store.has_endpoint(sub["endpoint"]))
        self.assertFalse(self.store.has_endpoint("https://nope"))

    def test_invalid_subscription_raises(self):
        """缺少 endpoint 或 keys 应抛 ValueError."""
        with self.assertRaises(ValueError):
            self.store.add({"keys": {"p256dh": "x", "auth": "y"}})
        with self.assertRaises(ValueError):
            self.store.add({"endpoint": "https://x", "keys": {}})

    def test_concurrent_add_is_thread_safe(self):
        """多线程并发 add 不应破坏 JSON 文件."""
        N_THREADS = 8

        def add_many(idx: int) -> None:
            for j in range(5):
                self.store.add(self._fake_sub(f"t{idx}-{j}"))

        threads = [threading.Thread(target=add_many, args=(i,)) for i in range(N_THREADS)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # 至少 N_THREADS * 5 条, 但因 dedup endpoint 不冲突, 全部保留
        all_subs = self.store.list_all()
        self.assertEqual(len(all_subs), N_THREADS * 5)


# ============================================================================
# Web Push 发送 (mock, 不真发推送)
# ============================================================================

class TestSendPushMocked(unittest.TestCase):
    """mock pywebpush.webpush 验证错误分类 + 批量逻辑."""

    def setUp(self) -> None:
        # 用临时 VAPID 路径, 避免污染 repo data/
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.vapid_path = Path(self.tmp.name) / "vapid.json"

        # 重置模块单例, 让 get_or_create_vapid_keys 用新路径
        import utils.vapid as vapid_mod
        vapid_mod._cached = None

        # 预生成 VAPID (避免 generate 依赖 repo path)
        from utils.vapid import generate_vapid_keys, save_vapid_keys
        save_vapid_keys(generate_vapid_keys(subject="mailto:test@mock"), self.vapid_path)

        # patch vapid 路径
        self._patcher = patch("utils.vapid.DEFAULT_VAPID_FILE", self.vapid_path)
        self._patcher.start()
        self.addCleanup(self._patcher.stop)

    def _make_sub(self, suffix: str = "1"):
        from utils.webpush import PushSubscription
        return PushSubscription(
            endpoint=f"https://fcm.googleapis.com/fcm/send/mock-{suffix}",
            keys_p256dh="BNcRdreALRFXTkOOUHK1EtK2wtaz5Ry4_yf7uDAPe9omIj3lJ6gOdkpPy4GrInC2tF6BxIbKVBlRnF5-J1qY2q0",
            keys_auth="tBHItJI5svbpez7KI4CCXg",
        )

    def test_send_push_success_returns_true(self):
        """mock webpush 返回 201 → send_push 返回 True."""
        from utils.webpush import send_push, PushPayload

        with patch("utils.webpush.pywebpush.webpush") as mock_webpush:
            mock_webpush.return_value = MagicMock(status_code=201)
            ok = send_push(self._make_sub(), PushPayload(title="t", body="b"))
        self.assertTrue(ok)
        mock_webpush.assert_called_once()

    def test_send_push_410_returns_false_silently(self):
        """410 Gone → 返回 False (订阅失效, 不抛)."""
        from utils.webpush import (
            send_push,
            PushPayload,
            SubscriptionExpired,
        )
        import pywebpush

        # 构造带 response.status_code=410 的异常
        fake_resp = MagicMock(status_code=410)
        exc = pywebpush.WebPushException("Gone")
        exc.response = fake_resp

        with patch("utils.webpush.pywebpush.webpush", side_effect=exc):
            ok = send_push(self._make_sub("dead"), PushPayload(title="t", body="b"))

        self.assertFalse(ok, "410 应返回 False (不抛)")

    def test_send_push_401_raises_vapid_config_error(self):
        """401 → 抛 VAPIDConfigError (运维介入)."""
        from utils.webpush import send_push, PushPayload, VAPIDConfigError
        import pywebpush

        fake_resp = MagicMock(status_code=401)
        exc = pywebpush.WebPushException("Unauthorized")
        exc.response = fake_resp

        with patch("utils.webpush.pywebpush.webpush", side_effect=exc):
            with self.assertRaises(VAPIDConfigError):
                send_push(self._make_sub(), PushPayload(title="t", body="b"))

    def test_send_push_429_raises_rate_limited(self):
        """429 → 抛 RateLimited (退避重试)."""
        from utils.webpush import send_push, PushPayload, RateLimited
        import pywebpush

        fake_resp = MagicMock(status_code=429)
        exc = pywebpush.WebPushException("Too Many Requests")
        exc.response = fake_resp

        with patch("utils.webpush.pywebpush.webpush", side_effect=exc):
            with self.assertRaises(RateLimited):
                send_push(self._make_sub(), PushPayload(title="t", body="b"))

    def test_send_push_batch_counts(self):
        """批量推送: success / expired / error 三类应正确分类."""
        from utils.webpush import (
            send_push_batch,
            PushPayload,
            PushSubscription,
        )
        import pywebpush

        # 3 条订阅: ok / expired(410) / server error(500)
        ok_sub = PushSubscription(
            endpoint="https://fcm.googleapis.com/fcm/send/ok",
            keys_p256dh="BNcRdreALRFXTkOOUHK1EtK2wtaz5Ry4_yf7uDAPe9omIj3lJ6gOdkpPy4GrInC2tF6BxIbKVBlRnF5-J1qY2q0",
            keys_auth="tBHItJI5svbpez7KI4CCXg",
        )
        dead_sub = PushSubscription(
            endpoint="https://fcm.googleapis.com/fcm/send/dead",
            keys_p256dh="BNcRdreALRFXTkOOUHK1EtK2wtaz5Ry4_yf7uDAPe9omIj3lJ6gOdkpPy4GrInC2tF6BxIbKVBlRnF5-J1qY2q0",
            keys_auth="tBHItJI5svbpez7KI4CCXg",
        )
        err_sub = PushSubscription(
            endpoint="https://fcm.googleapis.com/fcm/send/err",
            keys_p256dh="BNcRdreALRFXTkOOUHK1EtK2wtaz5Ry4_yf7uDAPe9omIj3lJ6gOdkpPy4GrInC2tF6BxIbKVBlRnF5-J1qY2q0",
            keys_auth="tBHItJI5svbpez7KI4CCXg",
        )

        def fake_webpush(subscription_info, **_kwargs):
            ep = subscription_info["endpoint"]
            if "dead" in ep:
                exc = pywebpush.WebPushException("Gone")
                exc.response = MagicMock(status_code=410)
                raise exc
            if "err" in ep:
                raise pywebpush.WebPushException("Server Error")
            return MagicMock(status_code=201)

        with patch("utils.webpush.pywebpush.webpush", side_effect=fake_webpush):
            success, expired, error = send_push_batch(
                [ok_sub, dead_sub, err_sub],
                PushPayload(title="t", body="b"),
            )

        self.assertEqual(success, 1)
        self.assertEqual(expired, 1)
        self.assertEqual(error, 1)


# ============================================================================
# OneSignal 配置检测 (无需真实 API key)
# ============================================================================

class TestOneSignalConfig(unittest.TestCase):
    """OneSignalConfig.from_env + is_configured."""

    def test_unconfigured_returns_none(self):
        from utils.onesignal import OneSignalConfig
        env = {k: v for k, v in os.environ.items()
               if k not in ("ONESIGNAL_APP_ID", "ONESIGNAL_REST_API_KEY")}
        with patch.dict(os.environ, env, clear=True):
            cfg = OneSignalConfig.from_env()
        self.assertIsNone(cfg)

    def test_partial_config_returns_none(self):
        """只设 APP_ID 不设 API KEY → 不视为已配置."""
        from utils.onesignal import OneSignalConfig
        env = {k: v for k, v in os.environ.items()
               if k not in ("ONESIGNAL_APP_ID", "ONESIGNAL_REST_API_KEY")}
        with patch.dict(os.environ, env, clear=True):
            with patch.dict(os.environ, {"ONESIGNAL_APP_ID": "abc-only"}):
                cfg = OneSignalConfig.from_env()
        self.assertIsNone(cfg)

    def test_full_config_returns_instance(self):
        from utils.onesignal import OneSignalConfig
        env = {k: v for k, v in os.environ.items()
               if k not in ("ONESIGNAL_APP_ID", "ONESIGNAL_REST_API_KEY")}
        with patch.dict(os.environ, env, clear=True):
            with patch.dict(os.environ, {
                "ONESIGNAL_APP_ID": "abc-123",
                "ONESIGNAL_REST_API_KEY": "secret-key",
            }):
                cfg = OneSignalConfig.from_env()
        self.assertIsNotNone(cfg)
        self.assertEqual(cfg.app_id, "abc-123")
        self.assertEqual(cfg.rest_api_key, "secret-key")

    def test_notification_body_shape_and_app_id(self):
        """to_api_body 应填入 app_id + 各语言 contents."""
        from utils.onesignal import OneSignalNotification
        n = OneSignalNotification(
            heading="新政策",
            contents={"zh": "正文", "en": "body"},
            url="https://example.com/p/1",
        )
        body = n.to_api_body(app_id="test-app")
        self.assertEqual(body["app_id"], "test-app")
        # heading 落入 headings.en (默认语言)
        self.assertEqual(body["headings"]["en"], "新政策")
        # contents 多语言
        self.assertEqual(body["contents"]["en"], "body")
        self.assertEqual(body["contents"]["zh"], "正文")
        self.assertEqual(body["url"], "https://example.com/p/1")
        self.assertIn("included_segments", body)
        self.assertEqual(body["ttl"], 86400)


# ============================================================================
# 工具函数
# ============================================================================

def _b64url_decode(data: str) -> bytes:
    pad = 4 - len(data) % 4
    if pad != 4:
        data += "=" * pad
    return base64.urlsafe_b64decode(data)


if __name__ == "__main__":
    unittest.main(verbosity=2)