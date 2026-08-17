"""
NSP-IM 主抓取器（每日 09:00 调度）
"""
import asyncio
import logging
from datetime import datetime
from pathlib import Path
from fetchers.ndrc import NdrcFetcher
# W1 后续添加：
# from fetchers.nea import NeaFetcher
# from fetchers.csg import CsgFetcher
# from fetchers.sgcc import SgccFetcher
# from fetchers.bjx import BjxFetcher

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('logs/fetcher.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# W1 启用列表
W1_FETCHERS = [
    NdrcFetcher(),
    # NeaFetcher(),    # 能源局
    # CsgFetcher(),    # 南网
    # SgccFetcher(),   # 国网
    # BjxFetcher(),    # 北极星
]

async def main():
    logger.info(f"=== NSP-IM 抓取启动 {datetime.now().isoformat()} ===")
    
    # 并发抓取（W1 串行，后续并发）
    results = []
    for fetcher in W1_FETCHERS:
        try:
            policies = await fetcher.run()
            results.append((fetcher.name, len(policies) if policies else 0))
        except Exception as e:
            logger.error(f"{fetcher.name} 异常: {e}")
            results.append((fetcher.name, -1))
    
    # 总结
    logger.info("=== 抓取结果 ===")
    for name, count in results:
        status = "✅" if count > 0 else ("⏭" if count == 0 else "❌")
        logger.info(f"{status} {name}: {count} 条")
    
    # 健康探针
    total = sum(c for _, c in results if c > 0)
    failed = sum(1 for _, c in results if c < 0)
    if failed > 0:
        logger.warning(f"⚠️ {failed} 个源失败，需要人工介入")
    logger.info(f"=== 总计: {total} 条新政策 ===")

if __name__ == "__main__":
    Path('logs').mkdir(exist_ok=True)
    asyncio.run(main())
