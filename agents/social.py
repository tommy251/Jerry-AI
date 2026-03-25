"""
Social Media Agent - 100% Free sources that actually work:
1. Reddit public JSON API (no auth needed for search)
2. HackerNews discussions
3. RSS from major news (sentiment analysis)
4. Mastodon public API (no key needed)
"""

import httpx
import asyncio
from .brain import chat

HEADERS = {"User-Agent": "JerryAI/1.0 (personal research tool)"}


class SocialAgent:
    def __init__(self):
        pass

    async def initialize(self):
        pass

    async def run(self, query: str) -> str:
        reddit, hn, mastodon = await asyncio.gather(
            self._reddit(query),
            self._hackernews_discuss(query),
            self._mastodon(query),
        )

        all_data = []
        if reddit:   all_data.append(f"REDDIT:\n{reddit}")
        if hn:       all_data.append(f"HACKER NEWS DISCUSSIONS:\n{hn}")
        if mastodon: all_data.append(f"MASTODON (public posts):\n{mastodon}")

        if not all_data:
            return "Social media APIs returned no data right now. Try again in a moment."

        combined = "\n\n".join(all_data)

        return chat(
            [{"role": "user", "content":
              f"Tom wants to know what people are saying about: '{query}'\n\n"
              f"Social media data collected:\n{combined[:4000]}\n\n"
              f"Analyse this for Tom:\n"
              f"1. Overall sentiment (Positive/Negative/Mixed/Neutral)\n"
              f"2. Top 3 themes people are discussing\n"
              f"3. Anything viral, controversial or fast-moving\n"
              f"4. One-line signal: what does public perception mean right now"}],
            system="You are Jerry, Tom's social intelligence analyst. Extract real signal from the noise."
        )

    async def _reddit(self, query: str) -> str:
        """Reddit public JSON API — works without auth for search."""
        try:
            async with httpx.AsyncClient(timeout=12, headers=HEADERS,
                                         follow_redirects=True) as client:
                # Use Reddit's JSON search
                resp = await client.get(
                    "https://www.reddit.com/search.json",
                    params={"q": query, "sort": "hot", "limit": 15, "type": "link"},
                )
                if resp.status_code != 200:
                    return ""
                posts = resp.json()["data"]["children"]
                lines = []
                for p in posts[:10]:
                    d = p["data"]
                    lines.append(
                        f"• r/{d['subreddit']} | {d['score']} upvotes | "
                        f"{d['num_comments']} comments\n  {d['title']}"
                    )
                return "\n".join(lines)
        except Exception as e:
            return ""

    async def _hackernews_discuss(self, query: str) -> str:
        """HackerNews discussions — always free."""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    "https://hn.algolia.com/api/v1/search",
                    params={"query": query, "tags": "comment", "hitsPerPage": 10}
                )
                hits = resp.json().get("hits", [])
                lines = [
                    f"• {h.get('comment_text','')[:150]}"
                    for h in hits if h.get("comment_text")
                ]
                return "\n".join(lines[:6])
        except Exception:
            return ""

    async def _mastodon(self, query: str) -> str:
        """Mastodon public search — no key needed on mastodon.social."""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    "https://mastodon.social/api/v2/search",
                    params={"q": query, "type": "statuses", "limit": 10},
                )
                if resp.status_code != 200:
                    return ""
                statuses = resp.json().get("statuses", [])
                lines = []
                for s in statuses[:6]:
                    # Strip HTML tags from content
                    import re
                    text = re.sub(r'<[^>]+>', '', s.get("content", ""))
                    text = text.strip()[:150]
                    if text:
                        lines.append(f"• {text}")
                return "\n".join(lines)
        except Exception:
            return ""
