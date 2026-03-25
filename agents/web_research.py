"""
Web Research Agent - 100% Free
Uses DuckDuckGo search (no API key needed) + httpx for page reading
"""

import httpx
from bs4 import BeautifulSoup
from .brain import chat


class WebResearchAgent:
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

    async def initialize(self):
        pass

    async def run(self, query: str) -> str:
        results = await self._search(query)
        if not results:
            return f"No web results found for: {query}"

        # Fetch full content from top results
        pages = []
        async with httpx.AsyncClient(timeout=15, headers=self.headers, follow_redirects=True) as client:
            for r in results[:4]:
                try:
                    resp = await client.get(r["url"])
                    soup = BeautifulSoup(resp.text, "html.parser")

                    # Remove junk tags
                    for tag in soup(["script", "style", "nav", "footer", "header"]):
                        tag.decompose()

                    text = " ".join(p.get_text(strip=True) for p in soup.find_all("p"))
                    text = " ".join(text.split())[:2000]  # clean whitespace, limit size

                    if text:
                        pages.append(f"SOURCE: {r['url']}\nTITLE: {r.get('title','')}\n{text}")
                    else:
                        pages.append(f"SOURCE: {r['url']}\n{r.get('snippet','')}")
                except Exception:
                    pages.append(f"SOURCE: {r['url']}\n{r.get('snippet','')}")

        raw = "\n\n---\n\n".join(pages)

        # Ask Jerry to synthesise the research
        summary = chat(
            [{"role": "user", "content":
                f"Research query: {query}\n\nWeb content collected:\n{raw[:4000]}\n\n"
                f"Summarise the key findings clearly and completely."
            }],
            system="You are a brilliant research analyst. Extract and summarise the most important information."
        )
        return summary

    async def _search(self, query: str) -> list:
        """DuckDuckGo search — completely free, no API key."""
        try:
            async with httpx.AsyncClient(timeout=10, headers=self.headers) as client:
                # Use DuckDuckGo HTML endpoint
                resp = await client.get(
                    "https://html.duckduckgo.com/html/",
                    params={"q": query},
                )
                soup = BeautifulSoup(resp.text, "html.parser")
                results = []
                for r in soup.select(".result")[:6]:
                    title_el = r.select_one(".result__title")
                    url_el   = r.select_one(".result__url")
                    snip_el  = r.select_one(".result__snippet")
                    if title_el and url_el:
                        url = url_el.get_text(strip=True)
                        if not url.startswith("http"):
                            url = "https://" + url
                        results.append({
                            "title":   title_el.get_text(strip=True),
                            "url":     url,
                            "snippet": snip_el.get_text(strip=True) if snip_el else "",
                        })
                return results
        except Exception as e:
            return []
