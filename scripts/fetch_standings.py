#!/usr/bin/env python3
"""Refresh the current season's live table. Runs daily at 00:00 UTC.

Overwrites data/standings.csv's block for whatever season is named in
data/current-season.txt with the latest real Premier League table -
this is what makes the Overview tab's live standings and everyone's
golf-score-so-far change day to day as results come in.

Also re-derives data/deadline.txt (the season's first kickoff) every run,
even after the season has started - harmless once that fixture is in the
past, but self-corrects for a TV reschedule if this runs in the days
between fetch_new_season.py's Aug 1st fetch and the season actually
kicking off.
"""
import csv
import datetime
import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"


def fetch_json(url):
    headers = {"User-Agent": "table-predictions-sync/1.0"}
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def replace_season_block(csv_path, header, season, new_rows):
    existing = []
    if csv_path.exists():
        with csv_path.open(encoding="utf-8") as fh:
            existing = [row for row in csv.DictReader(fh) if row.get("season") != season]
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh, lineterminator="\n")
        writer.writerow(header)
        writer.writerows([row[h] for h in header] for row in existing)
        writer.writerows(new_rows)


def main():
    current_season_file = DATA / "current-season.txt"
    season = current_season_file.read_text(encoding="utf-8").strip() if current_season_file.exists() else ""
    if not season:
        print("current-season.txt is empty - no cycle open, skipping.")
        return

    comp_season_file = DATA / "comp-season-id.txt"
    if not comp_season_file.exists():
        print("comp-season-id.txt missing - nothing to fetch against, skipping.")
        return
    comp_season_id = comp_season_file.read_text(encoding="utf-8").strip()

    standings = fetch_json(
        f"https://footballapi.pulselive.com/football/standings?altIds=true&compSeasons={comp_season_id}"
    )
    tables = standings.get("tables", [])
    entries = tables[0]["entries"] if tables else []
    if len(entries) != 20:
        print(f"WARNING: expected 20 teams, got {len(entries)} - leaving standings.csv untouched.")
        return

    STANDINGS_HEADER = ["season", "team_id", "team_name", "team_abbr", "position",
                        "played", "won", "drawn", "lost", "gf", "ga", "gd", "points"]

    rows = []
    for e in sorted(entries, key=lambda e: e["position"]):
        club = e["team"].get("club", {})
        o = e["overall"]
        rows.append([
            season, int(e["team"]["id"]), e["team"]["name"], club.get("abbr", ""),
            e["position"], o["played"], o["won"], o["drawn"], o["lost"], o["goalsFor"], o["goalsAgainst"],
            o["goalsDifference"], o["points"],
        ])

    replace_season_block(DATA / "standings.csv", STANDINGS_HEADER, season, rows)
    print(f"{season}: refreshed standings for {len(rows)} teams.")

    fixtures = fetch_json(
        f"https://footballapi.pulselive.com/football/fixtures?comps=1"
        f"&compSeasons={comp_season_id}&page=0&pageSize=1&sort=asc&altIds=true"
    )["content"]
    if fixtures:
        kickoff_millis = fixtures[0]["kickoff"]["millis"]
        kickoff_iso = datetime.datetime.fromtimestamp(kickoff_millis / 1000, tz=datetime.timezone.utc).isoformat()
        (DATA / "deadline.txt").write_text(kickoff_iso, encoding="utf-8")
        print(f"deadline.txt refreshed to {kickoff_iso}.")


if __name__ == "__main__":
    main()
