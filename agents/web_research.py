"""
Web Research Agent - Uses multiple FREE sources that actually work:
1. Wikipedia API (no key, no blocks)
2. NewsAPI free tier (100 req/day)
3. HackerNews API (completely free)
4. RSS feeds from major news sites (no key)
5. SerpAPI free tier OR Brave Search API (free tier)
"""

import httpx
import asyncio
import xml.etree.ElementTree as ET
from .brain import chat

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; JerryAI/1.0; +research bot)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# Free RSS feeds from reliable sources
RSS_FEEDS = [
    "https://feeds.bbci.co.uk/news/rss.xml",
    "https://rss.cnn.com/rss/edition.rss",
    "https://feeds.reuters.com/reuters/topNews",
    "https://techcrunch.com/feed/",
    "https://feeds.feedburner.com/TechCrunch",
]


class WebResearchAgent:
    def __init__(self):
        self.news_api_key = None  # optional — newsapi.org free tier

    async def initialize(self):
        pass

    async def run(self, query: str) -> str:
        # Run all sources in parallel
        wiki, news, hn = await asyncio.gather(
            self._wikipedia(query),
            self._rss_news(query),
            self._hackernews(query),
        )

        all_data = []
        if wiki:  all_data.append(f"WIKIPEDIA:\n{wiki}")
        if news:  all_data.append(f"RECENT NEWS:\n{news}")
        if hn:    all_data.append(f"HACKER NEWS / TECH:\n{hn}")

        if not all_data:
            return f"Could not fetch data for: {query}. APIs may be temporarily down."

        combined = "\n\n".join(all_data)

        return chat(
            [{"role": "user", "content":
              f"Research query: '{query}'\n\n"
              f"Data collected from multiple sources:\n{combined[:5000]}\n\n"
              f"Give Tom a thorough, well-organised research summary. "
              f"Include key facts, recent developments, and important context."}],
            system="You are Jerry, Tom's research analyst. Be thorough, factual, and well-organised."
        )

    async def _wikipedia(self, query: str) -> str:
        """Wikipedia API - always free, no blocks."""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                # Search for relevant article
                search = await client.get(
                    "https://en.wikipedia.org/w/api.php",
                    params={
                        "action": "query", "list": "search",
                        "srsearch": query, "format": "json",
                        "srlimit": 3,
                    }
                )
                results = search.json()["query"]["search"]
                if not results:
                    return ""

                # Get extract of top result
                title = results[0]["title"]
                extract = await client.get(
                    "https://en.wikipedia.org/w/api.php",
                    params={
                        "action": "query", "prop": "extracts",
                        "exintro": True, "explaintext": True,
                        "titles": title, "format": "json",
                    }
                )
                pages = extract.json()["query"]["pages"]
                text  = next(iter(pages.values())).get("extract", "")
                return f"[{title}]\n{text[:2000]}"
        except Exception:
            return ""

    async def _rss_news(self, query: str) -> str:
        """Fetch and filter RSS feeds — no API key needed."""
        keywords = query.lower().split()
        articles = []

        async with httpx.AsyncClient(timeout=10, headers=HEADERS) as client:
            for feed_url in RSS_FEEDS[:3]:
                try:
                    resp = await client.get(feed_url)
                    root = ET.fromstring(resp.text)
                    for item in root.iter("item"):
                        title = item.findtext("title", "")
                        desc  = item.findtext("description", "")
                        link  = item.findtext("link", "")
                        combined = (title + " " + desc).lower()
                        if any(kw in combined for kw in keywords):
                            articles.append(f"• {title}\n  {desc[:150]}")
                        if len(articles) >= 8:
                            break
                except Exception:
                    continue

        return "\n".join(articles[:8]) if articles else ""

    async def _hackernews(self, query: str) -> str:
        """HackerNews Algolia API — completely free, no key."""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    "https://hn.algolia.com/api/v1/search",
                    params={"query": query, "tags": "story", "hitsPerPage": 8}
                )
                hits = resp.json().get("hits", [])
                lines = [
                    f"• {h.get('title','')} ({h.get('points',0)} points)\n"
                    f"  {h.get('url','')}"
                    for h in hits if h.get("title")
                ]
                return "\n".join(lines[:6])
        except Exception:
            return ""
