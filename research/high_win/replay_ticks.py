"""Replay a locked high-win candidate through verified public Exness ticks.

This is a custom research replay of public XAUUSD quotes, not an MT5 Strategy
Tester.  Signals remain derived from the verified M1 cache, while exits use
native tick order from the corresponding public ZIP archives.
"""
from __future__ import annotations

import argparse
import csv
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
import hashlib
import io
import json
import math
from pathlib import Path
import sys
from typing import Sequence
import zipfile

# Keep the documented script-style CLI usable as well as ``python -m``.
if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from research.backtest_pullback import Minute, load_minutes
from research.high_win.engine import Costs, Portfolio
from research.high_win.signals import Candidate, Setup, build_setups, candidates


UTC = timezone.utc
WARMUP_MONTH = '2024-12'
DEFAULT_DATA = Path('.hoplite/artifacts/xau-research/exness')
TICK_HEADER = ['Exness', 'Symbol', 'Timestamp', 'Bid', 'Ask']
TRADE_FIELDS = (
    'entry_time', 'exit_time', 'side', 'entry', 'sl', 'tp', 'exit', 'gross',
    'net', 'commission', 'reason', 'hold_minutes', 'cross_utc_date',
)


class ReplayDataError(ValueError):
    """Raised when the public cache cannot prove a complete replay input."""


@dataclass(frozen=True, slots=True)
class MonthSource:
    """One verified monthly M1 cache record and its native tick archive."""

    month: str
    csv_path: Path
    zip_path: Path
    csv_sha256: str
    zip_sha256: str
    url: str | None
    metadata_minutes: int | None
    metadata_ticks: int | None


@dataclass(frozen=True, slots=True)
class SourceCatalog:
    """Verified metadata references needed for indicator and tick inputs."""

    metadata_path: Path
    metadata_sha256: str
    source_label: str | None
    reference: str | None
    setup_months: tuple[MonthSource, ...]
    replay_months: tuple[MonthSource, ...]


def parse_utc_date(value: str) -> int:
    """Parse one strict YYYY-MM-DD UTC boundary into an epoch second."""

    if not isinstance(value, str) or len(value) != 10:
        raise ReplayDataError(f'Expected YYYY-MM-DD date, got {value!r}')
    try:
        parsed = datetime.strptime(value, '%Y-%m-%d')
    except ValueError as exc:
        raise ReplayDataError(f'Expected YYYY-MM-DD date, got {value!r}') from exc
    if parsed.strftime('%Y-%m-%d') != value:
        raise ReplayDataError(f'Expected YYYY-MM-DD date, got {value!r}')
    return int(parsed.replace(tzinfo=UTC).timestamp())


def locked_candidate(candidate_id: str) -> Candidate:
    """Look up, but never rank or select, one frozen candidate ID."""

    matches = [candidate for candidate in candidates() if candidate.id == candidate_id]
    if len(matches) != 1:
        raise ReplayDataError(f'Unknown frozen candidate ID: {candidate_id!r}')
    return matches[0]


def _month_start(value: date) -> date:
    return date(value.year, value.month, 1)


def _next_month(value: date) -> date:
    return date(value.year + (value.month == 12), value.month % 12 + 1, 1)


def _month_label(value: date) -> str:
    return value.strftime('%Y-%m')


def _month_span(first: date, last: date) -> list[str]:
    """Return inclusive calendar-month labels between two month starts."""

    result = []
    cursor = _month_start(first)
    until = _month_start(last)
    while cursor <= until:
        result.append(_month_label(cursor))
        cursor = _next_month(cursor)
    return result


def _month_labels_for_request(start: int, end: int) -> tuple[list[str], list[str]]:
    if start >= end:
        raise ReplayDataError('Replay end must be after replay start')
    warmup_start = datetime.strptime(WARMUP_MONTH, '%Y-%m').replace(tzinfo=UTC)
    if start < int(warmup_start.timestamp()):
        raise ReplayDataError('Public cache warmup begins at 2024-12-01 UTC')
    first_replay = _month_start(datetime.fromtimestamp(start, UTC).date())
    last_replay = _month_start(datetime.fromtimestamp(end - 1, UTC).date())
    setup_months = _month_span(warmup_start.date(), last_replay)
    replay_months = _month_span(first_replay, last_replay)
    return setup_months, replay_months


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open('rb') as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b''):
                digest.update(chunk)
    except OSError as exc:
        raise ReplayDataError(f'Cannot read {path}: {exc}') from exc
    return digest.hexdigest()


