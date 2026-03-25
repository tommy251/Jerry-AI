"""
Orchestrator — routes Tom's messages to the right agent(s)
Uses Groq (free) as the AI brain
"""

import json
from .brain import chat
from .web_research import WebResearchAgent
from .stocks import StockAgent
from .sports import SportsAgent
from .social import SocialAgent
from memory.store import MemoryStore


SYSTEM_PROMPT = """You are Jerry, Tom's personal AI assistant. You are sharp, direct, and brilliant.

You have access to these specialist agents:
- [RESEARCH] : deep web research on any topic
- [STOCKS]   : stock analysis and market data
- [SPORTS]   : game predictions with deep 4-layer analysis
- [SOCIAL]   : social media sentiment and trending topics

When the user's message needs one or more agents, respond ONLY with valid JSON:
{"agents": ["RESEARCH"], "query": "refined search query"}

For multiple agents: {"agents": ["RESEARCH", "STOCKS"], "query": "refined query"}

If no agent is needed (casual chat, greetings, general knowledge), just reply normally as Jerry.
Never say you can't do something. Be Tom's most powerful tool."""


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
        # Pull relevant memory context
        context = await self.memory.search(user_input, top_k=2)
        context_str = "\n".join(context) if context else ""

        messages = []
        if context_str:
            messages.append({
                "role": "user",
                "content": f"[Past context that may be relevant]\n{context_str}"
            })
            messages.append({
                "role": "assistant",
                "content": "Got it, I have that context."
            })
        messages.append({"role": "user", "content": user_input})

        # Ask Jerry's brain to route the request
        routing_text = chat(messages, system=SYSTEM_PROMPT)

        # Try to parse as agent routing JSON
        try:
            # Extract JSON if wrapped in markdown
            if "```" in routing_text:
                routing_text = routing_text.split("```")[1].replace("json", "").strip()
            plan = json.loads(routing_text)
            agents_to_call = plan.get("agents", [])
            refined_query  = plan.get("query", user_input)
        except (json.JSONDecodeError, ValueError):
            # Jerry answered directly — save and return
            await self.memory.save(user_input, routing_text)
            return routing_text

        if not agents_to_call:
            await self.memory.save(user_input, routing_text)
            return routing_text

        # Run agents in parallel
        import asyncio
        tasks = [
            self.agents[a].run(refined_query)
            for a in agents_to_call
            if a in self.agents
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Build combined data block
        combined = "\n\n".join(
            f"[{name} DATA]\n{result}"
            for name, result in zip(agents_to_call, results)
            if not isinstance(result, Exception)
        )

        # Final synthesis
        synthesis_prompt = f"""Tom asked: "{user_input}"

Here is the data from your specialist agents:
{combined}

Give Tom a sharp, direct, complete answer. Be his best analyst.
Use all the data above. Format it clearly. Talk to him like a trusted advisor."""

        answer = chat(
            [{"role": "user", "content": synthesis_prompt}],
            system="You are Jerry, Tom's personal AI. Be direct, sharp, and use all available data to give the best possible answer."
        )

        await self.memory.save(user_input, answer)
        return answer
