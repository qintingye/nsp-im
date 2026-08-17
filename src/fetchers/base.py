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
    
    def save(self, policies: List[Dict]):
        """保存到 data/policies.json"""
        policy_file = Path("data/policies.json")
        if policy_file.exists():
            with open(policy_file, 'r', encoding='utf-8') as f:
                existing = json.load(f)
        else:
            existing = {"version": "1.0", "policies": []}
        
        # 去重 + 追加
        existing_ids = {p['id'] for p in existing['policies']}
        for p in policies:
            if p['id'] not in existing_ids:
                existing['policies'].append(p)
        
        existing['generated_at'] = datetime.utcnow().isoformat() + 'Z'
        
        # 原子写入
        tmp_file = policy_file.with_suffix('.tmp')
        with open(tmp_file, 'w', encoding='utf-8') as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)
        tmp_file.replace(policy_file)
        print(f"✅ [{self.name}] Saved {len(policies)} policies")
    
    async def run(self):
        """主流程"""
        if not self.enabled:
            print(f"⏭ [{self.name}] disabled, skip")
            return
        policies = await self.fetch_with_retry()
        if policies:
            self.save(policies)
