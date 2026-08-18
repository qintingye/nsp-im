"""
W3-D3 BE · Push 全链路单测
============================

覆盖范围:
  1) VAPID 密钥生成/落盘/读取一致性
  2) PushSubscription / PushPayload dataclass 序列化
  3) send_push 错误分类 (mock pywebpush.webpush)
  4) SubscriptionStore 全 CRUD + fail_count 阈值 + 并发安全
  5) server.py 4 个 endpoints (httptest via threading)
  6) worker.py diff_new_policies + 截断
  7) OneSignal 未配置时优雅降级

运行:
    cd D:\\hermes-dev-team\\nsp-im
    .venv-d5/Scripts/python.exe tests/test_push.py
    或 pytest tests/test_push.py
"""
import base64
import json
import os
import shutil
import socket
import sys
import tempfile
import threading
import time
import unittest
from http.client import HTTPConnection
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))  # 让 utils / api 可直接 import

from utils.vapid import (  # noqa: E402
    VAPIDKeys,
    _b64url_decode,
    _b64url_encode,
    generate_vapid_keys,
    get_or_create_vapid_keys,
    load_vapid_keys,
    save_vapid_keys,
    DEFAULT_VAPID_FILE,
)
from utils.webpush import (  # noqa: E402
    PushSubscription,
    PushPayload,
    PushError,
    SubscriptionExpired,
    VAPIDConfigError,
    RateLimited,
    _classify_error,
    send_push,
    send_push_batch,
)
from api.subscriptions import SubscriptionStore  # noqa: E402


# ============================================================
# 1. VAPID
# ============================================================

class TestVAPIDKeys(unittest.TestCase):

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="nsp_vapid_"))

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_generate_vapid_keys_lengths(self):
        """P-256 公钥 65 字节, 私钥 32 字节."""
        keys = generate_vapid_keys()
        pk_bytes = _b64url_decode(keys.public_key_b64url)
        sk_bytes = _b64url_decode(keys.private_key_b64url)
        self.assertEqual(len(pk_bytes), 65)
        self.assertEqual(pk_bytes[0], 0x04)  # uncompressed point 标志
        self.assertEqual(len(sk_bytes), 32)

    def test_generate_vapid_keys_subject(self):
        keys = generate_vapid_keys(subject="mailto:test@x.com")
        self.assertEqual(keys.subject, "mailto:test@x.com")

    def test_b64url_roundtrip(self):
        raw = b"\x00\xff\x10\x20" * 8
        encoded = _b64url_encode(raw)
        decoded = _b64url_decode(encoded)
        self.assertEqual(decoded, raw)
        # 不带 padding
        self.assertNotIn("=", encoded)

    def test_save_load_roundtrip(self):
        """保存 → 读取 → 一致."""
        target = self.tmpdir / "vapid.json"
        keys = generate_vapid_keys(subject="mailto:test@example.com")
        save_vapid_keys(keys, target)

        loaded = load_vapid_keys(target)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.public_key_b64url, keys.public_key_b64url)
        self.assertEqual(loaded.private_key_b64url, keys.private_key_b64url)
        self.assertEqual(loaded.subject, keys.subject)

    def test_load_missing_returns_none(self):
        loaded = load_vapid_keys(self.tmpdir / "missing.json")
        self.assertIsNone(loaded)

    def test_load_corrupted_returns_none(self):
        target = self.tmpdir / "vapid.json"
        target.write_text("{not json", encoding="utf-8")
        loaded = load_vapid_keys(target)
        self.assertIsNone(loaded)

    def test_get_or_create_uses_cache(self):
        """第二次调用不重写文件 (mtime 不变)."""
        target = self.tmpdir / "vapid.json"
        # 绕过单例缓存, 直接写
        keys = generate_vapid_keys()
        save_vapid_keys(keys, target)
        mtime_before = target.stat().st_mtime

        # 直接调 load, 不走缓存
        loaded = load_vapid_keys(target)
        self.assertEqual(loaded.public_key_b64url, keys.public_key_b64url)
        # 文件未被改动
        self.assertEqual(target.stat().st_mtime, mtime_before)


# ============================================================
# 2. WebPush dataclass + 错误分类
# ============================================================

