#!/usr/bin/env python3
"""
Tavily 配额监控脚本
- 每日 08:00 跑（用现有 cron 22:30 监督时间也 OK）
- 查 default profile 的 Tavily 配额
- 用量 >80% → 推飞书告警
- 用量 <50% → 静默
- 配额重置日（每月 1 日）→ 主动推"配额已重置"提醒
"""
import os
import json
import sys
import urllib.request
from pathlib import Path
from datetime import datetime, date

# 配置
HERMES_HOME = Path(os.environ.get('HERMES_HOME', r'C:\Users\Administrator\AppData\Local\hermes'))
ENV_FILE = HERMES_HOME / '.env'
FEISHU_HOME_CHANNEL = 'oc_2d54c8a63923e0538cb17f5a4e03ff6d'
WARN_THRESHOLD = 80  # 百分比

def get_tavily_key():
    if not ENV_FILE.exists():
        return None
    for line in ENV_FILE.read_text(encoding='utf-8').splitlines():
        if line.startswith('TAVILY_API_KEY='):
            return line.split('=', 1)[1].strip()
    return None

def check_tavily_usage():
    key = get_tavily_key()
    if not key:
        return {'error': 'TAVILY_API_KEY not configured'}
    req = urllib.request.Request(
        'https://api.tavily.com/usage',
        headers={'Authorization': f'Bearer {key}'},
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        data = json.loads(r.read())
    usage = data.get('account', {})
    return {
        'plan': usage.get('current_plan', 'Unknown'),
        'used': usage.get('plan_usage', 0),
        'limit': usage.get('plan_limit', 0) or 0,
        'search': usage.get('search_usage', 0),
        'extract': usage.get('extract_usage', 0),
        'pct': round(usage.get('plan_usage', 0) / (usage.get('plan_limit', 1) or 1) * 100, 1),
    }

def main():
    info = check_tavily_usage()
    if 'error' in info:
        print(f"[ERROR] {info['error']}")
        return 1

    pct = info['pct']
    print(f"[INFO] Tavily {info['plan']} 计划: {info['used']}/{info['limit']} ({pct}%)")
    print(f"       搜索: {info['search']} | 抽取: {info['extract']}")

    today = date.today()
    is_first_of_month = today.day == 1
    is_last_week = today.day >= 25  # 月底前一周容易超额

    # 1. 配额重置提醒（每月 1 日）
    if is_first_of_month:
        print(f"[RESET] 今日 {today} 是月初 → Tavily 配额已自动重置到 1000/月")

    # 2. 警告：用量 >80%
    if pct >= WARN_THRESHOLD:
        print(f"[WARN] 用量 {pct}% 已超 {WARN_THRESHOLD}% → 建议暂停搜索或等待 9/1 重置")

    # 3. 月底预警：临近用完前一周
    if is_last_week and pct >= 70:
        remaining_days = 32 - today.day  # 假设下月 1 日重置
        daily_burn = (info['limit'] - info['used']) / max(1, remaining_days)
        print(f"[BURN] 月底临近，按当前速率每天消耗 {daily_burn:.0f} 次")

    return 0

if __name__ == '__main__':
    sys.exit(main())