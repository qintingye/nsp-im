"""NSP-IM v3.0 实时自动同步（CloudBase 函数）
每 30 分钟跑一次：
1. HTTP 读 NSP-IM policies.json（最新政策）—— 从 CloudBase 静态托管
2. HTTP 读 projects.json（25 项目）
3. HTTP 读 today.json（今日数据）
4. HTTP 读 index.html 当模板（最新部署版）
5. 生成 HTML（替换 TODAY 数据）
6. 上传到 CloudBase 静态托管
"""
import os
import json
import urllib.request
import http.client
from datetime import datetime


# CloudBase 环境 ID + 静态托管基址
ENV_ID = 'liuwang-jiankong-d2eatyj479b1861-1471069936'
STATIC_BASE = f'https://{ENV_ID}.tcloudbaseapp.com/liuwang-jiankong'


def fetch_url(url, timeout=10):
    """HTTP GET 返回 bytes；失败抛异常。"""
    req = urllib.request.Request(url, headers={'User-Agent': 'nsp-im-trigger/1.0'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def fetch_json(name):
    """从静态托管读 JSON 文件。"""
    url = f'{STATIC_BASE}/data/{name}'
    raw = fetch_url(url)
    return json.loads(raw.decode('utf-8'))


def fetch_text(path):
    """从静态托管读文本（HTML 模板）。"""
    url = f'{STATIC_BASE}{path}'
    raw = fetch_url(url)
    return raw.decode('utf-8')


def main_handler(event, context):
    print(f"=== V3.0 自动同步 {datetime.now().isoformat()} ===")

    try:
        # 1. HTTP 读数据（不再依赖 ./data/，避免云端工作目录无 data/）
        projects_doc = fetch_json('projects.json')
        # projects.json 是 { version, generated_at, projects: [...] } 结构
        projects = (
            projects_doc['projects']
            if isinstance(projects_doc, dict) and 'projects' in projects_doc
            else projects_doc
        )
        policies_doc = fetch_json('policies.json')
        # policies.json 是 { version, generated_at, policies: [...] } 结构
        policies = (
            policies_doc['policies']
            if isinstance(policies_doc, dict) and 'policies' in policies_doc
            else policies_doc
        )
        today = fetch_json('today.json')

        # 2. 模板直接用 index.html（最新部署版，含 V3.0 全部功能）
        html = fetch_text('/index.html')

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

        # 4. 上传到 CloudBase 静态托管（直接调用 HTTP API，不用 cloudbase SDK）
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

        conn = http.client.HTTPSConnection(f'{ENV_ID}.api.tcloudbaseapp.com')
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
                'msg': f'上传失败：{response.status}',
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