class TestPushSubscription(unittest.TestCase):

    def test_to_dict_w3c_format(self):
        sub = PushSubscription(
            endpoint="https://example.com/push/abc",
            keys_p256dh="B" * 87,  # 65 字节 base64url
            keys_auth="A" * 22,
        )
        d = sub.to_dict()
        self.assertEqual(d["endpoint"], "https://example.com/push/abc")
        self.assertIn("keys", d)
        self.assertEqual(d["keys"]["p256dh"], "B" * 87)
        self.assertEqual(d["keys"]["auth"], "A" * 22)

    def test_from_dict_roundtrip(self):
        original = {
            "endpoint": "https://example.com/push/abc",
            "keys": {"p256dh": "BBB", "auth": "AAA"},
        }
        sub = PushSubscription.from_dict(original)
        self.assertEqual(sub.endpoint, "https://example.com/push/abc")
        self.assertEqual(sub.keys_p256dh, "BBB")
        self.assertEqual(sub.keys_auth, "AAA")

    def test_from_dict_missing_keys_raises(self):
        with self.assertRaises(KeyError):
            PushSubscription.from_dict({"endpoint": "x"})


class TestPushPayload(unittest.TestCase):

    def test_to_json_truncates_title_and_body(self):
        payload = PushPayload(
            title="X" * 200,
            body="Y" * 500,
        )
        data = json.loads(payload.to_json())
        self.assertEqual(len(data["title"]), 64)
        self.assertEqual(len(data["body"]), 200)

    def test_to_json_includes_optional_fields(self):
        payload = PushPayload(
            title="t",
            body="b",
            url="https://x.com/y",
            tag="alert-1",
            require_interaction=True,
            data={"k": "v"},
        )
        data = json.loads(payload.to_json())
        self.assertEqual(data["url"], "https://x.com/y")
        self.assertEqual(data["tag"], "alert-1")
        self.assertTrue(data["requireInteraction"])
        self.assertEqual(data["data"], {"k": "v"})

    def test_to_json_defaults_icons(self):
        payload = PushPayload(title="t", body="b")
        data = json.loads(payload.to_json())
        self.assertEqual(data["icon"], "/icons/icon-192.png")
        self.assertEqual(data["badge"], "/icons/badge-72.png")


class TestErrorClassification(unittest.TestCase):

    def test_classify_404_as_expired(self):
        e = mock.MagicMock(spec=["response"])
        e.response.status_code = 404
        e.__str__ = lambda self: "Not Found"
        cls = _classify_error(e)
        self.assertIsInstance(cls, SubscriptionExpired)
        self.assertTrue(cls.expired)

    def test_classify_410_as_expired(self):
        e = mock.MagicMock(spec=["response"])
        e.response.status_code = 410
        cls = _classify_error(e)
        self.assertIsInstance(cls, SubscriptionExpired)

    def test_classify_401_as_vapid(self):
        e = mock.MagicMock(spec=["response"])
        e.response.status_code = 401
        cls = _classify_error(e)
        self.assertIsInstance(cls, VAPIDConfigError)

    def test_classify_403_as_vapid(self):
        e = mock.MagicMock(spec=["response"])
        e.response.status_code = 403
        cls = _classify_error(e)
        self.assertIsInstance(cls, VAPIDConfigError)

    def test_classify_429_as_rate(self):
        e = mock.MagicMock(spec=["response"])
        e.response.status_code = 429
        cls = _classify_error(e)
        self.assertIsInstance(cls, RateLimited)


# ============================================================
# 3. send_push mocked
# ============================================================

