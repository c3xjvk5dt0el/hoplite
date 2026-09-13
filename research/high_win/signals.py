"""Completed-bar signal generation for the frozen high-win candidate study.

This module deliberately contains no execution, selection, or performance
calculation.  Every setup is keyed by its rule variant so the simulator can
share indicator work among the six configurations that differ only in stop
minimum or reward/risk target.
"""
from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass
import math
from typing import Sequence

from research.backtest_pullback import Bar, Minute, aggregate, atr_sma, ema


M5_SECONDS = 5 * 60
M15_SECONDS = 15 * 60
RSI_PERIOD = 2
BOLLINGER_PERIOD = 20
ATR_PERIOD = 14
M15_EMA_WARMUP_BARS = 201

# Keep this order stable for reproducible serialized research output.
SIGNAL_KEYS = (
    'rsi2_10',
    'rsi2_20',
    'bands_2',
    'bands_2.5',
    'sweep_12',
    'sweep_24',
)


@dataclass(frozen=True, slots=True)
class Candidate:
    """One execution configuration from the fixed 36-candidate universe."""

    id: str
    family: str
    entry_setting: float
    min_stop_atr: float
    rr: float

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id:
            raise ValueError('Candidate id must be a non-empty string')
        if self.family not in {'rsi2', 'bands', 'sweep'}:
            raise ValueError(f'Unknown candidate family: {self.family!r}')
        _positive_finite(self.entry_setting, 'Candidate entry_setting')
        _positive_finite(self.min_stop_atr, 'Candidate min_stop_atr')
        _positive_finite(self.rr, 'Candidate rr')
        # Validate that the setting maps to one of the frozen rule variants.
        candidate_signal_key(self.family, self.entry_setting)

    @property
    def signal_key(self) -> str:
        """The shared signal variant used by this execution configuration."""

        return candidate_signal_key(self.family, self.entry_setting)


@dataclass(frozen=True, slots=True)
class Setup:
    """A completed-bar directional setup ready at ``time`` (next M5 open)."""

    time: int
    buy: bool
    high: float
    low: float
    atr: float

    def __post_init__(self) -> None:
        if isinstance(self.time, bool) or not isinstance(self.time, int) or self.time % M5_SECONDS:
            raise ValueError('Setup time must be an M5-aligned epoch integer')
        if not isinstance(self.buy, bool):
            raise ValueError('Setup buy must be a bool')
        high = _positive_finite(self.high, 'Setup high')
        low = _positive_finite(self.low, 'Setup low')
        if low > high:
            raise ValueError('Setup low cannot exceed high')
        _positive_finite(self.atr, 'Setup atr')


def _positive_finite(value: object, name: str) -> float:
    """Return a finite positive number, rejecting booleans and non-numbers."""

    if isinstance(value, bool):
        raise ValueError(f'{name} must be a finite positive number')
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f'{name} must be a finite positive number') from exc
    if not math.isfinite(number) or number <= 0:
        raise ValueError(f'{name} must be a finite positive number')
    return number


def _setting_label(setting: float) -> str:
    """Format frozen numeric settings without accidental float suffixes."""

    number = _positive_finite(setting, 'entry_setting')
    return str(int(number)) if number.is_integer() else format(number, 'g')


def candidate_signal_key(family: str, entry_setting: float) -> str:
    """Return the signal variant key for a candidate's family and setting."""

    label = _setting_label(entry_setting)
    key = f'{family}_{label}'
    if key not in SIGNAL_KEYS:
        raise ValueError(f'Unsupported frozen signal variant: {key!r}')
    return key


def candidates() -> list[Candidate]:
    """Return the frozen 36 execution configurations in deterministic ID order."""

    variants = (
        ('rsi2', (10.0, 20.0)),
        ('bands', (2.0, 2.5)),
        ('sweep', (12.0, 24.0)),
    )
    items = []
    for family, settings in variants:
        for setting in settings:
            for minimum_stop in (0.75, 1.25):
                for rr in (0.60, 0.85, 1.00):
                    label = _setting_label(setting)
                    items.append(Candidate(
                        id=f'{family}_{label}_stop{minimum_stop:.2f}_rr{rr:.2f}',
                        family=family,
                        entry_setting=setting,
                        min_stop_atr=minimum_stop,
                        rr=rr,
                    ))
    return sorted(items, key=lambda candidate: candidate.id)


