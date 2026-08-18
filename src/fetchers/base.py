"""
NSP-IM Fetcher 基础类 v1.0
所有具体源 fetcher 继承此类

W1-D4 BE 重构要点:
  P0-2 修复: 路径锚定仓库根 (REPO_ROOT/data/policies.json), 不再依赖 CWD
  P0-1 修复合流: 子类应可在 basicConfig 之后才做 mkdir
  去重升级: 集成 utils.dedup, URL 归一化兜底, 多策略 (freshest/first)
  健康探针: 集成 utils.health._HealthProbe
  合并策略: 重复源不互相覆盖 - 用 dedup 后的 unique 列表参与合并

W3-D1 升级:
  v5 字段继承: dedup "freshest" 不会覆盖已有 policy 的
    support_direction / carrier_relation / v4_cers_dccib / v5_source
"""
from __future__ import annotations

import asyncio
import json
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# 仓库根 = 当前 src/fetchers/base.py 的爷爷目录的爷爷目录 (nsp-im/)
# src/fetchers/base.py → parents[0]=src/fetchers, parents[1]=src, parents[2]=nsp-im
BASE_FILE = Path(__file__).resolve()
REPO_ROOT = BASE_FILE.parents[2]
REPO_DATA_DIR = REPO_ROOT / "data"

