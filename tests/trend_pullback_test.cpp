#include <algorithm>
#include <cmath>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <iterator>
#include <limits>
#include <random>
#include <string>

double MathAbs(double x) { return std::abs(x); }
double MathMin(double a, double b) { return std::min(a, b); }
double MathMax(double a, double b) { return std::max(a, b); }
double MathCeil(double x) { return std::ceil(x); }
double MathFloor(double x) { return std::floor(x); }
bool MathIsValidNumber(double x) { return std::isfinite(x); }
double NormalizeDouble(double x, int digits)
{
    const double scale = std::pow(10.0, digits);
    return std::round(x * scale) / scale;
}

// Compile the actual production helpers, not a duplicate implementation.
#define PULLBACK_CORE_TEST
#include "../Experts/TrendPullbackXAU/TrendPullbackXAU.mq5"

int checks = 0;
void check(bool condition, const char* name)
{
    ++checks;
    if (!condition) {
        std::cerr << "FAILED: " << name << '\n';
        std::exit(1);
    }
}

bool near(double a, double b) { return std::abs(a - b) < 1e-8; }

std::string sourceText()
{
    for (const char* path : {"Experts/TrendPullbackXAU/TrendPullbackXAU.mq5",
                             "../Experts/TrendPullbackXAU/TrendPullbackXAU.mq5"}) {
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
    bool buy = false;
    const std::string source = sourceText();

    check(!source.empty(), "production EA source available for MQL static guard");
    check(source.find("ACCOUNT_MARGIN_FREE") != std::string::npos,
          "MQL5 margin guard uses ACCOUNT_MARGIN_FREE");
    check(source.find("ACCOUNT_FREEMARGIN") == std::string::npos,
          "invalid MQL4 ACCOUNT_FREEMARGIN identifier absent");
    check(source.find("free_margin * 0.90") != std::string::npos,
          "margin guard reserves 10 percent free margin");
    check(source.find("ReadCompletedValue(m15_ema50_handle, 50, 4") != std::string::npos,
          "M15 EMA50 slope uses completed shift four");
    check(source.find("ReadCompletedValue(m15_ema50_handle, 50, 0") == std::string::npos,
          "no developing M15 EMA50 value is read");

    check(PullbackSignal(100, 103, 99, 101, 99, buy) && buy,
          "buy reclaim above EMA");
    check(PullbackSignal(100, 103, 100, 101, 100, buy) && buy,
          "buy EMA low touch is inclusive");
    check(PullbackSignal(101, 102, 98, 99, 102, buy) && !buy,
          "sell reclaim below EMA");
    check(PullbackSignal(101, 101, 98, 99, 101, buy) && !buy,
          "sell EMA high touch is inclusive");
    check(!PullbackSignal(100, 103, 99, 100, 99, buy), "doji rejected");
    check(!PullbackSignal(100, 103, 99, 101, 101, buy), "buy close must exceed EMA");
    check(!PullbackSignal(101, 101, 98, 99, 99, buy), "sell close must be below EMA");
    check(!PullbackSignal(100, 99, 98, 101, 99, buy), "invalid OHLC rejected");
    check(!PullbackSignal(100, 103, 99, 101, nan, buy), "NaN EMA rejected");
    check(!PullbackSignal(100, inf, 99, 101, 99, buy), "infinite candle rejected");

    double sl = 0;
    check(PullbackSwingStop(true, 2010, 2000, 2008, 1995, 2007, 1998, 10, .3, .1, sl),
          "buy swing stop calculated");
    check(near(sl, 1994.0), "buy uses min of three lows minus 0.10 ATR");
    check(PullbackSwingStop(false, 2010, 2000, 2008, 1995, 2012, 1998, 10, .3, .1, sl),
          "sell swing stop calculated");
    check(near(sl, 2013.3), "sell uses max of three highs plus ATR buffer and spread");
    check(PullbackSwingStop(true, 100, 99, 101, 98.96, 102, 99.1, .1, 0, .1, sl) &&
          near(sl, 98.8), "buy minimum tick buffer rounds stop down");
    check(PullbackSwingStop(false, 100.01, 99, 100, 98, 100, 97, .1, .06, .1, sl) &&
          near(sl, 100.2), "sell minimum tick buffer rounds stop up");
    check(!PullbackSwingStop(true, 100, 101, 100, 98, 100, 97, 1, 0, .1, sl),
          "reversed high low rejected");
    check(!PullbackSwingStop(true, 100, 99, 100, 98, 100, 97, nan, 0, .1, sl),
          "NaN ATR rejected");

    double entry = 0;
    check(CurrentQuote(true, 2000.2, 2000.5, entry) && near(entry, 2000.5),
          "buy uses Ask quote");
    check(CurrentQuote(false, 2000.2, 2000.5, entry) && near(entry, 2000.2),
          "sell uses Bid quote");
    check(!CurrentQuote(true, 2000.5, 2000.2, entry), "crossed quote rejected");
    check(!CurrentQuote(false, nan, 2000.2, entry), "NaN quote rejected");

    double tp = 0;
    check(TargetFromEntry(true, 2000.5, 1994.0, .1, 1.5, tp) && near(tp, 2010.3),
          "buy target RR 1.5 rounded upward");
    check(TargetFromEntry(false, 2000.2, 2013.3, .1, 1.5, tp) && near(tp, 1980.5),
          "sell target RR 1.5 rounded downward");
    check(!TargetFromEntry(true, 2000, 2001, .1, 1.5, tp), "invalid buy risk rejected");
    check(!TargetFromEntry(false, 2000, 1999, .1, 1.5, tp), "invalid sell risk rejected");
    check(!TargetFromEntry(true, 2000, 1999, .1, inf, tp), "infinite RR rejected");

    check(SpreadRatioAllowed(.5, 2000.5, 1994.0, .5, 10), "inclusive absolute spread cap");
    check(SpreadRatioAllowed(.65, 2000.5, 1994.0, 1, 10), "inclusive 10 percent risk spread cap");
    check(!SpreadRatioAllowed(.651, 2000.5, 1994.0, 1, 10), "spread above 10 percent risk rejected");
    check(!SpreadRatioAllowed(.51, 2000.5, 1994.0, .5, 20), "spread above price cap rejected");
    check(!SpreadRatioAllowed(.1, 2000, 2000, 1, 10), "zero stop risk rejected");
    check(!SpreadRatioAllowed(nan, 2000, 1999, 1, 10), "NaN spread rejected");

    check(FixedVolume(.01, .01, 100, .01) == .01, "default fixed lots accepted");
    check(FixedVolume(.01, .001, 100, .001) == .01, "three decimal broker lots accepted");
    check(FixedVolume(.01, .1, 100, .1) == 0, "never round fixed lots upward");
    check(FixedVolume(.015, .01, 100, .01) == 0, "off-grid lots rejected");
    check(FixedVolume(.01, .01, 100, nan) == 0, "NaN lot step rejected");

    check(!TimeExpired(1000, 4599, 60), "59 minutes 59 seconds not expired");
    check(TimeExpired(1000, 4600, 60), "60 minute boundary expires");
    check(TimeExpired(1000, 4601, 60), "after 60 minutes expires");
    check(!TimeExpired(1000, 999, 60), "time before position open rejected");
    check(!TimeExpired(1000, 4600, 0), "zero hold duration disables timeout");
    check(SignalWindowOpen(1000, 1000, 30), "signal accepted at bar open");
    check(SignalWindowOpen(1000, 1030, 30), "signal accepted at delay boundary");
    check(!SignalWindowOpen(1000, 1031, 30), "stale signal rejected");
    check(!SignalWindowOpen(1000, 999, 30), "future bar rejected");
    check(!SignalWindowOpen(0, 1, 30), "unknown bar rejected");
    check(CloseVolumeReflected(.02, .01, .01, .01), "partial close reflected in position");
    check(!CloseVolumeReflected(.02, .01, .02, .01), "stale position after partial fill waits");
    check(!CloseVolumeReflected(.01, .01, .01, .01), "full fill with stale live position waits");
    check(CloseVolumeReflected(.01, 0, .01, .01), "rejected close permits retry after terminal history");
    check(!CloseVolumeReflected(.01, nan, .01, .01), "invalid close history blocks retry");
    check(source.find("CloseInFlight(ticket)") != std::string::npos,
          "timeout close checks in-flight requests");
    check(source.find("!HistoryOrderSelect(pending_close_order)") != std::string::npos,
          "unknown accepted close is not automatically resent");
    check(source.find("HistorySelectByPosition(pending_close_position_id)") != std::string::npos &&
          source.find("HistoryDealGetDouble(deal, DEAL_VOLUME)") != std::string::npos,
          "partial close volume is read from scoped execution deals");
    check(source.find("ORDER_VOLUME_CURRENT") == std::string::npos,
          "canceled IOC remainder is never mistaken for executed close volume");

    check(MarketStopsValid(true, 2000, 2000.4, 1999, 2001, 1), "buy stop distance uses Bid");
    check(MarketStopsValid(false, 2000, 2000.4, 2001.4, 1999.4, 1), "sell stop distance uses Ask");
    check(!MarketStopsValid(true, 2000, 2000.4, 1999.1, 2001.1, 1), "buy invalid near SL rejected");
    check(!MarketStopsValid(false, 2000, 2000.4, 2001.3, 1999.3, 1), "sell invalid near SL rejected");

    std::mt19937 random(26091320);
    std::uniform_real_distribution<double> unit(0.0, 1.0);
    for (int i = 0; i < 10000; ++i) {
        const bool direction = i % 2 == 0;
        const double low1 = 1800 + 400 * unit(random);
        const double low2 = 1800 + 400 * unit(random);
        const double low3 = 1800 + 400 * unit(random);
        const double high1 = low1 + 1 + 20 * unit(random);
        const double high2 = low2 + 1 + 20 * unit(random);
        const double high3 = low3 + 1 + 20 * unit(random);
        const double atr = .1 + 20 * unit(random);
        const double spread = unit(random);
        const double tick = (i % 3 == 0) ? .01 : ((i % 3 == 1) ? .05 : .1);
        check(PullbackSwingStop(direction, high1, low1, high2, low2, high3, low3,
                                atr, spread, tick, sl), "random valid swing stop");
        const double expected = direction
            ? std::floor((std::min({low1, low2, low3}) - std::max(.1 * atr, tick)) / tick + 1e-9) * tick
            : std::ceil((std::max({high1, high2, high3}) + std::max(.1 * atr, tick) + spread) / tick - 1e-9) * tick;
        check(near(sl, expected), "random stop matches documented ATR formula");
        const double bid = direction ? sl + 1 + 10 * unit(random) : sl - 1 - 10 * unit(random);
        const double ask = bid + spread;
        check(CurrentQuote(direction, bid, ask, entry), "random current quote");
        check(TargetFromEntry(direction, entry, sl, tick, 1.5, tp), "random target from actual quote");
        check(direction ? tp > entry && sl < entry : tp < entry && sl > entry,
              "random levels keep correct orientation");
        check(std::abs(tp - entry) + 1e-8 >= 1.5 * std::abs(entry - sl),
              "random target rounds reward away from entry");
    }

    std::cout << "PASS: " << checks << " checks (including 10,000 deterministic randomized cases).\n";
}
