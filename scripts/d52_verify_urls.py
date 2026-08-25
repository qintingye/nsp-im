"""D52 — verify every URL in policies.json + projects.json via HTTP, then classify."""
import urllib.request, urllib.error, ssl, json, time
from pathlib import Path
from collections import Counter

ROOT = Path(r'D:/hermes-dev-team/nsp-im')
ctx = ssl._create_unverified_context()
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9',
}

def check(url):
    if not url or not isinstance(url, str):
        return ('EMPTY', '')
    if not (url.startswith('http://') or url.startswith('https://')):
        return ('NOT-URL', url[:60])
    try:
        req = urllib.request.Request(url, headers=HEADERS, method='HEAD')
        try:
            r = urllib.request.urlopen(req, timeout=10, context=ctx)
            return (f'H{r.status}', r.headers.get('Content-Type', ''))
        except urllib.error.HTTPError as he:
            if he.code in (403, 405, 400):
                req2 = urllib.request.Request(url, headers=HEADERS)
                r2 = urllib.request.urlopen(req2, timeout=10, context=ctx)
                return (f'G{r2.status}', r2.headers.get('Content-Type', ''))
            return (f'H{he.code}', '')
    except Exception as e:
        return ('ERR', str(e)[:60])


def collect_urls():
    records = []
    with open(ROOT / 'data' / 'policies.json', encoding='utf-8') as f:
        policies = json.load(f)
    with open(ROOT / 'data' / 'projects.json', encoding='utf-8') as f:
        projects = json.load(f)

    for p in policies['policies']:
        pid = p.get('id', '?')
        title = p.get('title', '')[:30]
        if p.get('source_url'):
            records.append(('policies', 'source_url', pid, title, p['source_url']))
        if p.get('official_document_url') and p.get('official_document_url') != p.get('source_url'):
            records.append(('policies', 'official_document_url', pid, title, p['official_document_url']))
        if p.get('interpretation_source'):
            records.append(('policies', 'interpretation_source', pid, title, p['interpretation_source']))
        bs = p.get('backup_sources') or []
        if isinstance(bs, list):
            for i, b in enumerate(bs):
                if isinstance(b, str):
                    records.append(('policies', f'backup_sources[{i}]', pid, title, b))
                elif isinstance(b, dict) and b.get('url'):
                    records.append(('policies', f'backup_sources[{i}]', pid, title, b['url']))

    for pr in projects['projects']:
        prid = pr.get('id', '?')
        name = pr.get('name', '')[:30]
        if pr.get('source') and isinstance(pr['source'], dict) and pr['source'].get('url'):
            records.append(('projects', 'source.url', prid, name, pr['source']['url']))
        for i, s in enumerate(pr.get('sources') or []):
            if isinstance(s, dict) and s.get('url'):
                records.append(('projects', f'sources[{i}]', prid, name, s['url']))
        for i, u in enumerate(pr.get('updates') or []):
            if isinstance(u, dict) and u.get('source_url'):
                records.append(('projects', f'updates[{i}].source_url', prid, name, u['source_url']))
    return records, policies, projects


def main():
    records, policies, projects = collect_urls()
    print(f'Total URLs to check: {len(records)}')

    results = []
    t0 = time.time()
    for i, rec in enumerate(records):
        file, key, pid, label, url = rec
        status, ctype = check(url)
        results.append((file, key, pid, label, url, status, ctype))
        if (i+1) % 25 == 0:
            print(f'  {i+1}/{len(records)} ({time.time()-t0:.0f}s)')
        time.sleep(0.15)

    out_dir = ROOT / 'logs' / 'd52'
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / 'url_verify_all.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    statuses = Counter(r[5] for r in results)
    print('\n=== STATUS COUNTS ===')
    for s, c in statuses.most_common():
        print(f'  {s}: {c}')

    invalid = [r for r in results if not (r[5].startswith('H2') or r[5].startswith('G2'))]
    print(f'\nInvalid: {len(invalid)} / {len(results)}')
    for r in invalid:
        print(f"  [{r[0]}/{r[1]}] {r[2]} {r[4][:90]}  → {r[5]}")

if __name__ == '__main__':
    main()