# 让 utils.* 可以直接被 import (utils 不在 src 包内, 是 src/utils/)
import sys
SRC_DIR = str(REPO_ROOT / "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)


# W3-D1: dedup "freshest" 不应覆盖已有 policy 的 v5 字段
_V5_INHERIT_KEYS = ("support_direction", "carrier_relation", "v4_cers_dccib", "v5_source")


class BaseFetcher(ABC):
    def __init__(self, name: str, source_url: str, enabled: bool = True):
        self.name = name
        self.source_url = source_url
        self.enabled = enabled
        self.timeout = 30
        self.max_retries = 3

    @abstractmethod
    async def fetch_raw(self) -> List[Dict[str, Any]]:
        """从源抓取原始数据，子类必须实现。"""
        pass

    @abstractmethod
    def parse(self, raw: List[Dict]) -> List[Dict[str, Any]]:
        """解析为标准 policy 格式（必须含 `id` 字段，schema 校验）。"""
        pass

    async def fetch_with_retry(self) -> List[Dict[str, Any]]:
        """带重试的抓取。"""
        last_err: Optional[Exception] = None
        for attempt in range(self.max_retries):
            try:
                raw = await self.fetch_raw()
                return self.parse(raw)
            except Exception as e:  # noqa: BLE001 - P0 容错优先
                last_err = e
                print(f"[{self.name}] Attempt {attempt + 1}/{self.max_retries} failed: {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)  # 指数退避
                else:
                    await self.alert_failure(e)
                    return []
        # 不可达, 仅补全类型
        return []

    async def alert_failure(self, error) -> None:
        """失败告警 - W1 实现 webhook / 邮件。W1-D4 落地: 配置 URL 时真实推送。"""
        from utils.health import FetcherHealth  # noqa: F401  # import 健康但避免循环
        print(f"🔴 [{self.name}] ALERT: {error}")
        # TODO(W1 后续): webhook to 飞书 (FEISHU_WEBHOOK 环境变量)
        # TODO(W1 后续): send email
        # TODO(W1 后续): write to dead-letter queue

    # ---------- 落盘 ----------
    def save(
        self,
        policies: List[Dict[str, Any]],
        *,
        target: Optional[str] = None,
        dedup: bool = True,
    ) -> Dict[str, Any]:
        """把 policies 合并写入 data/policies.json (W1 默认目标)。

        Args:
            policies: 本次新抓到的政策列表。
            target: 自定义输出路径; 默认 `REPO_ROOT/data/policies.json` (P0-2 修复)。
            dedup: 是否对合并结果去重 (URL 归一化兜底)。

        Returns:
            {"added": N, "total": N, "duplicates": N, "path": str}

        设计原则:
          - 路径永远以仓库根为基准, 不依赖 CWD (CI `cd src` 也不会错位)
          - 全部走 utils.atomic_write, 防止半写 (fetcher 崩溃后旧 JSON 仍可用)
          - safe_read_json 兜底: 上次写崩留了半 JSON, 不会阻塞本次
          - 失败时不抛, 让 fetcher 的 health 探针负责告警
          - W3-D1: dedup "freshest" 不应覆盖已有 v5 字段, 新抓到的相同 id 会
            继承 _V5_INHERIT_KEYS (support_direction / carrier_relation / ...).
        """
        from utils.atomic_write import atomic_write_json, safe_read_json  # noqa: PLC0415
        from utils.dedup import deduplicate  # noqa: PLC0415

        policy_file = Path(target) if target else (REPO_DATA_DIR / "policies.json")

        existing = safe_read_json(policy_file, default={"version": "1.0", "policies": []})
        if not isinstance(existing, dict):
            existing = {"version": "1.0", "policies": []}
        existing_policies = existing.get("policies", [])
        if not isinstance(existing_policies, list):
            existing_policies = []

        # W3-D1 兜底: 用 id 索引已有 policies, 让新抓到的相同 id 继承 v5 字段
        #   (避免 dedup "freshest" 把已升级字段覆盖掉)
        existing_by_id: Dict[str, Dict[str, Any]] = {}
        for p in existing_policies:
            if isinstance(p, dict) and p.get("id"):
                existing_by_id[p["id"]] = p

        def _inherit_v5_fields(new_p: Dict[str, Any]) -> Dict[str, Any]:
            old = existing_by_id.get(new_p.get("id", ""))
            if not old:
                return new_p
            for k in _V5_INHERIT_KEYS:
                if k not in new_p and k in old:
                    new_p[k] = old[k]
            return new_p

        # 1. 合并: 把新 policies 与旧 policies 一起, 用 dedup 统一去重
        new_policies = [_inherit_v5_fields(dict(p)) for p in (policies or [])]
        merged_input: List[Dict[str, Any]] = list(existing_policies) + new_policies
        if dedup:
            result = deduplicate(merged_input, prefer="freshest")
            merged_unique = result["unique"]
            duplicates_dropped = result["stats"].get("removed_by_id", 0) + result["stats"].get("removed_by_url", 0)
        else:
            # 不去重, 仅按 id 集去一下, 防止多份同 id 残留
            seen_ids: set = set()
            merged_unique = []
            for p in merged_input:
                pid = p.get("id") if isinstance(p, dict) else None
                if pid and pid not in seen_ids:
                    seen_ids.add(pid)
                    merged_unique.append(p)
                elif not pid:
                    merged_unique.append(p)
            duplicates_dropped = len(merged_input) - len(merged_unique)

        added = max(0, len(merged_unique) - len(existing_policies))

        out = dict(existing)
        out["version"] = existing.get("version", "1.0")
        out["policies"] = merged_unique
        out["generated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")

        try:
            atomic_write_json(policy_file, out, ensure_ascii=False, indent=2)
        except OSError as e:
            print(f"❌ [{self.name}] save() 写盘失败: {e}")
            raise

        print(
            f"✅ [{self.name}] +{added} 合并后总数 {len(merged_unique)} "
            f"(去重 {duplicates_dropped}) → {policy_file}"
        )
        return {
            "added": added,
            "total": len(merged_unique),
            "duplicates": duplicates_dropped,
            "path": str(policy_file),
        }

    # ---------- 主流程 ----------
    async def run(self, *, health_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """主流程。

        集成 _HealthProbe 自动记录 success/fail + latency, 并把状态写入 data/health.json。
        """
        from utils.health import _HealthProbe  # noqa: PLC0415

        if not self.enabled:
            print(f"⏭ [{self.name}] disabled, skip")
            return None

        hpath = health_path or str(REPO_DATA_DIR / "health.json")
        with _HealthProbe(self.name, hpath):
            policies = await self.fetch_with_retry()
        if policies:
            return self.save(policies)
        return None


__all__ = ["BaseFetcher", "REPO_ROOT", "REPO_DATA_DIR"]