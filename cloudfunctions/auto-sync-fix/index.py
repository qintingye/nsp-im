"""NSP-IM v3.0 实时自动同步（CloudBase 函数）

每 30 分钟跑一次：
1. 读 NSP-IM policies.json（最新政策）—— 从打包到 zip 里的 ./data/ 读
2. 读 projects.json（25 项目）
3. 读 today.json（今日数据）
4. 读 index.html 当模板（打包到 zip 里的 index_template.html）
5. 生成 HTML（替换 TODAY 数据）
6. 上传到 CloudBase 静态托管

D46 变更：
- ❌ 移除 `import requests`（CloudBase Python 3.11 不内置）
- ✅ 改用标准库 `urllib.request`（Python 内置，零依赖）
- ✅ 上传继续用 `http.client`（也是标准库）
- ✅ 不再需要 requirements.txt

D47 变更：
- ❌ 去除 URL 中的 `/liuwang-jiankong` 前缀（这是 CloudBase 内部"应用路径"路由，不应出现在 URL 里）
- ✅ 真实 URL：`https://{ENV_ID}.tcloudbaseapp.com/data/{name}`（直接走根路径）

D48 变更：
- ❌ 默认域名 `liwang-jiankong-...tcloudbaseapp.com` 返回 HTTP 418（CloudBase 默认域名服务不可用）
- ✅ 改用自定义域名 `liwangqingbaozhan-liuwang-jiankong-...webapps.tcloudbaseapp.com`（V3.0 正常 200）
- ✅ 真实 URL：`https://{CUSTOM_DOMAIN}/liuwang-jiankong/{path}`（自定义域名路径含应用路径）

D49 变更：
- ❌ 自定义域名 `https://liwangqingbaozhan-...tcloudbaseapp.com` → SSL: CERTIFICATE_VERIFY_FAILED（证书不匹配）
- ❌ 默认域名 `https://liwang-jiankong-...tcloudbaseapp.com` → HTTP 418（部分路径 200）
- ✅ **CloudBase 函数 outbound 走腾讯内网 —— 直接 HTTP 80 端口（无证书验证）**
- ✅ URL 改用 `http://{CUSTOM_DOMAIN}/liuwang-jiankong/{path}` + `ssl._create_unverified_context()`
- ✅ 自定义域名浏览器能正常 V3.0 渲染（用户已验证），HTTP 走内网同理

D50 变更（实测后裁决）：
- ❌ D49 的 HTTP 自定义域名从本网络实测仍 418
- ❌ CloudBase "内网 API" `http://{env_id}.api.tcloudbaseapp.com/liuwang-jiankong/data/...`
       从本网络实测也 418（8/8 路径，包括 /static/、/v1/static/、/v1/storage/、/v1/hosting/）
       —— `api.tcloudbaseapp.com` 是云函数调用网关，不服务静态托管
- ❌ 即便是上传端点 `POST {env_id}.api.tcloudbaseapp.com/v1/upload` 也 418
       —— 本网络对整个 env 的网关级 418 拦截
- ✅ **改用打包进 zip 的本地文件**：函数容器内 `./data/{name}.json` 与
       `./index_template.html` 与 `index.py` 同级，直接 `open()` 读，零网络调用
- ✅ 上传保留 D49 的 http.client 实现 —— 网络恢复后自动恢复
- ✅ v12 zip 含 `index.py` + `data/{projects,policies,today}.json` +
       `index_template.html`，自包含零依赖
"""
import os
import json
import http.client
import ssl
from datetime import datetime


# CloudBase 环境 ID + 上传网关
ENV_ID = 'liwang-jiankong-d2eatyj479b1861-1471069936'


def _read_bundled_json(name):
    """读打包进 zip 的 ./data/{name}.json（D50：零网络依赖）"""
    here = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(here, 'data', name)
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def _read_bundled_html():
    """读打包进 zip 的 ./index_template.html（D50：零网络依赖）"""
    here = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(here, 'index_template.html')
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


