"""NSP-IM v3.0 实时自动同步（CloudBase 函数）
每 30 分钟跑一次：
1. 读 NSP-IM policies.json（最新政策）
2. 读 projects.json（25 项目）
3. 生成 HTML（替换 TODAY 数据）
4. 上传到 CloudBase 静态托管
"""
import os
import json
from datetime import datetime


def main_handler(event, context):
    print(f"=== V3.0 自动同步 {datetime.now().isoformat()} ===")

    try:
        # 1. 读数据
        with open('/tmp/data/projects.json', 'r', encoding='utf-8') as f:
            projects = json.load(f)
        with open('/tmp/data/policies.json', 'r', encoding='utf-8') as f:
            policies_doc = json.load(f)
        # policies.json 是 { version, generated_at, policies: [...] } 结构
        policies = policies_doc['policies'] if isinstance(policies_doc, dict) and 'policies' in policies_doc else policies_doc
        with open('/tmp/data/today.json', 'r', encoding='utf-8') as f:
            today = json.load(f)
        with open('/tmp/index_template.html', 'r', encoding='utf-8') as f:
            html = f.read()

        # 2. 注入最新数据
        # 取最新 5 条政策（兼容多种字段名）
        def _date_key(p):
            return p.get('publish_date', '') or p.get('date', '') or ''
        recent_policies = sorted(policies, key=_date_key, reverse=True)[:5]
        today_data = {
            'date': today.get('date', datetime.now().strftime('%Y-%m-%d')),
            'generated_at': datetime.now().isoformat(),
            'total': len(policies),
            'items': recent_policies
        }

        # 替换模板占位符
        html = html.replace('/*__TODAY__*/',
                            'const TODAY = ' + json.dumps(today_data, ensure_ascii=False) + ';')
        html = html.replace('/*__PROJECTS__*/',
                            'const PROJECTS = ' + json.dumps(projects, ensure_ascii=False) + ';')
        html = html.replace('/*__BUILD_TIME__*/',
                            "'" + datetime.now().strftime('%Y-%m-%d %H:%M:%S') + "'")

        # 3. 上传到 CloudBase 静态托管
        from cloudbase import CloudBase
        cb = CloudBase({'env': 'liuwang-jiankong-d2eatyj479b1861-1471069936'})
        result = cb.static_hosting.upload_file(
            cloud_path='/index.html',
            content=html.encode('utf-8'),
            content_type='text/html'
        )

        print(f"✓ 上传成功: {len(policies)} 条政策, HTML={len(html)} bytes")
        return {
            'code': 0,
            'msg': f'同步成功：{len(policies)} 条政策',
            'total': len(policies)
        }
    except Exception as e:
        print(f"✗ 同步失败: {e}")
        return {
            'code': 500,
            'msg': f'同步失败：{str(e)}'
        }
