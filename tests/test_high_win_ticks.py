import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from research.high_win.engine import Costs, Portfolio
from research.high_win.replay_ticks import (
    MonthSource, ReplayDataError, load_source_catalog, replay_ticks, run_replay,
)
from research.high_win.signals import Candidate, Setup


UTC = timezone.utc
HEADER = ['Exness', 'Symbol', 'Timestamp', 'Bid', 'Ask']
CANDIDATE = Candidate('fixture_rsi2', 'rsi2', 10, .75, .60)


def _epoch(value):
    return int(datetime.strptime(value, '%Y-%m-%d %H:%M:%S').replace(tzinfo=UTC).timestamp())


def _stamp(value, milliseconds=0):
    return f'{value}.{milliseconds:03d}Z'


def _digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _tick_csv(rows):
    output = [','.join(f'"{item}"' for item in HEADER)]
    output.extend(
        f'"{venue}","{symbol}","{stamp}",{bid},{ask}'
        for venue, symbol, stamp, bid, ask in rows
    )
    return '\n'.join(output) + '\n'


def _minute_csv(stamp):
    return (
        'timestamp,bid_open,bid_high,bid_low,bid_close,ask_open,ask_high,ask_low,ask_close\n'
        f'{stamp},100,100.2,99.8,100,100.1,100.3,99.9,100.1\n'
    )


def _source(folder, month, rows):
    csv_path = folder / f'xauusd_m1_bid_ask_{month}_utc.csv'
    csv_path.write_text(_minute_csv(f'{month}-02T00:00:00Z'), encoding='utf-8')
    year, number = month.split('-')
    archive = folder / f'Exness_XAUUSD_{year}_{number}.zip'
    with zipfile.ZipFile(archive, 'w') as output:
        output.writestr('ticks.csv', _tick_csv(rows))
    return MonthSource(
        month=month,
        csv_path=csv_path,
        zip_path=archive,
        csv_sha256=_digest(csv_path),
        zip_sha256=_digest(archive),
        url='https://example.invalid/public-ticks',
        metadata_minutes=1,
        metadata_ticks=len(rows),
    )


def _portfolios(start, end, setups, base_slippage=.05, stress_slippage=.05):
    return (
        Portfolio(CANDIDATE, setups, start, end, Costs(slippage=base_slippage)),
        Portfolio(CANDIDATE, setups, start, end, Costs(slippage=stress_slippage)),
    )


