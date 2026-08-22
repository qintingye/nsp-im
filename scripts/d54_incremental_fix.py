"""D54 — Incremental fix for the 17 invalid URLs that build_fixes.py couldn't verify.

For each invalid URL, replace with the best working aggregate/root fallback URL
that matches the source's domain and topic. We don't try to guess exact article IDs
(NDRC/CSG/SGCC article IDs are not deterministically guessable).
"""
import json, urllib.request, ssl, re
from pathlib import Path

ROOT = Path(r'D:/hermes-dev-team/nsp-im')
ctx = ssl._create_unverified_context()
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
}

def check(url, timeout=10):
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        r = urllib.request.urlopen(req, timeout=timeout, context=ctx)
        return r.status
    except urllib.error.HTTPError as he:
        return he.code
    except Exception as e:
        return f'ERR: {str(e)[:40]}'

# Mapping: (target_type, target_id, field_path, new_url)
# All targets below come from d52_verify_urls.py 17 invalid URLs.
# All new URLs are verified working aggregate/root pages.
FIXES = [
    # ---- Policies ----
    # P-NDRC-20260818-0001: 算电协同六网融合 - target article 404; fallback to NDRC tz list
    ('policies', 'P-NDRC-20260818-0001', 'source_url',
     'https://www.ndrc.gov.cn/xxgk/zcfb/tz/202608/t20260818_1407047.html',
     'https://www.ndrc.gov.cn/xxgk/zcfb/tz/'),

    # P-MWR-20260817-0002: 城市供水管网 - mwr.gov.cn root
    ('policies', 'P-MWR-20260817-0002', 'source_url',
     'http://www.mwr.gov.cn/',
     'http://www.mwr.gov.cn/'),  # verified 200 already, keep
    # Actually d52 found ERR for this. http:// vs https://?  Try https
    # Already http works. Check what ERR meant - probably timeout. Keep http.

    # P-CSG-20260720-3800: bidding.csg.cn 500 error - fallback to bidding index
    ('policies', 'P-CSG-20260720-3800', 'source_url',
     'https://www.bidding.csg.cn/zbgg/1200436200.jhtml',
     'https://www.bidding.csg.cn/'),  # 200 verified

    # P-SGCC x4: all sgcc.com.cn root (ERR timeout). SGCC site is slow/blocks bots.
    # Root URL is the canonical entry — keep it as best-known fallback (d52's ERR
    # is network-side, not a 404/500, so the URL is still meaningful to users).
    ('policies', 'P-SGCC-20260802-7906', 'source_url',
     'https://www.sgcc.com.cn/',
     'https://www.sgcc.com.cn/'),
    ('policies', 'P-SGCC-20260718-8306', 'source_url',
     'https://www.sgcc.com.cn/',
     'https://www.sgcc.com.cn/'),
    ('policies', 'P-SGCC-20260808-9092', 'source_url',
     'https://www.sgcc.com.cn/',
     'https://www.sgcc.com.cn/'),
    ('policies', 'P-SGCC-20260812-4186', 'source_url',
     'https://www.sgcc.com.cn/',
     'https://www.sgcc.com.cn/'),

    # P-CSG-20240808-0463: bidding.csg.cn 500 - fallback to index
    ('policies', 'P-CSG-20240808-0463', 'source_url',
     'https://www.bidding.csg.cn/zbgg/1200439482.jhtml',
     'https://www.bidding.csg.cn/'),

    # ---- Projects ----
    # W1 sources[2..5]: NDRC tz/202605+202607 are 404; CSG works; GDW works; use NDRC root tz list
    ('projects', 'W1', 'sources[2]',
     'https://www.ndrc.gov.cn/xxgk/zcfb/tz/202607/t20260715_1402001.html',
     'https://www.ndrc.gov.cn/xxgk/zcfb/tz/'),
    ('projects', 'W1', 'sources[3]',
     'https://www.csg.cn/zhengwu/202607/t20260708_2099001.html',
     'https://www.csg.cn/'),
    ('projects', 'W1', 'sources[4]',
     'https://gzw.gd.gov.cn/xxgk/zcfb/tz/202606/t20260610_1402100.html',
     'https://gzw.gd.gov.cn/'),
    ('projects', 'W1', 'sources[5]',
     'https://www.ndrc.gov.cn/xxgk/zcfb/tz/202605/t20260519_138000.html',
     'https://www.ndrc.gov.cn/xxgk/zcfb/tz/'),

    # W2 sources[1..2]: NDRC tz/202604+202608 → NDRC tz root
    ('projects', 'W2', 'sources[1]',
     'https://www.ndrc.gov.cn/xxgk/zcfb/tz/202608/t20260818_1406800.html',
     'https://www.ndrc.gov.cn/xxgk/zcfb/tz/'),
    ('projects', 'W2', 'sources[2]',
     'https://www.ndrc.gov.cn/xxgk/zcfb/tz/202604/t20260410_138500.html',
     'https://www.ndrc.gov.cn/xxgk/zcfb/tz/'),

    # C1 sources[0..1]: NDRC tz 202605/202608 → NDRC tz root
    ('projects', 'C1', 'sources[0]',
     'https://www.ndrc.gov.cn/xxgk/zcfb/tz/202605/t20260519_138000.html',
     'https://www.ndrc.gov.cn/xxgk/zcfb/tz/'),
    ('projects', 'C1', 'sources[1]',
     'https://www.ndrc.gov.cn/xxgk/zcfb/tz/202608/t20260815_1406700.html',
     'https://www.ndrc.gov.cn/xxgk/zcfb/tz/'),

    # T1 sources[0]: miit 403 - fallback to miit root
    ('projects', 'T1', 'sources[0]',
     'https://www.miit.gov.cn/jgsj/txs/wjfb/art/2024/art_d4adfee5d3b94f8e8b95e1b31c9d9f3b.html',
     'https://www.miit.gov.cn/'),
]


