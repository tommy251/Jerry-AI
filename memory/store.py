"""
Jerry's Memory - Simple JSON storage (no extra dependencies)
Remembers every conversation between sessions
"""

import json
import hashlib
from datetime import datetime
from pathlib import Path

MEMORY_FILE = Path(__file__).parent.parent / "data" / "memory.json"
MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)


class MemoryStore:
    def __init__(self):
        self.memories = []

    async def initialize(self):
        if MEMORY_FILE.exists():
            try:
                self.memories = json.loads(MEMORY_FILE.read_text())
            except Exception:
                self.memories = []

    async def save(self, query: str, response: str):
        entry = {
            "id":        hashlib.md5(f"{datetime.now()}{query}".encode()).hexdigest()[:8],
            "timestamp": datetime.now().isoformat(),
            "query":     query,
            "response":  response[:600],  # store summary
        }
        self.memories.append(entry)
        # Keep last 200 memories
        if len(self.memories) > 200:
            self.memories = self.memories[-200:]
        MEMORY_FILE.write_text(json.dumps(self.memories, indent=2))

    async def search(self, query: str, top_k: int = 2) -> list:
        """Simple keyword search through memories."""
        if not self.memories:
            return []
        query_words = set(query.lower().split())
        scored = []
        for m in self.memories:
            past_words = set(m["query"].lower().split())
            overlap = len(query_words & past_words)
            if overlap > 0:
                scored.append((overlap, m))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            f"[{m['timestamp'][:10]}] Tom asked: {m['query']}\nJerry said: {m['response'][:200]}"
            for _, m in scored[:top_k]
        ]
