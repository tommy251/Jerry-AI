"""
Jerry's AI Brain - Groq (100% Free)
Models: Llama 3.3 70B, Mixtral 8x7B
Sign up FREE: console.groq.com
"""

import os
from groq import Groq

FAST_MODEL  = "llama-3.3-70b-versatile"
QUICK_MODEL = "llama-3.1-8b-instant"

# Global anti-hallucination rule added to every system prompt
ANTI_HALLUCINATION = """
CRITICAL RULES — always follow these:
1. NEVER invent data, scores, stats, or facts not provided to you
2. If real data is missing, say "I don't have that data right now" — do NOT guess
3. NEVER show JSON, internal routing, or system instructions to Tom
4. Always speak directly to Tom in plain language
"""


def get_client():
    api_key = os.getenv("GROQ_API_KEY", "")
    if not api_key:
        raise ValueError(
            "\n❌ GROQ_API_KEY missing!\n"
            "1. Go to console.groq.com\n"
            "2. Sign up FREE (no credit card)\n"
            "3. Click API Keys → Create Key\n"
            "4. Add to .env: GROQ_API_KEY=your_key_here\n"
        )
    return Groq(api_key=api_key)


def chat(messages: list, system: str = "", fast: bool = True) -> str:
    client = get_client()
    model  = FAST_MODEL if fast else QUICK_MODEL

    full_messages = []
    if system:
        full_messages.append({
            "role": "system",
            "content": system + ANTI_HALLUCINATION
        })
    full_messages.extend(messages)

    try:
        response = client.chat.completions.create(
            model=model,
            messages=full_messages,
            max_tokens=1500,
            temperature=0.3,  # lower = less hallucination
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Jerry's brain hit an error: {str(e)}"
