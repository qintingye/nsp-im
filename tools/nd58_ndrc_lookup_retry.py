#!/usr/bin/env python3
"""Try harder on the 8 NOT_FOUND — various keyword strategies."""
import urllib.request, urllib.parse, ssl, json, re, time, sys
ctx = ssl._create_unverified_context()
API_URL = 'https://fwfx.ndrc.gov.cn/api/query'

def query_ndrc_api(qt, page_size=20):
    data = urllib.parse.urlencode({
        'siteCode': 'bm04000fgk',
        'key': 'CAB549A94CF659904A7D6B0E8FC8A7E9',
        'qt': qt,
        'pageSize': str(page_size)
    }).encode('utf-8')
    req = urllib.request.Request(API_URL, data=data, headers={
        'Content-Type': 'application/x-www-form-urlencoded',
        'Referer': 'https://fwfx.ndrc.gov.cn/'
    })
    try:
        with urllib.request.urlopen(req, timeout=15, context=ctx) as r:
            return json.loads(r.read().decode('utf-8'))
    except Exception as e:
        return {'error': str(e)}


cases = [
    ('P-NDRC-20260603-0002', '发改农经〔2026〕812号', '城市公共供水管网漏损治理', '2026-06-03'),
    ('P-NDRC-20260618-0003', '发改高技〔2026〕1024号', '5G专网 能源', '2026-06-18'),
    ('P-NDRC-20260705-0004', '发改投资〔2026〕1107号', '城镇燃气管网更新改造', '2026-07-05'),
    ('P-NDRC-20260722-0005', '发改基础〔2026〕1198号', '多式联运高质量', '2026-07-22'),
    ('P-NDRC-20260802-0006', '发改价格〔2026〕1256号', '能源商品价格监测预警', '2026-08-02'),
    ('P-NDRC-20260812-0007', '发改高技〔2026〕1302号', '新型数据中心 算力计量', '2026-08-12'),
    ('P-NDRC-20260818-0001', '发改能源〔2026〕999号', '算电协同 六网融合', '2026-08-18'),
]

for pid, doc, kw, pub in cases:
    print(f'\n=== {pid} (doc={doc}) ===')
    # Try just the doc department
    dept = re.search(r'发改(\S+?)〔', doc).group(1) if '〔' in doc else ''
    queries = [
        doc,                                          # full
        doc.replace('〔', '').replace('〕', ''),       # no brackets
        re.sub(r'[^\d]', '', doc),                    # digits
        re.sub(r'[^\d]', '', doc)[-8:],               # last 8 digits
        kw[:25],                                      # title snippet
        kw[:15],                                      # shorter
        dept,                                         # just dept name
        kw.replace(' ', ''),                          # no-space kw
    ]
    seen = set()
    for q in queries:
        if not q or q in seen or len(q) < 2:
            continue
        seen.add(q)
        r = query_ndrc_api(q, page_size=10)
        n = r.get('data', {}).get('totalHits', 0)
        hits = r.get('data', {}).get('resultList', [])
        ok_match = None
        for h in hits:
            ttl = h.get('title', '') or ''
            if doc in ttl:
                ok_match = h
                break
        if ok_match:
            print(f"  q='{q[:30]}' -> n={n}, EXACT MATCH:")
            print(f"    url: {ok_match.get('url')}")
            print(f"    title: {ok_match.get('title')}")
            break
        elif hits:
            # show top 3 titles
            print(f"  q='{q[:30]}' -> n={n} (no exact match, top hits):")
            for h in hits[:3]:
                print(f"    - {h.get('title', '')[:70]}")
        else:
            print(f"  q='{q[:30]}' -> n=0")
        time.sleep(0.3)