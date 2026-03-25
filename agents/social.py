"""
Social Media Agent - 100% Free
Reddit public API (no key needed for read-only)
DuckDuckGo news search
"""

import httpx
from bs4 import BeautifulSoup
from .brain import chat

HEADERS = {"User-Agent": "JerryAI/1.0 (personal assistant bot)"}


class SocialAgent:
    def __init__(self):
        pass

    async def initialize(self):
        pass

    async def run(self, query: str) -> str:
        reddit_posts, news = await self._gather(query)
        return self._analyse(query, reddit_posts, news)

    async def _gather(self, query: str) -> tuple:
        import asyncio
        reddit, news = await asyncio.gather(
            self._reddit_search(query),
            self._ddg_news(query),
        )
        return reddit, news

    async def _reddit_search(self, query: str) -> list:
        """Reddit public JSON API — no key needed for read access."""
        try:
            async with httpx.AsyncClient(timeout=10, headers=HEADERS) as client:
                resp = await client.get(
                    "https://www.reddit.com/search.json",
                    params={"q": query, "sort": "hot", "limit": 15, "type": "link"},
                )
                posts = resp.json()["data"]["children"]
                return [
                    {
                        "title":     p["data"]["title"],
                        "subreddit": p["data"]["subreddit"],
                        "score":     p["data"]["score"],
                        "comments":  p["data"]["num_comments"],
                        "url":       p["data"]["url"],
                    }
                    for p in posts
                ]
        except Exception:
            return []

    async def _ddg_news(self, query: str) -> list:
        """DuckDuckGo news — free, no key."""
        try:
            async with httpx.AsyncClient(timeout=10, headers=HEADERS) as client:
                resp = await client.get(
                    "https://html.duckduckgo.com/html/",
                    params={"q": f"{query} news", "df": "w"},  # last week
                )
                soup = BeautifulSoup(resp.text, "html.parser")
                results = []
                for r in soup.select(".result")[:8]:
                    title = r.select_one(".result__title")
                    snip  = r.select_one(".result__snippet")
                    if title:
                        results.append({
                            "title":   title.get_text(strip=True),
                            "snippet": snip.get_text(strip=True) if snip else "",
                        })
                return results
        except Exception:
            return []

    def _analyse(self, query: str, reddit: list, news: list) -> str:
        reddit_text = "\n".join(
            f"  r/{p['subreddit']} [{p['score']} upvotes, {p['comments']} comments]: {p['title']}"
            for p in reddit[:10]
        ) if reddit else "No Reddit posts found."

        news_text = "\n".join(
            f"  • {n['title']} — {n['snippet'][:100]}"
            for n in news[:6]
        ) if news else "No news found."

        prompt = f"""Tom wants to know what people are saying about: "{query}"

Reddit posts (sorted by hotness):
{reddit_text}

Recent news:
{news_text}

Give Tom:
1. Overall sentiment (Positive / Negative / Mixed / Neutral) and why
2. Top 3 themes or narratives people are talking about
3. Anything viral, controversial or fast-moving
4. One-line signal: what does public perception mean for this topic right now

Be direct and sharp."""

        return chat(
            [{"role": "user", "content": prompt}],
            system="You are Jerry, Tom's social intelligence analyst. Extract signal from noise."
        )
