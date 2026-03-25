"""
Jerry's AI Brain - Powered by Groq (100% Free)
Groq gives you: Llama 3.3 70B, Mixtral 8x7B — all free
Sign up: console.groq.com (no credit card needed)
"""

import os
from groq import Groq

# Free models available on Groq
FAST_MODEL = "llama-3.3-70b-versatile"   # best for complex reasoning
QUICK_MODEL = "llama-3.1-8b-instant"     # faster for simple tasks


def get_client():
    api_key = os.getenv("GROQ_API_KEY", "")
    if not api_key:
        raise ValueError(
            "\n❌ GROQ_API_KEY missing!\n"
            "1. Go to console.groq.com\n"
            "2. Sign up FREE (no credit card)\n"
            "3. Click 'API Keys' → Create key\n"
            "4. Add to your .env file: GROQ_API_KEY=your_key_here\n"
        )
    return Groq(api_key=api_key)


def chat(messages: list, system: str = "", fast: bool = True) -> str:
    """Simple chat wrapper around Groq."""
    client = get_client()
    model = FAST_MODEL if fast else QUICK_MODEL

    full_messages = []
    if system:
        full_messages.append({"role": "system", "content": system})
    full_messages.extend(messages)

    response = client.chat.completions.create(
        model=model,
        messages=full_messages,
        max_tokens=1500,
        temperature=0.7,
    )
    return response.choices[0].message.content.strip()
