# High-win-rate candidate study (second research round)

Frozen before inspecting this round's candidate results. The objective is to investigate—not guarantee—USD 20 per trading day / USD 100 per week at fixed 0.01 lot. Never use martingale, grid, averaging, unrealized losses hidden from reporting, or a tiny TP against an unlimited SL to inflate win rate.

## Candidate universe: exactly 36 configurations

All strategies use completed Bid M5 bars and completed M15 context. Evaluate mirrored BUY/SELL rules, not a hindsight choice of direction. Each of the three families has two entry settings, two minimum stop distances (0.75 or 1.25 M5 ATR14), and three target multiples (0.60, 0.85, 1.00 R).

1. **Trend RSI2 recovery:** M15 EMA50 > EMA200 and EMA50 rising vs three completed M15 bars earlier for BUY (inverse SELL). Previous M5 RSI2 <= threshold 10 or 20, current RSI2 > threshold, current candle bullish. SELL uses previous RSI2 >= 100-threshold and a bearish recovery below it. Stop extreme is last three contiguous closed M5 bars.
2. **Bollinger re-entry in a range:** M5 SMA20 and population standard deviation, band multiplier 2.0 or 2.5. Previous close <= its lower band, current close back above its lower band with a bullish candle (inverse SELL). M15 range filter: abs(EMA20-EMA50) <= 0.5 ATR14 and abs(EMA50-EMA50 three bars earlier) <= 0.3 ATR14. Stop extreme is the previous and current closed M5 bars.
3. **Trend-aligned sweep/reclaim:** signal low below the lowest of the preceding 12 or 24 closed M5 bars, close back above that level, bullish, lower wick >= body (inverse SELL). M15 EMA20 > EMA50 and EMA50 rising vs three bars earlier for BUY (inverse SELL). Stop extreme is the signal candle.

Raw stop is beyond the selected swing by max(0.10 ATR14, one tick); short stops also include current spread. Expand outward to the configuration's minimum ATR stop distance. Skip—not clip—if quoted entry-to-stop distance exceeds 2.5 ATR14 or 15.00 price units. Target is the selected R multiple from actual simulated fill.

## Shared execution and risk policy

- Fixed 0.01 lot, assumed 100 oz/lot, USD account; one position; at most one new-bar signal attempt per M5 bar.
- Entry session 07:00 <= UTC time < 18:00. Maximum holding time 45 minutes, first available quote at/after deadline. No guaranteed exit through market closures.
- Maximum 12 entries per UTC weekday. Sunday/Saturday entries disabled.
- Daily entry-risk budget: USD 25. Do not open when realized daily P/L minus estimated loss at the proposed SL and commission would be below -25. This is an entry gate, not a guaranteed loss cap through slippage/gaps. No daily profit stop is added to make target attainment look better.
- Spread <= 0.50 and <= 10% of quoted stop distance. No parameter search over session, budget, holding time or spread limits.
- Commission USD 0.04 round trip; adverse slippage 0.05 price units per market/SL execution; stress 0.15. Same M1 Bid/Ask and SL-first ambiguity policy as the previous proxy. Swaps omitted and overnight/gap exits explicitly counted.
- No partial profit, trailing stop or breakeven mechanism in this first comparison. Report win rate by **net** closed-trade profit.

## Selection protocol

1. **Development:** compare all 36 on calendar 2025 only, with December 2024 indicator warmup. Publish every candidate result, including failures, under both cost scenarios.
2. Eligibility on development: >=200 trades, net win rate >=60%, base PF >=1.15, stress PF >=1.05, positive net in both 2025 half-years, positive weeks >=50%, maximum closed-trade drawdown <=USD 500. These thresholds are screening policy, not statistical proof.
3. Rank eligible candidates by stress net profit / max(closed-trade drawdown, 1), then stress profit factor, then deterministic candidate ID. Select at most one per family, at most three total. If none qualify, a descriptive highest-ranked fallback may be investigated and implemented, but label it **failed development gate**, not validated.
4. **Validation:** only the selected candidates are evaluated January–May 2026. Eligible validation requires >=80 trades, base win rate >=60%, base PF >=1.10, stress PF >1, and drawdown <=USD 500. Rank qualifying candidates by the same stress robustness ratio; choose one. If none qualify, retain the development leader as an explicitly failed candidate, not a profitable strategy.
5. **Historical final check:** evaluate only the locked candidate on June–August 2026. Do not switch candidate after viewing this result. Report all outcomes, not just weeks reaching the target.

All 2025–August 2026 data was already examined for the previous, different pullback strategy. These are **reused chronological development/validation/check windows**, not pristine, independent out-of-sample evidence. If more genuinely unseen history is used, record its purpose before loading outcomes; do not rename older history as forward validation. Any next tuning round consumes these results and needs new validation.

## Target reporting and handoff

- Aggregate daily P/L by UTC exit date and ISO weeks; include no-trade weekdays within each requested window. Report average/median, worst day/week, fraction of days >=20 and weeks >=100, losing weeks and losing streaks. Label partial boundary weeks and exclude them from full-week target percentages.
- Per-trade win rate, payoff ratio, net profit/PF, drawdown and cost stress remain primary safeguards: a high win rate alone does not qualify.
- If feasible, replay the locked candidate on the already-cached public native ticks for the final-check window. This remains a custom replay, **not MetaEditor compilation or MT5 Strategy Tester**. Do not call an OHLC proxy a tick replay.
- Implement at most one additional standalone `.mq5` with fixed lots and transparent risk/session controls; preserve earlier EAs. If the financial targets are not met, state that clearly rather than promising daily income.