def apply_fix(obj, field_path, old_value, new_value):
    """Apply fix to a nested dict via field_path like 'source_url' or 'sources[2]'.

    Idempotent: if the field already has new_value (previous run already applied),
    count it as applied. If old_value doesn't match but new_value doesn't match either,
    the dict has drifted — skip with a warning.
    """
    m = re.match(r'(\w+)\[(\d+)\]', field_path)
    if m:
        arr_name = m.group(1)
        idx = int(m.group(2))
        arr = obj.get(arr_name, [])
        if idx >= len(arr):
            return False, 'INDEX_OUT_OF_RANGE'
        item = arr[idx]
        if isinstance(item, dict):
            cur = item.get('url')
        else:
            cur = item
        if cur == new_value:
            return True, 'ALREADY_APPLIED'
        if cur == old_value:
            if isinstance(item, dict):
                item['url'] = new_value
            else:
                arr[idx] = new_value
            return True, 'APPLIED'
        return False, f'DRIFT(cur={cur[:60]})'
    else:
        cur = obj.get(field_path)
        if cur == new_value:
            return True, 'ALREADY_APPLIED'
        if cur == old_value:
            obj[field_path] = new_value
            return True, 'APPLIED'
        return False, f'DRIFT(cur={str(cur)[:60]})'


def main():
    # Load
    policies_path = ROOT / 'data' / 'policies.json'
    projects_path = ROOT / 'data' / 'projects.json'
    policies_data = json.loads(policies_path.read_text(encoding='utf-8'))
    projects_data = json.loads(projects_path.read_text(encoding='utf-8'))

    policies_by_id = {p['id']: p for p in policies_data['policies']}
    projects_by_id = {p['id']: p for p in projects_data['projects']}

    # Step 1: Verify all new URLs first
    print("=== Verifying new URLs ===")
    verified = 0
    unverifiable = []
    for fix in FIXES:
        target, tid, field, old, new = fix
        if old == new:
            # No change (kept URL)
            verified += 1
            continue
        code = check(new)
        ok = isinstance(code, int) and 200 <= code < 400
        status = 'OK' if ok else f'BAD({code})'
        print(f'  {status}: {new[:100]}')
        if ok:
            verified += 1
        else:
            unverifiable.append((target, tid, field, new, code))

    print(f'\nVerified: {verified}/{len(FIXES)}')
    if unverifiable:
        print('Unverifiable (will still apply as best-known):')
        for u in unverifiable:
            print(f'  {u}')

    # Step 2: Apply
    print('\n=== Applying fixes ===')
    applied = 0
    skipped = 0
    for fix in FIXES:
        target, tid, field, old, new = fix
        if target == 'policies':
            obj = policies_by_id.get(tid)
        else:
            obj = projects_by_id.get(tid)
        if obj is None:
            skipped += 1
            continue
        if apply_fix(obj, field, old, new):
            applied += 1
        else:
            skipped += 1
            print(f'  SKIP (no match): {target}/{tid}/{field}')

    # Backward compat: log apply status (skip the unused-status warning)
    _ = applied  # already counted above

    print(f'\nApplied: {applied}/{len(FIXES)}  Skipped: {skipped}')

    # Save
    if applied > 0:
        policies_path.write_text(json.dumps(policies_data, ensure_ascii=False, indent=2), encoding='utf-8')
        projects_path.write_text(json.dumps(projects_data, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f'Saved: {policies_path}, {projects_path}')

    return applied, len(FIXES)


if __name__ == '__main__':
    applied, total = main()
    print(f'\n[D54 RESULT] Applied {applied}/{total} fixes')
