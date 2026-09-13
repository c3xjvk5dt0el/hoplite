"""Conservative M1 BID/ASK research proxy, not an MT5/tick backtest."""
from __future__ import annotations

import argparse
from bisect import bisect_right
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
import csv
import hashlib
import json
import math
from pathlib import Path

UTC = timezone.utc


def timestamp(value: str) -> int:
    if value.isdigit():
        n = int(value)
        return n // 1000 if n > 10**11 else n
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return int(parsed.timestamp())


def iso(t: int) -> str:
    return datetime.fromtimestamp(t, UTC).isoformat().replace('+00:00', 'Z')


@dataclass(frozen=True, slots=True)
class Minute:
    time: int
    bid: tuple[float, float, float, float]  # open, high, low, close
    ask: tuple[float, float, float, float]


@dataclass(frozen=True, slots=True)
class Bar:
    time: int
    open: float
    high: float
    low: float
    close: float


@dataclass(frozen=True, slots=True)
class Signal:
    time: int
    buy: bool
    swing_high: float
    swing_low: float
    atr: float
    signal_bar: Bar
    trigger_ema: float
    trend_fast: float
    trend_slow: float


@dataclass(slots=True)
class Position:
    time: int
    buy: bool
    entry: float
    sl: float
    tp: float
    signal_time: int


@dataclass(frozen=True)
class Config:
    rr: float = 1.5
    stop_atr: float = .10
    tick: float = .001
    max_spread: float = .50
    max_spread_fraction: float = .10
    max_hold_seconds: int = 3600
    lots: float = .01
    contract_size: float = 100
    commission: float = .04  # USD round trip at 0.01 lot
    slippage: float = .05


def load_minutes(paths: list[Path]) -> list[Minute]:
    rows = []
    seen = set()
    for path in paths:
        with path.open(newline='') as f:
            for row in csv.DictReader(f):
                t = timestamp(row['timestamp'])
                if t % 60 or t in seen:
                    raise ValueError(f'Duplicate or unaligned minute: {path}: {t}')
                seen.add(t)
                bid = tuple(float(row['bid_' + k]) for k in ('open', 'high', 'low', 'close'))
                ask = tuple(float(row['ask_' + k]) for k in ('open', 'high', 'low', 'close'))
                for o, h, l, c in (bid, ask):
                    if not all(math.isfinite(v) and v > 0 for v in (o, h, l, c)) or not l <= min(o, c) <= max(o, c) <= h:
                        raise ValueError(f'Invalid OHLC at {iso(t)}')
                if any(a < b - 1e-9 for a, b in zip(ask, bid)):
                    raise ValueError(f'Crossed BID/ASK at {iso(t)}')
                rows.append(Minute(t, bid, ask))
    rows.sort(key=lambda x: x.time)
    if not rows:
        raise ValueError('No historical data loaded')
    return rows


def aggregate(minutes: list[Minute], seconds: int) -> list[Bar]:
    result = []
    current = None
    for minute in minutes:
        start = minute.time // seconds * seconds
        o, h, l, c = minute.bid
        if current is None or current.time != start:
            if current is not None:
                result.append(current)
            current = Bar(start, o, h, l, c)
        else:
            current = Bar(start, current.open, max(current.high, h), min(current.low, l), c)
    if current is not None:
        result.append(current)
    return result


def ema(values: list[float], period: int) -> list[float]:
    if not values or period < 1:
        raise ValueError('EMA needs data and a positive period')
    out = [values[0]]
    alpha = 2 / (period + 1)
    for value in values[1:]:
        out.append(alpha * value + (1 - alpha) * out[-1])
    return out


def atr_sma(bars: list[Bar], period: int) -> list[float]:
    if period < 1:
        raise ValueError('ATR period must be positive')
    tr = [0.0] + [max(bars[i].high, bars[i-1].close) - min(bars[i].low, bars[i-1].close)
                  for i in range(1, len(bars))]
    out = [math.nan] * len(bars)
    running = 0.0
    for i in range(1, len(bars)):
        running += tr[i]
        if i > period:
            running -= tr[i-period]
        if i >= period:
            out[i] = running / period
    return out


def pullback_direction(bar: Bar, trigger: float, fast: float, slow: float, old_slow: float) -> bool | None:
    if fast > slow and slow > old_slow and bar.close > bar.open and bar.low <= trigger < bar.close:
        return True
    if fast < slow and slow < old_slow and bar.close < bar.open and bar.high >= trigger > bar.close:
        return False
    return None


