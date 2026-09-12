# Raspberry Pi setup — weekly parkrun fetch

Every Saturday evening the Pi fetches Richard's full parkrun history, writes it
to `data/`, and pushes it to GitHub. Pull that repo anywhere and Claude can read
`data/athlete_448437.json`.

## 1. Put this project in its own git repo

The parkrun folder currently sits inside a much larger (uncommitted) iCloud repo.
The Pi wants a small, dedicated repo. On the Mac:

```bash
cd "~/Library/Mobile Documents/com~apple~CloudDocs/Programming/Python/My_Code/Web_Scraping/parkrun"
git init                       # creates a repo just for this folder
git add .
git commit -m "parkrun fetcher + weekly Pi job"
```

Create an empty repo on GitHub (private is fine), then:

```bash
git remote add origin git@github.com:<your-username>/parkrun.git
git branch -M main
git push -u origin main
```

> If `git init` complains that the folder is already inside a repo, that's the
> parent `Programming/Python` repo — it has no commits and no remote, so you can
> simply `rm -rf "../../../.git"` first, or keep this folder somewhere outside it.

## 2. Give the Pi push access

On the Pi:

```bash
ssh-keygen -t ed25519 -C "raspberrypi-parkrun"     # press Enter for no passphrase
cat ~/.ssh/id_ed25519.pub
```

Paste that key into GitHub → your repo → **Settings → Deploy keys → Add deploy
key**, and tick **Allow write access**. Then test:

```bash
ssh -T git@github.com
```

## 3. Clone and install on the Pi

```bash
sudo apt update && sudo apt install -y python3-venv git
git clone git@github.com:<your-username>/parkrun.git ~/parkrun
cd ~/parkrun
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
```

Tell git who is committing (cron has no interactive config):

```bash
git config user.name  "Raspberry Pi"
git config user.email "richard.clegg@me.com"
```

## 4. Test it by hand

```bash
cd ~/parkrun
./run_weekly.sh
```

You should see the fetch log, then either a push or
`no new parkrun data — nothing to commit`. Running it twice in a row should
give that second message — the files are only rewritten when the results change.

## 5. Schedule it

```bash
crontab -e
```

Add these two lines:

```cron
# Saturday 19:00 — parkrun results are usually published by late afternoon
0 19 * * 6 /home/pi/parkrun/run_weekly.sh >> /home/pi/parkrun/logs/cron.log 2>&1

# Sunday 09:00 — catch-up if the results were published late or the Pi was off
0 9 * * 0 /home/pi/parkrun/run_weekly.sh >> /home/pi/parkrun/logs/cron.log 2>&1
```

Adjust `/home/pi/` if your username differs (`echo $HOME` will tell you). The
Sunday run is free: if nothing changed it commits nothing.

Check it later with:

```bash
tail -n 40 ~/parkrun/logs/cron.log
tail -n 40 ~/parkrun/logs/parkrun.log
```

## 6. Read the data

Anywhere you've cloned the repo:

```bash
git pull
```

Then point Claude at `data/athlete_448437.json` (full history) or
`data/athlete_448437_summary.md` (quick digest).

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| `no virtualenv at .../.venv/bin/python` | Re-run step 3. |
| Fetch retries then exits 1 | parkrun was down or rate-limiting; the Sunday run retries. |
| `Parse failed` (exit 2) | parkrun changed their HTML — the table captions in `parkrun_athlete.py` need updating. |
| Cron never runs | Check the path in `crontab -l` is absolute and the script is `chmod +x`. |
| Push fails | Deploy key missing write access, or `git config user.email` unset. |
