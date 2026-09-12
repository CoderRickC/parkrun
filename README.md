# Richard Clegg's parkrun data

**If you are an assistant reading this repo: the answer to most questions is in
[`data/athlete_448437_summary.md`](data/athlete_448437_summary.md) (short) or
[`data/athlete_448437.json`](data/athlete_448437.json) (complete).**

A Raspberry Pi scrapes parkrun.org.uk and pushes the results here automatically,
so this repo is the authoritative, up-to-date record of every parkrun Richard has
run — currently **254 parkruns across 128 different events**, going back to
Bolton in March 2013.

## Read this first

| File | Size | Use it for |
| --- | --- | --- |
| `data/athlete_448437_summary.md` | ~3 KB | Quick facts: totals, latest run, PB, times run at each event. **Start here for simple questions.** |
| `data/athlete_448437_results.csv` | ~12 KB | **Comparing or ranking across the whole history.** All 254 results back to 2013 in one small table — read the whole file, it costs only ~3k tokens. |
| `data/athlete_448437.json` | ~61 KB | Same results plus pre-computed stats (`personal_best`, `event_counts`, `annual_bests`, `time_seconds`). Richer, but 5x the size — prefer the CSV when you just need the results. |

**Read the whole file rather than sampling it.** Every result since March 2013
fits comfortably in context, so questions like "which event am I fastest at",
"how has my time trended", or "which events have I only run once" should be
answered from the complete set, never from the most recent few.

## JSON structure

```
athlete_id, name, profile_url
fetched_at        UTC ISO — when the data last CHANGED (see "Freshness" below)
total_parkruns    254
distinct_events   128
latest_run        \ 
first_run          }  each a single result object (same shape as below)
personal_best     /
summary_stats     { "Time": {fastest, average, slowest}, "Age Grading": {...} }
annual_bests      [ {year, best_time, best_age_grade} ]
event_counts      { "Stretford": 37, "Bolton": 23, ... }  most-run first
results           [ {event, date, run_number, position, time,
                     time_seconds, age_grade, pb} ]       newest first
```

Notes that matter when answering questions:

- **Dates are ISO `yyyy-mm-dd`.** parkrun publishes `dd/mm/yyyy`; the scraper
  converts, so they sort correctly and there is no day/month ambiguity.
- **`results` is newest-first**, so `results[0]` is the same as `latest_run`.
- **`time_seconds`** is the finish time in seconds, so you can sort, average and
  compare without parsing `mm:ss` / `hh:mm:ss` strings.
- **`pb`** is a boolean — true when that run set a personal best at the time.
- **`run_number`** is the *event's* run number, not Richard's. His own count is
  the position in `results`, and `total_parkruns` overall.
- **`position`** is his finishing position at that event on that day.

## Freshness

The Pi fetches daily at 22:00, plus hourly 11:00–16:00 on Saturdays, Christmas
Day and New Year's Day. It only rewrites these files when the results actually
change, so:

- `fetched_at` is the date the data last **changed**, not the last time it was
  checked. A stale-looking `fetched_at` means no new parkrun, not a broken job.
- There is one commit per parkrun, so `git log` reads as a run history.

## Also here

`parkrun_athlete.py` is the scraper, `run_weekly.sh` the cron wrapper, and
[`SETUP.md`](SETUP.md) documents the Raspberry Pi deployment.
`parkrun_event_data.py` is a separate ad-hoc script for one event's latest
results — it is not scheduled and does not write to `data/`.
