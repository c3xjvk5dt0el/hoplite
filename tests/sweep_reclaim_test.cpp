#include <algorithm>
#include <cmath>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <iterator>
#include <limits>
#include <random>
#include <string>

double MathAbs(double value) { return std::abs(value); }
double MathMin(double left, double right) { return std::min(left, right); }
double MathMax(double left, double right) { return std::max(left, right); }
double MathCeil(double value) { return std::ceil(value); }
double MathFloor(double value) { return std::floor(value); }
bool MathIsValidNumber(double value) { return std::isfinite(value); }
double NormalizeDouble(double value, int digits)
{
    const double scale = std::pow(10.0, digits);
    return std::round(value * scale) / scale;
}

// Compile production math directly while excluding MT5-only execution code.
#define SWEEP_CORE_TEST
#include "../Experts/SweepReclaimXAU/SweepReclaimXAU.mq5"

int checks = 0;
void check(bool condition, const char* name)
{
    ++checks;
    if (!condition) {
        std::cerr << "FAILED: " << name << '\n';
        std::exit(1);
    }
}

bool near(double left, double right) { return std::abs(left - right) < 1e-8; }

std::string sourceText()
{
    for (const char* path : {"Experts/SweepReclaimXAU/SweepReclaimXAU.mq5",
                             "../Experts/SweepReclaimXAU/SweepReclaimXAU.mq5"}) {
        std::ifstream source(path);
        if (source)
            return {std::istreambuf_iterator<char>(source), std::istreambuf_iterator<char>()};
    }
    return {};
}