def rsi_wilder(values: Sequence[float], period: int = RSI_PERIOD) -> list[float]:
    """Compute RSI with MetaTrader-compatible Wilder smoothing.

    The first RSI value is placed after ``period`` price changes, using their
    arithmetic average as the seed.  A zero average gain and loss is RSI 50.
    Unwarmed entries are ``nan`` so callers cannot mistake them for signals.
    """

    if isinstance(period, bool) or not isinstance(period, int) or period < 1:
        raise ValueError('RSI period must be a positive integer')
    closes = [_positive_finite(value, f'RSI close {index}') for index, value in enumerate(values)]
    result = [math.nan] * len(closes)
    if len(closes) <= period:
        return result

    gains = [0.0] * len(closes)
    losses = [0.0] * len(closes)
    for index in range(1, len(closes)):
        change = closes[index] - closes[index - 1]
        gains[index] = max(change, 0.0)
        losses[index] = max(-change, 0.0)

    average_gain = math.fsum(gains[1:period + 1]) / period
    average_loss = math.fsum(losses[1:period + 1]) / period
    result[period] = _rsi_from_averages(average_gain, average_loss)
    for index in range(period + 1, len(closes)):
        average_gain = ((period - 1) * average_gain + gains[index]) / period
        average_loss = ((period - 1) * average_loss + losses[index]) / period
        result[index] = _rsi_from_averages(average_gain, average_loss)
    return result


def _rsi_from_averages(average_gain: float, average_loss: float) -> float:
    if average_gain == 0 and average_loss == 0:
        return 50.0
    if average_loss == 0:
        return 100.0
    if average_gain == 0:
        return 0.0
    relative_strength = average_gain / average_loss
    return 100.0 - 100.0 / (1.0 + relative_strength)


def bollinger_bands(
    values: Sequence[float],
    multiplier: float,
    period: int = BOLLINGER_PERIOD,
) -> tuple[list[float], list[float]]:
    """Return lower and upper SMA/population-standard-deviation bands."""

    if isinstance(period, bool) or not isinstance(period, int) or period < 1:
        raise ValueError('Bollinger period must be a positive integer')
    scale = _positive_finite(multiplier, 'Bollinger multiplier')
    closes = [_positive_finite(value, f'Bollinger close {index}') for index, value in enumerate(values)]
    lower = [math.nan] * len(closes)
    upper = [math.nan] * len(closes)
    for index in range(period - 1, len(closes)):
        window = closes[index - period + 1:index + 1]
        mean = math.fsum(window) / period
        variance = math.fsum((value - mean) ** 2 for value in window) / period
        # Rounding can only make a mathematically zero variance microscopically negative.
        deviation = math.sqrt(max(variance, 0.0))
        lower[index] = mean - scale * deviation
        upper[index] = mean + scale * deviation
    return lower, upper


def _validated_minutes(minutes: Sequence[Minute]) -> list[Minute]:
    """Validate source quotes before aggregation instead of silently repairing data."""

    normalized = []
    previous_time: int | None = None
    for index, minute in enumerate(minutes):
        if not isinstance(minute, Minute):
            raise ValueError(f'Item {index} is not a Minute')
        if isinstance(minute.time, bool) or not isinstance(minute.time, int) or minute.time % 60:
            raise ValueError(f'Minute {index} time must be a minute-aligned epoch integer')
        if previous_time is not None and minute.time <= previous_time:
            raise ValueError('Minutes must be strictly ordered with no duplicate timestamps')
        previous_time = minute.time
        bid = _validated_ohlc(minute.bid, f'Minute {index} bid')
        ask = _validated_ohlc(minute.ask, f'Minute {index} ask')
        if any(ask_value < bid_value - 1e-9 for ask_value, bid_value in zip(ask, bid)):
            raise ValueError(f'Minute {index} has crossed BID/ASK quotes')
        normalized.append(Minute(minute.time, bid, ask))
    return normalized


