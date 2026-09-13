"""Shared research execution for bounded high-win candidates; no broker connection."""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import math
from statistics import mean, median

from research.backtest_pullback import Minute, iso, price_down, price_up
from research.high_win.signals import Candidate, Setup

UTC = timezone.utc


@dataclass(frozen=True)
class Costs:
    slippage: float = .05
    commission: float = .04
    lots: float = .01
    contract_size: float = 100
    tick: float = .001


@dataclass(frozen=True)
class Rules:
    start_hour: int = 7
    end_hour: int = 18
    max_hold_seconds: int = 2700
    max_entries_day: int = 12
    daily_loss_budget: float = 25
    max_stop_price: float = 15
    max_stop_atr: float = 2.5
    max_spread: float = .5
    max_spread_fraction: float = .1
    max_delay_seconds: int = 30


@dataclass(slots=True)
class Trade:
    time: int
    buy: bool
    entry: float
    sl: float
    tp: float


def entry_levels(setup: Setup, bid: float, ask: float, candidate: Candidate,
                 costs: Costs, rules: Rules) -> tuple[Trade | None, str, float]:
    values = (bid, ask, setup.high, setup.low, setup.atr, candidate.min_stop_atr, candidate.rr)
    if not all(math.isfinite(v) and v > 0 for v in values) or ask < bid or setup.high < setup.low:
        return None, 'invalid_quote_or_setup', 0
    spread = ask-bid
    if spread > rules.max_spread:
        return None, 'spread', 0
    quote = ask if setup.buy else bid
    buffer = max(.1*setup.atr, costs.tick)
    if setup.buy:
        sl = price_down(min(setup.low-buffer, quote-candidate.min_stop_atr*setup.atr), costs.tick)
        risk = quote-sl
    else:
        sl = price_up(max(setup.high+buffer+spread, quote+candidate.min_stop_atr*setup.atr), costs.tick)
        risk = sl-quote
    if risk <= 0 or risk > rules.max_stop_price or risk > rules.max_stop_atr*setup.atr:
        return None, 'stop_cap', 0
    if spread > rules.max_spread_fraction*risk:
        return None, 'spread_to_risk', 0
    fill = quote+costs.slippage if setup.buy else quote-costs.slippage
    actual_risk = fill-sl if setup.buy else sl-fill
    tp = price_up(fill+candidate.rr*actual_risk, costs.tick) if setup.buy else price_down(fill-candidate.rr*actual_risk, costs.tick)
    if min(fill, sl, tp) <= 0 or (setup.buy and not sl < bid < tp) or (not setup.buy and not tp < ask < sl):
        return None, 'invalid_levels', 0
    estimated_loss = (actual_risk+costs.slippage)*costs.lots*costs.contract_size+costs.commission
    return Trade(setup.time, setup.buy, fill, sl, tp), 'opened', estimated_loss


