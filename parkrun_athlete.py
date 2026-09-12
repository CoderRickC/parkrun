#!/usr/bin/env python3
"""Fetch a parkrunner's full results history and save it for later analysis.

Designed to run unattended from cron on a Raspberry Pi every Saturday evening.
Writes JSON (the canonical machine-readable copy), CSV and Excel into a data
folder, plus a short Markdown digest.

Files are only rewritten when the results themselves change, so a week with no
parkrun leaves the data folder untouched and produces no git commit.

Exit codes: 0 success, 1 fetch failure, 2 parse failure.
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from openpyxl import Workbook

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_ATHLETE_ID = 448437

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                  'AppleWebKit/537.36 (KHTML, like Gecko) '
                  'Chrome/123.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-GB,en;q=0.9',
    'Referer': 'https://www.google.com/',
    'Connection': 'keep-alive',
}

RESULT_COLUMNS = ['Event', 'Event Date', 'Run Number',
                  'Position', 'Finish Time', 'Age Grade', 'PB']

log = logging.getLogger('parkrun')


def setup_logging(log_dir: Path, verbose: bool) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format='%(asctime)s %(levelname)-7s %(message)s',
        handlers=[
            logging.FileHandler(log_dir / 'parkrun.log', encoding='utf-8'),
            logging.StreamHandler(sys.stdout),
        ],
    )


def fetch(url: str, attempts: int = 4, timeout: int = 30) -> bytes:
    """GET the page, retrying with exponential backoff on transient failures."""
    last_error = None
    for attempt in range(1, attempts + 1):
        try:
            response = requests.get(url, headers=HEADERS, timeout=timeout)
            if response.status_code == 200:
                log.info('Fetched %s (%d bytes)', url, len(response.content))
                return response.content
            last_error = f'HTTP {response.status_code}'
            log.warning('Attempt %d/%d failed: %s', attempt, attempts, last_error)
        except requests.RequestException as exc:
            last_error = str(exc)
            log.warning('Attempt %d/%d failed: %s', attempt, attempts, last_error)
        if attempt < attempts:
            delay = 5 * 2 ** (attempt - 1)
            log.info('Retrying in %ds', delay)
            time.sleep(delay)
    raise RuntimeError(f'Could not fetch {url}: {last_error}')


def cell_text(cell) -> str:
    return ' '.join(cell.get_text(' ', strip=True).split())


def iso_date(uk_date: str) -> str:
    """Convert parkrun's dd/mm/yyyy into ISO yyyy-mm-dd so dates sort properly."""
    try:
        return datetime.strptime(uk_date, '%d/%m/%Y').date().isoformat()
    except ValueError:
        return uk_date


def to_seconds(finish_time: str) -> int | None:
    """'53:58' or '01:09:23' -> total seconds."""
    parts = finish_time.split(':')
    try:
        numbers = [int(p) for p in parts]
    except ValueError:
        return None
    if len(numbers) == 2:
        minutes, seconds = numbers
        hours = 0
    elif len(numbers) == 3:
        hours, minutes, seconds = numbers
    else:
        return None
    return hours * 3600 + minutes * 60 + seconds


def table_by_caption(soup: BeautifulSoup, needle: str):
    for table in soup.find_all('table'):
        caption = table.find('caption')
        if caption and needle in ' '.join(caption.get_text().split()).lower():
            return table
    return None


def parse_rows(table) -> list[list[str]]:
    if table is None:
        return []
    rows = []
    for row in table.find_all('tr'):
        cells = row.find_all('td')
        if cells:
            rows.append([cell_text(c) for c in cells])
    return rows


def parse_athlete(html: bytes, athlete_id: int) -> dict:
    soup = BeautifulSoup(html, 'html.parser')

    heading = soup.find('h2')
    name = heading.get_text(' ', strip=True).split('(')[0].strip() if heading else ''

    results_table = table_by_caption(soup, 'all  results') or table_by_caption(soup, 'all results')
    if results_table is None:
        raise ValueError('Could not find the "All Results" table on the page')

    results = []
    for cells in parse_rows(results_table):
        if len(cells) < 7:
            continue
        results.append({
            'event': cells[0],
            'date': iso_date(cells[1]),
            'run_number': cells[2],
            'position': cells[3],
            'time': cells[4],
            'time_seconds': to_seconds(cells[4]),
            'age_grade': cells[5],
            'pb': cells[6].upper() == 'PB',
        })

    if not results:
        raise ValueError('The "All Results" table contained no result rows')

    results.sort(key=lambda r: r['date'], reverse=True)

    summary_stats = {
        cells[0]: {'fastest': cells[1], 'average': cells[2], 'slowest': cells[3]}
        for cells in parse_rows(table_by_caption(soup, 'summary stats'))
        if len(cells) >= 4
    }

    annual_bests = [
        {'year': cells[0], 'best_time': cells[1], 'best_age_grade': cells[2]}
        for cells in parse_rows(table_by_caption(soup, 'annual achievements'))
        if len(cells) >= 3
    ]

    event_counts: dict[str, int] = {}
    for result in results:
        event_counts[result['event']] = event_counts.get(result['event'], 0) + 1

    timed = [r for r in results if r['time_seconds'] is not None]
    personal_best = min(timed, key=lambda r: r['time_seconds']) if timed else None

    return {
        'athlete_id': athlete_id,
        'name': name,
        'profile_url': f'https://www.parkrun.org.uk/parkrunner/{athlete_id}/all/',
        'fetched_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'total_parkruns': len(results),
        'distinct_events': len(event_counts),
        'latest_run': results[0],
        'first_run': results[-1],
        'personal_best': personal_best,
        'summary_stats': summary_stats,
        'annual_bests': annual_bests,
        'event_counts': dict(sorted(event_counts.items(), key=lambda kv: (-kv[1], kv[0]))),
        'results': results,
    }


