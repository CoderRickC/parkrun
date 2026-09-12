# parkrun

Scrapes parkrun.org.uk. Two independent scripts:

- `parkrun_athlete.py` — Richard's full results history (athlete **448437**).
  Runs on the Raspberry Pi via `run_weekly.sh` + cron, hourly 11:00-16:00 on
  Saturdays plus Christmas Day and New Year's Day. It commits and pushes `data/`
  only when a new parkrun appears, so only one of the six daily runs ever
  commits and a quiet week commits nothing. See `SETUP.md`.
- `parkrun_event_data.py` — one event's latest results (currently Stretford).
  Ad-hoc, not scheduled.

## Where the data is

`data/athlete_448437.json` is the canonical copy — read this one. Shape:

```
athlete_id, name, profile_url, fetched_at (UTC ISO — when the data last CHANGED)
total_parkruns, distinct_events
latest_run / first_run / personal_best   -> a single result object
summary_stats    { "Time": {fastest, average, slowest}, "Age Grading": {...} }
annual_bests     [ {year, best_time, best_age_grade} ]
event_counts     { "Stretford": 37, ... }   sorted most-run first
results          [ {event, date, run_number, position, time,
                    time_seconds, age_grade, pb} ]   newest first
```

Dates are ISO `yyyy-mm-dd` (parkrun serves `dd/mm/yyyy`; the script converts).
`time_seconds` is there so you can sort and average without re-parsing.
`results` is newest-first, so `results[0] == latest_run`.

The script fetches every week but only rewrites the files when the results
differ, so `fetched_at` is the date of the last *change*, not the last check —
check `logs/parkrun.log` to confirm the job is running. Pass `--force` to
rewrite regardless.

Also written, all derived from the same fetch:
`data/athlete_448437_results.csv`, `data/athlete_448437_summary.md`, and
`data/athlete_448437_results.xlsx` (gitignored — its bytes churn every run).

## Conventions

- Run scripts with the venv: `.venv/bin/python parkrun_athlete.py`
- Only `parkrun_athlete.py` is scheduled. Don't make it slower or chattier;
  a quiet week must stay a no-op with no commit.
- `parkrun_athlete.py` is cron-safe: retries with backoff, logs to `logs/`,
  exits 0 ok / 1 fetch failure / 2 parse failure. Keep it that way — cron has
  no one to prompt, so never add interactive input.
- Don't hardcode paths; `--out-dir` and `--log-dir` default relative to the
  script so the Mac and the Pi both work.

<!-- deployment verified 2026-09-12 -->
