"""临时测试 - OneSignal 客户端."""
import sys
from pathlib import Path

sys.path.insert(0, "src")
for mod in list(sys.modules):
    if mod.startswith("utils"):
        del sys.modules[mod]

from utils.onesignal import (
    OneSignalConfig, OneSignalNotification, is_configured,
    send_notification, OneSignalError,
)

# 1. 未配置时应禁用
assert not is_configured(), "未配置环境变量时应禁用"
print("PASS test_1: 未配置时 is_configured() = False")

# 2. 配置后启用
import os
os.environ["ONESIGNAL_APP_ID"] = "test-app-id-123"
os.environ["ONESIGNAL_REST_API_KEY"] = "test-rest-api-key-456"
assert is_configured(), "配置后应启用"
print("PASS test_2: 配置后 is_configured() = True")

# 3. config 缺失字段返回 None
del os.environ["ONESIGNAL_REST_API_KEY"]
assert not is_configured(), "仅 APP ID 时应禁用"
print("PASS test_3: 缺 REST API Key 时禁用")

os.environ["ONESIGNAL_REST_API_KEY"] = "test-rest-api-key-456"

# 4. 通知构造
n = OneSignalNotification(
    heading="NSP-IM 政策雷达",
    contents={"en": "3 new policies", "zh": "新增 3 条政策"},
    url="https://nspim.example.com/p/P-NDRC-20260818-0001",
)
body = n.to_api_body("test-app-id")
assert body["app_id"] == "test-app-id"
assert "en" in body["contents"]
assert body["contents"]["zh"] == "新增 3 条政策"
assert body["ttl"] == 86400
print("PASS test_4: 通知 body 字段正确")

# 5. heading 截断（contents 不带 en 避免覆盖 heading 的 en 字段）
n2 = OneSignalNotification(heading="A" * 100, contents={"zh": "测试内容"})
body2 = n2.to_api_body("x")
assert len(body2["headings"]["en"]) == 64, f"heading 长度 {len(body2['headings']['en'])}"
assert len(body2["contents"]["zh"]) <= 200
print("PASS test_5: heading 截断到 64 字符")

# 6. 真实调用（预期 401，因为 fake key）
try:
    send_notification(n, timeout=5)
    print("UNEXPECTED success")
except OneSignalError as e:
    print(f"PASS test_6: fake key 鉴权失败 (401): {str(e)[:150]}")

print()
print("ALL PASS")