def build_signals(minutes: list[Minute]) -> tuple[dict[int, Signal], list[Bar]]:
    m5, m15 = aggregate(minutes, 300), aggregate(minutes, 900)
    if not m5 or not m15:
        return {}, m5
    trigger = ema([b.close for b in m5], 20)
    fast = ema([b.close for b in m15], 20)
    slow = ema([b.close for b in m15], 50)
    atr = atr_sma(m5, 14)
    ends15 = [b.time + 900 for b in m15]
    available_starts = {m.time for m in minutes if m.time % 300 == 0}
    signals = {}
    for i in range(21, len(m5)):
        now = m5[i].time + 300
        if now not in available_starts or m5[i-1].time != m5[i].time - 300 or m5[i-2].time != m5[i].time - 600:
            continue
        j = bisect_right(ends15, now) - 1
        if j < 51 or not math.isfinite(atr[i]) or atr[i] <= 0:
            continue
        side = pullback_direction(m5[i], trigger[i], fast[j], slow[j], slow[j-3])
        if side is None:
            continue
        swing = m5[i-2:i+1]
        signals[now] = Signal(now, side, max(b.high for b in swing), min(b.low for b in swing), atr[i],
                              m5[i], trigger[i], fast[j], slow[j])
    return signals, m5


def price_up(price: float, tick: float) -> float:
    return math.ceil(price / tick - 1e-9) * tick


def price_down(price: float, tick: float) -> float:
    return math.floor(price / tick + 1e-9) * tick


def open_position(signal: Signal, minute: Minute, cfg: Config) -> tuple[Position | None, str]:
    bid, ask = minute.bid[0], minute.ask[0]
    spread = ask - bid
    if spread > cfg.max_spread:
        return None, 'spread'
    buffer = max(cfg.stop_atr * signal.atr, cfg.tick)
    sl = price_down(signal.swing_low - buffer, cfg.tick) if signal.buy else price_up(signal.swing_high + buffer + spread, cfg.tick)
    quote_entry = ask if signal.buy else bid
    risk = quote_entry - sl if signal.buy else sl - quote_entry
    if risk <= 0 or spread > cfg.max_spread_fraction * risk:
        return None, 'spread_to_risk_or_invalid_stop'
    entry = quote_entry + cfg.slippage if signal.buy else quote_entry - cfg.slippage
    risk = entry - sl if signal.buy else sl - entry
    tp = price_up(entry + cfg.rr * risk, cfg.tick) if signal.buy else price_down(entry - cfg.rr * risk, cfg.tick)
    if (signal.buy and (sl >= bid or tp <= bid)) or (not signal.buy and (sl <= ask or tp >= ask)) or min(sl, tp) <= 0:
        return None, 'invalid_stop'
    return Position(minute.time, signal.buy, entry, sl, tp, signal.signal_bar.time), 'opened'


def exit_at_open(pos: Position, minute: Minute, cfg: Config) -> tuple[float, str] | None:
    price = minute.bid[0] if pos.buy else minute.ask[0]
    if (pos.buy and price <= pos.sl) or (not pos.buy and price >= pos.sl):
        return (price - cfg.slippage if pos.buy else price + cfg.slippage), 'stop_gap'
    if (pos.buy and price >= pos.tp) or (not pos.buy and price <= pos.tp):
        return pos.tp, 'target'
    if cfg.max_hold_seconds > 0 and minute.time - pos.time >= cfg.max_hold_seconds:
        return (price - cfg.slippage if pos.buy else price + cfg.slippage), 'timeout'
    return None


def exit_in_minute(pos: Position, minute: Minute, cfg: Config) -> tuple[float, str] | None:
    _, high, low, _ = minute.bid if pos.buy else minute.ask
    stop = low <= pos.sl if pos.buy else high >= pos.sl
    target = high >= pos.tp if pos.buy else low <= pos.tp
    if stop:
        return (pos.sl - cfg.slippage if pos.buy else pos.sl + cfg.slippage), 'both_hit_stop_first' if target else 'stop'
    if target:
        return pos.tp, 'target'
    return None


