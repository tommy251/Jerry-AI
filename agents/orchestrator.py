"""
Orchestrator — routes Tom's messages to the right agent(s)
Fixed: properly extracts JSON routing even when Groq wraps it in text
"""

import json
import re
import asyncio
from .brain import chat
from .web_research import WebResearchAgent
from .stocks import StockAgent
from .sports import SportsAgent
from .social import SocialAgent
from memory.store import MemoryStore


# Strict system prompt — forces pure JSON output for routing
ROUTING_PROMPT = """You are Jerry's internal router. Your ONLY job is to decide which agents to call.

Available agents:
- RESEARCH : web research, news, facts, current events, general knowledge
- STOCKS   : stock prices, market analysis, financial data
- SPORTS   : game predictions, match results, team stats, sports schedules
- SOCIAL   : social media sentiment, Reddit trends, what people are saying

Rules:
1. ALWAYS respond with ONLY a raw JSON object — no explanation, no text before or after
2. Format: {"agents": ["AGENT_NAME"], "query": "optimised search query"}
3. Multiple agents: {"agents": ["RESEARCH", "STOCKS"], "query": "query here"}
4. For greetings or pure chat (hi, thanks, how are you): {"agents": [], "query": ""}

Examples:
User: "what basketball games are tomorrow"
Response: {"agents": ["SPORTS"], "query": "NBA basketball games schedule March 26 2026"}

User: "analyze Tesla stock"
Response: {"agents": ["STOCKS"], "query": "Tesla TSLA stock analysis"}

User: "latest AI news"
Response: {"agents": ["RESEARCH"], "query": "latest artificial intelligence news 2026"}

User: "hey jerry"
Response: {"agents": [], "query": ""}

ONLY output the JSON. Nothing else. No explanation. No markdown."""


REPLY_PROMPT = """You are Jerry — Tom's personal AI. Sharp, direct, brilliant.
Never say you don't have access to something.
Never show JSON or internal routing to Tom.
Always give a complete, useful answer using the data provided."""


class Orchestrator:
    def __init__(self):
        self.memory = MemoryStore()
        self.agents = {}

    async def initialize(self):
        print("  Loading agents...")
        self.agents = {
            "RESEARCH": WebResearchAgent(),
            "STOCKS":   StockAgent(),
            "SPORTS":   SportsAgent(),
            "SOCIAL":   SocialAgent(),
        }
        await self.memory.initialize()
        for name, agent in self.agents.items():
            await agent.initialize()
            print(f"    ✓ {name} agent ready")

    async def run(self, user_input: str) -> str:
        # Pull memory context
        context = await self.memory.search(user_input, top_k=2)
        context_str = "\n".join(context) if context else ""

        # Step 1: Route the request
        agents_to_call, refined_query = await self._route(user_input)

        # Step 2: If no agents needed, reply directly as Jerry
        if not agents_to_call:
            reply = chat(
                [{"role": "user", "content": user_input}],
                system=REPLY_PROMPT + (f"\n\nPast context:\n{context_str}" if context_str else "")
            )
            await self.memory.save(user_input, reply)
            return reply

        # Step 3: Run agents in parallel
        tasks = [
            self.agents[a].run(refined_query)
            for a in agents_to_call
            if a in self.agents
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Step 4: Build data block from agent results
        data_blocks = []
        for name, result in zip(agents_to_call, results):
            if isinstance(result, Exception):
                data_blocks.append(f"[{name}]: Error — {str(result)}")
            elif result:
                data_blocks.append(f"[{name} DATA]\n{result}")

        combined = "\n\n".join(data_blocks)

        if not combined:
            return "Jerry hit a snag fetching data — all sources returned empty. Try again in a moment Tom."

        # Step 5: Synthesise final answer
        synthesis = f"""Tom asked: "{user_input}"

Agent data collected:
{combined}

{"Relevant past context: " + context_str if context_str else ""}

Give Tom a complete, sharp, well-formatted answer using all the data above.
Talk to him directly like a trusted analyst."""

        answer = chat(
            [{"role": "user", "content": synthesis}],
            system=REPLY_PROMPT
        )

        await self.memory.save(user_input, answer)
        return answer

    async def _route(self, user_input: str) -> tuple:
        """
        Ask Jerry's brain to route the request.
        Robustly extracts JSON even if the model wraps it in text.
        """
        routing_raw = chat(
            [{"role": "user", "content": user_input}],
            system=ROUTING_PROMPT
        )

        # Try 1: direct JSON parse
        try:
            plan = json.loads(routing_raw.strip())
            return plan.get("agents", []), plan.get("query", user_input)
        except (json.JSONDecodeError, ValueError):
            pass

        # Try 2: extract JSON object from anywhere in the response
        match = re.search(r'\{[^{}]+\}', routing_raw, re.DOTALL)
        if match:
            try:
                plan = json.loads(match.group())
                return plan.get("agents", []), plan.get("query", user_input)
            except (json.JSONDecodeError, ValueError):
                pass

        # Try 3: keyword-based fallback routing (when model ignores instructions)
        return self._keyword_route(user_input)

    def _keyword_route(self, text: str) -> tuple:
        """
        Fallback: route by keywords when the model fails to return JSON.
        This means Jerry ALWAYS calls the right agent no matter what.
        """
        lower = text.lower()
        agents = []

        sport_words = ["game", "match", "play", "score", "basketball", "football",
                       "soccer", "nba", "nfl", "predict", "team", "league", "tonight",
                       "tomorrow", "fixture", "sport", "lakers", "celtics", "arsenal",
                       "chelsea", "manchester", "liverpool", "real madrid", "barcelona"]

        stock_words = ["stock", "share", "price", "market", "invest", "nasdaq",
                       "nyse", "crypto", "bitcoin", "ethereum", "bull", "bear",
                       "aapl", "tsla", "nvda", "portfolio", "trading", "finance"]

        social_words = ["twitter", "reddit", "social", "trending", "viral", "people saying",
                        "opinion", "sentiment", "community", "post", "tweet", "mastodon"]

        research_words = ["research", "what is", "who is", "explain", "news", "latest",
                          "current", "find", "search", "tell me about", "how does",
                          "history", "why", "when", "where", "best", "top"]

        if any(w in lower for w in sport_words):   agents.append("SPORTS")
        if any(w in lower for w in stock_words):   agents.append("STOCKS")
        if any(w in lower for w in social_words):  agents.append("SOCIAL")
        if any(w in lower for w in research_words) or not agents:
            agents.append("RESEARCH")

        # Remove duplicates while preserving order
        seen = set()
        agents = [a for a in agents if not (a in seen or seen.add(a))]

        return agents, text
