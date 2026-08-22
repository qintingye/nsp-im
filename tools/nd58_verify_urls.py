#!/usr/bin/env python3
"""Verify the 32 newly assigned URLs return HTTP 200 (real article, not 404)."""
import urllib.request, ssl, json, re
ctx = ssl._create_unverified_context()

with open(r'D:\hermes-dev-team\nsp-im\data\.ndrc_d58_audit.json', encoding='utf-8') as f:
    audit = json.load(f)

new_urls = [(u['id'], u['new_url']) for u in audit['updates'] if u.get('new_url')]
print(f'Verifying {len(new_urls)} URLs ...')

ok = 0
fail = []
for pid, url in new_urls:
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=15, context=ctx) as r:
            code = r.getcode()
            body = r.read(2000).decode('utf-8', errors='ignore')
            title_match = re.search(r'<title>([^<]+)</title>', body)
            title = title_match.group(1) if title_match else '(no title)'
            # Reject 404 pages even if HTTP returns 200
            if '404' in body[:2000] or '页面不存在' in body or '未找到' in body:
                fail.append((pid, url, '404 in body'))
            elif code == 200:
                ok += 1
            else:
                fail.append((pid, url, f'HTTP {code}'))
    except Exception as e:
        fail.append((pid, url, f'EXC: {e}'))

print(f'OK: {ok}/{len(new_urls)}')
if fail:
    print('Failed:')
    for pid, url, reason in fail:
        print(f"  [{reason}] {pid}: {url}")
else:
    print('All URLs verified!')