def _validated_ohlc(values: object, name: str) -> tuple[float, float, float, float]:
    try:
        if len(values) != 4:  # type: ignore[arg-type]
            raise ValueError
        open_, high, low, close = tuple(values)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise ValueError(f'{name} must contain open, high, low, close') from exc
    open_value = _positive_finite(open_, f'{name} open')
    high_value = _positive_finite(high, f'{name} high')
    low_value = _positive_finite(low, f'{name} low')
    close_value = _positive_finite(close, f'{name} close')
    if not low_value <= min(open_value, close_value) <= max(open_value, close_value) <= high_value:
        raise ValueError(f'{name} has invalid OHLC geometry')
    return open_value, high_value, low_value, close_value


def _contiguous(bars: Sequence[Bar], first: int, last: int, seconds: int = M5_SECONDS) -> bool:
    """Whether an inclusive bar window has every real clock bucket present."""

    if first < 0 or last >= len(bars) or first > last:
        return False
    return all(bars[index].time == bars[index - 1].time + seconds for index in range(first + 1, last + 1))


def _setup(time: int, buy: bool, bars: Sequence[Bar], atr: float) -> Setup:
    if not bars:
        raise ValueError('A setup requires at least one selected swing bar')
    high = max(bar.high for bar in bars)
    low = min(bar.low for bar in bars)
    return Setup(time=time, buy=buy, high=high, low=low, atr=atr)


def _m15_context_index(ends: Sequence[int], setup_time: int) -> int:
    """Use only a M15 bar whose nominal close is no later than setup time."""

    return bisect_right(ends, setup_time) - 1


def _m15_trend(
    index: int,
    fast: Sequence[float],
    slow: Sequence[float],
    long: Sequence[float] | None,
    buy: bool,
) -> bool:
    if index < 3:
        return False
    current_fast = fast[index]
    current_slow = slow[index]
    earlier_slow = slow[index - 3]
    if not all(math.isfinite(value) for value in (current_fast, current_slow, earlier_slow)):
        return False
    if long is not None:
        current_long = long[index]
        if not math.isfinite(current_long):
            return False
        if buy:
            return current_slow > current_long and current_slow > earlier_slow
        return current_slow < current_long and current_slow < earlier_slow
    if buy:
        return current_fast > current_slow and current_slow > earlier_slow
    return current_fast < current_slow and current_slow < earlier_slow


def _m15_range(
    index: int,
    fast: Sequence[float],
    slow: Sequence[float],
    atr: Sequence[float],
) -> bool:
    if index < 3:
        return False
    values = (fast[index], slow[index], slow[index - 3], atr[index])
    if not all(math.isfinite(value) for value in values):
        return False
    current_fast, current_slow, earlier_slow, current_atr = values
    if current_atr < 0:
        return False
    return (abs(current_fast - current_slow) <= 0.5 * current_atr
            and abs(current_slow - earlier_slow) <= 0.3 * current_atr)


def _bullish(bar: Bar) -> bool:
    return bar.close > bar.open


def _bearish(bar: Bar) -> bool:
    return bar.close < bar.open


def _finite_positive_atr(value: float) -> bool:
    return math.isfinite(value) and value > 0


