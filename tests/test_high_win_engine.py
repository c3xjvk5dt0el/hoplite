import unittest

from research.backtest_pullback import Minute, iso, timestamp
from research.high_win.engine import Costs, Portfolio, Rules, entry_levels, summary
from research.high_win.signals import Candidate, Setup


class HighWinEngineTests(unittest.TestCase):
    def setUp(self):
        self.now=timestamp('2025-01-06T07:00:00Z')
        self.candidate=Candidate('test','rsi2',10,.75,.85)
        self.setup=Setup(self.now,True,103,99,2)
        self.costs=Costs()
        self.rules=Rules()

    def portfolio(self, setup=None):
        return Portfolio(self.candidate,{self.now:setup or self.setup},
                         timestamp('2025-01-01'),timestamp('2025-02-01'))

    def test_levels_fixed_lot_and_actual_fill(self):
        trade,reason,risk=entry_levels(self.setup,101,101.1,self.candidate,self.costs,self.rules)
        self.assertEqual(reason,'opened')
        self.assertAlmostEqual(trade.entry,101.15)
        self.assertAlmostEqual(trade.sl,98.8)
        self.assertAlmostEqual(trade.tp,103.148)
        self.assertAlmostEqual(risk,2.44)

    def test_minimum_stop_expands_outward(self):
        setup=Setup(self.now,True,103,100.9,2)
        trade,_,_=entry_levels(setup,101,101.1,self.candidate,self.costs,self.rules)
        self.assertAlmostEqual(trade.sl,99.6)

    def test_stop_caps_skip_not_clip(self):
        for setup in [Setup(self.now,True,103,80,10),Setup(self.now,True,103,95,2)]:
            trade,reason,_=entry_levels(setup,101,101.1,self.candidate,self.costs,self.rules)
            self.assertIsNone(trade)
            self.assertEqual(reason,'stop_cap')

    def test_short_stop_includes_spread_and_short_fill_bid(self):
        setup=Setup(self.now,False,103,99,2)
        trade,_,_=entry_levels(setup,101,101.1,self.candidate,self.costs,self.rules)
        self.assertAlmostEqual(trade.entry,100.95)
        self.assertAlmostEqual(trade.sl,103.3)
        self.assertLess(trade.tp,trade.entry)

    def test_invalid_and_wide_quotes_rejected(self):
        for bid,ask in [(101,100),(float('nan'),102),(101,101.6)]:
            self.assertIsNone(entry_levels(self.setup,bid,ask,self.candidate,self.costs,self.rules)[0])

    def test_daily_budget_counts_prospective_loss(self):
        p=self.portfolio();p.daily_pnl[self.now//86400]=-24
        p.on_quote(self.now,101,101.1)
        self.assertIsNone(p.position)
        self.assertEqual(p.skips['daily_risk_budget'],1)
        p=self.portfolio();p.daily_pnl[self.now//86400]=-22
        p.on_quote(self.now,101,101.1)
        self.assertIsNotNone(p.position)

    def test_daily_entry_limit(self):
        p=self.portfolio();p.daily_entries[self.now//86400]=12
        p.on_quote(self.now,101,101.1)
        self.assertIsNone(p.position)
        self.assertEqual(p.skips['entry_limit'],1)

    def test_first_tick_delay_and_same_bar_retry(self):
        p=self.portfolio();p.on_quote(self.now+31,101,101.1)
        self.assertIsNone(p.position)
        self.assertEqual(p.skips['late_first_quote'],1)
        p=self.portfolio();p.on_quote(self.now+30,101,101.1)
        self.assertIsNotNone(p.position)
        p.on_quote(self.now+31,98,98.1,True)
        p.on_quote(self.now+32,101,101.1,True)
        self.assertIsNone(p.position)
        self.assertEqual(len(p.trades),1)

    def test_session_and_weekend(self):
        for date in ['2025-01-06T06:55:00Z','2025-01-06T18:00:00Z','2025-01-11T07:00:00Z']:
            now=timestamp(date)
            setup=Setup(now,True,103,99,2)
            p=Portfolio(self.candidate,{now:setup},timestamp('2025-01-01'),timestamp('2025-02-01'))
            p.on_quote(now,101,101.1)
            self.assertIsNone(p.position)
            self.assertEqual(p.skips['session'],1)

    def test_ohlc_collision_stop_first_and_commission(self):
        p=self.portfolio();p.on_quote(self.now,101,101.1)
        p.on_range(Minute(self.now,(101,110,90,100),(101.1,110.1,90.1,100.1)))
        self.assertEqual(p.trades[0]['reason'],'both_hit_stop_first')
        self.assertAlmostEqual(p.trades[0]['net'],-2.44)

    def test_timeout_and_short_ask_exit(self):
        p=self.portfolio();p.on_quote(self.now,101,101.1)
        p.on_quote(self.now+2699,101,101.1)
        self.assertIsNotNone(p.position)
        p.on_quote(self.now+2700,101,101.1)
        self.assertEqual(p.trades[0]['reason'],'timeout')
        p=self.portfolio(Setup(self.now,False,103,99,2))
        p.on_quote(self.now,101,101.1)
        p.on_quote(self.now+1,103.25,103.35,True)
        self.assertEqual(p.trades[0]['reason'],'stop_tick')

    def test_target_statistics_include_zero_days_weeks(self):
        trade=dict(entry_time=iso(self.now),exit_time=iso(self.now+60),net=100,
                   reason='target',cross_utc_date=False,hold_minutes=1)
        result=summary([trade],timestamp('2025-01-06'),timestamp('2025-01-20'))
        self.assertEqual(result['weekday_count'],10)
        self.assertEqual(result['no_trade_weekdays'],9)
        self.assertEqual(result['average_weekday_usd'],10)
        self.assertEqual(result['full_week_count'],2)
        self.assertEqual(result['average_full_week_usd'],50)
        self.assertEqual(result['weeks_at_least_100'],1)
        self.assertEqual(result['days_at_least_20'],1)
        self.assertEqual(result['days_at_least_20_pct'],10)
        self.assertEqual(result['weeks_at_least_100_pct'],50)

    def test_partial_boundary_weeks_excluded(self):
        result=summary([],timestamp('2025-01-01'),timestamp('2025-01-15'))
        self.assertEqual(result['full_week_count'],1)
        self.assertEqual(result['partial_weeks'],2)
        self.assertEqual(result['weeks_at_least_100'],0)
        self.assertEqual(result['partial_week_ids'],['2025-W01','2025-W03'])


if __name__=='__main__':
    unittest.main()
