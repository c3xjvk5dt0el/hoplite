import math
from pathlib import Path
import tempfile
import unittest
import zipfile

from research.backtest_pullback import (
    Bar, Config, Minute, Position, Signal, aggregate, atr_sma, build_signals,
    ema, exit_at_open, exit_in_minute, load_minutes, open_position,
    pullback_direction, simulate, timestamp,
)
from research.download_exness import aggregate_zip, months


class PullbackResearchTests(unittest.TestCase):
    def setUp(self):
        self.cfg = Config()
        self.bar = Bar(0, 100, 102, 99, 101)
        self.signal = Signal(300, True, 103, 98, 2, self.bar, 100, 102, 101)

    def test_time_parsing(self):
        self.assertEqual(timestamp('2025-01-01'), 1735689600)
        self.assertEqual(timestamp('2025-01-01T00:00:00Z'), 1735689600)
        self.assertEqual(timestamp('2025-01-01T01:00:00+01:00'), 1735689600)
        self.assertEqual(timestamp('1735689600000'), 1735689600)

    def test_ema_recursion(self):
        self.assertEqual(ema([10, 12, 14], 3), [10, 11, 12.5])

    def test_atr_is_rolling_sma_not_wilder(self):
        bars = [Bar(0, 10, 11, 9, 10), Bar(300, 10, 12, 9, 11),
                Bar(600, 11, 15, 10, 14), Bar(900, 14, 20, 13, 19)]
        values = atr_sma(bars, 2)
        self.assertTrue(math.isnan(values[1]))
        self.assertEqual(values[2:], [4, 6])

    def test_touch_reclaim_and_trend(self):
        self.assertIs(pullback_direction(self.bar, 100, 102, 101, 100), True)
        self.assertIsNone(pullback_direction(self.bar, 100, 100, 101, 100))
        self.assertIsNone(pullback_direction(self.bar, 100, 102, 101, 101))
        self.assertIsNone(pullback_direction(self.bar, 101, 102, 101, 100))
        self.assertIs(pullback_direction(Bar(0, 101, 102, 99, 100), 101, 99, 100, 101), False)

    def test_no_invented_gap_bars(self):
        data = [Minute(0, (100, 102, 99, 101), (100.1, 102.1, 99.1, 101.1)),
                Minute(900, (101, 103, 100, 102), (101.1, 103.1, 100.1, 102.1))]
        self.assertEqual([b.time for b in aggregate(data, 300)], [0, 900])

    def test_closed_timeframe_no_future_leakage(self):
        data = []
        for i in range(1500):
            o = 100 + .004*i + .12*math.sin(i*.15)
            c = 100 + .004*(i+1) + .12*math.sin((i+1)*.15)
            bid = (o, max(o, c)+.08, min(o, c)-.08, c)
            data.append(Minute(i*60, bid, tuple(x+.05 for x in bid)))
        signals, _ = build_signals(data)
        self.assertTrue(signals, 'Fixture must exercise actual emitted signals')
        cutoff = 1200*60
        changed = [m if m.time < cutoff else Minute(m.time, tuple(x+1000 for x in m.bid), tuple(x+1000 for x in m.ask)) for m in data]
        later, _ = build_signals(changed)
        before = {t:s for t,s in signals.items() if t < cutoff}
        self.assertTrue(before)
        self.assertEqual(before, {t:s for t,s in later.items() if t < cutoff})
        for t, signal in list(before.items())[:5]:
            completed = [b for b in aggregate(data, 900) if b.time+900 <= t]
            self.assertAlmostEqual(signal.trend_fast, ema([b.close for b in completed], 20)[-1])
            self.assertAlmostEqual(signal.trend_slow, ema([b.close for b in completed], 50)[-1])

    def test_buy_actual_entry_and_rr(self):
        m = Minute(300, (101, 102, 100, 101), (101.2, 102.2, 100.2, 101.2))
        pos, reason = open_position(self.signal, m, self.cfg)
        self.assertEqual(reason, 'opened')
        self.assertAlmostEqual(pos.entry, 101.25)
        self.assertAlmostEqual(pos.sl, 97.8)
        self.assertAlmostEqual(pos.tp, 106.425)

    def test_spread_absolute_rejection(self):
        m = Minute(300, (101, 102, 100, 101), (101.6, 102.6, 100.6, 101.6))
        self.assertIsNone(open_position(self.signal, m, self.cfg)[0])

    def test_spread_risk_rejection(self):
        signal = Signal(300, True, 101, 100.8, .1, self.bar, 100, 102, 101)
        m = Minute(300, (101, 102, 100, 101), (101.2, 102.2, 100.2, 101.2))
        self.assertIsNone(open_position(signal, m, self.cfg)[0])

    def test_both_hits_resolve_stop_first(self):
        pos = Position(0, True, 100, 95, 107.5, -300)
        m = Minute(60, (100, 110, 90, 105), (100.2, 110.2, 90.2, 105.2))
        price, reason = exit_in_minute(pos, m, self.cfg)
        self.assertAlmostEqual(price, 94.95)
        self.assertEqual(reason, 'both_hit_stop_first')

    def test_sell_exit_uses_ask_not_bid(self):
        pos = Position(0, False, 100, 105, 96.1, -300)
        m = Minute(60, (100, 101, 96, 100), (100.2, 101.2, 96.2, 100.2))
        self.assertIsNone(exit_in_minute(pos, m, self.cfg))

    def test_stop_gap_uses_worse_open(self):
        pos = Position(0, True, 100, 95, 107.5, -300)
        m = Minute(60, (90, 91, 89, 90), (90.2, 91.2, 89.2, 90.2))
        price, reason = exit_at_open(pos, m, self.cfg)
        self.assertAlmostEqual(price, 89.95)
        self.assertEqual(reason, 'stop_gap')

    def test_target_gap_does_not_credit_positive_slippage(self):
        pos = Position(0, True, 100, 95, 107.5, -300)
        m = Minute(60, (110, 111, 109, 110), (110.2, 111.2, 109.2, 110.2))
        self.assertEqual(exit_at_open(pos, m, self.cfg), (107.5, 'target'))

    def test_timeout_first_available_quote(self):
        pos = Position(0, True, 100, 95, 107.5, -300)
        m = Minute(3600, (101, 102, 100, 101), (101.2, 102.2, 100.2, 101.2))
        self.assertEqual(exit_at_open(pos, m, self.cfg)[1], 'timeout')
        earlier = Minute(3540, m.bid, m.ask)
        self.assertIsNone(exit_at_open(pos, earlier, self.cfg))
        self.assertIsNone(exit_at_open(pos, m, Config(max_hold_seconds=0)))

    def test_single_position_commission_and_no_same_bar_retry(self):
        data = [Minute(300, (101, 102, 100, 101), (101.1, 102.1, 100.1, 101.1)),
                Minute(600, (101, 102, 100, 101), (101.1, 102.1, 100.1, 101.1)),
                Minute(3900, (101, 102, 100, 101), (101.1, 102.1, 100.1, 101.1))]
        result = simulate(data, {300:self.signal, 600:self.signal}, 0, 4000, self.cfg)
        self.assertEqual(result['summary']['trades'], 1)
        self.assertEqual(result['skips']['position_open'], 1)
        self.assertAlmostEqual(result['trades'][0]['net'], -.24)
        self.assertEqual(result['trades'][0]['reason'], 'timeout')

    def test_missing_period_is_not_a_zero_return(self):
        self.assertFalse(simulate([], {}, 0, 1000, self.cfg)['available'])

    def test_csv_rejects_duplicate_or_crossed_data(self):
        header = 'timestamp,bid_open,bid_high,bid_low,bid_close,ask_open,ask_high,ask_low,ask_close\n'
        row = '2025-01-01T00:00:00Z,100,102,99,101,100.2,102.2,99.2,101.2\n'
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'data.csv'
            path.write_text(header+row+row)
            with self.assertRaises(ValueError):
                load_minutes([path])
            path.write_text(header+row.replace('100.2,102.2,99.2,101.2', '99,101,98,100'))
            with self.assertRaises(ValueError):
                load_minutes([path])

    def test_exness_month_range_exclusive(self):
        self.assertEqual(months('2024-12', '2025-03'), ['2024-12', '2025-01', '2025-02'])
        with self.assertRaises(ValueError):
            months('2025-02', '2025-01')

    def test_exness_paired_tick_aggregation(self):
        ticks = ('"Exness","Symbol","Timestamp","Bid","Ask"\n'
                 '"exness","XAUUSD","2025-01-02 00:00:01.001Z",100,100.2\n'
                 '"exness","XAUUSD","2025-01-02 00:00:03.004Z",101,101.3\n'
                 '"exness","XAUUSD","2025-01-02 00:00:58.500Z",99,99.1\n'
                 '"exness","XAUUSD","2025-01-02 00:05:00.000Z",102,102.1\n')
        with tempfile.TemporaryDirectory() as folder:
            archive, output = Path(folder)/'ticks.zip', Path(folder)/'minutes.csv'
            with zipfile.ZipFile(archive, 'w') as z:
                z.writestr('test.csv', ticks)
            result = aggregate_zip(archive, output, '2025-01')
            self.assertEqual(result['ticks'], 4)
            self.assertEqual(result['minutes'], 2)
            rows = load_minutes([output])
            self.assertEqual(rows[0].bid, (100, 101, 99, 99))
            self.assertEqual(rows[0].ask, (100.2, 101.3, 99.1, 99.1))
            self.assertEqual(rows[1].time-rows[0].time, 300)

    def test_exness_rejects_unordered_ticks_without_publishing_csv(self):
        ticks = ('"Exness","Symbol","Timestamp","Bid","Ask"\n'
                 '"exness","XAUUSD","2025-01-02 00:00:03.004Z",101,101.3\n'
                 '"exness","XAUUSD","2025-01-02 00:00:01.001Z",100,100.2\n')
        with tempfile.TemporaryDirectory() as folder:
            archive, output = Path(folder)/'ticks.zip', Path(folder)/'minutes.csv'
            with zipfile.ZipFile(archive, 'w') as z:
                z.writestr('test.csv', ticks)
            with self.assertRaises(ValueError):
                aggregate_zip(archive, output, '2025-01')
            self.assertFalse(output.exists())
            self.assertFalse(output.with_suffix('.part').exists())


if __name__ == '__main__':
    unittest.main()
