# ESPN League Export

This folder contains a local exporter for ESPN Fantasy Football league history.

## Setup

Create a `.env` file with:

```env
ESPN_LEAGUE_ID=18254195
ESPN_SWID={your-swid}
ESPN_S2=your-espn-s2
ESPN_START_YEAR=2020
ESPN_END_YEAR=2026
```

The `.env` file is ignored by git because `ESPN_S2` is a session token.

## Run

```bash
python3 export_espn_league.py
```

By default, files are written to:

```text
espn_exports/league_18254195/
```

The exporter writes raw season JSON plus summaries for easier review.

## Build Player Lookup

After the raw export exists, build the playerId lookup table:

```bash
python3 build_player_lookup.py
```

Outputs are written to:

```text
espn_exports/league_18254195/player_lookup/
```

Important files:

- `player_weekly_points.json` maps each ESPN `playerId` to player metadata and `weekly_points`.
- `player_weekly_points_flat.json` is a row-oriented version for easy import into pandas/Sheets/databases.
- `trade_player_coverage.json` reports whether traded players have names and weekly points available.
- `lookup_summary.json` contains counts and validation details.

## Build Trade Grades

After the player lookup exists, build the completed-trade grading table:

```bash
python3 build_trade_grades.py
```

Outputs are written to:

```text
espn_exports/league_18254195/trade_grades/
```

Important files:

- `trade_grades.csv` is the table-shaped export.
- `trade_grades_table.json` is the same row-oriented table in JSON.
- `trade_grades.json` keeps nested player details for each side of each trade.
- `trade_grades_summary.json` records filter counts and ungraded rows.
- `trade_grades_sample.json` contains the sample trades printed by the script.

The grader filters to `TRADE_ACCEPT` transactions with `status == EXECUTED`.
By default it scores each side from the week after the trade scoring period
through the end of that season. Pass `--include-trade-week` to count the trade
week itself.