def simulate(minutes: list[Minute], signals: dict[int, Signal], start: int, end: int, cfg: Config) -> dict:
    data = [m for m in minutes if start <= m.time < end]
    if not data:
        return {'available': False, 'requested_start': iso(start), 'requested_end_exclusive': iso(end)}
    pos = None
    trades = []
    skips = Counter()

    def close_position(minute: Minute, price: float, reason: str) -> None:
        nonlocal pos
        assert pos is not None
        gross = (price - pos.entry) * (1 if pos.buy else -1) * cfg.lots * cfg.contract_size
        trades.append(dict(side='buy' if pos.buy else 'sell', entry_time=iso(pos.time), exit_time=iso(minute.time),
                           signal_time=iso(pos.signal_time), entry=pos.entry, sl=pos.sl, tp=pos.tp, exit=price,
                           gross=gross, commission=cfg.commission, net=gross-cfg.commission,
                           reason=reason, hold_minutes=(minute.time-pos.time)/60,
                           crosses_utc_date=iso(pos.time)[:10] != iso(minute.time)[:10]))
        pos = None

    for minute in data:
        if pos is not None:
            event = exit_at_open(pos, minute, cfg)
            if event:
                close_position(minute, *event)
        if minute.time in signals:
            if pos is None:
                pos, reason = open_position(signals[minute.time], minute, cfg)
                skips[reason] += 1
            else:
                skips['position_open'] += 1
        if pos is not None:
            event = exit_in_minute(pos, minute, cfg)
            if event:
                close_position(minute, *event)
    if pos is not None:
        minute = data[-1]
        price = minute.bid[3] - cfg.slippage if pos.buy else minute.ask[3] + cfg.slippage
        close_position(minute, price, 'end_of_period')
    return dict(available=True, observed_start=iso(data[0].time), observed_last_minute=iso(data[-1].time),
                minutes=len(data), skips=dict(skips), summary=summary(trades),
                by_side={s: summary([t for t in trades if t['side']==s]) for s in ('buy', 'sell')},
                by_exit_month={month: summary([t for t in trades if t['exit_time'][:7]==month])
                               for month in sorted({t['exit_time'][:7] for t in trades})}, trades=trades)


def summary(trades: list[dict]) -> dict:
    profits = [t['net'] for t in trades]
    wins, losses = [p for p in profits if p > 0], [p for p in profits if p < 0]
    equity = peak = max_dd = 0.0
    streak = longest = 0
    for p in profits:
        equity += p
        peak = max(peak, equity)
        max_dd = max(max_dd, peak-equity)
        streak = streak + 1 if p < 0 else 0
        longest = max(longest, streak)
    return dict(trades=len(trades), wins=len(wins), losses=len(losses),
                win_rate_pct=round(100*len(wins)/len(trades), 3) if trades else None,
                net_usd=round(sum(profits), 2), gross_profit_usd=round(sum(wins), 2),
                gross_loss_usd=round(sum(losses), 2),
                profit_factor=round(sum(wins)/-sum(losses), 4) if losses else None,
                average_win_usd=round(sum(wins)/len(wins), 3) if wins else None,
                average_loss_usd=round(sum(losses)/len(losses), 3) if losses else None,
                expected_payoff_usd=round(sum(profits)/len(trades), 4) if trades else None,
                closed_trade_max_drawdown_usd=round(max_dd, 2), max_consecutive_losses=longest,
                ambiguous_minutes=sum(t['reason']=='both_hit_stop_first' for t in trades),
                cross_utc_date_trades=sum(t['crosses_utc_date'] for t in trades),
                exits_after_60_minutes=sum(t['hold_minutes']>60 for t in trades),
                exit_reasons=dict(Counter(t['reason'] for t in trades)))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('csv', nargs='+', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    minutes = load_minutes(args.csv)
    signals, _ = build_signals(minutes)
    periods = [('2025_H1', '2025-01-01', '2025-07-01'), ('2025_H2', '2025-07-01', '2026-01-01'),
               ('2026_Jan_May', '2026-01-01', '2026-06-01'), ('2026_Jun_Aug', '2026-06-01', '2026-09-01')]
    result = dict(kind='M1 BID/ASK OHLC proxy, NOT MT5/tick backtest',
                  files=[{'path':str(p), 'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in args.csv],
                  total_minutes=len(minutes), signal_count=len(signals), scenarios={})
    args.out.mkdir(parents=True, exist_ok=True)
    for name, slippage in [('base', .05), ('stress', .15)]:
        cfg = Config(slippage=slippage)
        results = {}
        for label, start, end in periods:
            run = simulate(minutes, signals, timestamp(start), timestamp(end), cfg)
            if run.get('available'):
                trades = run.pop('trades')
                if trades:
                    with (args.out / f'{name}_{label}_trades.csv').open('w', newline='') as f:
                        writer = csv.DictWriter(f, fieldnames=list(trades[0]))
                        writer.writeheader()
                        writer.writerows(trades)
                print(name, label, json.dumps(run['summary']), flush=True)
            else:
                print(name, label, 'UNAVAILABLE', flush=True)
            results[label] = run
        result['scenarios'][name] = dict(config=cfg.__dict__, periods=results)
    (args.out / 'results.json').write_text(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