def build_setups(minutes: list[Minute]) -> dict[str, dict[int, Setup]]:
    """Build all six completed-bar setup streams from validated M1 BID/ASK data.

    A signal M5 candle becomes actionable only when the first actual minute of
    its next M5 bucket exists.  M15 values are selected by nominal close time,
    never from the currently developing M15 candle.
    """

    result: dict[str, dict[int, Setup]] = {key: {} for key in SIGNAL_KEYS}
    source = _validated_minutes(minutes)
    if not source:
        return result

    m5 = aggregate(source, M5_SECONDS)
    m15 = aggregate(source, M15_SECONDS)
    if not m5 or not m15:
        return result

    m5_closes = [bar.close for bar in m5]
    m15_closes = [bar.close for bar in m15]
    m5_atr = atr_sma(m5, ATR_PERIOD)
    m15_atr = atr_sma(m15, ATR_PERIOD)
    rsi2 = rsi_wilder(m5_closes)
    lower_2, upper_2 = bollinger_bands(m5_closes, 2.0)
    lower_25, upper_25 = bollinger_bands(m5_closes, 2.5)
    m15_ema20 = ema(m15_closes, 20)
    m15_ema50 = ema(m15_closes, 50)
    m15_ema200 = ema(m15_closes, 200)
    m15_ends = [bar.time + M15_SECONDS for bar in m15]
    minute_times = {minute.time for minute in source}

    for index, current in enumerate(m5):
        setup_time = current.time + M5_SECONDS
        # The simulator will reproduce the first-tick delay; this only proves
        # that a new M5 bar actually began rather than inventing a clock tick.
        if setup_time not in minute_times:
            continue
        context = _m15_context_index(m15_ends, setup_time)
        if context < M15_EMA_WARMUP_BARS - 1 or not _finite_positive_atr(m5_atr[index]):
            continue

        if index >= 2 and _contiguous(m5, index - 2, index):
            previous_rsi = rsi2[index - 1]
            current_rsi = rsi2[index]
            if math.isfinite(previous_rsi) and math.isfinite(current_rsi):
                swing = m5[index - 2:index + 1]
                if _bullish(current) and _m15_trend(context, m15_ema20, m15_ema50, m15_ema200, True):
                    for threshold, key in ((10.0, 'rsi2_10'), (20.0, 'rsi2_20')):
                        if previous_rsi <= threshold and current_rsi > threshold:
                            result[key][setup_time] = _setup(setup_time, True, swing, m5_atr[index])
                if _bearish(current) and _m15_trend(context, m15_ema20, m15_ema50, m15_ema200, False):
                    for threshold, key in ((10.0, 'rsi2_10'), (20.0, 'rsi2_20')):
                        upper_threshold = 100.0 - threshold
                        if previous_rsi >= upper_threshold and current_rsi < upper_threshold:
                            result[key][setup_time] = _setup(setup_time, False, swing, m5_atr[index])

        if index >= BOLLINGER_PERIOD and _contiguous(m5, index - BOLLINGER_PERIOD, index):
            # The union of previous/current 20-bar bands is 21 real M5 bars.
            band_values = (
                (2.0, 'bands_2', lower_2, upper_2),
                (2.5, 'bands_2.5', lower_25, upper_25),
            )
            if _m15_range(context, m15_ema20, m15_ema50, m15_atr):
                swing = m5[index - 1:index + 1]
                for _multiplier, key, lower, upper in band_values:
                    previous_lower = lower[index - 1]
                    current_lower = lower[index]
                    previous_upper = upper[index - 1]
                    current_upper = upper[index]
                    if not all(math.isfinite(value) for value in (
                        previous_lower, current_lower, previous_upper, current_upper,
                    )):
                        continue
                    if (_bullish(current) and m5[index - 1].close <= previous_lower
                            and current.close > current_lower):
                        result[key][setup_time] = _setup(setup_time, True, swing, m5_atr[index])
                    if (_bearish(current) and m5[index - 1].close >= previous_upper
                            and current.close < current_upper):
                        result[key][setup_time] = _setup(setup_time, False, swing, m5_atr[index])

        for window, key in ((12, 'sweep_12'), (24, 'sweep_24')):
            if index < window or not _contiguous(m5, index - window, index):
                continue
            preceding = m5[index - window:index]  # The signal candle is not part of its own sweep floor.
            previous_low = min(bar.low for bar in preceding)
            previous_high = max(bar.high for bar in preceding)
            body = abs(current.close - current.open)
            lower_wick = min(current.open, current.close) - current.low
            upper_wick = current.high - max(current.open, current.close)
            if (_bullish(current) and lower_wick >= body
                    and current.low < previous_low and current.close > previous_low
                    and _m15_trend(context, m15_ema20, m15_ema50, None, True)):
                result[key][setup_time] = _setup(setup_time, True, (current,), m5_atr[index])
            if (_bearish(current) and upper_wick >= body
                    and current.high > previous_high and current.close < previous_high
                    and _m15_trend(context, m15_ema20, m15_ema50, None, False)):
                result[key][setup_time] = _setup(setup_time, False, (current,), m5_atr[index])

    return result