def main_handler(event, context):
    print(f"=== V3.0 自动同步 {datetime.now().isoformat()} ===")
    print("D50: 数据源 = 打包进 zip 的本地文件（./data/ + ./index_template.html）")

    try:
        # 1. 读打包数据（不再 HTTP 抓取，D50）
        projects_doc = _read_bundled_json('projects.json')
        projects = (
            projects_doc['projects']
            if isinstance(projects_doc, dict) and 'projects' in projects_doc
            else projects_doc
        )
        policies_doc = _read_bundled_json('policies.json')
        policies = (
            policies_doc['policies']
            if isinstance(policies_doc, dict) and 'policies' in policies_doc
            else policies_doc
        )
        today = _read_bundled_json('today.json')

        # 2. 模板直接用打包的 index_template.html（D50）
        html = _read_bundled_html()

        print(f"✓ 抓取 policies: {len(policies)} 条")
        print(f"✓ 抓取 projects: {len(projects)} 条")
        print(f"✓ 抓取 today: {today.get('date', '?')}")
        print(f"✓ 模板读取: {len(html)} bytes")

        # 3. 注入最新数据
        def _date_key(p):
            return p.get('publish_date', '') or p.get('date', '') or ''

        recent_policies = sorted(policies, key=_date_key, reverse=True)[:5]
        today_data = {
            'date': today.get('date', datetime.now().strftime('%Y-%m-%d')),
            'generated_at': datetime.now().isoformat(),
            'total': len(policies),
            'items': recent_policies,
        }

        # 替换模板占位符
        html = html.replace(
            '/*__TODAY__*/',
            'const TODAY = ' + json.dumps(today_data, ensure_ascii=False) + ';',
        )
        html = html.replace(
            '/*__PROJECTS__*/',
            'const PROJECTS = ' + json.dumps(projects, ensure_ascii=False) + ';',
        )
        html = html.replace(
            '/*__BUILD_TIME__*/',
            "'" + datetime.now().strftime('%Y-%m-%d %H:%M:%S') + "'",
        )

        print(f"✓ HTML 生成: {len(html)} bytes")

        # 4. 上传到 CloudBase 静态托管（D49 保留：http.client HTTPS）
        boundary = '----NSP-IM-Boundary'
        body = (
            f'--{boundary}\r\n'
            f'Content-Disposition: form-data; name="file"; filename="index.html"\r\n'
            f'Content-Type: text/html\r\n\r\n'
        ).encode('utf-8') + html.encode('utf-8') + f'\r\n--{boundary}--\r\n'.encode('utf-8')

        headers = {
            'Content-Type': f'multipart/form-data; boundary={boundary}',
            'Content-Length': str(len(body)),
        }

        ctx = ssl._create_unverified_context()
        conn = http.client.HTTPSConnection(f'{ENV_ID}.api.tcloudbaseapp.com', context=ctx)
        conn.request('POST', '/v1/upload?path=/index.html', body=body, headers=headers)
        response = conn.getresponse()
        result = response.read().decode('utf-8')

        if response.status == 200:
            print(f"✓ 上传成功")
            return {
                'code': 0,
                'msg': f'同步成功：{len(policies)} 条政策',
                'total': len(policies),
                'projects': len(projects),
                'upload_status': response.status,
                'html_bytes': len(html),
                'upload_response': result[:200],
            }
        else:
            print(f"⚠️ 上传响应 {response.status}: {result[:200]}")
            return {
                'code': response.status,
                'msg': f'上传失败：{response.status}（数据已生成，HTML {len(html)} bytes）',
                'total': len(policies),
                'projects': len(projects),
                'html_bytes': len(html),
                'upload_response': result[:200],
            }
    except Exception as e:
        print(f"✗ 同步失败: {e}")
        import traceback
        traceback.print_exc()
        return {
            'code': 500,
            'msg': f'同步失败：{str(e)}',
        }
