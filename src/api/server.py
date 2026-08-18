"""
NSP-IM Push HTTP API (W3-D3 BE)
=================================

极简 HTTP 服务器, 4 个 endpoints:
    GET  /api/vapid-public-key   返回 VAPID 公钥 (前端订阅用)
    POST /api/subscribe          接收前端 PushSubscription 落盘
    POST /api/unsubscribe        退订 (按 endpoint)
    POST /api/notify             触发批量推送 (admin only, 简单 token 校验)

为什么用 stdlib http.server:
    - 依赖最少 (不引入 Flask/FastAPI 部署负担)
    - 单进程够用 (内网 25 人内测量级 < 1000 订阅)
    - 启动快, 测试覆盖简单 (不依赖 ASGI 测试客户端)

生产路径:
    - 部署到任意 host (systemd / docker / vercel-serverless 不适合长连接但 ok)
    - 后续可替换实现 (FastAPI), endpoint 契约不变 (前端的 /api/* 调用零改动)

安全:
    - 默认监听 127.0.0.1:8081 (内网/反向代理后)
    - /api/notify 需要 X-Admin-Token (与 ADMIN_TOKEN 环境变量比对)
    - 订阅 endpoint 必须 https:// 开头 (Web Push 规范强制)
    - 跨域: 默认仅同源, 通过 ALLOW_ORIGIN 环境变量可放开 CORS

运行:
    cd src && python -m api.server
    或: python -m api.server --host 0.0.0.0 --port 8081
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Optional

# 路径锚定: src/api/server.py → parents[0]=src/api, parents[1]=src, parents[2]=nsp-im
_THIS = Path(__file__).resolve()
REPO_ROOT = _THIS.parents[2]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from utils.vapid import get_or_create_vapid_keys  # noqa: E402
from utils.webpush import (  # noqa: E402
    PushSubscription,
    PushPayload,
    SubscriptionExpired,
    VAPIDConfigError,
    send_push,
)
from api.subscriptions import SubscriptionStore, get_default_store  # noqa: E402

LOG = logging.getLogger("nspim.push.server")

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8081


# ---------------- 请求处理 ----------------

class PushAPIHandler(BaseHTTPRequestHandler):
    """路由分发. server 启动时通过 set_handler_globals 注入 store/admin_token."""

    server_version = "NSP-IM-PushAPI/1.0"

    # 由 set_handler_globals 注入
    store: SubscriptionStore = None  # type: ignore[assignment]
    admin_token: str = ""
    allow_origin: str = ""

    # 抑制默认 access log (我们用 LOG.info 控制)
    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        LOG.debug(format, *args)

    # ---- helpers ----

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        if self.allow_origin:
            self.send_header("Access-Control-Allow-Origin", self.allow_origin)
        self.end_headers()
        self.wfile.write(body)

    def _send_error_json(self, status: int, message: str, **details: Any) -> None:
        payload: dict[str, Any] = {"code": status, "message": message}
        if details:
            payload["details"] = details
        self._send_json(status, payload)

    def _read_json_body(self) -> Optional[dict]:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0:
            return None
        if length > 16 * 1024:  # 16 KiB 上限 (subscription 远小于此)
            raise ValueError(f"请求体过大 ({length} bytes)")
        raw = self.rfile.read(length)
        try:
            data = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as e:
            raise ValueError(f"JSON 解析失败: {e}") from e
        if not isinstance(data, dict):
            raise ValueError("请求体必须是 JSON object")
        return data

    def _check_origin(self) -> bool:
        """简单 CORS / 同源检查."""
        origin = self.headers.get("Origin", "")
        if not self.allow_origin:
            # 默认: 不放 CORS, 同源 OK
            return True
        if origin == self.allow_origin:
            self.send_header("Access-Control-Allow-Origin", self.allow_origin)
            return True
        return False

    # ---- 路由 ----

    def do_OPTIONS(self) -> None:  # noqa: N802
        # CORS preflight (仅在 allow_origin 设置时生效)
        if self.allow_origin:
            self.send_response(HTTPStatus.NO_CONTENT)
            self.send_header("Access-Control-Allow-Origin", self.allow_origin)
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Admin-Token")
            self.send_header("Access-Control-Max-Age", "600")
            self.end_headers()
        else:
            self.send_response(HTTPStatus.NO_CONTENT)
            self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]
        if path == "/api/vapid-public-key":
            self._handle_vapid_public_key()
        elif path == "/api/subscriptions":
            self._handle_subscriptions_list()
        elif path == "/api/health":
            self._handle_health()
        else:
            self._send_error_json(HTTPStatus.NOT_FOUND, f"路径不存在: {path}")

    def do_POST(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]
        if path == "/api/subscribe":
            self._handle_subscribe()
        elif path == "/api/unsubscribe":
            self._handle_unsubscribe()
        elif path == "/api/notify":
            self._handle_notify()
        else:
            self._send_error_json(HTTPStatus.NOT_FOUND, f"路径不存在: {path}")

    # ---- handlers ----

    def _handle_vapid_public_key(self) -> None:
        keys = get_or_create_vapid_keys()
        self._send_json(HTTPStatus.OK, {
            "public_key": keys.public_key_b64url,
            "subject": keys.subject,
        })

    def _handle_subscriptions_list(self) -> None:
        # 需要 admin token (查看订阅总数可能泄漏隐私)
        if not self._check_admin():
            self._send_error_json(HTTPStatus.UNAUTHORIZED, "需要 X-Admin-Token")
            return
        subs = self.store.list_all()
        # 脱敏: 不返回 keys (admin 排查时手动看 data/.subscriptions.json)
        sanitized = [
            {
                "endpoint": s["endpoint"][:80] + ("..." if len(s["endpoint"]) > 80 else ""),
                "status": s.get("status"),
                "fail_count": s.get("fail_count", 0),
                "ua": (s.get("ua") or "")[:64],
                "created_at": s.get("created_at"),
                "last_seen_at": s.get("last_seen_at"),
                "expired_at": s.get("expired_at"),
            }
            for s in subs
        ]
        self._send_json(HTTPStatus.OK, {
            "total": len(subs),
            "active": sum(1 for s in subs if s.get("status") == "active"),
            "expired": sum(1 for s in subs if s.get("status") == "expired"),
            "subscriptions": sanitized,
        })

    def _handle_health(self) -> None:
        self._send_json(HTTPStatus.OK, {
            "status": "ok",
            "service": "nspim-push-api",
            "version": "1.0",
            "subscriptions_active": self.store.count_active(),
        })

    def _handle_subscribe(self) -> None:
        try:
            body = self._read_json_body()
        except ValueError as e:
            self._send_error_json(HTTPStatus.BAD_REQUEST, str(e))
            return
        if not body:
            self._send_error_json(HTTPStatus.BAD_REQUEST, "请求体不能为空")
            return

        # 校验 endpoint
        endpoint = body.get("endpoint", "")
        if not endpoint or not isinstance(endpoint, str):
            self._send_error_json(HTTPStatus.BAD_REQUEST, "endpoint 缺失或类型错误")
            return
        if not endpoint.startswith("https://"):
            self._send_error_json(HTTPStatus.BAD_REQUEST, "endpoint 必须 https:// 开头")
            return
        if "keys" not in body or not isinstance(body["keys"], dict):
            self._send_error_json(HTTPStatus.BAD_REQUEST, "keys 字段缺失")
            return

        try:
            PushSubscription.from_dict(body)
        except (KeyError, ValueError) as e:
            self._send_error_json(HTTPStatus.BAD_REQUEST, f"订阅格式错误: {e}")
            return

        ua = self.headers.get("User-Agent", "")
        record = self.store.add(body, ua=ua)
        self._send_json(HTTPStatus.CREATED, {
            "ok": True,
            "endpoint": record["endpoint"][:80] + ("..." if len(record["endpoint"]) > 80 else ""),
            "created_at": record["created_at"],
        })

    def _handle_unsubscribe(self) -> None:
        try:
            body = self._read_json_body()
        except ValueError as e:
            self._send_error_json(HTTPStatus.BAD_REQUEST, str(e))
            return
        if not body or "endpoint" not in body:
            self._send_error_json(HTTPStatus.BAD_REQUEST, "endpoint 缺失")
            return
        endpoint = body["endpoint"]
        if not isinstance(endpoint, str) or not endpoint.startswith("https://"):
            self._send_error_json(HTTPStatus.BAD_REQUEST, "endpoint 格式错误")
            return
        removed = self.store.remove(endpoint)
        self._send_json(HTTPStatus.OK, {"ok": True, "removed": removed})

    def _handle_notify(self) -> None:
        # 鉴权
        if not self._check_admin():
            self._send_error_json(HTTPStatus.UNAUTHORIZED, "需要 X-Admin-Token")
            return

        try:
            body = self._read_json_body()
        except ValueError as e:
            self._send_error_json(HTTPStatus.BAD_REQUEST, str(e))
            return
        if not body:
            self._send_error_json(HTTPStatus.BAD_REQUEST, "请求体不能为空")
            return

        title = body.get("title")
        message = body.get("body") or body.get("message")
        if not title or not isinstance(title, str):
            self._send_error_json(HTTPStatus.BAD_REQUEST, "title 缺失")
            return
        if not message or not isinstance(message, str):
            self._send_error_json(HTTPStatus.BAD_REQUEST, "body 缺失")
            return

        url = body.get("url")
        tag = body.get("tag", "nspim-notify")
        dry_run = bool(body.get("dry_run", False))

        subs = self.store.list_active()
        if not subs:
            self._send_json(HTTPStatus.OK, {"ok": True, "sent": 0, "expired": 0, "error": 0, "note": "无活跃订阅"})

        success = expired = error = 0
        payload = PushPayload(
            title=title[:64],
            body=message[:200],
            url=url,
            tag=tag,
            require_interaction=False,
            data={"ts": body.get("ts")},
        )

        for record in subs:
            try:
                sub = PushSubscription.from_dict(record)
                if dry_run:
                    success += 1
                    continue
                if send_push(sub, payload):
                    success += 1
                else:
                    expired += 1
                    self.store.mark_expired(sub.endpoint)
            except SubscriptionExpired:
                expired += 1
                self.store.mark_expired(record.get("endpoint", ""))
            except VAPIDConfigError as e:
                LOG.error("VAPID 配置错误, 停止推送: %s", e)
                error += 1
                self._send_json(HTTPStatus.SERVICE_UNAVAILABLE, {
                    "ok": False,
                    "sent": success,
                    "error": error,
                    "error_type": "VAPID_CONFIG_ERROR",
                    "message": "VAPID 凭证配置错误, 请检查 data/.vapid.json 与 VAPID_SUBJECT",
                })
                return
            except Exception as e:  # noqa: BLE001
                LOG.warning("推送失败 endpoint=%s: %s", record.get("endpoint", "")[:60], e)
                self.store.increment_fail(record.get("endpoint", ""))
                error += 1

        LOG.info("批量推送完成 success=%d expired=%d error=%d (dry_run=%s)", success, expired, error, dry_run)
        self._send_json(HTTPStatus.OK, {
            "ok": True,
            "sent": success,
            "expired": expired,
            "error": error,
            "dry_run": dry_run,
        })

    # ---- auth ----

    def _check_admin(self) -> bool:
        if not self.admin_token:
            # 未配置 admin token → 仅信任 localhost
            return self.client_address[0] in ("127.0.0.1", "::1", "localhost")
        token = self.headers.get("X-Admin-Token", "")
        return bool(token) and token == self.admin_token


# ---------------- Server bootstrap ----------------

def set_handler_globals(
    *,
    store: SubscriptionStore,
    admin_token: str,
    allow_origin: str,
) -> None:
    """在 server 启动前注入运行时配置 (避免全局污染)."""
    PushAPIHandler.store = store
    PushAPIHandler.admin_token = admin_token
    PushAPIHandler.allow_origin = allow_origin


def make_server(host: str, port: int) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), PushAPIHandler)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="NSP-IM Push HTTP API")
    parser.add_argument("--host", default=os.environ.get("PUSH_API_HOST", DEFAULT_HOST))
    parser.add_argument("--port", type=int, default=int(os.environ.get("PUSH_API_PORT", DEFAULT_PORT)))
    parser.add_argument(
        "--admin-token",
        default=os.environ.get("ADMIN_TOKEN", ""),
        help="管理员 token (与 X-Admin-Token 头比对); 空则仅 localhost 可调用管理接口",
    )
    parser.add_argument(
        "--allow-origin",
        default=os.environ.get("ALLOW_ORIGIN", ""),
        help="CORS allow-origin (空=同源 only)",
    )
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # 启动时确保 VAPID 密钥就绪
    keys = get_or_create_vapid_keys()
    LOG.info("VAPID 主体: %s", keys.subject)

    store = get_default_store()
    set_handler_globals(
        store=store,
        admin_token=args.admin_token,
        allow_origin=args.allow_origin,
    )

    httpd = make_server(args.host, args.port)
    sa = httpd.socket.getsockname()
    LOG.info("NSP-IM Push API 监听 %s:%d (subs=%d)", sa[0], sa[1], store.count_active())
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        LOG.info("收到 Ctrl-C, 关闭...")
        httpd.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())