import math
import unittest

from research.backtest_pullback import Minute
from research.high_win.signals import (
    SIGNAL_KEYS, Candidate, Setup, bollinger_bands, build_setups, candidates,
    rsi_wilder,
)


def _minute(time, open_, high, low, close):
    bid = (open_, high, low, close)
    return Minute(time, bid, tuple(value + .05 for value in bid))


def _trend_minutes(direction=1, bars=604):
    """One real first-minute quote per M5 bucket; partial bars are intentional."""

    closes = [100 + direction * .1 * index for index in range(bars)]
    target = bars - 2
    # A steep pullback then recovery, while the last completed M15 close keeps
    # the long-duration direction intact for the trend-context tests.
    closes[target - 2] = 100 + direction * .1 * (target - 2)
    closes[target - 1] = closes[target - 2] - direction * 2
    closes[target] = closes[target - 2]

    minutes = []
    previous = closes[0] - direction * .1
    for index, close in enumerate(closes):
        open_ = previous
        high = max(open_, close) + .4
        low = min(open_, close) - .4
        if index == target:
            if direction > 0:
                open_ = closes[target - 1]
                high, low = closes[target] + .4, closes[target - 1] - 2.2
            else:
                open_ = closes[target - 1]
                high, low = closes[target - 1] + 2.2, closes[target] - .4
        minutes.append(_minute(index * 300, open_, high, low, close))
        previous = close
    return minutes, target


class HighWinSignalTests(unittest.TestCase):
    def test_candidate_universe_is_complete_and_shares_six_signal_keys(self):
        universe = candidates()
        self.assertEqual(len(universe), 36)
        self.assertEqual([candidate.id for candidate in universe], sorted(candidate.id for candidate in universe))
        self.assertEqual(len({candidate.id for candidate in universe}), 36)
        self.assertEqual({candidate.signal_key for candidate in universe}, set(SIGNAL_KEYS))
        self.assertTrue(all(sum(candidate.signal_key == key for candidate in universe) == 6 for key in SIGNAL_KEYS))
        self.assertEqual(Candidate('example', 'bands', 2.5, .75, .6).signal_key, 'bands_2.5')

    def test_wilder_rsi_seeds_two_changes_and_flat_market_is_fifty(self):
        flat = rsi_wilder([10, 10, 10, 10])
        self.assertTrue(math.isnan(flat[0]))
        self.assertTrue(math.isnan(flat[1]))
        self.assertEqual(flat[2:], [50.0, 50.0])
        self.assertEqual(rsi_wilder([10, 11, 12])[2], 100.0)
        self.assertEqual(rsi_wilder([12, 11, 10])[2], 0.0)
        # Two seed changes with a 1:9 gain/loss ratio are exactly RSI 10.
        boundary = rsi_wilder([100, 102, 84, 86])
        self.assertEqual(boundary[2], 10.0)
        self.assertGreater(boundary[3], 10.0)

    def test_bollinger_uses_population_not_sample_standard_deviation(self):
        lower, upper = bollinger_bands(list(range(1, 21)), 2)
        mean = 10.5
        population_std = math.sqrt(sum((value - mean) ** 2 for value in range(1, 21)) / 20)
        self.assertAlmostEqual(lower[19], mean - 2 * population_std)
        self.assertAlmostEqual(upper[19], mean + 2 * population_std)

    def test_rsi_setup_uses_exact_crossing_boundaries_and_trend_regime(self):
        minutes, target = _trend_minutes(1)
        setups = build_setups(minutes)
        setup_time = (target + 1) * 300
        self.assertIn(setup_time, setups['rsi2_10'])
        self.assertIn(setup_time, setups['rsi2_20'])
        self.assertTrue(setups['rsi2_10'][setup_time].buy)

        down_minutes, down_target = _trend_minutes(-1)
        down_setups = build_setups(down_minutes)
        down_setup = down_setups['rsi2_10'][(down_target + 1) * 300]
        self.assertFalse(down_setup.buy)

    def test_setup_requires_next_m5_first_minute(self):
        minutes, target = _trend_minutes(1)
        without_next_open = [minute for minute in minutes if minute.time != (target + 1) * 300]
        setups = build_setups(without_next_open)
        setup_time = (target + 1) * 300
        self.assertTrue(all(setup_time not in stream for stream in setups.values()))

    def test_m15_ema200_context_requires_201_closed_bars(self):
        minutes, target = _trend_minutes(1, bars=601)
        setup_time = (target + 1) * 300
        setups = build_setups(minutes)
        self.assertTrue(all(setup_time not in stream for stream in setups.values()))

    def test_m15_context_is_closed_at_boundary_and_does_not_look_ahead(self):
        # Target index 604 opens its next M5 at 181500, inside (not at the
        # end of) the developing M15 bar that starts at 180900.
        minutes, target = _trend_minutes(1, bars=606)
        cutoff = (target + 1) * 300
        before = build_setups(minutes)
        changed = [
            minute if minute.time < cutoff else _minute(
                minute.time,
                minute.bid[0] + 1_000,
                minute.bid[1] + 1_000,
                minute.bid[2] + 1_000,
                minute.bid[3] + 1_000,
            )
            for minute in minutes
        ]
        after = build_setups(changed)
        for key in SIGNAL_KEYS:
            self.assertEqual(
                {time: setup for time, setup in before[key].items() if time <= cutoff},
                {time: setup for time, setup in after[key].items() if time <= cutoff},
            )

    def test_sweep_uses_previous_window_without_including_signal_candle(self):
        minutes, target = _trend_minutes(1)
        # The target low is deliberately below the preceding 24-bar low.  If
        # the signal bar were included while finding that floor, no reclaim
        # could ever satisfy the strict comparison.
        setups = build_setups(minutes)
        setup_time = (target + 1) * 300
        self.assertIn(setup_time, setups['sweep_12'])
        self.assertIn(setup_time, setups['sweep_24'])
        setup = setups['sweep_24'][setup_time]
        self.assertEqual((setup.high, setup.low), (minutes[target].bid[1], minutes[target].bid[2]))

    def test_sweep_window_requires_real_contiguous_m5_buckets(self):
        minutes, target = _trend_minutes(1)
        missing_bucket = (target - 4) * 300
        gapped = [minute for minute in minutes if minute.time != missing_bucket]
        setups = build_setups(gapped)
        setup_time = (target + 1) * 300
        self.assertNotIn(setup_time, setups['sweep_12'])
        self.assertNotIn(setup_time, setups['sweep_24'])

    def test_setup_and_source_geometry_are_validated(self):
        with self.assertRaises(ValueError):
            Setup(301, True, 101, 100, 1)
        with self.assertRaises(ValueError):
            build_setups([Minute(0, (100, 99, 98, 100), (100.1, 99.1, 98.1, 100.1))])


if __name__ == '__main__':
    unittest.main()
