# XAUUSD pullback research plan

This plan is fixed before inspecting the candidate's simulation results. It is not a promise of an 80% win rate. The existing momentum EA is preserved.

## Candidate

- Execution timeframe: M5, signal is the most recently completed candle.
- Trend: most recently completed M15 EMA20 above EMA50, and that EMA50 above its value three M15 bars earlier for buys; inverse for sells.
- M5 trigger: bullish candle with low <= its EMA20 and close > EMA20 for buys; bearish candle with high >= EMA20 and close < EMA20 for sells.
- Market entry at next available new-M5-bar quote; no breakout/pending order.
- Stop: extreme of the last three contiguous completed M5 candles including the signal, plus 0.10 ATR14 buffer (minimum one tick); sell stop also allows for spread.
- Target: 1.5 times entry-to-stop distance, rounded outward to tick size.
- Fixed requested volume 0.01 lot. No martingale, grid or percentage-equity sizing.
- Spread at entry <= 0.50 price units and <= 10% of stop distance.
- One position on the symbol. No reopening within the same M5 bar.
- Maximum holding time 60 minutes; exit on the first tradable tick at/after the deadline, not a guaranteed execution time during market closures.
- No session/news filters, parameter optimization, trade-direction cherry-picking or selection of winning dates after looking at outcomes.

## Data and chronological evaluation

Public Dukascopy XAUUSD BID and ASK M1 candles, UTC, requested 2024-12-15 through 2026-09-01 exclusive. December 2024 is indicator warmup. Report actual availability and failed requests rather than silently inventing/filling data. Cache raw data outside Git with SHA256 provenance.

**Source-access amendment, before inspecting simulation outcomes:** Dukascopy returned a valid 2025-01-02 sample, but other requests encountered HTTP 503/timeouts. Use the publicly downloadable Exness XAUUSD (no suffix) monthly tick archives instead, aggregated into paired BID/ASK M1 candles without filling gaps. The January 2025 archive was accessible and its schema verified. Request December 2024 for warmup and January 2025–August 2026 for the same chronological evaluation periods. This changes data availability/provider, not the candidate rules or cost scenarios. Exness labels this archive indicative and does not allow selecting the user's MT5 server; it is not claimed identical to Exness-MT5Trial7.

Report fixed parameters separately for 2025 H1, 2025 H2, January–May 2026 and June–August 2026 if those periods are available. The user's prior Exness trade report is evidence about the old EA only: it does not contain all market candles/ticks and cannot backtest this strategy.

EMA recursion: alpha = 2/(period+1), initialized with first close. ATR: rolling simple average of true ranges, as in the public MetaQuotes ATR example. M5/M15 use Bid OHLC. Only fully elapsed timeframe bars are visible at signal time; do not interpolate missing bars.

## Proxy execution assumptions (not MT5)

- BID/ASK M1 opens for market execution; long SL/TP checked on Bid, short on Ask.
- Same-minute SL/TP collisions resolved SL-first, including the entry minute; report the ambiguous count.
- Stop gaps fill at the worse available opening quote. TP fills at the target, with no positive gap improvement credited.
- Adverse slippage 0.05 price units per market/SL exit and entry; stress case 0.15. Limit TP execution is not given adverse price improvement.
- Commission USD 0.04 round-trip per 0.01 lot, based on the earlier supplied Exness report, not a quote for every account.
- Contract assumption 100 oz/lot, USD account; 0.01 lot = 1 oz. Broker-specific contract/margin/rejections are not reproduced.
- Swaps are not modeled. Count positions crossing UTC dates and closures after >60 minutes so the omission is visible. This is especially relevant around market gaps.
- No native ticks, intra-minute spread path, precise first-tick delay, broker stops/freeze rules or asynchronous MT5 trade handling. Results are a screening approximation, not executable proof or equivalent to an Exness real-tick backtest.
- End-of-period positions are marked closed at the final available quote and identified separately. A new period starts flat; indicator warmup still uses prior history.

If this candidate loses or falls short of 80%, report that outcome. Do not retune the same sample until it appears successful. A higher win rate obtained by shrinking targets is not itself evidence of positive expectancy.

## Sources

- Dukascopy instrument coverage: https://www.dukascopy-node.app/instrument/xauusd
- Dukascopy data feed: https://datafeed.dukascopy.com/datafeed/XAUUSD/
- Exness public archive description: https://www.exness.com/tick-history/
- Exness server/account limitations: https://get.exness.help/hc/en-us/articles/360021547851-Tick-history
- MetaQuotes ATR description: https://www.mql5.com/en/code/12
- Public copy of MetaQuotes ATR calculation: https://raw.githubusercontent.com/zephyrrr/MLEA/master/MQL5/Indicators/Examples/ATR.mq5
- Public copy of MetaQuotes EMA calculation: https://raw.githubusercontent.com/zephyrrr/MLEA/master/MQL5/Indicators/Examples/Custom%20Moving%20Average.mq5