class Portfolio:
    def __init__(self, candidate: Candidate, setups: dict[int, Setup], start: int, end: int,
                 costs: Costs = Costs(), rules: Rules = Rules()):
        self.candidate, self.setups = candidate, setups
        self.start, self.end, self.costs, self.rules = start, end, costs, rules
        self.position = None
        self.trades = []
        self.daily_pnl = defaultdict(float)
        self.daily_entries = Counter()
        self.skips = Counter()
        self.last_bar = None
        self.last_quote = None
        self.quote_count = 0

    def close(self, time: int, price: float, reason: str):
        p = self.position
        assert p is not None
        gross = (price-p.entry)*(1 if p.buy else -1)*self.costs.lots*self.costs.contract_size
        net = gross-self.costs.commission
        self.trades.append(dict(entry_time=iso(p.time), exit_time=iso(time), side='buy' if p.buy else 'sell',
                                entry=p.entry, sl=p.sl, tp=p.tp, exit=price, gross=gross, net=net,
                                commission=self.costs.commission, reason=reason, hold_minutes=(time-p.time)/60,
                                cross_utc_date=p.time//86400 != time//86400))
        self.daily_pnl[time//86400] += net
        self.position = None

    def on_quote(self, time: int, bid: float, ask: float, tick_replay: bool = False):
        if not self.start <= time < self.end:
            return
        if not (math.isfinite(bid) and math.isfinite(ask) and 0 < bid <= ask):
            raise ValueError('Invalid executable quote')
        self.quote_count += 1
        self.last_quote = (time, bid, ask)
        p = self.position
        if p is not None:
            quote = bid if p.buy else ask
            hit_stop = quote <= p.sl if p.buy else quote >= p.sl
            hit_target = quote >= p.tp if p.buy else quote <= p.tp
            if hit_stop:
                fill = quote-self.costs.slippage if p.buy else quote+self.costs.slippage
                self.close(time, fill, 'stop_tick' if tick_replay else 'stop_gap')
            elif hit_target:
                self.close(time, p.tp, 'target')
            elif time-p.time >= self.rules.max_hold_seconds:
                self.close(time, quote-self.costs.slippage if p.buy else quote+self.costs.slippage, 'timeout')
        bar = time//300*300
        if bar == self.last_bar:
            return
        self.last_bar = bar
        setup = self.setups.get(bar)
        if setup is None:
            return
        day = time//86400
        weekday, hour = (day+3)%7, (time%86400)//3600
        if weekday >= 5 or not self.rules.start_hour <= hour < self.rules.end_hour:
            self.skips['session'] += 1
            return
        if time-bar > self.rules.max_delay_seconds:
            self.skips['late_first_quote'] += 1
            return
        if self.position is not None:
            self.skips['position_open'] += 1
            return
        if self.daily_entries[day] >= self.rules.max_entries_day:
            self.skips['entry_limit'] += 1
            return
        position, reason, risk = entry_levels(setup, bid, ask, self.candidate, self.costs, self.rules)
        if position is None:
            self.skips[reason] += 1
            return
        if self.daily_pnl[day]-risk < -self.rules.daily_loss_budget:
            self.skips['daily_risk_budget'] += 1
            return
        position.time = time
        self.position = position
        self.daily_entries[day] += 1
        self.skips['opened'] += 1

    def on_range(self, minute: Minute):
        p = self.position
        if p is None or not self.start <= minute.time < self.end:
            return
        _, high, low, _ = minute.bid if p.buy else minute.ask
        stop = low <= p.sl if p.buy else high >= p.sl
        target = high >= p.tp if p.buy else low <= p.tp
        if stop:
            self.close(minute.time, p.sl-self.costs.slippage if p.buy else p.sl+self.costs.slippage,
                       'both_hit_stop_first' if target else 'stop')
        elif target:
            self.close(minute.time, p.tp, 'target')

    def finish(self):
        if self.position is not None and self.last_quote is not None:
            time, bid, ask = self.last_quote
            quote = bid if self.position.buy else ask
            self.close(time, quote-self.costs.slippage if self.position.buy else quote+self.costs.slippage, 'end_of_period')
        return dict(summary=summary(self.trades, self.start, self.end), skips=dict(self.skips),
                    quotes=self.quote_count, trades=self.trades)


def simulate(minutes: list[Minute], candidate: Candidate, setups: dict[int, Setup], start: int, end: int,
             costs: Costs = Costs(), rules: Rules = Rules()):
    portfolio = Portfolio(candidate, setups, start, end, costs, rules)
    for m in minutes:
        if start <= m.time < end:
            portfolio.on_quote(m.time, m.bid[0], m.ask[0])
            portfolio.on_range(m)
            portfolio.last_quote = (m.time, m.bid[3], m.ask[3])
    return portfolio.finish()


def summary(trades: list[dict], start: int, end: int) -> dict:
    pnl = [t['net'] for t in trades]
    profits, losses = [p for p in pnl if p>0], [p for p in pnl if p<0]
    value = peak = drawdown = 0.0
    streak = max_streak = 0
    daily = defaultdict(float)
    for t in trades:
        p = t['net']
        value += p
        peak = max(peak, value)
        drawdown = max(drawdown, peak-value)
        streak = streak+1 if p < 0 else 0
        max_streak = max(max_streak, streak)
        daily[t['exit_time'][:10]] += p
    dates = []
    dt = datetime.fromtimestamp(start, UTC)
    until = datetime.fromtimestamp(end, UTC)
    while dt < until:
        dates.append(dt.date())
        dt += timedelta(days=1)
    weekdays = [d for d in dates if d.weekday()<5]
    activity_dates = {t[key][:10] for t in trades for key in ('entry_time', 'exit_time')}
    day_values = [daily[d.isoformat()] for d in weekdays]
    weeks = defaultdict(list)
    for d in dates:
        y, w, _ = d.isocalendar()
        weeks[f'{y}-W{w:02d}'].append(d)
    weekly = {key:dict(net_usd=round(sum(daily[d.isoformat()] for d in days), 6),
                      complete=len(days)==7, days=len(days)) for key,days in sorted(weeks.items())}
    full_week_values = [v['net_usd'] for v in weekly.values() if v['complete']]
    positive_weeks = sum(v>0 for v in full_week_values)
    losing_weeks = sum(v<0 for v in full_week_values)
    weekly_streak = max_weekly_streak = 0
    for value in full_week_values:
        weekly_streak = weekly_streak+1 if value<0 else 0
        max_weekly_streak = max(max_weekly_streak,weekly_streak)
    return dict(trades=len(trades), wins=len(profits), losses=len(losses),
                win_rate_pct=round(100*len(profits)/len(trades), 4) if trades else 0,
                net_usd=round(sum(pnl), 6), profit_factor=sum(profits)/-sum(losses) if losses else None,
                average_win_usd=mean(profits) if profits else 0, average_loss_usd=mean(losses) if losses else 0,
                expected_payoff_usd=mean(pnl) if pnl else 0,
                closed_trade_max_drawdown_usd=drawdown, max_consecutive_losses=max_streak,
                weekday_count=len(day_values), no_trade_weekdays=sum(d.isoformat() not in activity_dates for d in weekdays),
                average_weekday_usd=mean(day_values) if day_values else 0,
                median_weekday_usd=median(day_values) if day_values else 0,
                worst_weekday_usd=min(day_values) if day_values else 0,
                days_at_least_20=sum(v>=20 for v in day_values),
                days_at_least_20_pct=100*sum(v>=20 for v in day_values)/len(day_values) if day_values else 0,
                full_week_count=len(full_week_values), positive_weeks=positive_weeks,
                positive_weeks_pct=100*positive_weeks/len(full_week_values) if full_week_values else 0,
                average_full_week_usd=mean(full_week_values) if full_week_values else 0,
                median_full_week_usd=median(full_week_values) if full_week_values else 0,
                worst_full_week_usd=min(full_week_values) if full_week_values else 0,
                weeks_at_least_100=sum(v>=100 for v in full_week_values),
                weeks_at_least_100_pct=100*sum(v>=100 for v in full_week_values)/len(full_week_values) if full_week_values else 0,
                losing_weeks=losing_weeks, max_consecutive_losing_weeks=max_weekly_streak,
                partial_weeks=sum(not v['complete'] for v in weekly.values()),
                partial_week_ids=[key for key,v in weekly.items() if not v['complete']],
                off_weekday_net_usd=sum(daily[d.isoformat()] for d in dates if d.weekday()>=5),
                cross_utc_date_trades=sum(t['cross_utc_date'] for t in trades),
                exits_after_45_minutes=sum(t['hold_minutes']>45 for t in trades),
                ambiguous_minutes=sum(t['reason']=='both_hit_stop_first' for t in trades),
                exit_reasons=dict(Counter(t['reason'] for t in trades)),
                weeks=weekly, days={d.isoformat():round(daily[d.isoformat()], 6) for d in dates})