def _expected_sha(record: dict, key: str, month: str) -> str:
    value = record.get(key)
    if not isinstance(value, str) or len(value) != 64:
        raise ReplayDataError(f'Missing or invalid {key} for {month}')
    try:
        int(value, 16)
    except ValueError as exc:
        raise ReplayDataError(f'Missing or invalid {key} for {month}') from exc
    return value.lower()


def _metadata_count(record: dict, key: str, month: str) -> int | None:
    if key not in record:
        return None
    value = record[key]
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ReplayDataError(f'Invalid {key} count for {month}')
    return value


def _resolve_metadata_path(root: Path, value: object, fallback: Path, description: str) -> Path:
    """Resolve downloader metadata that may retain its original workspace path."""

    if value is None:
        return root / fallback
    if not isinstance(value, str) or not value:
        raise ReplayDataError(f'Invalid {description} path in source metadata')
    declared = Path(value)
    if declared.is_absolute():
        return declared
    options = (root / declared, root / declared.name)
    for candidate in options:
        if candidate.exists():
            return candidate
    return options[0]


def _month_source(root: Path, record: dict, month: str) -> MonthSource:
    csv_path = _resolve_metadata_path(
        root,
        record.get('csv'),
        Path(f'xauusd_m1_bid_ask_{month}_utc.csv'),
        f'{month} M1 CSV',
    )
    year, number = month.split('-')
    zip_path = _resolve_metadata_path(
        root,
        record.get('zip', record.get('archive')),
        Path('raw') / f'Exness_XAUUSD_{year}_{number}.zip',
        f'{month} tick ZIP',
    )
    url = record.get('url')
    if url is not None and not isinstance(url, str):
        raise ReplayDataError(f'Invalid URL in source metadata for {month}')
    return MonthSource(
        month=month,
        csv_path=csv_path,
        zip_path=zip_path,
        csv_sha256=_expected_sha(record, 'csv_sha256', month),
        zip_sha256=_expected_sha(record, 'zip_sha256', month),
        url=url,
        metadata_minutes=_metadata_count(record, 'minutes', month),
        metadata_ticks=_metadata_count(record, 'ticks', month),
    )


def load_source_catalog(data: Path, start: int, end: int) -> SourceCatalog:
    """Load metadata and require verified records for every needed month."""

    root = Path(data)
    metadata_path = root / 'metadata.json'
    try:
        raw = metadata_path.read_bytes()
    except OSError as exc:
        raise ReplayDataError(f'Cannot read source metadata {metadata_path}: {exc}') from exc
    try:
        metadata = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ReplayDataError(f'Invalid source metadata {metadata_path}') from exc
    if not isinstance(metadata, dict) or not isinstance(metadata.get('months'), list):
        raise ReplayDataError('Source metadata must contain a months list')

    records: dict[str, dict] = {}
    for record in metadata['months']:
        if not isinstance(record, dict):
            raise ReplayDataError('Source metadata contains a non-object month record')
        month = record.get('month')
        if not isinstance(month, str) or len(month) != 7:
            raise ReplayDataError(f'Invalid month record: {month!r}')
        try:
            parsed = datetime.strptime(month, '%Y-%m')
        except ValueError as exc:
            raise ReplayDataError(f'Invalid month record: {month!r}') from exc
        if parsed.strftime('%Y-%m') != month or month in records:
            raise ReplayDataError(f'Duplicate or invalid month record: {month!r}')
        records[month] = record

    setup_labels, replay_labels = _month_labels_for_request(start, end)
    declared = metadata.get('requested_months')
    if declared is not None:
        if not isinstance(declared, list) or not all(isinstance(month, str) for month in declared):
            raise ReplayDataError('Source metadata requested_months must be a list of month labels')
        declared_months = set(declared)
    else:
        declared_months = None

    sources: dict[str, MonthSource] = {}
    for month in setup_labels:
        record = records.get(month)
        if record is None or record.get('status') != 'verified':
            raise ReplayDataError(f'No verified source coverage for required month {month}')
        if declared_months is not None and month not in declared_months:
            raise ReplayDataError(f'Unknown source coverage for required month {month}')
        sources[month] = _month_source(root, record, month)

    source_label = metadata.get('source')
    reference = metadata.get('reference')
    if source_label is not None and not isinstance(source_label, str):
        raise ReplayDataError('Source metadata has an invalid source label')
    if reference is not None and not isinstance(reference, str):
        raise ReplayDataError('Source metadata has an invalid reference')
    return SourceCatalog(
        metadata_path=metadata_path,
        metadata_sha256=hashlib.sha256(raw).hexdigest(),
        source_label=source_label,
        reference=reference,
        setup_months=tuple(sources[month] for month in setup_labels),
        replay_months=tuple(sources[month] for month in replay_labels),
    )


