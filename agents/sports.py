"""
Jerry's Sports Intelligence Engine - 4 Layer Analysis
FREE data sources that actually work:
1. ESPN public API (no key needed)
2. TheSportsDB API (free tier, no key for basic)
3. Wikipedia for H2H and historical data
4. HackerNews + RSS for sports news
5. Open-Meteo for weather (no key)
"""

import re
import json
import hashlib
import asyncio
import httpx
from datetime import datetime
from pathlib import Path
from .brain import chat

DATA_DIR       = Path(__file__).parent.parent / "data"
PREDICTIONS_DB = DATA_DIR / "predictions_log.json"
DATA_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; JerryAI/1.0)"}


class SportsAgent:
    def __init__(self):
        self.predictions_log = self._load_predictions()

    async def initialize(self):
        await self._review_past_predictions()

    async def run(self, query: str) -> str:
        sport, teams = self._parse_query(query)

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
        data = {"espn": {}, "sportsdb": {}, "wiki_h2h": "", "news": {}}

        tasks = []
        for team in teams[:2]:
            tasks.append(self._espn_team(team, sport))
            tasks.append(self._sportsdb_team(team))
            tasks.append(self._wiki_stats(team, sport))

        if len(teams) >= 2:
            tasks.append(self._wiki_stats(f"{teams[0]} vs {teams[1]}", sport))

        results = await asyncio.gather(*tasks)

        idx = 0
        for i, team in enumerate(teams[:2]):
            data["espn"][team]    = results[idx];   idx += 1
            data["sportsdb"][team]= results[idx];   idx += 1
            data["news"][team]    = results[idx];   idx += 1

        if len(teams) >= 2 and idx < len(results):
            data["wiki_h2h"] = results[idx]

        return data

    # ── LAYER 2: CONTEXT ─────────────────────────────────────────────────────

    async def _layer_2_context(self, sport: str, teams: list) -> dict:
        data = {"standings": "", "importance": "", "weather": {}}

        tasks = [self._espn_standings(sport)]
        if len(teams) >= 2:
            tasks.append(self._wiki_stats(f"{' '.join(teams[:2])} {sport} standings season", sport))

        results = await asyncio.gather(*tasks)
        data["standings"]  = results[0] if results else ""
        data["importance"] = results[1] if len(results) > 1 else ""
        data["weather"]    = await self._weather(teams[0] if teams else "New York")

        return data

    # ── LAYER 3: HEALTH ───────────────────────────────────────────────────────

    async def _layer_3_health(self, sport: str, teams: list) -> dict:
        data = {"injuries": {}, "fatigue": {}}

        tasks = []
        for team in teams[:2]:
            tasks.append(self._espn_injuries(team, sport))
            tasks.append(self._wiki_stats(f"{team} injuries roster {sport} 2025", sport))

        results = await asyncio.gather(*tasks)

        for i, team in enumerate(teams[:2]):
            espn_inj = results[i * 2]     if i * 2     < len(results) else ""
            wiki_inj = results[i * 2 + 1] if i * 2 + 1 < len(results) else ""
            data["injuries"][team] = f"{espn_inj}\n{wiki_inj}".strip()[:800]
            data["fatigue"][team]  = self._estimate_fatigue(espn_inj + wiki_inj)

        return data

    def _estimate_fatigue(self, text: str) -> str:
        markers = ["days ago", "yesterday", "back-to-back", "3 games", "4 games", "wednesday", "thursday"]
        hits = sum(1 for m in markers if m in text.lower())
        if hits >= 3: return "HIGH ⚠ — likely fatigued"
        if hits >= 1: return "MODERATE"
        return "LOW — adequate rest"

    # ── LAYER 4: PSYCHOLOGY ───────────────────────────────────────────────────

    async def _layer_4_psychology(self, sport: str, teams: list) -> dict:
        data = {"morale": {}, "momentum": {}}

        tasks = []
        for team in teams[:2]:
            tasks.append(self._wiki_stats(f"{team} {sport} 2025 form confidence morale", sport))

        results = await asyncio.gather(*tasks)

        for i, team in enumerate(teams[:2]):
            text = results[i] if i < len(results) else ""
            data["morale"][team]   = text[:500]
            data["momentum"][team] = self._score_momentum(text)

        return data

    def _score_momentum(self, text: str) -> str:
        pos = ["win", "victory", "unbeaten", "confident", "dominant", "scored", "form"]
        neg = ["loss", "defeat", "crisis", "sacked", "struggling", "poor", "injury"]
        score = sum(1 for w in pos if w in text.lower()) - \
                sum(1 for w in neg if w in text.lower())
        if score >= 2:  return "Positive ↑"
        if score <= -2: return "Negative ↓"
        return "Neutral →"

    # ── ESPN FREE APIs ─────────────────────────────────────────────────────────

    async def _espn_team(self, team: str, sport: str) -> str:
        """ESPN has a hidden public API — no key needed."""
        sport_map = {
            "basketball": "basketball/nba",
            "american football": "football/nfl",
            "soccer": "soccer/eng.1",
            "baseball": "baseball/mlb",
            "ice hockey": "hockey/nhl",
        }
        league = sport_map.get(sport, "basketball/nba")
        try:
            async with httpx.AsyncClient(timeout=10, headers=HEADERS) as client:
                # Search ESPN for the team
                resp = await client.get(
                    f"https://site.api.espn.com/apis/site/v2/sports/{league}/teams",
                    params={"limit": 100}
                )
                teams_data = resp.json().get("sports", [{}])[0].get("leagues", [{}])[0].get("teams", [])
                team_lower = team.lower()
                for t in teams_data:
                    t_info = t.get("team", {})
                    name = t_info.get("displayName", "").lower()
                    if team_lower in name or any(w in name for w in team_lower.split()):
                        tid = t_info.get("id")
                        # Get team stats
                        stats = await client.get(
                            f"https://site.api.espn.com/apis/site/v2/sports/{league}/teams/{tid}"
                        )
                        s = stats.json().get("team", {})
                        record = s.get("record", {}).get("items", [{}])[0]
                        summary = record.get("summary", "No record data")
                        return f"{t_info.get('displayName')} | Record: {summary}"
            return ""
        except Exception:
            return ""

    async def _espn_standings(self, sport: str) -> str:
        sport_map = {
            "basketball": "basketball/nba",
            "american football": "football/nfl",
            "soccer": "soccer/eng.1",
            "baseball": "baseball/mlb",
            "ice hockey": "hockey/nhl",
        }
        league = sport_map.get(sport, "basketball/nba")
        try:
            async with httpx.AsyncClient(timeout=10, headers=HEADERS) as client:
                resp = await client.get(
                    f"https://site.api.espn.com/apis/v2/sports/{league}/standings"
                )
                groups = resp.json().get("children", [])
                lines = []
                for g in groups[:2]:
                    for entry in g.get("standings", {}).get("entries", [])[:5]:
                        team = entry.get("team", {}).get("displayName", "")
                        stats = entry.get("stats", [])
                        rec   = next((s["displayValue"] for s in stats if s.get("name") == "overall"), "")
                        lines.append(f"  {team}: {rec}")
                return "\n".join(lines[:10])
        except Exception:
            return ""

    async def _espn_injuries(self, team: str, sport: str) -> str:
        sport_map = {
            "basketball": "basketball/nba",
            "american football": "football/nfl",
            "soccer": "soccer/eng.1",
            "baseball": "baseball/mlb",
            "ice hockey": "hockey/nhl",
        }
        league = sport_map.get(sport, "basketball/nba")
        try:
            async with httpx.AsyncClient(timeout=10, headers=HEADERS) as client:
                resp = await client.get(
                    f"https://site.api.espn.com/apis/site/v2/sports/{league}/injuries"
                )
                injuries = resp.json().get("injuries", [])
                team_lower = team.lower()
                lines = []
                for inj in injuries:
                    t_name = inj.get("team", {}).get("displayName", "").lower()
                    if team_lower in t_name or any(w in t_name for w in team_lower.split()):
                        for p in inj.get("injuries", [])[:5]:
                            lines.append(
                                f"  {p.get('athlete',{}).get('displayName','?')} — "
                                f"{p.get('type','?')} ({p.get('status','?')})"
                            )
                return "\n".join(lines) if lines else "No injury data found"
        except Exception:
            return ""

    async def _sportsdb_team(self, team: str) -> str:
        """TheSportsDB free API — no key needed for basic data."""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    "https://www.thesportsdb.com/api/v1/json/3/searchteams.php",
                    params={"t": team}
                )
                teams = resp.json().get("teams", []) or []
                if not teams:
                    return ""
                t = teams[0]
                return (
                    f"Team: {t.get('strTeam')}\n"
                    f"League: {t.get('strLeague')}\n"
                    f"Stadium: {t.get('strStadium')}\n"
                    f"Stadium capacity: {t.get('intStadiumCapacity')}\n"
                    f"Description: {(t.get('strDescriptionEN') or '')[:300]}"
                )
        except Exception:
            return ""

    async def _wiki_stats(self, query: str, sport: str) -> str:
        """Wikipedia for deep historical stats."""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                search = await client.get(
                    "https://en.wikipedia.org/w/api.php",
                    params={"action": "query", "list": "search",
                            "srsearch": query, "format": "json", "srlimit": 2}
                )
                results = search.json()["query"]["search"]
                if not results:
                    return ""
                title = results[0]["title"]
                extract = await client.get(
                    "https://en.wikipedia.org/w/api.php",
                    params={"action": "query", "prop": "extracts",
                            "exintro": True, "explaintext": True,
                            "titles": title, "format": "json"}
                )
                pages = extract.json()["query"]["pages"]
                text  = next(iter(pages.values())).get("extract", "")
                return text[:1000]
        except Exception:
            return ""

    async def _weather(self, location: str) -> dict:
        """Open-Meteo — completely free, no key."""
        try:
            async with httpx.AsyncClient(timeout=8) as client:
                geo = await client.get(
                    "https://geocoding-api.open-meteo.com/v1/search",
                    params={"name": location, "count": 1}
                )
                results = geo.json().get("results", [])
                if not results:
                    return {}
                lat = results[0]["latitude"]
                lon = results[0]["longitude"]
                w = await client.get(
                    "https://api.open-meteo.com/v1/forecast",
                    params={
                        "latitude": lat, "longitude": lon,
                        "current": "temperature_2m,wind_speed_10m,precipitation,weathercode",
                        "wind_speed_unit": "mph",
                    }
                )
                cur = w.json().get("current", {})
                codes = {0:"Clear",1:"Mostly clear",2:"Partly cloudy",3:"Overcast",
                         51:"Drizzle",61:"Rain",71:"Snow",80:"Showers",95:"Thunderstorm"}
                code = cur.get("weathercode", 0)
                return {
                    "condition": codes.get(code, "Unknown"),
                    "temp_c":    cur.get("temperature_2m"),
                    "wind_mph":  cur.get("wind_speed_10m"),
                    "rain_mm":   cur.get("precipitation", 0),
                }
        except Exception:
            return {}

    # ── SYNTHESIS ─────────────────────────────────────────────────────────────

    async def _synthesise(self, query, sport, teams, perf, ctx, health, psych) -> str:
        learning = self._get_learning_notes()

        def safe(d, key, limit=300):
            val = d.get(key, "")
            if isinstance(val, dict):
                return json.dumps({k: str(v)[:limit] for k,v in val.items()})
            return str(val)[:limit]

        prompt = f"""You are Jerry — Tom's elite sports intelligence AI.
Analyse all 4 layers and give Tom the sharpest possible prediction.

QUERY: {query}
Sport: {sport} | Teams: {', '.join(teams) or 'analyse from query'}

━━ LAYER 1 — PERFORMANCE ━━
ESPN data: {safe(perf,'espn')}
SportsDB: {safe(perf,'sportsdb')}
Historical/H2H: {safe(perf,'wiki_h2h')}

━━ LAYER 2 — CONTEXT ━━
Current standings: {safe(ctx,'standings')}
Game importance: {safe(ctx,'importance')}
Weather: {json.dumps(ctx.get('weather',{}))}

━━ LAYER 3 — HEALTH ━━
Injuries: {safe(health,'injuries')}
Fatigue: {json.dumps(health.get('fatigue',{}))}

━━ LAYER 4 — PSYCHOLOGY ━━
Momentum: {json.dumps(psych.get('momentum',{}))}
Morale: {safe(psych,'morale')}

━━ PAST LEARNING ━━
{learning or 'No past predictions yet.'}

Give Tom this exact format:

MATCH OVERVIEW
[teams, sport, context]

LAYER BREAKDOWN
[one key insight per layer]

KEY DECIDING FACTORS
[the 2-3 things that will determine the result]

INJURY / FATIGUE WATCH
[flag missing players or tired squads]

PREDICTION
[Winner + expected margin/scoreline]
Confidence: Low/Medium/High — one sentence reason

RISK FLAGS
[what could make this wrong — be honest]

Talk to Tom directly. Sharp and analytical."""

        return chat(
            [{"role": "user", "content": prompt}],
            system="You are Jerry, Tom's sports intelligence AI. Be sharp, direct and data-driven."
        )

    # ── ALERTS, LEARNING, UTILS ───────────────────────────────────────────────

    def _build_alerts(self, health, ctx, psych) -> list:
        alerts = []
        for team, level in health.get("fatigue", {}).items():
            if "HIGH" in level:
                alerts.append(f"{team} is HIGH fatigue — rotation risk is real.")
        for team in psych.get("momentum", {}):
            if "Negative" in psych["momentum"].get(team, ""):
                inj = health.get("injuries", {}).get(team, "")
                if len(inj) > 60:
                    alerts.append(f"{team}: negative momentum + injuries = double red flag.")
        weather = ctx.get("weather", {})
        wind = weather.get("wind_mph", 0) or 0
        rain = weather.get("rain_mm", 0) or 0
        if wind > 25:
            alerts.append(f"Wind {wind}mph — will affect shooting and passing accuracy.")
        if rain > 5:
            alerts.append(f"Heavy rain {rain}mm — favours physical teams.")
        return alerts

    def _log_prediction(self, query, sport, teams, prediction):
        pred_id = hashlib.md5(f"{datetime.now()}{query}".encode()).hexdigest()[:8]
        self.predictions_log.append({
            "id": pred_id, "timestamp": datetime.now().isoformat(),
            "query": query, "sport": sport, "teams": teams,
            "prediction": prediction[:400], "outcome": None, "correct": None,
        })
        self._save_predictions()
        return pred_id

    def update_outcome(self, pred_id: str, actual: str, correct: bool):
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
        summary = "\n".join(
            f"- {p['timestamp'][:10]} | {p.get('sport')} | {p.get('query')} | "
            f"Predicted: {p['prediction'][:80]} | Actual: {p.get('outcome','?')}"
            for p in wrong[-5:]
        )
        notes = chat(
            [{"role": "user", "content":
              f"You are Jerry reviewing past sports prediction mistakes. "
              f"Write 3-5 short lessons to improve:\n\n{summary}"}],
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

    def _parse_query(self, query: str) -> tuple:
        lower = query.lower()
        sport_map = {
            "nba": "basketball", "basketball": "basketball",
            "lakers": "basketball", "celtics": "basketball",
            "warriors": "basketball", "heat": "basketball",
            "nfl": "american football", "premier league": "soccer",
            "champions league": "soccer", "la liga": "soccer",
            "soccer": "soccer", "football": "soccer",
            "mlb": "baseball", "nhl": "ice hockey",
        }
        sport = "basketball"
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
            skip = {"Predict","Game","Match","Jerry","Tom","Tonight","Sports","Analysis","NBA","NFL"}
            teams = [c for c in caps if c not in skip][:2]
        return sport, teams

    def _load_predictions(self) -> list:
        if PREDICTIONS_DB.exists():
            try:
                return json.loads(PREDICTIONS_DB.read_text())
            except Exception:
                return []
        return []

    def _save_predictions(self):
        PREDICTIONS_DB.write_text(json.dumps(self.predictions_log, indent=2))
