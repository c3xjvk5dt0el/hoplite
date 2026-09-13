"""Download public Exness XAUUSD tick archives and aggregate paired UTC M1 candles."""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
import math
from pathlib import Path
import time
from urllib.error import HTTPError, URLError
from urllib.request import urlopen
import zipfile

UTC = timezone.utc
HEADER = ['timestamp'] + [side+'_'+field for side in ('bid', 'ask') for field in ('open', 'high', 'low', 'close')]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024*1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def months(start: str, end: str) -> list[str]:
    a, b = datetime.strptime(start, '%Y-%m'), datetime.strptime(end, '%Y-%m')
    if a >= b:
        raise ValueError('End month must be after start month (exclusive)')
    result = []
    while a < b:
        result.append(a.strftime('%Y-%m'))
        a = datetime(a.year + (a.month == 12), a.month % 12 + 1, 1)
    return result


def aggregate_zip(archive: Path, output: Path, month: str) -> dict:
    temporary = output.with_suffix('.part')
    count = bars = 0
    first = previous = None
    key = None
    minute_open = None
    quotes = None
    try:
        with zipfile.ZipFile(archive) as z:
            files = [p for p in z.infolist() if not p.is_dir()]
            if len(files) != 1 or not files[0].filename.endswith('.csv'):
                raise ValueError('Expected one CSV member; archive is never extracted')
            with z.open(files[0]) as source, temporary.open('w', newline='') as destination:
                rows = csv.reader(io.TextIOWrapper(source, encoding='utf-8-sig'))
                header = next(rows)
                if header != ['Exness', 'Symbol', 'Timestamp', 'Bid', 'Ask']:
                    raise ValueError(f'Unexpected tick header: {header!r}')
                writer = csv.writer(destination)
                writer.writerow(HEADER)
                for row in rows:
                    if len(row) != 5 or row[0].lower() != 'exness' or row[1] != 'XAUUSD':
                        raise ValueError(f'Unexpected symbol/row at tick {count+1}')
                    stamp, bid, ask = row[2], float(row[3]), float(row[4])
                    if not stamp.endswith('Z') or stamp[:7] != month or (previous is not None and stamp < previous):
                        raise ValueError(f'Non-UTC, wrong month, or unordered tick {stamp}')
                    if not (math.isfinite(bid) and math.isfinite(ask) and 0 < bid <= ask):
                        raise ValueError(f'Invalid/crossed quote at {stamp}')
                    minute = stamp[:16]
                    if minute != key:
                        if quotes is not None:
                            writer.writerow([minute_open] + quotes)
                            bars += 1
                        parsed = datetime.strptime(minute, '%Y-%m-%d %H:%M').replace(tzinfo=UTC)
                        minute_open = parsed.isoformat().replace('+00:00', 'Z')
                        key = minute
                        quotes = [bid, bid, bid, bid, ask, ask, ask, ask]
                    else:
                        quotes[1], quotes[2], quotes[3] = max(quotes[1], bid), min(quotes[2], bid), bid
                        quotes[5], quotes[6], quotes[7] = max(quotes[5], ask), min(quotes[6], ask), ask
                    if first is None:
                        first = stamp
                    previous = stamp
                    count += 1
                if quotes is not None:
                    writer.writerow([minute_open] + quotes)
                    bars += 1
        if count == 0:
            raise ValueError('Empty tick archive')
        temporary.replace(output)
        return dict(ticks=count, minutes=bars, first_tick=first, last_tick=previous,
                    csv=str(output), csv_sha256=sha256(output), zip_sha256=sha256(archive))
    finally:
        temporary.unlink(missing_ok=True)


def fetch_month(root_string: str, month: str) -> dict:
    root = Path(root_string)
    year, number = month.split('-')
    name = f'Exness_XAUUSD_{year}_{number}.zip'
    url = f'https://ticks.ex2archive.com/ticks/XAUUSD/{year}/{number}/{name}'
    archive = root/'raw'/name
    output = root/f'xauusd_m1_bid_ask_{month}_utc.csv'
    cache_meta = root/f'{month}.json'
    archive.parent.mkdir(parents=True, exist_ok=True)
    record = dict(month=month, url=url, status='failed')
    try:
        if archive.exists() and output.exists() and cache_meta.exists():
            cached = json.loads(cache_meta.read_text())
            if sha256(archive) == cached.get('zip_sha256') and sha256(output) == cached.get('csv_sha256'):
                return cached
        if not archive.exists():
            for attempt in range(3):
                try:
                    with urlopen(url, timeout=30) as response, archive.with_suffix('.part').open('wb') as f:
                        while chunk := response.read(1024*1024):
                            f.write(chunk)
                    archive.with_suffix('.part').replace(archive)
                    break
                except (HTTPError, URLError, TimeoutError) as e:
                    if attempt == 2 or (isinstance(e, HTTPError) and e.code not in (429, 500, 502, 503, 504)):
                        raise
                    time.sleep(attempt+1)
        record.update(aggregate_zip(archive, output, month))
        record.update(status='verified', downloaded_bytes=archive.stat().st_size)
        cache_meta.write_text(json.dumps(record, indent=2))
    except Exception as e:
        record['error'] = f'{type(e).__name__}: {e}'
    finally:
        archive.with_suffix('.part').unlink(missing_ok=True)
    return record


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--start', default='2024-12')
    parser.add_argument('--end', default='2026-09', help='Exclusive YYYY-MM')
    parser.add_argument('--out', type=Path, default=Path('.hoplite/artifacts/xau-research/exness'))
    parser.add_argument('--workers', type=int, choices=range(1, 5), default=3)
    args = parser.parse_args()
    requested = months(args.start, args.end)
    args.out.mkdir(parents=True, exist_ok=True)
    metadata = dict(source='Public Exness indicative tick archive, XAUUSD (no suffix)',
                    reference='https://www.exness.com/tick-history/',
                    server_limitations='Not selectable by MT5 server; account-type spreads and execution may differ.',
                    validation_scope='Archive CRC, schema, ordering, quote validity and SHA256; not independent proof of upstream tick completeness.',
                    kind='Paired BID/ASK M1 OHLC aggregated from tick order; no fabricated gap candles',
                    requested_months=requested, months=[])
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(fetch_month, str(args.out), month) for month in requested]
        for future in as_completed(futures):
            record = future.result()
            metadata['months'].append(record)
            metadata['months'].sort(key=lambda r:r['month'])
            temporary = args.out/'metadata.part'
            temporary.write_text(json.dumps(metadata, indent=2))
            temporary.replace(args.out/'metadata.json')
            print(json.dumps(record), flush=True)
    if any(record['status'] != 'verified' for record in metadata['months']):
        raise SystemExit('Some months failed: do not report incomplete periods as complete backtests.')


if __name__ == '__main__':
    main()
