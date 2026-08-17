"""
NSP-IM 发改委政策抓取器 v0.1
源：https://www.ndrc.gov.cn
"""
import aiohttp
from bs4 import BeautifulSoup
from datetime import datetime
from .base import BaseFetcher

class NdrcFetcher(BaseFetcher):
    def __init__(self):
        super().__init__(
            name="发改委",
            source_url="https://www.ndrc.gov.cn/xxgk/zcfb/tz/index.html"
        )
    
    async def fetch_raw(self):
        async with aiohttp.ClientSession() as session:
            async with session.get(self.source_url, timeout=self.timeout) as resp:
                html = await resp.text()
        
        soup = BeautifulSoup(html, 'html.parser')
        items = []
        # 发改委列表页结构：li > a（标题） + span（日期）
        for li in soup.select('li')[:20]:
            a = li.find('a')
            if not a: continue
            title = a.get_text(strip=True)
            href = a.get('href', '')
            if not title or '通知' not in title: continue
            
            date_span = li.find('span')
            date = date_span.get_text(strip=True) if date_span else ''
            
            items.append({
                'title': title,
                'url': href if href.startswith('http') else f'https://www.ndrc.gov.cn{href}',
                'date': date
            })
        return items
    
    def parse(self, raw):
        policies = []
        for item in raw:
            policies.append({
                'id': f"P-NDRC-{item['date'].replace('-','')}-{hash(item['title'])%10000:04d}",
                'title': item['title'],
                'department': '国家发改委',
                'doc_number': None,  # 需要详情页解析
                'publish_date': item['date'],
                'effective_date': item['date'],
                'category': 'policy',
                'scope': self._guess_scope(item['title']),
                'priority': 2,
                'summary': item['title'][:100],
                'key_points': [],
                'source_url': item['url'],
                'captured_at': datetime.utcnow().isoformat() + 'Z',
                'captured_by': 'ndrc-fetcher-v0.1',
                'tags': [],
                'review_status': 'pending'
            })
        return policies
    
    def _guess_scope(self, title: str):
        """根据标题猜测适用范围"""
        scopes = ['monitor']  # 默认
        if '电网' in title or '电力' in title or '能源' in title: scopes.append('grid')
        if '水' in title: scopes.append('water')
        if '算' in title or '数据' in title: scopes.append('compute')
        if '通信' in title or '5G' in title: scopes.append('telecom')
        if '管网' in title or '管廊' in title: scopes.append('pipe')
        if '运输' in title or '物流' in title: scopes.append('logi')
        return list(set(scopes))
