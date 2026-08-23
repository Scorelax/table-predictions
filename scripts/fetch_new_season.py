#!/usr/bin/env python3
"""Open a new Table Predictions cycle.

Meant to run once a year, Aug 1st - by then the Premier League's 20 clubs
for the upcoming season are settled (promotion/relegation confirmed) and
the opening weekend's fixtures are at least provisionally scheduled.
Writes:

  data/standings.csv    this season's 20 teams, seeded at 0 played -
                         doubles as both "the team pool" and "the live
                         table" once fetch_standings.py starts updating it
  data/current-season.txt   set to this season's string - the signal the
                             site uses for which season Edit form/Overview
                             default to
  data/deadline.txt          ISO timestamp of the season's first kickoff -
                              re-checked and refreshed daily by
                              fetch_standings.py in case the PL reschedules
                              opening weekend for TV between now and then

Unlike the sibling boxing-day project, there's no separate "archive"
script - data/standings.csv accumulates forever keyed by a `season`
column (see replace_season_block), so the moment this script rolls
current-season.txt to a new season, whatever was last fetched for the
previous season simply stops being touched and stands as that season's
permanent final table.
"""
import csv
import datetime
import json
import os
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"


def fetch_json(url):
    headers = {"User-Agent": "table-predictions-sync/1.0"}
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def target_year():
    override = os.environ.get("TABLE_PREDICTIONS_YEAR")
    if override:
        return int(override)
    return datetime.datetime.utcnow().year


def season_string(year):
    """The PL season that starts in <year> is <year>/<year+1>."""
    return f"{year}/{str(year + 1)[2:]}"


def find_comp_season_id(season):
    """The season string ("2027/28") isn't pulselive's own id - look it up
    by matching its season-name label across the compseasons listing."""
    label_year = season.split("/")[0]
    for page in range(0, 10):
        data = fetch_json(
            f"https://footballapi.pulselive.com/football/competitions/1/compseasons"
            f"?page={page}&pageSize=30&sort=desc"
        )
        content = data.get("content", [])
        if not content:
            break
        for entry in content:
            label = entry.get("label", "")
            if label_year in label and "/" in label:
                return int(entry["id"])
    return None


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


def fetch_first_kickoff(comp_season_id):
    fixtures = fetch_json(
        f"https://footballapi.pulselive.com/football/fixtures?comps=1"
        f"&compSeasons={comp_season_id}&page=0&pageSize=1&sort=asc&altIds=true"
    )["content"]
    if not fixtures:
        return None
    return fixtures[0]["kickoff"]["millis"]


def main():
    year = target_year()
    season = season_string(year)

    comp_season_id = find_comp_season_id(season)
    if comp_season_id is None:
        sys.exit(f"ERROR: couldn't find a pulselive compSeason id for {season} yet.")

    standings = fetch_json(
        f"https://footballapi.pulselive.com/football/standings?altIds=true&compSeasons={comp_season_id}"
    )
    tables = standings.get("tables", [])
    entries = tables[0]["entries"] if tables else []
    if len(entries) != 20:
        sys.exit(f"ERROR: expected 20 teams for {season}, got {len(entries)}. Has the season's club list been confirmed?")

    STANDINGS_HEADER = ["season", "team_id", "team_name", "team_abbr", "position",
                        "played", "won", "drawn", "lost", "gf", "ga", "gd", "points"]

    # Alphabetical by team name for the initial seed - matches/played is 0 for
    # everyone pre-season anyway, so "position" here is just alphabetical rank.
    teams_sorted = sorted(entries, key=lambda e: e["team"]["name"])
    rows = []
    for i, e in enumerate(teams_sorted, start=1):
        club = e["team"].get("club", {})
        o = e["overall"]
        rows.append([
            season, int(e["team"]["id"]), e["team"]["name"], club.get("abbr", ""),
            i, o["played"], o["won"], o["drawn"], o["lost"], o["goalsFor"], o["goalsAgainst"],
            o["goalsDifference"], o["points"],
        ])

    replace_season_block(DATA / "standings.csv", STANDINGS_HEADER, season, rows)
    print(f"{season}: wrote {len(rows)} teams to standings.csv (comp season id {comp_season_id}).")

    (DATA / "current-season.txt").write_text(season, encoding="utf-8")
    print(f"current-season.txt set to {season}.")

    (DATA / "comp-season-id.txt").write_text(str(comp_season_id), encoding="utf-8")

    kickoff_millis = fetch_first_kickoff(comp_season_id)
    if kickoff_millis is not None:
        kickoff_iso = datetime.datetime.fromtimestamp(kickoff_millis / 1000, tz=datetime.timezone.utc).isoformat()
        (DATA / "deadline.txt").write_text(kickoff_iso, encoding="utf-8")
        print(f"deadline.txt set to {kickoff_iso} (first fixture kickoff).")
    else:
        print("WARNING: no fixtures found yet to derive a deadline from - fetch_standings.py will keep retrying daily.")


if __name__ == "__main__":
    main()