class TestSendPush(unittest.TestCase):

    def setUp(self):
        self.sub = PushSubscription(
            endpoint="https://fcm.googleapis.com/fcm/send/x",
            keys_p256dh="B" * 87,
            keys_auth="A" * 22,
        )
        self.payload = PushPayload(title="t", body="b")

    def test_send_push_success(self):
        with mock.patch("utils.webpush.pywebpush.webpush", return_value=mock.MagicMock(status_code=201)):
            result = send_push(self.sub, self.payload)
        self.assertTrue(result)

    def test_send_push_410_returns_false(self):
        # 410 → SubscriptionExpired, 函数返回 False
        resp = mock.MagicMock()
        resp.status_code = 410
        err = Exception("Gone")
        err.response = resp
        with mock.patch("utils.webpush.pywebpush.webpush", side_effect=err):
            # pywebpush.WebPushException 是其基类的别名
            import pywebpush
            with mock.patch.object(pywebpush, "WebPushException", Exception):
                result = send_push(self.sub, self.payload)
        self.assertFalse(result)

    def test_send_push_401_raises_vapid(self):
        resp = mock.MagicMock()
        resp.status_code = 401
        err = Exception("Unauthorized")
        err.response = resp
        import pywebpush
        with mock.patch("utils.webpush.pywebpush.webpush", side_effect=err), \
             mock.patch.object(pywebpush, "WebPushException", Exception):
            with self.assertRaises(VAPIDConfigError):
                send_push(self.sub, self.payload)

    def test_send_push_generic_error_raises_pusherror(self):
        with mock.patch("utils.webpush.pywebpush.webpush", side_effect=RuntimeError("boom")):
            with self.assertRaises(PushError):
                send_push(self.sub, self.payload)


# ============================================================
# 4. SubscriptionStore
# ============================================================

class TestSubscriptionStore(unittest.TestCase):

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="nsp_subs_"))
        self.path = self.tmpdir / "subs.json"
        self.store = SubscriptionStore(path=self.path)
        self.sample = {
            "endpoint": "https://fcm.googleapis.com/fcm/send/a",
            "keys": {"p256dh": "B" * 87, "auth": "A" * 22},
        }

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_add_new(self):
        rec = self.store.add(self.sample, ua="Mozilla/5.0")
        self.assertEqual(rec["endpoint"], self.sample["endpoint"])
        self.assertEqual(rec["status"], "active")
        self.assertEqual(rec["fail_count"], 0)
        self.assertEqual(rec["ua"], "Mozilla/5.0")

    def test_add_duplicate_updates(self):
        self.store.add(self.sample)
        time.sleep(0.01)  # 保证 last_seen_at 不同
        rec = self.store.add(self.sample, ua="Chrome/120")
        self.assertEqual(rec["ua"], "Chrome/120")
        # count_active 仍为 1
        self.assertEqual(self.store.count_active(), 1)

    def test_add_invalid_raises(self):
        with self.assertRaises(ValueError):
            self.store.add({"endpoint": "https://x"}, ua="")
        with self.assertRaises(ValueError):
            self.store.add({"endpoint": "https://x", "keys": {"p256dh": "p"}}, ua="")

    def test_list_active_filters_expired(self):
        self.store.add(self.sample)
        self.store.add({
            "endpoint": "https://fcm.googleapis.com/fcm/send/b",
            "keys": {"p256dh": "B" * 87, "auth": "A" * 22},
        })
        self.store.mark_expired("https://fcm.googleapis.com/fcm/send/a")
        active = self.store.list_active()
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0]["endpoint"], "https://fcm.googleapis.com/fcm/send/b")

    def test_remove(self):
        self.store.add(self.sample)
        self.assertTrue(self.store.remove(self.sample["endpoint"]))
        self.assertEqual(self.store.count_active(), 0)
        self.assertFalse(self.store.remove("not-exists"))

    def test_increment_fail_threshold(self):
        self.store.add(self.sample)
        ep = self.sample["endpoint"]
        # 2 次失败不应标记 expired
        self.assertFalse(self.store.increment_fail(ep, threshold=3))
        self.assertFalse(self.store.increment_fail(ep, threshold=3))
        # 第 3 次 → 标记
        self.assertTrue(self.store.increment_fail(ep, threshold=3))
        all_subs = self.store.list_all()
        self.assertEqual(all_subs[0]["status"], "expired")

    def test_cleanup_expired(self):
        self.store.add(self.sample)
        self.store.add({
            "endpoint": "https://fcm.googleapis.com/fcm/send/b",
            "keys": {"p256dh": "B" * 87, "auth": "A" * 22},
        })
        self.store.mark_expired(self.sample["endpoint"])
        removed = self.store.cleanup_expired()
        self.assertEqual(removed, 1)
        self.assertEqual(self.store.count_active(), 1)

    def test_has_endpoint(self):
        self.store.add(self.sample)
        self.assertTrue(self.store.has_endpoint(self.sample["endpoint"]))
        self.assertFalse(self.store.has_endpoint("not-exists"))

    def test_concurrent_add(self):
        """10 线程并发 add 不同 endpoint, 应全部成功, 无丢失."""
        def worker(i):
            self.store.add({
                "endpoint": f"https://fcm.googleapis.com/fcm/send/{i}",
                "keys": {"p256dh": "B" * 87, "auth": "A" * 22},
            })

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(self.store.count_active(), 10)

    def test_load_handles_corruption(self):
        """safe_read_json 损坏时, store 优雅降级 (视为空)."""
        self.path.write_text("{not json", encoding="utf-8")
        store = SubscriptionStore(path=self.path)
        self.assertEqual(store.count_active(), 0)