int main()
{
    const double nan = std::numeric_limits<double>::quiet_NaN();
    const double inf = std::numeric_limits<double>::infinity();
    const std::string source = sourceText();

    check(!source.empty(), "production EA source available for static guards");
    check(source.find("#ifndef SWEEP_CORE_TEST") != std::string::npos,
          "MQL-only code is excluded by the SWEEP_CORE_TEST guard");
    check(source.find("#include <Trade\\Trade.mqh>") != std::string::npos,
          "only built-in MT5 Trade library is declared");
    const std::size_t first_include = source.find("#include");
    check(first_include != std::string::npos && source.find("#include", first_include + 1) == std::string::npos,
          "EA has no external or custom include");
    check(source.find("CopyRates(_Symbol, PERIOD_M5, 1, 25, bars)") != std::string::npos &&
          source.find("PreviousWindowSelected(25, 0, 1, 24, 24)") != std::string::npos,
          "production selects the signal plus exactly 24 prior M5 candles");
    check(source.find("for(int i = 2; i <= 24; ++i)") != std::string::npos,
          "production boundary loop excludes bars[0] signal candle");
    check(source.find("ReadCompletedValue(m15_ema50_handle, 50, 4") != std::string::npos &&
          source.find("ReadCompletedValue(m15_ema50_handle, 50, 0") == std::string::npos,
          "M15 EMA50 slope only uses completed shifts one and four");
    check(source.find("ReadM5Atr14(bars, atr)") != std::string::npos &&
          source.find("TrueRange(bars[i].high, bars[i].low, bars[i + 1].close, range)") != std::string::npos,
          "ATR14 matches the research simple true-range window ending at the signal");
    check(source.find("input bool InpAllowLiveTrading = false;") != std::string::npos &&
          source.find("ACCOUNT_TRADE_MODE_REAL") != std::string::npos &&
          source.find("AccountModeAllowed(demo_account, real_account, InpAllowLiveTrading, tester)") != std::string::npos,
          "unvalidated fallback has a real-account opt-in guard");
    check(source.find("input double InpFixedLots = 0.01;") != std::string::npos &&
          source.find("input double InpRewardRisk = 1.0;") != std::string::npos &&
          source.find("MathAbs(InpFixedLots - LOCKED_FIXED_LOTS)") != std::string::npos &&
          source.find("MathAbs(InpRewardRisk - LOCKED_REWARD_RISK)") != std::string::npos,
          "lot and RR cannot drift from the locked fallback candidate");
    check(source.find("SYMBOL_TRADE_CONTRACT_SIZE") != std::string::npos &&
          source.find("AccountInfoString(ACCOUNT_CURRENCY)") != std::string::npos,
          "USD-account and 100-ounce contract guards are present");
    check(source.find("HistorySelect(broker_day_start, broker_now)") != std::string::npos &&
          source.find("DEAL_ORDER") != std::string::npos && source.find("DEAL_FEE") != std::string::npos,
          "daily history is bounded at now and includes order dedup and fees");
    check(source.find("!HistoryDealGetDouble(deal, DEAL_PROFIT, profit)") != std::string::npos &&
          source.find("!HistoryDealGetDouble(deal, DEAL_COMMISSION, commission)") != std::string::npos &&
          source.find("!HistoryDealGetInteger(deal, DEAL_ORDER, raw_order)") != std::string::npos,
          "history property read failures cannot masquerade as zero losses or entries");
    check(source.find("InpMagic > (ulong)LONG_MAX") != std::string::npos &&
          source.find("raw_order <= 0") != std::string::npos,
          "signed history identities cannot wrap into accepted unsigned IDs");
    check(source.find("M15WarmupReady(Bars(_Symbol, PERIOD_M15)") != std::string::npos,
          "native evaluation uses the same completed-M15 warmup gate");
    check(source.find("OrderCalcProfit(order_type, _Symbol, volume, estimated_entry, estimated_stop_exit, profit)") != std::string::npos,
          "daily gate estimates loss through broker OrderCalcProfit");
    check(source.find("trade.Buy(volume, _Symbol, entry, sl, tp, MARKET_COMMENT)") != std::string::npos &&
          source.find("trade.Sell(volume, _Symbol, entry, sl, tp, MARKET_COMMENT)") != std::string::npos &&
          source.find("margin > free_margin * 0.90") != std::string::npos,
          "market entries carry attached protection and retain ten-percent margin reserve");
    check(source.find("HistorySelectByPosition(pending_close_position_id)") != std::string::npos &&
          source.find("CloseVolumeReflected(pending_close_volume, filled") != std::string::npos &&
          source.find("ORDER_VOLUME_CURRENT") == std::string::npos,
          "timeout close guard reconciles actual deal volume without IOC remainder shortcuts");
    check(source.find("SYMBOL_TRADE_STOPS_LEVEL") != std::string::npos &&
          source.find("SYMBOL_TRADE_FREEZE_LEVEL") != std::string::npos &&
          source.find("MarketStopsValid(buy, quote.bid, quote.ask, sl, tp, distance)") != std::string::npos,
          "broker stop and freeze distances guard initial and amended protection");
    check(source.find("ACCOUNT_EQUITY") == std::string::npos && source.find("ACCOUNT_BALANCE") == std::string::npos,
          "EA has no equity or balance sizing");
    check(source.find("TimeGMT") == std::string::npos,
          "UTC conversion never auto-assumes an unreliable tester clock");
    for (const char* forbidden : {"BuyStop", "SellStop", "BuyLimit", "SellLimit", "ORDER_TIME_SPECIFIED", "ORDER_FILLING_RETURN"})
        check(source.find(forbidden) == std::string::npos, "no pending-order execution feature");

    check(PreviousWindowSelected(25, 0, 1, 24, 24), "exact previous sweep window is selected");
    check(!PreviousWindowSelected(24, 0, 1, 24, 24), "missing prior bar rejects sweep window");
    check(!PreviousWindowSelected(25, 1, 1, 24, 24), "signal must remain outside prior window");
    check(!PreviousWindowSelected(25, 0, 1, 23, 24), "truncated prior window rejected");

    double previous_low = 100.0;
    double previous_high = 105.0;
    check(AccumulateSweepBoundaries(107.0, 99.0, previous_low, previous_high),
          "valid prior bar updates sweep bounds");
    check(AccumulateSweepBoundaries(104.0, 97.0, previous_low, previous_high) &&
          near(previous_low, 97.0) && near(previous_high, 107.0),
          "boundary helper keeps min low and max high");
    check(!AccumulateSweepBoundaries(98.0, 99.0, previous_low, previous_high),
          "reversed prior high low rejected");
    check(!AccumulateSweepBoundaries(inf, 99.0, previous_low, previous_high),
          "infinite prior boundary rejected");

    double true_range = 0.0;
    check(TrueRange(110.0, 100.0, 105.0, true_range) && near(true_range, 10.0),
          "true range uses high-low when prior close is inside");
    check(TrueRange(110.0, 100.0, 115.0, true_range) && near(true_range, 15.0),
          "true range includes gap from prior close");
    double atr = 0.0;
    check(SimpleAtrFromSum(28.0, 14, atr) && near(atr, 2.0), "ATR14 is a simple average");
    check(!SimpleAtrFromSum(0.0, 14, atr), "zero ATR is unusable for the strategy");

    bool buy = false;
    check(SweepReclaimSignal(100.0, 104.0, 95.0, 102.0, 96.0, 110.0, buy) && buy,
          "bullish low sweep and reclaim qualifies");
    check(SweepReclaimSignal(102.0, 106.0, 97.0, 100.0, 96.0, 105.0, buy) && !buy,
          "bearish high sweep and reclaim qualifies");
    check(!SweepReclaimSignal(100.0, 104.0, 96.0, 102.0, 96.0, 110.0, buy),
          "equal low does not sweep prior floor");
    check(!SweepReclaimSignal(100.0, 104.0, 95.0, 96.0, 96.0, 110.0, buy),
          "buy close must strictly reclaim prior floor");
    check(!SweepReclaimSignal(100.0, 101.0, 95.0, 104.0, 96.0, 110.0, buy),
          "buy lower wick must be at least candle body");
    check(!SweepReclaimSignal(102.0, 105.0, 97.0, 100.0, 96.0, 105.0, buy),
          "equal high does not sweep prior ceiling");
    check(!SweepReclaimSignal(100.0, 104.0, 96.0, 100.0, 96.0, 110.0, buy),
          "doji is neither bullish nor bearish signal");
    check(!SweepReclaimSignal(100.0, 99.0, 95.0, 102.0, 96.0, 110.0, buy),
          "invalid OHLC geometry rejects signal");
    check(!SweepReclaimSignal(nan, 104.0, 95.0, 102.0, 96.0, 110.0, buy),
          "NaN signal candle rejected");

    double entry = 0.0;
    double sl = 0.0;
    check(SweepStop(true, 2011.0, 2007.0, 4.0, 2009.7, 2010.0, 0.1, 1.25, entry, sl),
          "buy stop with 1.25 ATR floor is calculated");
    check(near(entry, 2010.0) && near(sl, 2005.0),
          "buy uses Ask and expands outward to exactly 1.25 ATR");
    double quoted_risk = 0.0;
    check(QuotedStopRisk(true, entry, sl, quoted_risk) && near(quoted_risk, 5.0),
          "buy quoted risk is entry minus SL");
    check(SweepStop(false, 2003.0, 1998.0, 1.0, 2000.0, 2000.3, 0.1, 1.25, entry, sl),
          "sell signal stop is calculated");
    check(near(entry, 2000.0) && near(sl, 2003.4),
          "sell raw stop includes current spread and rounds upward");
    check(QuotedStopRisk(false, entry, sl, quoted_risk) && near(quoted_risk, 3.4),
          "sell quoted risk is SL minus Bid");
    check(!SweepStop(true, 2011.0, 2007.0, 0.0, 2009.7, 2010.0, 0.1, 1.25, entry, sl),
          "zero ATR rejects stop");
    check(!SweepStop(false, 2011.0, 2007.0, 4.0, 2010.0, 2009.7, 0.1, 1.25, entry, sl),
          "crossed Bid Ask rejects stop");
    check(StopRiskWithinCaps(true, 2010.0, 2000.0, 4.0, 2.5, 15.0),
          "2.5 ATR cap is inclusive");
    check(!StopRiskWithinCaps(true, 2010.0, 1999.9, 4.0, 2.5, 15.0),
          "risk over 2.5 ATR is rejected rather than clipped");
    check(!StopRiskWithinCaps(false, 2000.0, 2015.1, 10.0, 2.5, 15.0),
          "risk over absolute 15 price cap is rejected");
    check(SpreadRatioAllowed(0.50, 2010.0, 2005.0, 0.50, 0.10),
          "absolute spread cap and ten-percent risk cap are inclusive");
    check(!SpreadRatioAllowed(0.501, 2010.0, 2005.0, 0.50, 0.10),
          "spread above 0.50 is rejected");
    check(!SpreadRatioAllowed(0.51, 2010.0, 2005.0, 1.0, 0.10),
          "spread above ten percent of quoted risk is rejected");

    check(CurrentQuote(true, 2000.2, 2000.5, entry) && near(entry, 2000.5),
          "buy entry uses Ask");
    check(CurrentQuote(false, 2000.2, 2000.5, entry) && near(entry, 2000.2),
          "sell entry uses Bid");
    check(!CurrentQuote(true, 2000.5, 2000.2, entry), "crossed quote rejected");
    check(!CurrentQuote(false, nan, 2000.2, entry), "NaN quote rejected");

    double tp = 0.0;
    check(TargetFromEntry(true, 2010.0, 2005.0, 0.1, 1.0, tp) && near(tp, 2015.0),
          "buy one-R target derives from actual entry and rounds up");
    check(TargetFromEntry(false, 2000.0, 2005.0, 0.1, 1.0, tp) && near(tp, 1995.0),
          "sell one-R target derives from actual entry and rounds down");
    check(!TargetFromEntry(true, 2000.0, 2001.0, 0.1, 1.0, tp), "wrong-side buy SL rejected");
    check(!TargetFromEntry(false, 2000.0, 1999.0, 0.1, 1.0, tp), "wrong-side sell SL rejected");
    check(!TargetFromEntry(true, 2000.0, 1999.0, 0.1, inf, tp), "infinite RR rejected");
    check(MarketStopsValid(true, 2000.0, 2000.3, 1999.0, 2001.0, 1.0),
          "buy broker stops are checked against Bid");
    check(MarketStopsValid(false, 2000.0, 2000.3, 2001.3, 1999.3, 1.0),
          "sell broker stops are checked against Ask");
    check(!MarketStopsValid(true, 2000.0, 2000.3, 1999.1, 2001.1, 1.0),
          "too-near buy protection rejected");

    double adverse_entry = 0.0;
    double adverse_exit = 0.0;
    check(EstimatedAdverseStopPrices(true, 2010.0, 2005.0, 0.05, 0.05, adverse_entry, adverse_exit) &&
          near(adverse_entry, 2010.05) && near(adverse_exit, 2004.95),
          "buy USD loss estimate applies adverse entry and stop slippage");
    check(EstimatedAdverseStopPrices(false, 2000.0, 2005.0, 0.05, 0.05, adverse_entry, adverse_exit) &&
          near(adverse_entry, 1999.95) && near(adverse_exit, 2005.05),
          "sell USD loss estimate applies adverse entry and stop slippage");
    check(!EstimatedAdverseStopPrices(true, 2000.0, 2001.0, 0.05, 0.05, adverse_entry, adverse_exit),
          "estimate rejects wrong-side stop");

    const long monday = 4L * SECONDS_PER_DAY; // 1970-01-05 UTC.
    check(UtcEntrySessionOpen(monday + 7L * 3600, 0, 7, 18), "Monday 07:00 UTC is included");
    check(UtcEntrySessionOpen(monday + 17L * 3600 + 59L * 60, 0, 7, 18),
          "Monday before 18:00 UTC is included");
    check(!UtcEntrySessionOpen(monday + 18L * 3600, 0, 7, 18), "18:00 UTC is excluded");
    check(!UtcEntrySessionOpen(monday - SECONDS_PER_DAY + 10L * 3600, 0, 7, 18),
          "Sunday UTC is excluded");
    check(!UtcEntrySessionOpen(monday + 5L * SECONDS_PER_DAY + 10L * 3600, 0, 7, 18),
          "Saturday UTC is excluded");
    check(UtcEntrySessionOpen(monday + 9L * 3600, 120, 7, 18),
          "explicit UTC plus-two broker offset converts to 07:00 UTC");
    long utc_time = 0;
    check(BrokerTimeToUtc(monday + 9L * 3600, 120, utc_time) && utc_time == monday + 7L * 3600,
          "broker offset conversion is explicit and deterministic");
    long broker_day_start = 0;
    check(UtcDayBrokerStart(monday + 9L * 3600, 120, broker_day_start) &&
          broker_day_start == monday + 2L * 3600,
          "daily history starts at this UTC day in broker time");
    check(!ValidUtcOffsetMinutes(14 * 60 + 1), "invalid UTC offset rejected");
    check(!ValidUtcSessionHours(18, 7), "reversed UTC session rejected");

    check(DailyEntryLimitAllowed(11, 12), "eleventh daily opening order remains allowed");
    check(!DailyEntryLimitAllowed(12, 12), "twelfth daily opening order blocks another entry");
    check(DailyRiskBudgetAllowed(-20.0, 5.0, 25.0), "daily USD risk boundary is inclusive");
    check(!DailyRiskBudgetAllowed(-20.0, 5.01, 25.0), "daily USD risk overrun blocks entry");
    check(DailyRiskBudgetAllowed(100.0, 124.99, 25.0), "positive day has no artificial profit stop");
    check(!DailyRiskBudgetAllowed(nan, 1.0, 25.0), "NaN daily net blocks entry");

    check(!TimeExpired(1000, 3699, 45), "44 minutes 59 seconds has not expired");
    check(TimeExpired(1000, 3700, 45), "45 minute boundary expires");
    check(SignalWindowOpen(1000, 1030, 30), "first-tick delay boundary is included");
    check(!SignalWindowOpen(1000, 1031, 30), "late signal is rejected");
    check(FixedVolume(0.01, 0.01, 100.0, 0.01) == 0.01, "default fixed lot is accepted");
    check(FixedVolume(0.015, 0.01, 100.0, 0.01) == 0.0, "off-grid fixed lot is rejected not rounded");
    check(FixedVolume(0.01, 0.10, 100.0, 0.10) == 0.0, "unsupported broker minimum rejects lot");
    check(CloseVolumeReflected(0.02, 0.01, 0.01, 0.01), "partial close reconciliation accepts reflected volume");
    check(!CloseVolumeReflected(0.02, 0.01, 0.02, 0.01), "stale partial close remains in flight");
    check(!AccountModeAllowed(false, true, false, false), "real account is denied without explicit opt-in");
    check(AccountModeAllowed(false, true, true, false), "real account explicit opt-in is recognized");
    check(AccountModeAllowed(false, true, false, true), "tester remains usable without live opt-in");
    check(AccountModeAllowed(true, false, false, false), "demo is allowed by default");
    check(!AccountModeAllowed(false, false, false, false), "contest/unknown account is denied");
    check(!AccountModeAllowed(false, false, true, false), "live opt-in does not admit contest/unknown accounts");
    check(!M15WarmupReady(201, 201, 201), "200 completed M15 bars do not satisfy warmup");
    check(M15WarmupReady(202, 202, 202), "201 completed M15 bars satisfy warmup");
    check(!M15WarmupReady(202, 201, 202), "unready fast EMA is rejected");
    check(!M15WarmupReady(202, 202, 201), "unready slow EMA is rejected");

    std::mt19937 random(26091330);
    std::uniform_real_distribution<double> unit(0.0, 1.0);
    for (int i = 0; i < 2000; ++i) {
        const bool direction = i % 2 == 0;
        const double atr = 0.1 + 20.0 * unit(random);
        const double tick = i % 3 == 0 ? 0.01 : (i % 3 == 1 ? 0.05 : 0.1);
        const double bid = 1900.0 + 200.0 * unit(random);
        const double ask = bid + unit(random) * 0.50;
        const double signal_low = bid - 0.1 - 15.0 * unit(random);
        const double signal_high = ask + 0.1 + 15.0 * unit(random);
        check(SweepStop(direction, signal_high, signal_low, atr, bid, ask, tick, 1.25, entry, sl),
              "random valid sweep stop");
        check(QuotedStopRisk(direction, entry, sl, quoted_risk) && quoted_risk >= 1.25 * atr - 1e-8,
              "random stop always satisfies minimum ATR floor");
        check(TargetFromEntry(direction, entry, sl, tick, 1.0, tp), "random one-R target");
        check(direction ? tp > entry && sl < entry : tp < entry && sl > entry,
              "random price levels keep correct orientation");
    }

    std::cout << "PASS: " << checks << " checks (including 2,000 deterministic randomized cases).\n";
}