def is_unchanged(athlete: dict, path: Path) -> bool:
    """True if `path` already holds this data, ignoring the fetch timestamp."""
    if not path.exists():
        return False
    try:
        previous = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return False
    return {k: v for k, v in previous.items() if k != 'fetched_at'} == \
           {k: v for k, v in athlete.items() if k != 'fetched_at'}


def write_json(athlete: dict, path: Path) -> None:
    path.write_text(json.dumps(athlete, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    log.info('Wrote %s', path)


def write_csv(athlete: dict, path: Path) -> None:
    with path.open('w', newline='', encoding='utf-8') as handle:
        writer = csv.writer(handle)
        writer.writerow(RESULT_COLUMNS)
        for result in athlete['results']:
            writer.writerow([result['event'], result['date'], result['run_number'],
                             result['position'], result['time'], result['age_grade'],
                             'PB' if result['pb'] else ''])
    log.info('Wrote %s', path)


def write_xlsx(athlete: dict, path: Path) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = 'All Results'
    ws.append(RESULT_COLUMNS)
    for result in athlete['results']:
        ws.append([result['event'], result['date'], result['run_number'],
                   result['position'], result['time'], result['age_grade'],
                   'PB' if result['pb'] else ''])
    wb.save(path)
    log.info('Wrote %s', path)


def write_summary(athlete: dict, path: Path) -> None:
    latest, first, pb = athlete['latest_run'], athlete['first_run'], athlete['personal_best']
    lines = [
        f"# parkrun summary — {athlete['name']} (A{athlete['athlete_id']})",
        '',
        f"Updated: {athlete['fetched_at']}",
        '',
        f"- Total parkruns: **{athlete['total_parkruns']}**",
        f"- Different events: **{athlete['distinct_events']}**",
        f"- Latest: {latest['event']} on {latest['date']} in {latest['time']} "
        f"(position {latest['position']}, age grade {latest['age_grade']})",
        f"- First: {first['event']} on {first['date']} in {first['time']}",
    ]
    if pb:
        lines.append(f"- Personal best: {pb['time']} at {pb['event']} on {pb['date']}")
    lines += ['', '## Events run', '', '| Event | Times run |', '| --- | ---: |']
    lines += [f'| {event} | {count} |' for event, count in athlete['event_counts'].items()]
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    log.info('Wrote %s', path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--athlete-id', type=int, default=DEFAULT_ATHLETE_ID,
                        help=f'parkrun athlete number (default: {DEFAULT_ATHLETE_ID})')
    parser.add_argument('--out-dir', type=Path, default=BASE_DIR / 'data',
                        help='where to write the data files (default: ./data)')
    parser.add_argument('--log-dir', type=Path, default=BASE_DIR / 'logs',
                        help='where to write parkrun.log (default: ./logs)')
    parser.add_argument('--no-xlsx', action='store_true', help='skip the Excel file')
    parser.add_argument('--force', action='store_true',
                        help='rewrite the files even if the results are unchanged')
    parser.add_argument('-v', '--verbose', action='store_true')
    args = parser.parse_args()

    setup_logging(args.log_dir, args.verbose)
    args.out_dir.mkdir(parents=True, exist_ok=True)

    url = f'https://www.parkrun.org.uk/parkrunner/{args.athlete_id}/all/'
    log.info('Starting fetch for athlete %s', args.athlete_id)

    try:
        html = fetch(url)
    except RuntimeError as exc:
        log.error('%s', exc)
        return 1

    try:
        athlete = parse_athlete(html, args.athlete_id)
    except ValueError as exc:
        log.error('Parse failed: %s', exc)
        return 2

    stem = f'athlete_{args.athlete_id}'
    json_path = args.out_dir / f'{stem}.json'

    if not args.force and is_unchanged(athlete, json_path):
        log.info('No change since last fetch (%d parkruns); leaving files alone',
                 athlete['total_parkruns'])
        return 0

    write_json(athlete, json_path)
    write_csv(athlete, args.out_dir / f'{stem}_results.csv')
    write_summary(athlete, args.out_dir / f'{stem}_summary.md')
    if not args.no_xlsx:
        write_xlsx(athlete, args.out_dir / f'{stem}_results.xlsx')

    latest = athlete['latest_run']
    log.info('Done: %d parkruns, latest %s on %s in %s',
             athlete['total_parkruns'], latest['event'], latest['date'], latest['time'])
    return 0


if __name__ == '__main__':
    sys.exit(main())