class HighWinTickReplayTests(unittest.TestCase):
    def test_mql_second_clock_entry_and_timeout_boundaries(self):
        start=_epoch('2025-01-06 07:00:00')
        end=_epoch('2025-01-06 08:00:00')
        setup=Setup(start,True,101,99,2)
        cases=[('07:00:30',999,'07:45:30',1),
               ('07:00:31',0,'07:45:31',0),
               ('07:00:00',900,'07:45:00',1)]
        for opened,millis,closed,expected in cases:
            with self.subTest(opened=opened,millis=millis), tempfile.TemporaryDirectory() as tmp:
                rows=[('Exness','XAUUSD',_stamp('2025-01-06 '+opened,millis),100,100.1),
                      ('Exness','XAUUSD',_stamp('2025-01-06 '+closed),100,100.1)]
                source=_source(Path(tmp),'2025-01',rows)
                portfolios=_portfolios(start,end,{start:setup})
                replay_ticks((source,),portfolios,start,end)
                result=portfolios[0].finish()
                self.assertEqual(len(result['trades']),expected)
                if expected:
                    self.assertEqual(result['trades'][0]['reason'],'timeout')
                    self.assertEqual(result['trades'][0]['hold_minutes'],45)

    def test_native_tick_order_resolves_opposite_intraminute_sl_tp_orders(self):
        start = _epoch('2025-01-06 07:00:00')  # Monday
        end = start + 600
        rows = [
            ('exness', 'XAUUSD', _stamp('2025-01-06 07:00:00', 1), 100, 100.1),
            # This target precedes the stop in the first minute and second.
            ('exness', 'XAUUSD', _stamp('2025-01-06 07:00:00', 10), 101, 101.1),
            ('exness', 'XAUUSD', _stamp('2025-01-06 07:00:00', 20), 98, 98.1),
            ('exness', 'XAUUSD', _stamp('2025-01-06 07:05:00', 1), 100, 100.1),
            # The stop precedes the target in the second minute and second.
            ('exness', 'XAUUSD', _stamp('2025-01-06 07:05:00', 10), 98, 98.1),
            ('exness', 'XAUUSD', _stamp('2025-01-06 07:05:00', 20), 101, 101.1),
        ]
        setups = {
            start: Setup(start, True, 101, 99, 1),
            start + 300: Setup(start + 300, True, 101, 99, 1),
        }
        with tempfile.TemporaryDirectory() as directory:
            source = _source(Path(directory), '2025-01', rows)
            base, stress = _portfolios(start, end, setups)
            stats = replay_ticks((source,), (base, stress), start, end)

        trades = base.finish()['trades']
        self.assertEqual([trade['reason'] for trade in trades], ['target', 'stop_tick'])
        self.assertNotIn('both_hit_stop_first', [trade['reason'] for trade in trades])
        self.assertLess(trades[1]['exit'], trades[1]['sl'])
        self.assertAlmostEqual(trades[1]['exit'], 97.95)
        self.assertEqual(stats['ticks_read'], 6)
        self.assertEqual(stats['ticks_executed'], 6)
        self.assertEqual(stats['quote_period']['min_timestamp_utc'], rows[0][2])
        self.assertEqual(stats['quote_period']['max_timestamp_utc'], rows[-1][2])

    def test_first_tick_after_30_seconds_is_sent_to_engine_and_rejected(self):
        start = _epoch('2025-01-06 07:05:00')
        end = start + 60
        rows = [('exness', 'XAUUSD', _stamp('2025-01-06 07:05:31'), 100, 100.1)]
        with tempfile.TemporaryDirectory() as directory:
            source = _source(Path(directory), '2025-01', rows)
            base, stress = _portfolios(start, end, {start: Setup(start, True, 101, 99, 1)})
            stats = replay_ticks((source,), (base, stress), start, end)

        self.assertEqual(stats['ticks_executed'], 1)
        self.assertEqual(base.skips['late_first_quote'], 1)
        self.assertIsNone(base.position)

    def test_open_positions_continue_through_session_end_and_midnight_for_timeout(self):
        start = _epoch('2025-01-06 17:55:00')  # Monday, still inside the entry session
        midnight = _epoch('2025-01-07 00:00:00')
        end = midnight + 120
        rows = [
            ('exness', 'XAUUSD', _stamp('2025-01-06 17:55:00'), 100, 100.1),
            # This is outside the entry session and after the maximum hold time.
            ('exness', 'XAUUSD', _stamp('2025-01-07 00:00:00'), 100, 100.1),
            # Both portfolios are now flat, so this quote can be skipped.
            ('exness', 'XAUUSD', _stamp('2025-01-07 00:01:00'), 100, 100.1),
        ]
        with tempfile.TemporaryDirectory() as directory:
            source = _source(Path(directory), '2025-01', rows)
            base, stress = _portfolios(
                start, end, {start: Setup(start, True, 101, 99, 1)}, .05, .15,
            )
            stats = replay_ticks((source,), (base, stress), start, end)

        base_result = base.finish()
        trade = base_result['trades'][0]
        self.assertEqual(trade['reason'], 'timeout')
        self.assertTrue(trade['cross_utc_date'])
        self.assertAlmostEqual(base.daily_pnl[midnight // 86400], trade['net'])
        self.assertEqual(stats['ticks_executed'], 2)
        self.assertEqual(stats['ticks_skipped_flat_outside_entry_session'], 1)

    def test_unordered_public_ticks_are_rejected_after_hash_verification(self):
        start = _epoch('2025-01-06 07:00:00')
        rows = [
            ('exness', 'XAUUSD', _stamp('2025-01-06 07:00:02'), 100, 100.1),
            ('exness', 'XAUUSD', _stamp('2025-01-06 07:00:01'), 100, 100.1),
        ]
        with tempfile.TemporaryDirectory() as directory:
            source = _source(Path(directory), '2025-01', rows)
            base, stress = _portfolios(start, start + 60, {})
            with self.assertRaisesRegex(ReplayDataError, 'Unordered tick timestamp'):
                replay_ticks((source,), (base, stress), start, start + 60)

    def test_replay_requires_every_requested_month_in_order(self):
        start = _epoch('2025-01-31 23:59:00')
        end = _epoch('2025-02-01 00:01:00')
        rows = [('exness', 'XAUUSD', _stamp('2025-01-31 23:59:00'), 100, 100.1)]
        with tempfile.TemporaryDirectory() as directory:
            source = _source(Path(directory), '2025-01', rows)
            base, stress = _portfolios(start, end, {})
            with self.assertRaisesRegex(ReplayDataError, 'every requested calendar month'):
                replay_ticks((source,), (base, stress), start, end)

    def test_empty_tick_archive_fails_closed(self):
        start = _epoch('2025-01-06 07:00:00')
        with tempfile.TemporaryDirectory() as directory:
            source = _source(Path(directory), '2025-01', [])
            base, stress = _portfolios(start, start + 60, {})
            with self.assertRaisesRegex(ReplayDataError, 'Empty tick CSV'):
                replay_ticks((source,), (base, stress), start, start + 60)

    def test_missing_month_metadata_fails_closed(self):
        start = _epoch('2025-01-06 00:00:00')
        record = dict(
            month='2024-12', status='verified', csv='december.csv', zip='december.zip',
            csv_sha256='0' * 64, zip_sha256='0' * 64,
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'metadata.json').write_text(
                json.dumps(dict(requested_months=['2024-12'], months=[record])),
                encoding='utf-8',
            )
            with self.assertRaisesRegex(ReplayDataError, 'No verified source coverage'):
                load_source_catalog(root, start, start + 86400)

    def test_run_replay_writes_metrics_trade_csvs_and_source_hash_provenance(self):
        start = _epoch('2025-01-06 00:00:00')
        candidate_id = 'rsi2_10_stop0.75_rr0.60'
        ticks = [
            ('exness', 'XAUUSD', _stamp('2025-01-06 07:00:00'), 100, 100.1),
            ('exness', 'XAUUSD', _stamp('2025-01-06 07:00:01'), 102, 102.1),
        ]
        december_ticks = [('exness', 'XAUUSD', _stamp('2024-12-02 00:00:00'), 100, 100.1)]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw = root / 'raw'
            raw.mkdir()
            december = _source(root, '2024-12', december_ticks)
            january = _source(root, '2025-01', ticks)
            # Match the downloader's raw archive layout for catalog resolution.
            for source in (december, january):
                target = raw / source.zip_path.name
                source.zip_path.replace(target)
            records = []
            for month, source in (('2024-12', december), ('2025-01', january)):
                archive = raw / source.zip_path.name
                records.append(dict(
                    month=month,
                    status='verified',
                    csv=source.csv_path.name,
                    zip=str(Path('raw') / archive.name),
                    csv_sha256=_digest(source.csv_path),
                    zip_sha256=_digest(archive),
                    minutes=1,
                    ticks=1 if month == '2024-12' else 2,
                    url='https://example.invalid/public-ticks',
                ))
            (root / 'metadata.json').write_text(json.dumps(dict(
                source='Public fixture', reference='https://example.invalid',
                requested_months=['2024-12', '2025-01'], months=records,
            )), encoding='utf-8')
            out = root / 'out'
            setup_time = _epoch('2025-01-06 07:00:00')
            streams = {'rsi2_10': {setup_time: Setup(setup_time, True, 101, 99, 1)}}
            with patch('research.high_win.replay_ticks.build_setups', return_value=streams) as build:
                result = run_replay(candidate_id, '2025-01-06', '2025-01-07', root, out)

            self.assertEqual(len(build.call_args.args[0]), 2)
            self.assertEqual(result['label'], 'Custom public-tick replay of XAUUSD, NOT MT5 Strategy Tester.')
            self.assertEqual(result['tick_replay']['ticks_read'], 2)
            self.assertEqual(result['scenarios']['base']['metrics']['trades'], 1)
            self.assertTrue((out / 'results.json').exists())
            self.assertTrue((out / 'base_trades.csv').exists())
            self.assertTrue((out / 'stress_trades.csv').exists())
            with (out / 'base_trades.csv').open(newline='', encoding='utf-8') as source:
                self.assertEqual(len(list(csv.DictReader(source))), 1)
            saved = json.loads((out / 'results.json').read_text(encoding='utf-8'))
            self.assertEqual(saved['source']['metadata']['sha256'], _digest(root / 'metadata.json'))
            self.assertEqual(
                [entry['month'] for entry in saved['source']['tick_months_replayed']], ['2025-01'],
            )

    def test_script_cli_is_usable_from_the_repository_root(self):
        root = Path(__file__).resolve().parents[1]
        completed = subprocess.run(
            [sys.executable, str(root / 'research' / 'high_win' / 'replay_ticks.py'), '--help'],
            cwd=root,
            capture_output=True,
            check=False,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn('--candidate CANDIDATE', completed.stdout)


if __name__ == '__main__':
    unittest.main()
