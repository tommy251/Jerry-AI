"""
Jerry's Sports Intelligence Engine - REBUILT
Real data sources:
1. Ball Don't Lie API v1 (free, no key) — real NBA scores/schedules
2. ESPN hidden public API — standings and injuries  
3. TheSportsDB — team info
4. Open-Meteo — weather
5. Wikipedia — H2H history

STRICT RULE: Never hallucinate matches. Only report what the APIs return.
"""

import re
import json
import hashlib
import asyncio
import httpx
from datetime import datetime, timedelta
from pathlib import Path
from .brain import chat

DATA_DIR       = Path(__file__).parent.parent / "data"
PREDICTIONS_DB = DATA_DIR / "predictions_log.json"
DATA_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; JerryAI/1.0)",
    "Accept": "application/json",
}


class SportsAgent:
    def __init__(self):
        self.predictions_log = self._load_predictions()

    async def initialize(self):
        await self._review_past_predictions()

    async def run(self, query: str) -> str:
        lower = query.lower()

        # Detect intent
        wants_schedule = any(w in lower for w in [
            "today", "tomorrow", "tonight", "schedule", "games", "matches",
            "playing", "fixture", "upcoming", "this week", "march", "april"
        ])
        wants_prediction = any(w in lower for w in [
            "predict", "who will win", "vs", "versus", "against", "winner",
            "chance", "odds", "bet", "forecast"
        ])
        wants_standings = any(w in lower for w in [
            "standings", "table", "ranking", "top team", "best team", "record"
        ])

        sport, teams = self._parse_query(query)

        if wants_schedule and not wants_prediction:
            return await self._get_schedule(query, sport)

        if wants_standings:
            return await self._get_standings(sport)

        if wants_prediction or teams:
            return await self._full_prediction(query, sport, teams)

        # Default: schedule + quick context
        return await self._get_schedule(query, sport)

    # ── REAL SCHEDULE FROM BALL DON'T LIE ─────────────────────────────────────

    async def _get_schedule(self, query: str, sport: str) -> str:
        """Fetch real game schedule — never hallucinate."""

        # Determine target date
        lower = query.lower()
        today = datetime.now()
        if "tomorrow" in lower:
            target = today + timedelta(days=1)
        elif "yesterday" in lower:
            target = today - timedelta(days=1)
        else:
            target = today

        date_str = target.strftime("%Y-%m-%d")
        display  = target.strftime("%B %d, %Y")

        if "basketball" in sport or sport == "basketball" or "nba" in lower:
            games = await self._balldontlie_games(date_str)
            if games is None:
                return f"Jerry: API is down right now — can't fetch the schedule. Try again in a moment."
            if not games:
                return f"No NBA games scheduled for {display}. It may be a rest day or off-season."

            lines = [f"🏀 NBA Games — {display}\n"]
            for g in games:
                home = g["home_team"]["full_name"]
                away = g["visitor_team"]["full_name"]
                status = g.get("status", "")
                hs = g.get("home_team_score", 0)
                vs = g.get("visitor_team_score", 0)

                if status == "Final":
                    lines.append(f"  ✅ {away} {vs} @ {home} {hs} — FINAL")
                elif status and status not in ["", "scheduled"]:
                    lines.append(f"  🔴 LIVE: {away} {vs} @ {home} {hs} — {status}")
                else:
                    time_str = g.get("time", "TBD")
                    lines.append(f"  🕐 {away} @ {home} — {time_str} ET")

            result = "\n".join(lines)

            # Ask Jerry to add context
            commentary = chat(
                [{"role": "user", "content":
                  f"These are the REAL NBA games for {display}:\n{result}\n\n"
                  f"Tom asked: '{query}'\n\n"
                  f"Add brief context about the most interesting matchups. "
                  f"Do NOT invent scores or details not in the data above."}],
                system="You are Jerry, Tom's sports AI. Only comment on real data provided. Never invent games or scores."
            )
            return result + "\n\n" + commentary

        elif "soccer" in sport or "football" in sport:
            return await self._soccer_schedule(date_str, display)

        else:
            return f"Jerry: I have live NBA schedules via Ball Don't Lie API. For other sports, ask specifically and I'll pull what I can."

    async def _balldontlie_games(self, date: str):
        """Ball Don't Lie free API — real NBA game data, no key needed."""
        try:
            async with httpx.AsyncClient(timeout=15, headers=HEADERS) as client:
                resp = await client.get(
                    "https://api.balldontlie.io/v1/games",
                    params={"dates[]": date, "per_page": 30},
                )
                if resp.status_code == 200:
                    return resp.json().get("data", [])
                return None
        except Exception:
            return None

    async def _soccer_schedule(self, date_str: str, display: str) -> str:
        """TheSportsDB free events by date."""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"https://www.thesportsdb.com/api/v1/json/3/eventsday.php",
                    params={"d": date_str, "s": "Soccer"}
                )
                events = resp.json().get("events") or []
                if not events:
                    return f"No soccer matches found for {display}."
                lines = [f"⚽ Soccer — {display}\n"]
                for e in events[:15]:
                    home  = e.get("strHomeTeam", "?")
                    away  = e.get("strAwayTeam", "?")
                    league = e.get("strLeague", "")
                    time  = e.get("strTime", "TBD")
                    lines.append(f"  {home} vs {away} — {league} ({time})")
                return "\n".join(lines)
        except Exception:
            return "Soccer schedule unavailable right now."

    # ── STANDINGS ─────────────────────────────────────────────────────────────

    async def _get_standings(self, sport: str) -> str:
        try:
            async with httpx.AsyncClient(timeout=10, headers=HEADERS) as client:
                sport_map = {
                    "basketball": "basketball/nba",
                    "american football": "football/nfl",
                    "soccer": "soccer/eng.1",
                    "baseball": "baseball/mlb",
                    "ice hockey": "hockey/nhl",
                }
                league = sport_map.get(sport, "basketball/nba")
                resp = await client.get(
                    f"https://site.api.espn.com/apis/v2/sports/{league}/standings"
                )
                groups = resp.json().get("children", [])
                lines = []
                for g in groups[:2]:
                    conf = g.get("name", "")
                    if conf:
                        lines.append(f"\n{conf}:")
                    for entry in g.get("standings", {}).get("entries", [])[:8]:
                        team = entry.get("team", {}).get("displayName", "")
                        stats = entry.get("stats", [])
                        rec   = next((s["displayValue"] for s in stats if s.get("name") == "overall"), "")
                        pct   = next((s["displayValue"] for s in stats if s.get("name") == "winPercent"), "")
                        lines.append(f"  {team}: {rec} ({pct})")
                if not lines:
                    return "Standings unavailable right now."
                return "\n".join(lines)
        except Exception:
            return "Standings unavailable right now."

    # ── FULL 4-LAYER PREDICTION ────────────────────────────────────────────────

    async def _full_prediction(self, query: str, sport: str, teams: list) -> str:
        # First get real schedule to confirm the matchup exists
        today = datetime.now().strftime("%Y-%m-%d")
        real_games = await self._balldontlie_games(today) or []

        confirmed_matchup = ""
        for g in real_games:
            home = g["home_team"]["full_name"].lower()
            away = g["visitor_team"]["full_name"].lower()
            for team in teams:
                if team.lower() in home or team.lower() in away:
                    confirmed_matchup = f"{g['visitor_team']['full_name']} @ {g['home_team']['full_name']}"
                    break

        # Run 4 layers in parallel
        perf, ctx, health, psych = await asyncio.gather(
            self._layer_1_performance(sport, teams),
            self._layer_2_context(sport, teams),
            self._layer_3_health(sport, teams),
            self._layer_4_psychology(sport, teams),
        )

        prediction = await self._synthesise(
            query, sport, teams, perf, ctx, health, psych, confirmed_matchup
        )
        self._log_prediction(query, sport, teams, prediction)

        alerts = self._build_alerts(health, ctx, psych)
        result = prediction
        if alerts:
            result += "\n\n" + "━" * 48
            result += "\n🔔 JERRY ALERT — Tom:\n"
            result += "\n".join(f"  ⚠  {a}" for a in alerts)

        accuracy = self._accuracy_summary()
        if accuracy:
            result += f"\n\n[Jerry's track record: {accuracy}]"

        return result

    # ── 4 LAYERS ──────────────────────────────────────────────────────────────

    async def _layer_1_performance(self, sport: str, teams: list) -> dict:
        data = {"espn": {}, "sportsdb": {}, "h2h": ""}
        tasks = []
        for team in teams[:2]:
            tasks.append(self._espn_team_record(team, sport))
            tasks.append(self._sportsdb_team(team))
        if len(teams) >= 2:
            tasks.append(self._wiki(f"{teams[0]} vs {teams[1]} head to head NBA history"))
        results = await asyncio.gather(*tasks)
        idx = 0
        for i, team in enumerate(teams[:2]):
            data["espn"][team]    = results[idx] if idx < len(results) else ""; idx += 1
            data["sportsdb"][team]= results[idx] if idx < len(results) else ""; idx += 1
        if len(teams) >= 2 and idx < len(results):
            data["h2h"] = results[idx]
        return data

    async def _layer_2_context(self, sport: str, teams: list) -> dict:
        standings = await self._get_standings(sport)
        weather   = await self._weather(teams[0] if teams else "New York")
        return {"standings": standings, "weather": weather}

    async def _layer_3_health(self, sport: str, teams: list) -> dict:
        data = {"injuries": {}, "fatigue": {}}
        tasks = [self._espn_injuries(t, sport) for t in teams[:2]]
        results = await asyncio.gather(*tasks)
        for i, team in enumerate(teams[:2]):
            inj = results[i] if i < len(results) else ""
            data["injuries"][team] = inj
            data["fatigue"][team]  = self._estimate_fatigue(inj)
        return data

    async def _layer_4_psychology(self, sport: str, teams: list) -> dict:
        data = {"momentum": {}, "news": {}}
        tasks = [self._wiki(f"{t} {sport} 2025 2026 form recent results") for t in teams[:2]]
        results = await asyncio.gather(*tasks)
        for i, team in enumerate(teams[:2]):
            text = results[i] if i < len(results) else ""
            data["news"][team]     = text[:400]
            data["momentum"][team] = self._score_momentum(text)
        return data

    def _estimate_fatigue(self, text: str) -> str:
        markers = ["back-to-back", "3 games", "4 games", "days ago", "yesterday"]
        hits = sum(1 for m in markers if m in text.lower())
        if hits >= 2: return "HIGH ⚠"
        if hits == 1: return "MODERATE"
        return "LOW"

    def _score_momentum(self, text: str) -> str:
        pos = ["win", "victory", "dominant", "unbeaten", "confident", "streak"]
        neg = ["loss", "defeat", "slump", "struggling", "crisis", "injured"]
        score = sum(1 for w in pos if w in text.lower()) - \
                sum(1 for w in neg if w in text.lower())
        if score >= 2:  return "Positive ↑"
        if score <= -2: return "Negative ↓"
        return "Neutral →"

    # ── ESPN FREE APIs ─────────────────────────────────────────────────────────

    async def _espn_team_record(self, team: str, sport: str) -> str:
        sport_path = {
            "basketball": "basketball/nba", "american football": "football/nfl",
            "soccer": "soccer/eng.1", "baseball": "baseball/mlb", "ice hockey": "hockey/nhl",
        }.get(sport, "basketball/nba")
        try:
            async with httpx.AsyncClient(timeout=10, headers=HEADERS) as client:
                resp = await client.get(
                    f"https://site.api.espn.com/apis/site/v2/sports/{sport_path}/teams",
                    params={"limit": 100}
                )
                teams_list = (resp.json().get("sports", [{}])[0]
                              .get("leagues", [{}])[0].get("teams", []))
                tl = team.lower()
                for t in teams_list:
                    info = t.get("team", {})
                    name = info.get("displayName", "").lower()
                    if tl in name or any(w in name for w in tl.split()):
                        tid  = info.get("id")
                        det  = await client.get(
                            f"https://site.api.espn.com/apis/site/v2/sports/{sport_path}/teams/{tid}"
                        )
                        rec = (det.json().get("team", {})
                               .get("record", {}).get("items", [{}])[0]
                               .get("summary", "N/A"))
                        return f"{info.get('displayName')} — Record: {rec}"
            return ""
        except Exception:
            return ""

    async def _espn_injuries(self, team: str, sport: str) -> str:
        sport_path = {
            "basketball": "basketball/nba", "american football": "football/nfl",
            "soccer": "soccer/eng.1", "baseball": "baseball/mlb", "ice hockey": "hockey/nhl",
        }.get(sport, "basketball/nba")
        try:
            async with httpx.AsyncClient(timeout=10, headers=HEADERS) as client:
                resp = await client.get(
                    f"https://site.api.espn.com/apis/site/v2/sports/{sport_path}/injuries"
                )
                injuries = resp.json().get("injuries", [])
                tl = team.lower()
                lines = []
                for inj in injuries:
                    tname = inj.get("team", {}).get("displayName", "").lower()
                    if tl in tname or any(w in tname for w in tl.split()):
                        for p in inj.get("injuries", [])[:5]:
                            lines.append(
                                f"  {p.get('athlete',{}).get('displayName','?')} — "
                                f"{p.get('type','?')} ({p.get('status','?')})"
                            )
                return "\n".join(lines) if lines else "No injury report found."
        except Exception:
            return "Injury data unavailable."

    async def _sportsdb_team(self, team: str) -> str:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    "https://www.thesportsdb.com/api/v1/json/3/searchteams.php",
                    params={"t": team}
                )
                teams = resp.json().get("teams") or []
                if not teams:
                    return ""
                t = teams[0]
                return (f"{t.get('strTeam')} | {t.get('strLeague')} | "
                        f"Stadium: {t.get('strStadium')} | "
                        f"{(t.get('strDescriptionEN') or '')[:200]}")
        except Exception:
            return ""

    async def _wiki(self, query: str) -> str:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                s = await client.get(
                    "https://en.wikipedia.org/w/api.php",
                    params={"action":"query","list":"search","srsearch":query,
                            "format":"json","srlimit":1}
                )
                results = s.json()["query"]["search"]
                if not results:
                    return ""
                title = results[0]["title"]
                e = await client.get(
                    "https://en.wikipedia.org/w/api.php",
                    params={"action":"query","prop":"extracts","exintro":True,
                            "explaintext":True,"titles":title,"format":"json"}
                )
                pages = e.json()["query"]["pages"]
                return next(iter(pages.values())).get("extract","")[:800]
        except Exception:
            return ""

    async def _weather(self, location: str) -> dict:
        try:
            async with httpx.AsyncClient(timeout=8) as client:
                geo = await client.get(
                    "https://geocoding-api.open-meteo.com/v1/search",
                    params={"name": location, "count": 1}
                )
                r = geo.json().get("results", [])
                if not r:
                    return {}
                w = await client.get(
                    "https://api.open-meteo.com/v1/forecast",
                    params={"latitude": r[0]["latitude"], "longitude": r[0]["longitude"],
                            "current": "temperature_2m,wind_speed_10m,precipitation",
                            "wind_speed_unit": "mph"}
                )
                c = w.json().get("current", {})
                return {"temp_c": c.get("temperature_2m"),
                        "wind_mph": c.get("wind_speed_10m"),
                        "rain_mm": c.get("precipitation", 0)}
        except Exception:
            return {}

    # ── SYNTHESIS ─────────────────────────────────────────────────────────────

    async def _synthesise(self, query, sport, teams, perf, ctx, health, psych, confirmed_matchup) -> str:
        learning = self._get_learning_notes()

        prompt = f"""You are Jerry — Tom's elite sports AI.

STRICT RULES:
- NEVER invent scores, records, or player stats not in the data below
- If data is missing, say "no data available" — do NOT guess
- Only predict matchups that are confirmed or explicitly asked about

QUERY: {query}
Sport: {sport} | Teams: {', '.join(teams) or 'from query'}
Confirmed today's matchup: {confirmed_matchup or 'Not confirmed in today schedule — predicting based on historical data'}

━━ LAYER 1 — PERFORMANCE ━━
Records: {json.dumps({k: v[:200] for k,v in perf.get('espn',{}).items()})}
H2H history: {perf.get('h2h','N/A')[:400]}

━━ LAYER 2 — CONTEXT ━━
Standings: {str(ctx.get('standings',''))[:600]}
Weather: {json.dumps(ctx.get('weather',{}))}

━━ LAYER 3 — HEALTH ━━
Injuries: {json.dumps({k: v[:250] for k,v in health.get('injuries',{}).items()})}
Fatigue: {json.dumps(health.get('fatigue',{}))}

━━ LAYER 4 — PSYCHOLOGY ━━
Momentum: {json.dumps(psych.get('momentum',{}))}

━━ PAST LEARNING ━━
{learning or 'No past predictions yet.'}

FORMAT:
MATCH OVERVIEW
LAYER BREAKDOWN (one insight per layer — only from real data above)
KEY DECIDING FACTORS
INJURY / FATIGUE WATCH
PREDICTION: Winner + margin
Confidence: Low/Medium/High
RISK FLAGS"""

        return chat(
            [{"role": "user", "content": prompt}],
            system="You are Jerry. Only use real data provided. Never hallucinate stats, scores or games. If data is missing say so."
        )

    # ── ALERTS ────────────────────────────────────────────────────────────────

    def _build_alerts(self, health, ctx, psych) -> list:
        alerts = []
        for team, level in health.get("fatigue", {}).items():
            if "HIGH" in str(level):
                alerts.append(f"{team} HIGH fatigue — rotation risk.")
        for team, momentum in psych.get("momentum", {}).items():
            if "Negative" in str(momentum):
                alerts.append(f"{team} on negative momentum — watch out.")
        weather = ctx.get("weather", {})
        if isinstance(weather.get("wind_mph"), (int, float)) and weather["wind_mph"] > 25:
            alerts.append(f"High winds {weather['wind_mph']}mph — affects outdoor sports.")
        return alerts

    # ── SELF-LEARNING ─────────────────────────────────────────────────────────

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
              f"You are Jerry reviewing past sports mistakes. Write 3-5 lessons:\n\n{summary}"}],
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
            "knicks": "basketball", "bulls": "basketball",
            "nfl": "american football", "premier league": "soccer",
            "champions league": "soccer", "la liga": "soccer",
            "soccer": "soccer", "mlb": "baseball", "nhl": "ice hockey",
        }
        sport = "basketball"
        for kw, sp in sport_map.items():
            if kw in lower:
                sport = sp
                break

        teams = []
        vs_match = re.search(
            r'([\w\s]+?)\s+(?:vs\.?|versus|against)\s+([\w\s]+?)(?:\s+(?:predict|game|match|tonight|today)|$)',
            query, re.I
        )
        if vs_match:
            teams = [vs_match.group(1).strip(), vs_match.group(2).strip()]
        else:
            caps = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?\b', query)
            skip = {"Predict","Game","Match","Jerry","Tom","Tonight","Today","Sports","NBA","NFL","Tell","Show","Get","All"}
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