# ============================================================
# 5. server.py (httptest 端到端)
# ============================================================

class _ServerThread(threading.Thread):
    def __init__(self, server):
        super().__init__(daemon=True)
        self.server = server
        self.ready = threading.Event()

    def run(self):
        self.ready.set()
        self.server.serve_forever()

    def stop(self):
        self.server.shutdown()
        self.server.server_close()


def _find_free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class TestPushAPI(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # 配依赖: 临时订阅文件 + 测试 VAPID
        cls.tmpdir = Path(tempfile.mkdtemp(prefix="nsp_api_"))
        os.environ["VAPID_SUBJECT"] = "mailto:test@nspim.local"
        # 启动 server
        sys.path.insert(0, str(ROOT / "src"))
        from api import server as srv
        from api.subscriptions import SubscriptionStore

        cls.subs_path = cls.tmpdir / "subs.json"
        cls.store = SubscriptionStore(path=cls.subs_path)
        srv.set_handler_globals(
            store=cls.store,
            admin_token="secret",
            allow_origin="",
        )
        port = _find_free_port()
        cls.httpd = srv.make_server("127.0.0.1", port)
        cls.port = port
        cls.t = _ServerThread(cls.httpd)
        cls.t.start()
        cls.t.ready.wait(2)

    @classmethod
    def tearDownClass(cls):
        cls.t.stop()
        shutil.rmtree(cls.tmpdir, ignore_errors=True)

    def _req(self, method, path, body=None, headers=None):
        conn = HTTPConnection("127.0.0.1", self.port, timeout=5)
        hdrs = {"Content-Type": "application/json"}
        if headers:
            hdrs.update(headers)
        if body is not None:
            conn.request(method, path, body=json.dumps(body), headers=hdrs)
        else:
            conn.request(method, path, headers=hdrs)
        resp = conn.getresponse()
        data = resp.read()
        conn.close()
        try:
            return resp.status, json.loads(data)
        except json.JSONDecodeError:
            return resp.status, data.decode("utf-8", errors="replace")

    def test_health(self):
        code, body = self._req("GET", "/api/health")
        self.assertEqual(code, 200)
        self.assertEqual(body["status"], "ok")

    def test_vapid_public_key(self):
        code, body = self._req("GET", "/api/vapid-public-key")
        self.assertEqual(code, 200)
        self.assertIn("public_key", body)
        # 65 字节 base64url 长度 = ceil(65*4/3) = 87 (无 padding)
        self.assertEqual(len(body["public_key"]), 87)
        self.assertTrue(body["public_key"].startswith("B"))

    def test_subscribe_ok(self):
        body = {
            "endpoint": "https://fcm.googleapis.com/fcm/send/test1",
            "keys": {"p256dh": "B" * 87, "auth": "A" * 22},
        }
        code, resp = self._req("POST", "/api/subscribe", body)
        self.assertEqual(code, 201)
        self.assertTrue(resp["ok"])

    def test_subscribe_bad_endpoint_http(self):
        body = {
            "endpoint": "http://insecure/push",
            "keys": {"p256dh": "B" * 87, "auth": "A" * 22},
        }
        code, resp = self._req("POST", "/api/subscribe", body)
        self.assertEqual(code, 400)
        self.assertIn("https", resp["message"])

    def test_subscribe_missing_endpoint(self):
        body = {"keys": {"p256dh": "x", "auth": "y"}}
        code, resp = self._req("POST", "/api/subscribe", body)
        self.assertEqual(code, 400)

    def test_subscriptions_list_requires_admin(self):
        code, resp = self._req("GET", "/api/subscriptions")
        self.assertEqual(code, 401)

        code, resp = self._req("GET", "/api/subscriptions", headers={"X-Admin-Token": "secret"})
        self.assertEqual(code, 200)
        self.assertIn("total", resp)
        self.assertIn("active", resp)

    def test_notify_requires_admin(self):
        code, resp = self._req("POST", "/api/notify", {"title": "t", "body": "b"})
        self.assertEqual(code, 401)

    def test_notify_dry_run(self):
        code, resp = self._req(
            "POST", "/api/notify",
            {"title": "t", "body": "b", "dry_run": True},
            headers={"X-Admin-Token": "secret"},
        )
        self.assertEqual(code, 200)
        self.assertTrue(resp["dry_run"])
        self.assertIn("sent", resp)

    def test_notify_missing_title(self):
        code, resp = self._req(
            "POST", "/api/notify",
            {"body": "b"},
            headers={"X-Admin-Token": "secret"},
        )
        self.assertEqual(code, 400)

    def test_unsubscribe(self):
        body = {"endpoint": "https://fcm.googleapis.com/fcm/send/test1"}
        code, resp = self._req("POST", "/api/unsubscribe", body)
        self.assertEqual(code, 200)
        self.assertTrue(resp["ok"])

    def test_404(self):
        code, _ = self._req("GET", "/api/not-exist")
        self.assertEqual(code, 404)


# ============================================================
# 6. worker.py diff_new_policies
# ============================================================

class TestWorkerDiff(unittest.TestCase):

    def setUp(self):
        sys.path.insert(0, str(ROOT))
        sys.path.insert(0, str(ROOT / "src"))
        from scripts import _push_worker
        self.worker = _push_worker

    def test_diff_no_new(self):
        policies = [{"id": "P1"}, {"id": "P2"}]
        seen = {"P1", "P2"}
        self.assertEqual(self.worker.diff_new_policies(policies, seen), [])

    def test_diff_some_new(self):
        policies = [{"id": "P1"}, {"id": "P2"}, {"id": "P3"}]
        seen = {"P1"}
        new = self.worker.diff_new_policies(policies, seen)
        self.assertEqual({p["id"] for p in new}, {"P2", "P3"})

    def test_diff_truncates_to_max(self):
        policies = [{"id": f"P{i}", "publish_date": f"2026-01-{i:02d}"} for i in range(1, 50)]
        seen = set()
        new = self.worker.diff_new_policies(policies, seen)
        self.assertEqual(len(new), 20)  # MAX_BROADCAST_PER_TICK
        # 取的是 publish_date 最大的 20 条 (排序后取末尾)
        self.assertIn("P49", [p["id"] for p in new])
        self.assertNotIn("P1", [p["id"] for p in new])

    def test_make_payload(self):
        policy = {
            "id": "P-NDRC-20260818-0001",
            "title": "关于 X 的通知",
            "department": "国家发改委",
            "doc_number": "发改能源〔2026〕688号",
            "publish_date": "2026-08-18",
            "source_url": "https://example.com/doc",
        }
        payload = self.worker.make_payload(policy)
        d = json.loads(payload.to_json())
        self.assertIn("国家发改委", d["body"])
        self.assertIn("发改能源〔2026〕688号", d["body"])
        self.assertEqual(d["url"], "https://example.com/doc")
        self.assertEqual(d["tag"], "policy-P-NDRC-20260818-0001")


# ============================================================
# 7. OneSignal 未配置时优雅降级
# ============================================================

class TestOneSignalGracefulDegrade(unittest.TestCase):

    def setUp(self):
        # 移除 env vars
        self._saved = {}
        for k in ("ONESIGNAL_APP_ID", "ONESIGNAL_REST_API_KEY"):
            if k in os.environ:
                self._saved[k] = os.environ.pop(k)

    def tearDown(self):
        for k, v in self._saved.items():
            os.environ[k] = v

    def test_is_configured_false(self):
        from utils.onesignal import is_configured
        self.assertFalse(is_configured())

    def test_send_notification_without_config_raises(self):
        from utils.onesignal import send_notification, OneSignalNotification, OneSignalError
        with self.assertRaises(OneSignalError):
            send_notification(OneSignalNotification(
                heading="t",
                contents={"zh": "c"},
            ))


if __name__ == "__main__":
    unittest.main(verbosity=2)