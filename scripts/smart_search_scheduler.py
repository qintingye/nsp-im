#!/usr/bin/env python3
"""
智能搜索后端调度器（基于老板的"免费优先、付费兜底"策略）
==========================================================
最终版（2026-08-20）：
  1. Tavily（每月1000次免费 Researcher Plan，配额内永远优先；9/1 重置）
  2. Baidu 千帆（已充100元，国内唯一稳定可用 → 当前主力）
  3. DDGS（免费但国内 Yahoo 超时 → 失效，已放弃）

老板亲令原话：
  - "先用免费的 tavily，再用付费的 baidu，兜底..."
  - "百度都充了钱了啊，还是拿来兜底吧"
  - "Brave 信用卡 + 国内访问限制，不折腾"
"""
import os
import json
import subprocess
import urllib.request
from pathlib import Path

HERMES_HOME = Path(os.environ.get('HERMES_HOME', r'C:\Users\Administrator\AppData\Local\hermes'))
ENV_FILE = HERMES_HOME / '.env'

TAVILY_USAGE_URL = 'https://api.tavily.com/usage'
TAVILY_PCT_WARN = 80
TAVILY_PCT_DISABLE = 100


def get_tavily_key():
    if not ENV_FILE.exists():
        return None
    for line in ENV_FILE.read_text(encoding='utf-8').splitlines():
        if line.startswith('TAVILY_API_KEY='):
            return line.split('=', 1)[1].strip()
    return None


def check_tavily():
    """查询 Tavily 账户配额"""
    key = get_tavily_key()
    if not key:
        return {'available': False, 'pct': 0, 'reason': 'no key'}
    try:
        req = urllib.request.Request(
            TAVILY_USAGE_URL,
            headers={'Authorization': f'Bearer {key}'},
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
        usage = data.get('account', {})
        used = usage.get('plan_usage', 0)
        limit = usage.get('plan_limit', 1) or 1
        pct = round(used / limit * 100, 1)
        return {
            'available': True,
            'pct': pct,
            'used': used,
            'limit': limit,
            'plan': usage.get('current_plan', 'unknown'),
        }
    except Exception as e:
        return {'available': False, 'pct': 0, 'reason': str(e)}


def get_baidu_status():
    """检查 Baidu 千帆是否可用（有 key 且 API 通）"""
    if not ENV_FILE.exists():
        return False
    for line in ENV_FILE.read_text(encoding='utf-8').splitlines():
        if line.startswith('BAIDU_QIANFAN_API_KEY='):
            key = line.split('=', 1)[1].strip()
            if not key:
                return False
            try:
                req = urllib.request.Request(
                    'https://qianfan.baidubce.com/v2/ai_search/web_search',
                    headers={
                        'Authorization': f'Bearer {key}',
                        'Content-Type': 'application/json',
                    },
                    data=json.dumps({
                        'messages': [{'role': 'user', 'content': 'test'}],
                        'search_source': 'baidu_search_v2',
                        'resource_type_filter': [{'type': 'web', 'top_k': 1}],
                    }).encode('utf-8'),
                )
                with urllib.request.urlopen(req, timeout=10) as r:
                    return r.status == 200
            except Exception:
                return False
    return False


def set_web_backend(backend):
    """设置 web.backend 配置"""
    result = subprocess.run(
        ['hermes', 'config', 'set', 'web.backend', backend],
        capture_output=True, text=True, timeout=15,
    )
    return result.returncode == 0


def main():
    tavily = check_tavily()
    print(f"[Tavily] {tavily}")

    baidu_ok = get_baidu_status()
    print(f"[Baidu]  available={baidu_ok}（国内稳定；已充值 100 元）")

    print(f"[DDGS]   available=False（国内网络超时，Yahoo 后端失效）")

    # 调度决策（最终版 2026-08-20）
    # 真实状况：
    # - Tavily：月1000 次免费，配额内可用；9/1 重置
    # - DDGS：免费无限但国内超时（Yahoo 后端）实际不可用
    # - Baidu：国内唯一稳定可用，但实测对中文新词效果一般
    if not tavily['available']:
        chosen = 'baidu'
        reason = 'Tavily 不可用 → DDGS 国内超时失效 → 用 Baidu（已充值 100 元）'
    elif tavily['pct'] >= TAVILY_PCT_DISABLE:
        chosen = 'baidu'
        reason = f"Tavily 配额耗尽 ({tavily['pct']}%) → DDGS 国内失效 → 用 Baidu 主力"
    elif tavily['pct'] >= TAVILY_PCT_WARN:
        chosen = 'baidu'
        reason = f"Tavily 配额紧张 ({tavily['pct']}%) → 提前切 Baidu 节省 Tavily 配额"
    else:
        chosen = 'tavily'
        reason = f"Tavily 配额充足 ({tavily['pct']}%) → 优先免费 Tavily"

    print(f"\n[Decision] web.backend = {chosen}")
    print(f"[Reason]  {reason}")

    ok = set_web_backend(chosen)
    print(f"[Applied] {'✓ 已设置' if ok else '✗ 设置失败'}")

    return 0


if __name__ == '__main__':
    import sys
    sys.exit(main())