def _verify_sha256(path: Path, expected: str, description: str) -> str:
    actual = _sha256(path)
    if actual != expected:
        raise ReplayDataError(
            f'SHA256 mismatch for {description}: expected {expected}, got {actual}'
        )
    return actual


def _epoch_month(value: int) -> str:
    return datetime.fromtimestamp(value, UTC).strftime('%Y-%m')


def load_verified_minutes(sources: Sequence[MonthSource]) -> list[Minute]:
    """Hash-check all M1 files and load only their claimed calendar months."""

    all_minutes: list[Minute] = []
    seen = set()
    for source in sources:
        _verify_sha256(source.csv_path, source.csv_sha256, f'{source.month} M1 CSV')
        try:
            minutes = load_minutes([source.csv_path])
        except (OSError, ValueError, KeyError) as exc:
            raise ReplayDataError(f'Invalid {source.month} M1 CSV: {exc}') from exc
        if not minutes:
            raise ReplayDataError(f'Empty {source.month} M1 CSV')
        if source.metadata_minutes is not None and len(minutes) != source.metadata_minutes:
            raise ReplayDataError(
                f'M1 minute count does not match source metadata for {source.month}'
            )
        for minute in minutes:
            if _epoch_month(minute.time) != source.month:
                raise ReplayDataError(f'M1 CSV timestamp outside claimed month {source.month}')
            if minute.time in seen:
                raise ReplayDataError(f'Duplicate minute across source files: {minute.time}')
            seen.add(minute.time)
        all_minutes.extend(minutes)
    all_minutes.sort(key=lambda minute: minute.time)
    if not all_minutes:
        raise ReplayDataError('No M1 data loaded for setup construction')
    return all_minutes


def _tick_epoch(timestamp: str, minute_epoch_cache: dict[str, int]) -> int:
    """Use MT5's whole-server-second clock without coalescing ordered ticks."""

    if (
        not isinstance(timestamp, str)
        or len(timestamp) != 24
        or timestamp[4] != '-'
        or timestamp[7] != '-'
        or timestamp[10] != ' '
        or timestamp[13] != ':'
        or timestamp[16] != ':'
        or timestamp[19] != '.'
        or timestamp[23] != 'Z'
        or not (timestamp[:4] + timestamp[5:7] + timestamp[8:10]
                    + timestamp[11:13] + timestamp[14:16] + timestamp[17:19]
                    + timestamp[20:23]).isdigit()
    ):
        raise ReplayDataError(f'Invalid Exness UTC timestamp: {timestamp!r}')
    minute = timestamp[:16]
    epoch = minute_epoch_cache.get(minute)
    if epoch is None:
        try:
            parsed = datetime.strptime(minute, '%Y-%m-%d %H:%M')
        except ValueError as exc:
            raise ReplayDataError(f'Invalid Exness UTC timestamp: {timestamp!r}') from exc
        epoch = int(parsed.replace(tzinfo=UTC).timestamp())
        minute_epoch_cache[minute] = epoch
    second = int(timestamp[17:19])
    if second > 59:
        raise ReplayDataError(f'Invalid Exness UTC timestamp: {timestamp!r}')
    return epoch + second


