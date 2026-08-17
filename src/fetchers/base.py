"""
NSP-IM Fetcher 基础类
所有具体源 fetcher 继承此类
"""
import asyncio
import aiohttp
import json
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

class BaseFetcher(ABC):
    def __init__(self, name: str, source_url: str, enabled: bool = True):
        self.name = name
        self.source_url = source_url
        self.enabled = enabled
        self.timeout = 30
        self.max_retries = 3
    
    @abstractmethod
    async def fetch_raw(self) -> List[Dict[str, Any]]:
        """从源抓取原始数据，子类必须实现"""
        pass
    
    @abstractmethod
    def parse(self, raw: List[Dict]) -> List[Dict[str, Any]]:
        """解析为标准 policy 格式"""
        pass
    
    async def fetch_with_retry(self) -> List[Dict[str, Any]]:
        """带重试的抓取"""
        for attempt in range(self.max_retries):
            try:
                raw = await self.fetch_raw()
                return self.parse(raw)
            except Exception as e:
                print(f"[{self.name}] Attempt {attempt+1}/{self.max_retries} failed: {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)  # 指数退避
                else:
                    # 失败告警
                    await self.alert_failure(e)
                    return []
    
    async def alert_failure(self, error):
        """失败告警 - W1 实现 webhook / 邮件"""
        print(f"🔴 [{self.name}] ALERT: {error}")
        # TODO: webhook to 飞书
        # TODO: send email
        # TODO: write to dead-letter queue
    
    def save(self, policies: List[Dict], target: Optional[str] = None):
        """保存到 data/policies.json (或指定路径)。

        W1-D4 重构（B4 原子写入）:
          * 改用 utils.atomic_write，提供 fsync+rename 强保证
          * safe_read_json 兜底: 即便上次写崩留了半 JSON，也不会阻塞本次
          * 去重+追加 逻辑保持
        """
        from utils.atomic_write import atomic_write_json, safe_read_json
        policy_file = Path(target) if target else Path("data/policies.json")

        existing = safe_read_json(policy_file, default={"version": "1.0", "policies": []})
        if not isinstance(existing, dict):
            existing = {"version": "1.0", "policies": []}

        # 去重 + 追加
        existing_ids = {p['id'] for p in existing.get('policies', [])}
        added = 0
        for p in policies:
            if p['id'] not in existing_ids:
                existing.setdefault('policies', []).append(p)
                existing_ids.add(p['id'])
                added += 1

        existing['generated_at'] = datetime.utcnow().isoformat() + 'Z'

        atomic_write_json(policy_file, existing, ensure_ascii=False, indent=2)
        print(f"✅ [{self.name}] Saved {added} new policies (total {len(existing.get('policies', []))}) → {policy_file}")
    
    async def run(self):
        """主流程"""
        if not self.enabled:
            print(f"⏭ [{self.name}] disabled, skip")
            return
        policies = await self.fetch_with_retry()
        if policies:
            self.save(policies)
