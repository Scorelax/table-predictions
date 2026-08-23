# Table Predictions

**Live site:** https://scorelax.github.io/table-predictions/

A yearly pool where everyone predicts the Premier League's final table order.
Sibling site to [`boxing-day`](https://github.com/Scorelax/boxing-day) and
[`fpl-draft-stats`](https://github.com/Scorelax/fpl-draft-stats) — same
zero-backend, GitHub-only architecture, same visual design, linked together
via the shared header nav.

## The yearly cycle

1. **Aug 1, 06:00 UTC — `fetch_new_season.py`.** Fetches this season's 20
   Premier League clubs from `footballapi.pulselive.com`, seeds
   `data/standings.csv` with them (0 played, alphabetical order), points
   `data/current-season.txt` at the new season, and stores the season's
   first kickoff time in `data/deadline.txt`.
2. **Every day, 00:00 UTC — `fetch_standings.py`.** Refreshes the current
   season's block in `data/standings.csv` with the real table, and
   re-derives `data/deadline.txt` (self-correcting if the PL reschedules
   opening weekend for TV between Aug 1 and kickoff).
3. **On issue open/edit — `process_submission.py`.** Validates a prediction
   issue (see below) and records it — or comments back with what's wrong.
   Rejects anything after `data/deadline.txt`'s timestamp.

There's no separate "archive" step like `boxing-day` has. `data/standings.csv`
accumulates forever keyed by `season`, so the moment next year's Aug 1 job
rolls `current-season.txt` forward, whatever was last fetched for the
previous season simply stops being touched and stands as that season's
permanent final table — no explicit close/clear needed.

## Submitting a prediction

GitHub Issue Forms can't do drag-and-drop, so submitting is two steps:

1. On the site's **Edit form** tab, drag the 20 teams (or use the ↑/↓
   buttons) into your predicted final order.
2. Click **Submit on GitHub** — this opens a pre-filled issue (via a
   [query-param-prefilled issue form URL](https://docs.github.com/en/issues/tracking-your-work-with-issues/using-issues/creating-an-issue#creating-an-issue-from-a-url-query)),
   already carrying your name and order. Just hit Create.

To change a prediction before the deadline: rearrange the table again, hit
**Copy order text**, then paste it into the `order` field of your existing
issue (found via `author:@me` in the repo's issues, linked from the Edit
form tab) and save the edit — that re-triggers validation and re-records it.

## Scoring — golf rules

For each team: `abs(predicted_position - actual_position)`. Sum across all
20 teams. Lower is better; **0 is a perfect table**. Computed client-side
in `index.html` (`computeSeasonStandings`), continuously, from whatever
`data/standings.csv` currently shows — which is what makes the Overview
tab "live": it's exactly whatever the last daily fetch left behind.

## The Collective

`computeCollective()` blends every player's predicted rank per team (mean
of their predicted positions) into one composite table, re-ranks it, and
scores it the same golf way — a "wisdom of the crowd" read on the group's
picks, not a real submission. Rendered on every Overview/History table
alongside the real players' cards, purely derived from `submissions.csv` -
no separate data file.

## `data/standings.csv` schema

One file, two jobs: it's both the season's 20-team roster (seeded Aug 1)
and the live table (refreshed daily).

| column | meaning |
|---|---|
| `season` | e.g. `2027/28` |
| `team_id` | pulselive's team id — stable across seasons |
| `team_name` / `team_abbr` | e.g. `Arsenal` / `ARS` |
| `position` | 1–20; alphabetical rank at 0-played, real table position once matches are played |
| `played`, `won`, `drawn`, `lost`, `gf`, `ga`, `gd`, `points` | standard table columns |

A season counts as "complete" (eligible for the All-time tab) once every
row for it shows `played >= 38` — derived, no manual flag needed.

## `data/submissions.csv` schema

One row per **player per season** (not per-answer like `boxing-day`, since
there's only one thing being predicted here — the whole table).

| column | meaning |
|---|---|
| `season` | e.g. `2027/28` |
| `player_name` | as typed in the "Your name" field |
| `submitted_at` | ISO timestamp, updates on every valid edit |
| `order` | 20 `team_id`s joined with `;`, position 1 (predicted champion) first |
| `issue_number` | which issue this came from — editing that issue replaces this row, doesn't duplicate it |

## `data/deadline.txt` and `data/comp-season-id.txt`

`deadline.txt`: ISO timestamp of the current season's first kickoff —
`process_submission.py`'s hard cutoff. `comp-season-id.txt`: pulselive's
internal id for the current compSeason (looked up once by matching the
season's label string against `/football/competitions/1/compseasons`), so
`fetch_standings.py` doesn't have to re-resolve it every single day.

## Live match data

Same `footballapi.pulselive.com` source the `boxing-day` project uses —
undocumented, unofficial, no API key required. `/football/standings` gives
the full 20-team table (position, played/won/drawn/lost, goal difference,
points) for a given `compSeasons` id in one call; `/football/fixtures`
gives kickoff times. Since it's unofficial it could change or get blocked
without warning — low risk for a script that runs once a day, but worth
knowing.

## Status

Built and verified end-to-end, including real runs on GitHub's own
infrastructure (not just local testing):

- Both fetch scripts, via manually triggered `workflow_dispatch` runs -
  `fetch_new_season.py` and `fetch_standings.py` both successfully fetched
  real 2026/27 data, committed, and pushed.
- The full submission pipeline, against a real test issue -
  rejection while the deadline is in the future was correct (2026/27's
  actual kickoff already passed before this was built, so a submission was
  correctly rejected as closed); temporarily pushing a future test deadline
  and re-editing the same issue then recorded it correctly; a follow-up
  edit with a duplicate team was correctly rejected *without* touching the
  prior valid data; the `recorded` label was added and removed at the
  right times throughout. Test issue and test data were cleaned up
  afterward - `data/deadline.txt` is back to 2026/27's real (passed)
  kickoff time and `data/submissions.csv` was empty again afterward.
- The golf scoring math (a perfect prediction scores 0, a fully-reversed
  one scores 200 - the correct maximum for 20 teams) and `computeCollective`'s
  blended-table math, both cross-checked with a Python port against real data.

`data/standings.csv` holds real, live-fetched `2026/27` data (not test
data) - that season is already underway, so this repo's first real
*site-driven* prediction window (drag-and-drop → GitHub issue) is
`2027/28`, opening automatically next August 1st.

### `2026/27` predictions

Since this site didn't exist yet when `2026/27`'s window would have been
open, all 5 players' predictions (Kriss, Seb, Simon, Morten, Leo) were
imported by hand into `submissions.csv` (`issue_number: manual`, same
convention `boxing-day` uses for pre-site history) rather than submitted
through the real form. Team names were cross-checked against
`data/standings.csv` - all 20 valid, no duplicates, for every player.

Each player supplied their own golf score at prediction time (132, 130,
116, 126, 122) as a sanity check; recomputing against the table as it
stood when this was imported gave different numbers (138, 124, 124, 138,
126) for every player, by amounts too large and inconsistent to be a
transcription error. This is expected, not a bug: the golf score is
scored against a live, moving target, and only gameweek 1 had partially
played by the time of import (several clubs hadn't kicked off yet) - it
will keep drifting from whatever a player calculated by hand until the
table settles down.