def _parse_tick_row(row: list[str], source: MonthSource, number: int,
                    minute_epoch_cache: dict[str, int]) -> tuple[str, int, float, float]:
    if len(row) != 5:
        raise ReplayDataError(f'Unexpected tick column count in {source.month} row {number}')
    venue, symbol, stamp, bid_string, ask_string = row
    if venue.casefold() != 'exness' or symbol != 'XAUUSD':
        raise ReplayDataError(f'Unexpected venue or symbol in {source.month} row {number}')
    if stamp[:7] != source.month:
        raise ReplayDataError(f'Timestamp outside {source.month} in row {number}: {stamp!r}')
    epoch = _tick_epoch(stamp, minute_epoch_cache)
    try:
        bid, ask = float(bid_string), float(ask_string)
    except ValueError as exc:
        raise ReplayDataError(f'Invalid quote in {source.month} row {number}') from exc
    if not (math.isfinite(bid) and math.isfinite(ask) and 0 < bid <= ask):
        raise ReplayDataError(f'Invalid or crossed quote in {source.month} row {number}')
    return stamp, epoch, bid, ask


def _in_entry_session(time: int, portfolio: Portfolio) -> bool:
    day = time // 86400
    weekday = (day + 3) % 7
    hour = (time % 86400) // 3600
    return weekday < 5 and portfolio.rules.start_hour <= hour < portfolio.rules.end_hour


def _empty_month_stats(month: str) -> dict:
    return dict(
        month=month,
        ticks_read=0,
        ticks_before_requested_period=0,
        ticks_after_requested_period=0,
        ticks_in_requested_period=0,
        ticks_executed=0,
        ticks_skipped_flat_outside_entry_session=0,
        first_quote_utc=None,
        last_quote_utc=None,
    )


def _replay_archive(source: MonthSource, portfolios: Sequence[Portfolio], start: int, end: int,
                    minute_epoch_cache: dict[str, int], previous_timestamp: str | None) -> tuple[dict, str | None]:
    """Stream one ZIP fully so ZipExtFile consumes and verifies its CRC."""

    _verify_sha256(source.zip_path, source.zip_sha256, f'{source.month} tick ZIP')
    stats = _empty_month_stats(source.month)
    try:
        with zipfile.ZipFile(source.zip_path) as archive:
            members = [member for member in archive.infolist() if not member.is_dir()]
            if len(members) != 1 or not members[0].filename.lower().endswith('.csv'):
                raise ReplayDataError(f'Expected exactly one CSV member in {source.zip_path}')
            with archive.open(members[0]) as binary:
                with io.TextIOWrapper(binary, encoding='utf-8-sig', newline='') as text:
                    rows = csv.reader(text)
                    try:
                        header = next(rows)
                    except StopIteration as exc:
                        raise ReplayDataError(f'Empty tick CSV in {source.zip_path}') from exc
                    if header != TICK_HEADER:
                        raise ReplayDataError(f'Unexpected tick header in {source.zip_path}: {header!r}')
                    for row in rows:
                        stats['ticks_read'] += 1
                        stamp, epoch, bid, ask = _parse_tick_row(
                            row, source, stats['ticks_read'], minute_epoch_cache,
                        )
                        if previous_timestamp is not None and stamp < previous_timestamp:
                            raise ReplayDataError(
                                f'Unordered tick timestamp in {source.month}: {stamp!r}'
                            )
                        previous_timestamp = stamp
                        if epoch < start:
                            stats['ticks_before_requested_period'] += 1
                            continue
                        if epoch >= end:
                            stats['ticks_after_requested_period'] += 1
                            continue
                        stats['ticks_in_requested_period'] += 1
                        if stats['first_quote_utc'] is None:
                            stats['first_quote_utc'] = stamp
                        stats['last_quote_utc'] = stamp

                        # Quotes outside an entry session matter whenever either
                        # cost scenario still holds a position.
                        if (all(portfolio.position is None for portfolio in portfolios)
                                and not any(_in_entry_session(epoch, portfolio) for portfolio in portfolios)):
                            stats['ticks_skipped_flat_outside_entry_session'] += 1
                            continue
                        for portfolio in portfolios:
                            portfolio.on_quote(epoch, bid, ask, tick_replay=True)
                        stats['ticks_executed'] += 1
    except ReplayDataError:
        raise
    except (OSError, UnicodeError, csv.Error, zipfile.BadZipFile) as exc:
        raise ReplayDataError(f'Cannot replay {source.month} tick archive: {exc}') from exc

    if not stats['ticks_read']:
        raise ReplayDataError(f'Empty tick CSV in {source.zip_path}')
    if source.metadata_ticks is not None and stats['ticks_read'] != source.metadata_ticks:
        raise ReplayDataError(f'Tick count does not match source metadata for {source.month}')
    return stats, previous_timestamp


