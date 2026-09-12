# Weekly parkrun fetch — live setup

**Status: deployed and tested 2026-09-12.**

Every Saturday at 19:00 (and again Sunday 09:00 as a catch-up) the Raspberry Pi
fetches Richard's full parkrun history, and pushes it to GitHub *only if a new
parkrun has appeared*. Pull the repo anywhere and read `data/athlete_448437.json`.

```
Pi (cron)  ──fetch──>  parkrun.org.uk
   │
   └──push (deploy key)──>  github.com/CoderRickC/parkrun  ──git pull──>  Mac
```

## What's where

| | |
| --- | --- |
| GitHub repo | `git@github.com:CoderRickC/parkrun.git` (private) |
| Pi | `pi@raspberrypi.local` — Raspberry Pi 5, Debian 13 (trixie), Python 3.13.5 |
| Path on the Pi | `/home/pi/parkrun` |
| Pi auth | ed25519 **deploy key** `raspberrypi-parkrun (write)`, no passphrase |
| Pi git identity | `Raspberry Pi <richard.clegg@me.com>` |
| Timezone | Europe/London, so cron times are local |
| Logs | `~/parkrun/logs/parkrun.log` (script) and `logs/cron.log` (cron) |

Crontab on the Pi (alongside the existing `oldham-news` job):

```cron
0 19 * * 6 /home/pi/parkrun/run_weekly.sh >> /home/pi/parkrun/logs/cron.log 2>&1
0  9 * * 0 /home/pi/parkrun/run_weekly.sh >> /home/pi/parkrun/logs/cron.log 2>&1
```

## Day-to-day

Get the latest data on the Mac:

```bash
git pull
```

Check the Pi is behaving:

```bash
ssh pi@raspberrypi.local 'tail -20 ~/parkrun/logs/parkrun.log'
```

Run it early by hand (e.g. straight after a parkrun):

```bash
ssh pi@raspberrypi.local '~/parkrun/run_weekly.sh'
```

## Things worth knowing

- **A quiet week is silent by design.** The script only rewrites the data files
  when the results actually change, so no parkrun means no commit. `fetched_at`
  in the JSON is therefore the date the data last *changed*, not the last check.
  Use the log to confirm the job is alive. `--force` rewrites regardless.
- **parkrun 403s lazy user agents.** A bare `curl -A "Mozilla/5.0"` gets 403
  from the Pi; the full header set in `parkrun_athlete.py` gets 200. Don't trim
  those headers.
- **The `.xlsx` is gitignored.** Its bytes change on every write even with
  identical data, which would defeat the change detection. The committed CSV
  opens in Excel fine.
- **The deploy key has no passphrase.** That's required for unattended cron. It
  grants write access to this one repo only, not the whole GitHub account.

## Rebuilding the Pi from scratch

```bash
ssh-keygen -t ed25519 -C "raspberrypi-parkrun" -f ~/.ssh/id_ed25519 -N ""
# add ~/.ssh/id_ed25519.pub at GitHub -> repo -> Settings -> Deploy keys (allow write)
git clone git@github.com:CoderRickC/parkrun.git ~/parkrun
cd ~/parkrun
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
git config user.name "Raspberry Pi" && git config user.email "richard.clegg@me.com"
mkdir -p logs
crontab -e     # add the two lines above
```

Verify it works the way cron will actually invoke it (stripped environment, no
ssh-agent — this is where such jobs usually fail):

```bash
env -i HOME=/home/pi LOGNAME=pi PATH=/usr/bin:/bin SHELL=/bin/sh \
  /home/pi/parkrun/run_weekly.sh </dev/null
```

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| `no virtualenv at .../.venv/bin/python` | Rebuild the venv (above). |
| Retries then exit 1 | parkrun down or rate-limiting; the Sunday run retries. |
| `Parse failed` (exit 2) | parkrun changed their HTML — update the table captions in `parkrun_athlete.py`. |
| Nothing ever commits | Expected if you haven't run a parkrun. Check `logs/parkrun.log` for "No change since last fetch". |
| Push fails | Deploy key lost write access, or `git config user.email` unset in `~/parkrun`. |
| Cron silent | `grep CRON /var/log/syslog`; confirm `crontab -l` paths are absolute. |
