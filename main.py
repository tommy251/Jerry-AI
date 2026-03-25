"""
Jerry AI - Tom's Personal AI
100% Free - No paid APIs required
Run locally: python main.py
"""

import os
import asyncio
from dotenv import load_dotenv
from agents.orchestrator import Orchestrator

load_dotenv()

BANNER = """
╔══════════════════════════════════════════════╗
║         JERRY AI - Tom's Personal AI         ║
║   Web · Stocks · Sports · Social · Memory    ║
║            100% Free Forever                 ║
╚══════════════════════════════════════════════╝
"""

async def main():
    print(BANNER)
    orchestrator = Orchestrator()
    await orchestrator.initialize()
    print("✅ Jerry is ready. Hey Tom, what do you need?\n")

    while True:
        try:
            user_input = input("Tom → ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nJerry: Catch you later Tom!")
            break

        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit", "bye"):
            print("Jerry: Alright Tom, shutting down. Later!")
            break
        if user_input.lower() == "help":
            print_help()
            continue

        response = await orchestrator.run(user_input)
        print(f"\nJerry → {response}\n")


def print_help():
    print("""
Things you can ask Jerry:
  Research  → "Research the latest AI news"
  Stocks    → "Analyze Tesla stock"
  Sports    → "Predict Lakers vs Celtics tonight"
  Social    → "What are people saying about Bitcoin"
  Combined  → "Research NVDA news and predict the stock"
  quit/exit → Shut Jerry down
""")


if __name__ == "__main__":
    asyncio.run(main())