def replay_ticks(sources: Sequence[MonthSource], portfolios: Sequence[Portfolio], start: int, end: int) -> dict:
    """Replay verified archives in native CSV order through two fresh portfolios.

    Every CSV row is streamed to EOF for validation and ZIP CRC checking.  The
    engine receives only quotes in ``[start, end)`` and never receives an M1
    OHLC range, so intra-minute SL/TP order remains the public tick order.
    """

    if start >= end:
        raise ReplayDataError('Replay end must be after replay start')
    if len(portfolios) != 2:
        raise ReplayDataError('Tick replay requires exactly base and stress portfolios')
    if not sources:
        raise ReplayDataError('No verified tick archives were selected for replay')
    _setup_labels, expected_months = _month_labels_for_request(start, end)
    if [source.month for source in sources] != expected_months:
        raise ReplayDataError(
            'Tick archives must cover every requested calendar month in chronological order'
        )
    for portfolio in portfolios:
        if portfolio.start != start or portfolio.end != end:
            raise ReplayDataError('Portfolio period does not match replay period')

    minute_epoch_cache: dict[str, int] = {}
    previous_timestamp = None
    monthly = []
    for source in sources:
        stats, previous_timestamp = _replay_archive(
            source, portfolios, start, end, minute_epoch_cache, previous_timestamp,
        )
        monthly.append(stats)

    first = next((entry['first_quote_utc'] for entry in monthly if entry['first_quote_utc']), None)
    last = next((entry['last_quote_utc'] for entry in reversed(monthly) if entry['last_quote_utc']), None)
    keys = (
        'ticks_read', 'ticks_before_requested_period', 'ticks_after_requested_period',
        'ticks_in_requested_period', 'ticks_executed',
        'ticks_skipped_flat_outside_entry_session',
    )
    result = {key: sum(entry[key] for entry in monthly) for key in keys}
    result.update(
        quote_period=dict(min_timestamp_utc=first, max_timestamp_utc=last),
        months_replayed=monthly,
        minute_epoch_cache_entries=len(minute_epoch_cache),
    )
    return result


def _source_provenance(catalog: SourceCatalog) -> dict:
    def m1_record(source: MonthSource) -> dict:
        return dict(
            month=source.month,
            path=str(source.csv_path),
            sha256=source.csv_sha256,
            metadata_minutes=source.metadata_minutes,
        )

    def tick_record(source: MonthSource) -> dict:
        return dict(
            month=source.month,
            path=str(source.zip_path),
            sha256=source.zip_sha256,
            url=source.url,
            metadata_ticks=source.metadata_ticks,
        )

    return dict(
        metadata=dict(path=str(catalog.metadata_path), sha256=catalog.metadata_sha256),
        source=catalog.source_label,
        reference=catalog.reference,
        m1_months_loaded_for_setups=[m1_record(source) for source in catalog.setup_months],
        tick_months_replayed=[tick_record(source) for source in catalog.replay_months],
    )


def _write_trades(path: Path, trades: Sequence[dict]) -> None:
    with path.open('x', newline='', encoding='utf-8') as destination:
        writer = csv.DictWriter(destination, fieldnames=TRADE_FIELDS)
        writer.writeheader()
        writer.writerows(trades)


def _write_json(path: Path, value: dict) -> None:
    if path.exists():
        raise ReplayDataError(f'Refusing to overwrite completed replay: {path}')
    temporary = path.with_suffix(path.suffix + '.part')
    with temporary.open('x',encoding='utf-8') as output:
        output.write(json.dumps(value, indent=2, sort_keys=True) + '\n')
    temporary.replace(path)


