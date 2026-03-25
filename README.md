# Jerry AI — Tom's Personal AI
### 100% Free. Forever.

---

## Setup in 3 steps

### Step 1 — Get your ONE free API key
1. Go to **console.groq.com**
2. Sign up (no credit card, completely free)
3. Click **"API Keys"** → **"Create API Key"**
4. Copy the key

### Step 2 — Add the key
```
Copy .env.example → rename it to .env
Open .env and replace "your_groq_key_here" with your actual key
```

### Step 3 — Install and run
```powershell
pip install -r requirements.txt
python main.py
```

---

## What's free and how

| Feature | Tool | Cost |
|---|---|---|
| AI Brain | Groq (Llama 3.3 70B) | Free |
| Web Research | DuckDuckGo | Free, no key |
| Stock Data | Yahoo Finance (yfinance) | Free, no key |
| Sports Analysis | Web scraping | Free, no key |
| Weather | Open-Meteo | Free, no key |
| Social Media | Reddit public API | Free, no key |
| Memory | Local JSON file | Free, no key |

---

## Example commands

```
Tom → hey jerry
Tom → Research the latest developments in quantum computing
Tom → Analyze Tesla stock
Tom → Predict Lakers vs Celtics tonight
Tom → What are people saying about Bitcoin on Reddit
Tom → Research NVDA news and give me a stock analysis
```

---

## Teach Jerry from sports results

After a game, open Python and run:
```python
from agents.sports import SportsAgent
agent = SportsAgent()
agent.update_outcome("pred_id_here", "Lakers won 112-98", True)
```
Jerry will learn from every mistake and improve over time.

---

## Deploy to Render (free hosting)

1. Push this folder to a GitHub repo
2. Go to **render.com** → New → Web Service
3. Connect your GitHub repo
4. Set environment variable: `GROQ_API_KEY` = your key
5. Deploy — Jerry runs 24/7 free

---

## File structure

```
jerry_ai/
├── main.py                  # Start Jerry here
├── .env                     # Your Groq key goes here
├── requirements.txt         # pip install -r this
├── render.yaml              # Render deployment config
├── agents/
│   ├── brain.py             # Groq AI brain
│   ├── orchestrator.py      # Routes requests to agents
│   ├── web_research.py      # DuckDuckGo research
│   ├── stocks.py            # Yahoo Finance analysis
│   ├── sports.py            # 4-layer sports prediction
│   └── social.py            # Reddit + news sentiment
├── memory/
│   └── store.py             # Remembers past conversations
└── data/
    ├── memory.json          # Auto-created conversation history
    ├── predictions_log.json # Auto-created sports predictions
    └── learning_notes.txt   # Auto-created from Jerry's mistakes
```
