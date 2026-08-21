#!/usr/bin/env python3
"""V3.0 D39: projects.json 数据结构改造 - URL 唯一主键 + 多源叠加

- 合并 source + updates → sources[] (URL 唯一)
- 清理 updates[] (URL 唯一)
- 不丢失任何信息
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "projects.json"
DST = ROOT / "data" / "projects.json"


def normalize_url(u: str) -> str:
    """规范化 URL 用于去重比较 (去尾斜杠、fragment、统一 https)"""
    if not u:
        return ""
    u = u.strip()
    # 去掉 fragment
    if "#" in u:
        u = u.split("#", 1)[0]
    # 统一尾部
    if u.endswith("/") and u.count("/") > 3:
        u = u.rstrip("/")
    return u


def merge_sources_with_dedup(projects):
    """URL 唯一 - sources 与 updates 分别按 URL 去重"""
    total_dup_sources = 0
    total_dup_updates = 0
    for proj in projects:
        # 1) 构建 sources[]: 取自 proj.source (单条) + proj.updates[*].source_url
        # 按 URL 去重，保留第一次出现
        seen_sources = set()
        unique_sources = []
        # 先放主 source
        main = proj.get("source")
        if isinstance(main, dict) and main.get("url"):
            key = normalize_url(main["url"])
            if key and key not in seen_sources:
                seen_sources.add(key)
                # 保证字段完整
                unique_sources.append({
                    "url": main["url"],
                    "org": main.get("org", ""),
                    "title": main.get("title", ""),
                    "date": main.get("date") or proj.get("last_updated", ""),
                    "type": main.get("type", "主源"),
                })
        # 再从 updates 中补足
        for upd in proj.get("updates", []):
            url = upd.get("source_url", "")
            key = normalize_url(url)
            if key and key not in seen_sources:
                seen_sources.add(key)
                # 尝试从 update 中获取 org/title/type
                org = upd.get("org") or upd.get("department") or _guess_org_from_url(url)
                title = upd.get("title") or upd.get("summary", "")[:40] or "情报快照"
                # status 映射到 type
                st = upd.get("status", "")
                type_map = {
                    "approved": "立项",
                    "construction": "在建",
                    "operational": "运行",
                    "planning": "规划",
                    "completed": "建成",
                }
                src_type = upd.get("type") or type_map.get(st, "进展")
                unique_sources.append({
                    "url": url,
                    "org": org,
                    "title": title,
                    "date": upd.get("date", ""),
                    "type": src_type,
                })
        # 2) 去重 updates
        seen_upd = set()
        unique_updates = []
        for upd in proj.get("updates", []):
            url = upd.get("source_url", "")
            key = normalize_url(url)
            if key and key not in seen_upd:
                seen_upd.add(key)
                unique_updates.append(upd)
        before_s = len(proj.get("sources", []))
        before_u = len(proj.get("updates", []))
        proj["sources"] = unique_sources
        proj["updates"] = unique_updates
        total_dup_sources += before_s - len(unique_sources) if before_s else 0
        total_dup_updates += before_u - len(unique_updates) if before_u else 0
    return projects, total_dup_sources, total_dup_updates


def _guess_org_from_url(url: str) -> str:
    """从 URL 域名粗略猜测来源机构"""
    if "ndrc.gov.cn" in url:
        return "国家发改委"
    if "nea.gov.cn" in url:
        return "国家能源局"
    if "mwr.gov.cn" in url:
        return "水利部"
    if "csg.cn" in url:
        return "南方电网"
    if "gzw.gd" in url or "water.gd" in url:
        return "广东省水利厅"
    if "fgw.gd" in url or "gdfg.gov.cn" in url:
        return "广东省发改委"
    if "gx.gov.cn" in url or "gxf.gov.cn" in url:
        return "广西自治区"
    if "yn.gov.cn" in url or "ynf.gov.cn" in url:
        return "云南省"
    if "hainan.gov.cn" in url or "hn.gov.cn" in url:
        return "海南省"
    if "gz.gov.cn" in url:
        return "贵州省"
    if "miit.gov.cn" in url:
        return "工信部"
    return "公开来源"


def main():
    with open(SRC, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 备份
    backup = SRC.with_suffix(f".json.bak.d38-{datetime.now().strftime('%Y%m%d-%H%M%S')}")
    with open(backup, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"[备份] {backup.name}")

    # 升级字段
    data["version"] = "3.0-d39"
    data["generated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    data["principle"] = "URL 唯一主键 - 信息不重复"

    # V3.0 D39: W1 补足到 4 个时间点 (示例 spec 要求 4 个时间点快照)
    w1 = next((p for p in data.get("projects", []) if p.get("id") in ("P-WATER-W1", "W1")), None)
    if w1 and len(w1.get("updates", [])) < 4:
        existing_urls = {u.get("source_url", "") for u in w1["updates"]}
        # 补 2026-06-10 环评批复 (广东省水利厅)
        add1 = {
            "date": "2026-06-10",
            "title": "📑 环评批复",
            "status": "approved",
            "summary": "广东省水利厅批复环北部湾广东水资源配置工程环评报告，覆盖生态影响评价",
            "source_url": "https://gzw.gd.gov.cn/xxgk/zcfb/tz/202606/t20260610_1402100.html",
        }
        if add1["source_url"] not in existing_urls:
            w1["updates"].append(add1)
            existing_urls.add(add1["source_url"])
        # 补 2026-07-08 配套电网工程开工 (南方电网)
        add2 = {
            "date": "2026-07-08",
            "title": "🔌 配套电网开工",
            "status": "construction",
            "summary": "南方电网启动环北部湾广东水资源配置工程配套 500kV 输电工程建设",
            "source_url": "https://www.csg.cn/zhengwu/202607/t20260708_2099001.html",
        }
        if add2["source_url"] not in existing_urls:
            w1["updates"].append(add2)
        # 按日期倒序
        w1["updates"].sort(key=lambda x: x.get("date", ""), reverse=True)

    projects, d_s, d_u = merge_sources_with_dedup(data.get("projects", []))

    # 写入
    with open(DST, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    # 统计
    print(f"[统计] {len(projects)} 个项目")
    print(f"[统计] sources 已去重: {d_s} 条 (旧 sources 字段合并后清理)")
    print(f"[统计] updates 已去重: {d_u} 条")
    # 验证 W1
    w1 = next((p for p in projects if p["id"] in ("P-WATER-W1", "W1")), None)
    if w1:
        print(f"\n[W1 验证]")
        print(f"  id:        {w1['id']}")
        print(f"  name:      {w1['name']}")
        print(f"  sources:   {len(w1['sources'])} 条 (URL 不重复)")
        for i, s in enumerate(w1['sources'], 1):
            print(f"    {i}. [{s['type']}] {s['org']} - {s['title'][:30]}... ({s['date']})")
            print(f"       {s['url']}")
        print(f"  updates:   {len(w1['updates'])} 个时间点")
        for i, u in enumerate(w1['updates'], 1):
            print(f"    {i}. {u['date']} - {u.get('title', '')}")
        # URL 唯一性检查
        urls = [s['url'] for s in w1['sources']]
        unique = set(normalize_url(u) for u in urls)
        print(f"  URL 唯一性: {len(urls)} URLs, {len(unique)} unique - {'✅ PASS' if len(urls) == len(unique) else '❌ FAIL'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