def run_replay(candidate_id: str, start_date: str, end_date: str, data: Path = DEFAULT_DATA,
               out: Path | None = None) -> dict:
    """Build all frozen setups and replay one supplied candidate under two costs."""

    if out is None:
        raise ReplayDataError('An output directory is required for replay artifacts')
    start, end = parse_utc_date(start_date), parse_utc_date(end_date)
    output = Path(out)
    if any((output/name).exists() for name in ('results.json','base_trades.csv','stress_trades.csv')):
        raise ReplayDataError('Replay output already contains results; preserve them and use a new directory')
    candidate = locked_candidate(candidate_id)
    catalog = load_source_catalog(Path(data), start, end)
    all_minutes = load_verified_minutes(catalog.setup_months)
    setup_streams = build_setups(all_minutes)
    try:
        setup_map: dict[int, Setup] = setup_streams[candidate.signal_key]
    except KeyError as exc:
        raise ReplayDataError(f'Missing setup stream for {candidate.signal_key}') from exc

    base = Portfolio(candidate, setup_map, start, end, Costs(slippage=.05))
    stress = Portfolio(candidate, setup_map, start, end, Costs(slippage=.15))
    tick_stats = replay_ticks(catalog.replay_months, (base, stress), start, end)
    base_result, stress_result = base.finish(), stress.finish()

    output = Path(out)
    output.mkdir(parents=True, exist_ok=True)
    base_csv, stress_csv = output / 'base_trades.csv', output / 'stress_trades.csv'
    _write_trades(base_csv, base_result['trades'])
    _write_trades(stress_csv, stress_result['trades'])

    def scenario(costs: Costs, result: dict, trades_csv: Path) -> dict:
        return dict(
            costs=asdict(costs),
            metrics=result['summary'],
            skips=result['skips'],
            portfolio_quotes=result['quotes'],
            trades_csv=trades_csv.name,
        )

    result = dict(
        label='Custom public-tick replay of XAUUSD, NOT MT5 Strategy Tester.',
        candidate=asdict(candidate),
        requested_period=dict(start=start_date, end=end_date, start_epoch=start, end_epoch=end),
        assumptions=dict(
            signal_bars='Completed M1-derived M5 and M15 bars only; December 2024 is included as indicator warmup.',
            execution='Public native quote order with instant simulated fills; BUY uses Ask and SELL uses Bid.',
            clock='TimeCurrent/POSITION_TIME-compatible whole seconds; every tick is processed in original millisecond order, never coalesced. Trade timestamps are second-resolution.',
            costs='Fixed 0.01 lot, 100 oz contract, USD 0.04 round-trip commission; adverse slippage is .05 base or .15 stress.',
            exits='SL uses the triggering public quote plus adverse slippage; TP fills at its target; no OHLC SL-first rule is used.',
            limits='No latency, rejection, partial fill, margin, swap, or broker-specific stop/freeze-level simulation.',
        ),
        source=_source_provenance(catalog),
        m1_minutes_loaded=len(all_minutes),
        tick_replay=tick_stats,
        scenarios=dict(
            base=scenario(base.costs, base_result, base_csv),
            stress=scenario(stress.costs, stress_result, stress_csv),
        ),
    )
    _write_json(output / 'results.json', result)
    return result


def verify_final_request(lock_path: Path, candidate_id: str, start: str, end: str) -> dict:
    from research.high_win.study import PERIODS, verified_lock
    try:
        lock=verified_lock(lock_path)
    except (OSError, ValueError, KeyError) as exc:
        raise ReplayDataError(f'Invalid completed validation lock: {exc}') from exc
    if candidate_id!=lock['candidate_id'] or (start,end)!=PERIODS['check']:
        raise ReplayDataError('Final replay must use the locked candidate and complete June–August 2026 check period')
    return lock


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate', required=True, help='Frozen candidate ID from signals.candidates()')
    parser.add_argument('--lock',type=Path,required=True,help='Completed study validation lock.json')
    parser.add_argument('--start', required=True, metavar='YYYY-MM-DD', help='Inclusive UTC date')
    parser.add_argument('--end', required=True, metavar='YYYY-MM-DD', help='Exclusive UTC date')
    parser.add_argument('--data', type=Path, default=DEFAULT_DATA, help='Verified Exness cache directory')
    parser.add_argument('--out', required=True, type=Path, help='Directory for JSON and trade CSV artifacts')
    args = parser.parse_args(argv)
    try:
        verify_final_request(args.lock,args.candidate,args.start,args.end)
        result = run_replay(args.candidate, args.start, args.end, args.data, args.out)
    except ReplayDataError as exc:
        parser.error(str(exc))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == '__main__':
    main()
