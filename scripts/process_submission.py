#!/usr/bin/env python3
"""Parse a Table Predictions submission issue, validate it, and (if valid)
write it into data/submissions.csv - or comment back explaining exactly
what's wrong so the submitter can fix it; editing the issue re-triggers
this same check.

Run by .github/workflows/process-submission.yml on issue open/edit. Uses
`gh` (pre-authenticated inside Actions via GH_TOKEN) for comments/labels,
and plain git for the commit - both already have everything they need
from the workflow's default GITHUB_TOKEN, no extra secrets required.
"""
import csv
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SUBMISSION_LABEL = "table-prediction-submission"
RECORDED_LABEL = "recorded"


def read_csv(path):
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def gh(*args):
    return subprocess.run(["gh", *args], capture_output=True, text=True)


def comment(issue_number, body):
    gh("issue", "comment", issue_number, "--body", body)


def parse_issue_body(body):
    """### <label incl. [[key]]>\n\n<value>\n\n... -> {key: value}"""
    answers = {}
    for sec in re.split(r"(?m)^### ", body)[1:]:
        lines = sec.split("\n", 1)
        label = lines[0].strip()
        value = (lines[1] if len(lines) > 1 else "").strip()
        m = re.search(r"\[\[([^\]]+)\]\]", label)
        if not m:
            continue
        answers[m.group(1)] = "" if value == "_No response_" else value
    return answers


def main():
    issue_number = os.environ["ISSUE_NUMBER"]

    res = gh("issue", "view", issue_number, "--json", "body,labels")
    if res.returncode != 0:
        sys.exit(f"Couldn't fetch issue #{issue_number}: {res.stderr}")
    issue = json.loads(res.stdout)
    if not any(l["name"] == SUBMISSION_LABEL for l in issue["labels"]):
        print(f"Issue #{issue_number} doesn't have the '{SUBMISSION_LABEL}' label - ignoring.")
        return

    current_season_file = DATA / "current-season.txt"
    season = current_season_file.read_text(encoding="utf-8").strip() if current_season_file.exists() else ""
    if not season:
        comment(issue_number, "Predictions aren't open right now (no season is currently active). Try again from August 1st.")
        return

    teams = [t for t in read_csv(DATA / "standings.csv") if t["season"] == season]
    if not teams:
        comment(issue_number, "Predictions aren't open yet for this season (the team list hasn't been fetched). Try again from August 1st.")
        return

    deadline_file = DATA / "deadline.txt"
    deadline_str = deadline_file.read_text(encoding="utf-8").strip() if deadline_file.exists() else ""
    if deadline_str:
        deadline = datetime.fromisoformat(deadline_str)
        if datetime.now(timezone.utc) > deadline:
            comment(issue_number, "Predictions closed when the season's first match kicked off - this entry can no longer be recorded or changed. Whatever was recorded before kickoff stands.")
            return

    answers = parse_issue_body(issue["body"] or "")
    errors = []

    player_name = answers.get("player_name", "").strip()
    if not player_name:
        errors.append("Missing your name.")

    by_abbr = {t["team_abbr"].strip().upper(): t for t in teams}
    order_lines = [l.strip().upper() for l in answers.get("order", "").strip().splitlines() if l.strip()]

    if len(order_lines) != 20:
        errors.append(f"Predicted table must have exactly 20 teams, one per line (found {len(order_lines)}).")
    elif len(set(order_lines)) != 20:
        errors.append("Every team must appear exactly once - found a duplicate.")
    else:
        unknown = [l for l in order_lines if l not in by_abbr]
        if unknown:
            errors.append(f"Not a team playing this season: {', '.join(unknown)}.")

    if errors:
        body = "Couldn't record this prediction yet:\n\n" + "\n".join(f"- {e}" for e in errors) + \
               "\n\nEdit this issue to fix them - it'll be re-checked automatically."
        comment(issue_number, body)
        gh("issue", "edit", issue_number, "--remove-label", RECORDED_LABEL)
        return

    team_ids = [by_abbr[abbr]["team_id"] for abbr in order_lines]

    now = datetime.now(timezone.utc).isoformat()
    sub_path = DATA / "submissions.csv"
    header = ["season", "player_name", "submitted_at", "order", "issue_number"]
    existing = read_csv(sub_path)
    kept = [[r.get(h, "") for h in header] for r in existing if r.get("issue_number") != issue_number]
    new_row = [season, player_name, now, ";".join(team_ids), issue_number]
    all_rows = kept + [new_row]

    with sub_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(header)
        w.writerows(all_rows)

    subprocess.run(["git", "config", "user.name", "github-actions[bot]"], cwd=ROOT, check=True)
    subprocess.run(["git", "config", "user.email", "github-actions[bot]@users.noreply.github.com"], cwd=ROOT, check=True)
    subprocess.run(["git", "add", "data/submissions.csv"], cwd=ROOT, check=True)
    commit = subprocess.run(["git", "commit", "-m", f"Prediction: {player_name} ({season}) via #{issue_number}"], cwd=ROOT, capture_output=True, text=True)
    if commit.returncode == 0:
        subprocess.run(["git", "push"], cwd=ROOT, check=True)

    comment(issue_number, f"Recorded! **{player_name}**'s predicted table for {season} is saved. Edit this issue any time before kickoff to update it.")
    gh("issue", "edit", issue_number, "--add-label", RECORDED_LABEL)


if __name__ == "__main__":
    main()
