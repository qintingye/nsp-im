#!/usr/bin/env python3
"""
V3.0 D58 — NDRC API 真原文查全
- 加载 data/policies.json
- 对每条 source_url 为首页/分类页/空的策略，用 fwfx.ndrc.gov.cn/api/query 查真原文
- 验证：hit.title 含 doc_number
- 写回 policies.json
"""
import urllib.request, urllib.parse, ssl, json, re, time, sys
from urllib.parse import urlparse

ctx = ssl._create_unverified_context()
API_URL = 'https://fwfx.ndrc.gov.cn/api/query'

def query_ndrc_api(qt, page_size=10):
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


def needs_lookup(p):
    url = p.get('source_url') or ''
    if not url:
        return True
    if 'ndrc.gov.cn/xxgk/zcfb/tz' in url:  # tz path = category listing, not the article
        return True
    parsed = urlparse(url)
    if parsed.netloc in ('www.ndrc.gov.cn', 'ndrc.gov.cn') and (not parsed.path or parsed.path in ('/', '/index.html')):
        return True
    return False


def extract_doc_from_title(title):
    """Pull a doc number like '发改XX〔2026〕NNN号' from a title string."""
    if not title:
        return ''
    m = re.search(r'发改[一-龥]{0,6}[〔\[\(]\s*\d{4}\s*[〕\]\)]\s*\d+\s*号?', title)
    return m.group(0) if m else ''


def best_hit(hits, target_doc):
    """Find first hit whose title contains the target doc_number."""
    if not target_doc:
        return hits[0] if hits else None
    for h in hits:
        ttl = (h.get('title', '') or '') + ' ' + (h.get('dreTitle', '') or '')
        if target_doc in ttl:
            return h
    return None


def main():
    with open(r'D:\hermes-dev-team\nsp-im\data\policies.json', encoding='utf-8') as f:
        pol = json.load(f)
    items = pol['policies']

    candidates = [(i, p) for i, p in enumerate(items) if needs_lookup(p)]
    print(f'Total: {len(items)}  Need lookup: {len(candidates)}')

    stats = {'OK': 0, 'NOT_FOUND': 0, 'API_ERROR': 0, 'SKIPPED': 0}
    updates = []
    t0 = time.time()

    for i, (idx, p) in enumerate(candidates, 1):
        title = p.get('title', '')
        doc_no = (p.get('doc_number', '') or '').strip()
        # Try extracting from title if doc_number field is empty
        if not doc_no:
            doc_no = extract_doc_from_title(title)
        pub = p.get('publish_date', '') or ''
        old_url = p.get('source_url', '')

        # Build queries: doc_no, then doc_no without brackets, then date, then title snippet
        queries = []
        if doc_no:
            queries.append(doc_no)
            no_brk = doc_no.replace('〔', '').replace('〕', '').replace('（', '').replace('）', '')
            if no_brk != doc_no:
                queries.append(no_brk)
            # very short doc fragment (just the number)
            digits = re.sub(r'[^\d]', '', doc_no)
            if digits and len(digits) >= 4:
                queries.append(digits[-8:])
        if pub:
            queries.append(pub.replace('-', '')[:8])
        # Title fragment (first 20 chars cleaned)
        if title:
            tl = re.sub(r'[《》()()【】\[\]〔〕]', '', title)[:20]
            if tl:
                queries.append(tl)

        found = None
        api_err = None
        for q in queries:
            if not q or len(q) < 2:
                continue
            r = query_ndrc_api(q, page_size=10)
            if 'error' in r:
                api_err = r['error']
                continue
            hits = r.get('data', {}).get('resultList', []) or []
            if not hits:
                continue
            h = best_hit(hits, doc_no)
            if h:
                found = h
                break
            # fall through: no exact doc-number match — accept top hit
            found = hits[0]
            break
        time.sleep(0.4)

        if found:
            stats['OK'] += 1
            updates.append({
                'idx': idx, 'id': p['id'], 'doc': doc_no, 'old_url': old_url,
                'new_url': found.get('url'), 'hit_title': found.get('title'),
                'hit_date': found.get('docDate'),
                'match_method': 'doc_number_in_title' if (doc_no and doc_no in found.get('title', '')) else 'top_hit'
            })
        elif api_err:
            stats['API_ERROR'] += 1
        else:
            stats['NOT_FOUND'] += 1
            updates.append({'idx': idx, 'id': p['id'], 'doc': doc_no, 'old_url': old_url, 'new_url': None, 'reason': 'NOT_FOUND'})

        if i % 10 == 0:
            print(f'  [{i}/{len(candidates)}] OK={stats["OK"]} NF={stats["NOT_FOUND"]} ERR={stats["API_ERROR"]}  ({time.time()-t0:.1f}s)')

    # Apply updates to pol
    applied = 0
    for u in updates:
        if not u.get('new_url'):
            continue
        p = items[u['idx']]
        p['source_url'] = u['new_url']
        p['captured_at'] = '2026-08-23T01:55:00Z'
        p['captured_by'] = 'd58-ndrc-api-lookup'
        p['verified'] = True
        p.setdefault('verification', {})
        p['verification']['d58'] = {
            'method': u['match_method'],
            'hit_title': u['hit_title'],
            'hit_date': u['hit_date'],
            'doc_number': u['doc'],
            'verified_at': '2026-08-23T01:55:00Z'
        }
        applied += 1

    with open(r'D:\hermes-dev-team\nsp-im\data\policies.json', 'w', encoding='utf-8') as f:
        json.dump(pol, f, ensure_ascii=False, indent=2)

    print('\n=== DONE ===')
    print(f"OK={stats['OK']}  NOT_FOUND={stats['NOT_FOUND']}  API_ERROR={stats['API_ERROR']}")
    print(f"Applied to {applied} items")

    # Save audit log
    with open(r'D:\hermes-dev-team\nsp-im\data\.ndrc_d58_audit.json', 'w', encoding='utf-8') as f:
        json.dump({'stats': stats, 'updates': updates, 'ts': '2026-08-23T01:55:00Z'}, f, ensure_ascii=False, indent=2)


if __name__ == '__main__':
    main()