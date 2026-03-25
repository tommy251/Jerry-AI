"""
Jerry's Sports Intelligence Engine - 100% Free
4-Layer Analysis: Performance | Context | Health | Psychology
Self-learning from past predictions
Free data: web scraping + Open-Meteo weather (no key needed)
"""

import re
import json
import hashlib
import asyncio
import httpx
from datetime import datetime
from pathlib import Path
from bs4 import BeautifulSoup
from .brain import chat

DATA_DIR       = Path(__file__).parent.parent / "data"
PREDICTIONS_DB = DATA_DIR / "predictions_log.json"
DATA_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


class SportsAgent:
    def __init__(self):
        self.predictions_log = self._load_predictions()

    async def initialize(self):
        await self._review_past_predictions()

    # ── MAIN ─────────────────────────────────────────────────────────────────

    async def run(self, query: str) -> str:
        sport, teams = self._parse_query(query)

        # Run all 4 layers in parallel
        perf, ctx, health, psych = await asyncio.gather(
            self._layer_1_performance(sport, teams),
            self._layer_2_context(sport, teams),
            self._layer_3_health(sport, teams),
            self._layer_4_psychology(sport, teams),
        )

        prediction = await self._synthesise(query, sport, teams, perf, ctx, health, psych)
        self._log_prediction(query, sport, teams, prediction)

        alerts = self._build_alerts(health, ctx, psych)
        result = prediction
        if alerts:
            result += "\n\n" + "━" * 48
            result += "\n🔔 JERRY ALERT — Tom, heads up:\n"
            result += "\n".join(f"  ⚠  {a}" for a in alerts)

        accuracy = self._accuracy_summary()
        if accuracy:
            result += f"\n\n[Jerry's track record: {accuracy}]"

        return result

    # ── LAYER 1: PERFORMANCE ─────────────────────────────────────────────────

    async def _layer_1_performance(self, sport: str, teams: list) -> dict:
        data = {"stats": {}, "h2h": ""}
        tasks = []
        for team in teams[:2]:
            tasks.append(self._ddg_search(f"{team} {sport} stats form results 2025"))
        if len(teams) >= 2:
            tasks.append(self._ddg_search(f"{teams[0]} vs {teams[1]} head to head history {sport}"))

        results = await asyncio.gather(*tasks)
        for i, team in enumerate(teams[:2]):
            data["stats"][team] = results[i][:1200] if i < len(results) else ""
        if len(teams) >= 2 and len(results) > 2:
            data["h2h"] = results[2][:1000]
        return data

    # ── LAYER 2: CONTEXT / ENVIRONMENT ───────────────────────────────────────

    async def _layer_2_context(self, sport: str, teams: list) -> dict:
        data = {"home_away": {}, "importance": "", "weather": {}}
        tasks = []
        for team in teams[:2]:
            tasks.append(self._ddg_search(f"{team} home away record 2025 {sport}"))
        if len(teams) >= 2:
            tasks.append(self._ddg_search(f"{' vs '.join(teams[:2])} {sport} standings playoff 2025"))

        results = await asyncio.gather(*tasks)
        for i, team in enumerate(teams[:2]):
            data["home_away"][team] = results[i][:600] if i < len(results) else ""
        if len(results) > 2:
            data["importance"] = results[2][:500]

        # Free weather from Open-Meteo (no key needed!)
        if teams:
            data["weather"] = await self._fetch_weather_free(teams[0])
        return data

    # ── LAYER 3: BIOMETRIC / HEALTH ───────────────────────────────────────────

    async def _layer_3_health(self, sport: str, teams: list) -> dict:
        data = {"injuries": {}, "fatigue": {}, "schedule": {}}
        tasks = []
        for team in teams[:2]:
            tasks.append(self._ddg_search(f"{team} injury news suspended out {sport} 2025"))
            tasks.append(self._ddg_search(f"{team} {sport} recent games schedule last week"))

        results = await asyncio.gather(*tasks)
        for i, team in enumerate(teams[:2]):
            inj   = results[i * 2]     if i * 2     < len(results) else ""
            sched = results[i * 2 + 1] if i * 2 + 1 < len(results) else ""
            data["injuries"][team] = inj[:700]
            data["schedule"][team] = sched[:500]
            data["fatigue"][team]  = self._estimate_fatigue(sched)
        return data

    def _estimate_fatigue(self, text: str) -> str:
        markers = ["days ago", "yesterday", "back-to-back", "3 games", "4 games",
                   "wednesday", "thursday", "friday"]
        hits = sum(1 for m in markers if m in text.lower())
        if hits >= 3: return "HIGH ⚠ — likely fatigued"
        if hits >= 1: return "MODERATE — some fatigue possible"
        return "LOW — adequate rest likely"

    # ── LAYER 4: PSYCHOLOGY ───────────────────────────────────────────────────

    async def _layer_4_psychology(self, sport: str, teams: list) -> dict:
        data = {"morale": {}, "manager": {}, "momentum": {}}
        tasks = []
        for team in teams[:2]:
            tasks.append(self._ddg_search(f"{team} squad morale confidence form {sport} 2025"))
            tasks.append(self._ddg_search(f"{team} coach manager tactics news 2025"))

        results = await asyncio.gather(*tasks)
        for i, team in enumerate(teams[:2]):
            morale  = results[i * 2]     if i * 2     < len(results) else ""
            manager = results[i * 2 + 1] if i * 2 + 1 < len(results) else ""
            data["morale"][team]   = morale[:500]
            data["manager"][team]  = manager[:500]
            data["momentum"][team] = self._score_momentum(morale)
        return data

    def _score_momentum(self, text: str) -> str:
        pos = ["win", "unbeaten", "confident", "strong", "dominant", "scored", "form"]
        neg = ["loss", "crisis", "sacked", "struggling", "poor", "injury", "relegated"]
        score = sum(1 for w in pos if w in text.lower()) - \
                sum(1 for w in neg if w in text.lower())
        if score >= 3:  return "Positive ↑"
        if score <= -2: return "Negative ↓"
        return "Neutral →"

    # ── SYNTHESIS ─────────────────────────────────────────────────────────────

    async def _synthesise(self, query, sport, teams, perf, ctx, health, psych) -> str:
        learning = self._get_learning_notes()

        prompt = f"""You are Jerry — Tom's elite sports intelligence AI.
Use the 4 layers of data below to give Tom the sharpest possible prediction.

QUERY: {query}
Sport: {sport} | Teams: {', '.join(teams) or 'analyse from query'}

━━ LAYER 1 — PERFORMANCE ━━
Recent stats & form:
{json.dumps({k: v[:300] for k,v in perf.get('stats',{}).items()}, indent=2)}
Head-to-head: {perf.get('h2h','N/A')[:400]}

━━ LAYER 2 — CONTEXT ━━
Game importance: {ctx.get('importance','N/A')[:300]}
Home/Away record: {json.dumps({k: v[:200] for k,v in ctx.get('home_away',{}).items()})}
Weather: {json.dumps(ctx.get('weather',{}))}

━━ LAYER 3 — HEALTH / PHYSICAL ━━
Injuries & suspensions: {json.dumps({k: v[:250] for k,v in health.get('injuries',{}).items()})}
Fatigue estimate: {json.dumps(health.get('fatigue',{}))}

━━ LAYER 4 — PSYCHOLOGICAL ━━
Momentum: {json.dumps(psych.get('momentum',{}))}
Morale signals: {json.dumps({k: v[:150] for k,v in psych.get('morale',{}).items()})}
Manager news: {json.dumps({k: v[:150] for k,v in psych.get('manager',{}).items()})}

━━ JERRY'S LEARNING FROM PAST MISTAKES ━━
{learning or 'No past predictions yet — first game!'}

━━ YOUR PREDICTION FORMAT ━━
MATCH OVERVIEW
[teams, sport, context — 2 lines]

LAYER BREAKDOWN
[one sharp insight from each of the 4 layers]

KEY DECIDING FACTORS
[the 2-3 things that will actually determine this result]

INJURY / FATIGUE WATCH
[flag anything critical here — missing players flip games]

PREDICTION
[Winner + expected margin or scoreline]
Confidence: Low / Medium / High — one sentence reason

RISK FLAGS
[what could make this prediction wrong — be real with Tom]

Talk to Tom directly — like a trusted analyst, not a formal report.
Note: even perfect data can't beat a lucky deflection — that's sport."""

        return chat(
            [{"role": "user", "content": prompt}],
            system="You are Jerry, Tom's sports intelligence AI. Be sharp, direct and analytical."
        )

    # ── ALERTS ────────────────────────────────────────────────────────────────

    def _build_alerts(self, health, ctx, psych) -> list:
        alerts = []
        for team, level in health.get("fatigue", {}).items():
            if "HIGH" in level:
                alerts.append(f"{team} is HIGH fatigue — rotation or underperformance very likely.")
        for team in psych.get("momentum", {}):
            if "Negative" in psych["momentum"].get(team, "") and \
               len(health.get("injuries", {}).get(team, "")) > 60:
                alerts.append(f"{team}: negative momentum + injury problems — double red flag.")
        weather = ctx.get("weather", {})
        wind = weather.get("wind_mph", 0)
        rain = weather.get("rain_mm", 0)
        if isinstance(wind, (int, float)) and wind > 25:
            alerts.append(f"Wind at {wind}mph — shooting accuracy and passing will suffer.")
        if isinstance(rain, (int, float)) and rain > 5:
            alerts.append(f"Heavy rain ({rain}mm) — favours physical teams, hurts technical play.")
        return alerts

    # ── SELF-LEARNING ─────────────────────────────────────────────────────────

    def _log_prediction(self, query, sport, teams, prediction):
        pred_id = hashlib.md5(f"{datetime.now()}{query}".encode()).hexdigest()[:8]
        self.predictions_log.append({
            "id":         pred_id,
            "timestamp":  datetime.now().isoformat(),
            "query":      query,
            "sport":      sport,
            "teams":      teams,
            "prediction": prediction[:400],
            "outcome":    None,
            "correct":    None,
        })
        self._save_predictions()
        return pred_id

    def update_outcome(self, pred_id: str, actual: str, correct: bool):
        """Teach Jerry after a game. Call this once results are in."""
        for p in self.predictions_log:
            if p["id"] == pred_id:
                p["outcome"] = actual
                p["correct"] = correct
                p["reviewed_at"] = datetime.now().isoformat()
                break
        self._save_predictions()

    async def _review_past_predictions(self):
        wrong = [p for p in self.predictions_log if p.get("correct") is False]
        if not wrong:
            return
        recent = wrong[-5:]
        summary = "\n".join(
            f"- {p['timestamp'][:10]} | {p.get('sport')} | Q: {p.get('query')} | "
            f"Predicted: {p['prediction'][:80]} | Actual: {p.get('outcome','?')}"
            for p in recent
        )
        notes = chat(
            [{"role": "user", "content":
              f"You are Jerry reviewing your past sports prediction mistakes. "
              f"Write 3-5 short lessons to improve future predictions:\n\n{summary}"}],
            system="You are a self-improving sports analyst AI."
        )
        (DATA_DIR / "learning_notes.txt").write_text(
            f"Updated: {datetime.now().isoformat()}\n\n{notes}"
        )

    def _get_learning_notes(self) -> str:
        f = DATA_DIR / "learning_notes.txt"
        return f.read_text()[:500] if f.exists() else ""

    def _accuracy_summary(self) -> str:
        reviewed = [p for p in self.predictions_log if p.get("correct") is not None]
        if len(reviewed) < 3:
            return ""
        correct = sum(1 for p in reviewed if p["correct"])
        return f"{round(correct/len(reviewed)*100,1)}% ({correct}/{len(reviewed)} reviewed)"

    # ── UTILITIES ─────────────────────────────────────────────────────────────

    def _parse_query(self, query: str) -> tuple:
        lower = query.lower()
        sport_map = {
            "nba": "basketball", "basketball": "basketball",
            "lakers": "basketball", "celtics": "basketball",
            "nfl": "american football", "premier league": "soccer",
            "champions league": "soccer", "la liga": "soccer",
            "soccer": "soccer", "football": "soccer",
            "mlb": "baseball", "nhl": "ice hockey",
        }
        sport = "sport"
        for kw, sp in sport_map.items():
            if kw in lower:
                sport = sp
                break

        teams = []
        vs_match = re.search(
            r'([\w\s]+?)\s+(?:vs\.?|versus|against)\s+([\w\s]+?)(?:\s+(?:predict|game|match|tonight)|$)',
            query, re.I
        )
        if vs_match:
            teams = [vs_match.group(1).strip(), vs_match.group(2).strip()]
        else:
            caps = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?\b', query)
            skip = {"Predict", "Game", "Match", "Jerry", "Tom", "Tonight", "Analysis", "Sports"}
            teams = [c for c in caps if c not in skip][:2]

        return sport, teams

    async def _ddg_search(self, query: str) -> str:
        """DuckDuckGo search — free, no key."""
        try:
            async with httpx.AsyncClient(timeout=10, headers=HEADERS) as client:
                resp = await client.get(
                    "https://html.duckduckgo.com/html/",
                    params={"q": query},
                )
                soup = BeautifulSoup(resp.text, "html.parser")
                snippets = [
                    s.get_text(strip=True)
                    for s in soup.select(".result__snippet")[:5]
                ]
                return " | ".join(snippets)
        except Exception:
            return ""

    async def _fetch_weather_free(self, location: str) -> dict:
        """Open-Meteo — completely free, no API key needed."""
        try:
            async with httpx.AsyncClient(timeout=8) as client:
                # Geocode the location first
                geo = await client.get(
                    "https://geocoding-api.open-meteo.com/v1/search",
                    params={"name": location, "count": 1}
                )
                geo_data = geo.json().get("results", [])
                if not geo_data:
                    return {"note": f"Could not geocode: {location}"}

                lat = geo_data[0]["latitude"]
                lon = geo_data[0]["longitude"]

                weather = await client.get(
                    "https://api.open-meteo.com/v1/forecast",
                    params={
                        "latitude": lat, "longitude": lon,
                        "current": "temperature_2m,wind_speed_10m,precipitation,weathercode",
                        "wind_speed_unit": "mph",
                    }
                )
                w = weather.json().get("current", {})
                code = w.get("weathercode", 0)
                condition = self._weather_code(code)
                return {
                    "condition":  condition,
                    "temp_c":     w.get("temperature_2m"),
                    "wind_mph":   w.get("wind_speed_10m"),
                    "rain_mm":    w.get("precipitation", 0),
                }
        except Exception:
            return {"note": "Weather unavailable"}

    def _weather_code(self, code: int) -> str:
        if code == 0:   return "Clear sky"
        if code <= 3:   return "Partly cloudy"
        if code <= 48:  return "Foggy"
        if code <= 67:  return "Rainy"
        if code <= 77:  return "Snow"
        if code <= 82:  return "Rain showers"
        return "Thunderstorm"

    def _load_predictions(self) -> list:
        if PREDICTIONS_DB.exists():
            try:
                return json.loads(PREDICTIONS_DB.read_text())
            except Exception:
                return []
        return []

    def _save_predictions(self):
        PREDICTIONS_DB.write_text(json.dumps(self.predictions_log, indent=2))
