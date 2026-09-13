#include <algorithm>
#include <cmath>
#include <cstdlib>
#include <iostream>
#include <limits>
#include <random>

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

// Compile the actual production math, not a separately implemented strategy.
#define MOMENTUM_CORE_TEST
#include "../Experts/MomentumCandleXAU/MomentumCandleXAU.mq5"

int checks = 0;
void check(bool condition, const char* name)
{
    ++checks;
    if (!condition) {
        std::cerr << "FAILED: " << name << '\n';
        std::exit(1);
    }
}

bool near(double a, double b) { return std::abs(a - b) < 1e-7; }

int main()
{
    bool buy = false;
    const double nan = std::numeric_limits<double>::quiet_NaN();
    const double inf = std::numeric_limits<double>::infinity();
    check(!MomentumSignal(nan, 107, 99, 106, 6, 30, false, buy), "reject NaN candle");
    check(!MomentumSignal(100, inf, 99, 106, 6, 30, false, buy), "reject infinite candle");
    check(!MomentumSignal(100, 107, 99, 106, 6, nan, false, buy), "reject NaN wick threshold");
    check(MomentumSignal(100, 107, 99, 106, 6, 30, false, buy) && buy,
          "bullish, inclusive minimum body");
    check(MomentumSignal(106, 107, 99, 100, 6, 30, false, buy) && !buy,
          "bearish signal");
    check(!MomentumSignal(100, 107, 99, 106, 6.1, 30, false, buy), "small body");
    check(!MomentumSignal(100, 110, 99, 106, 6, 30, false, buy), "excess wick");
    check(MomentumSignal(101, 110, 100, 108, 7, 30, false, buy), "30 percent wick boundary");
    check(!MomentumSignal(100, 100, 100, 100, 1, 30, false, buy), "zero range");
    check(!MomentumSignal(100, 101, 99, 100, 1, 30, false, buy), "doji");
    check(!MomentumSignal(100, 99, 98, 106, 1, 30, false, buy), "invalid OHLC");
    check(!MomentumSignal(100, 108, 101, 106, 1, 30, false, buy), "invalid low");
    check(MomentumSignal(101, 110, 100, 108, 7, 30, true, buy) && buy,
          "original conservative bullish wick direction");
    check(MomentumSignal(108, 109, 99, 101, 7, 30, true, buy) && !buy,
          "original conservative bearish wick direction");
    check(!MomentumSignal(100, 107, 99, 106, 6, 30, true, buy), "equal conservative wicks");
    check(!MomentumSignal(101, 109, 99, 108, 7, 30, true, buy), "opposite bullish wick direction");
    check(!MomentumSignal(108, 110, 100, 101, 7, 30, true, buy), "opposite bearish wick direction");

    double entry = 0, sl = 0, tp = 0;
    check(!MarketLevels(true, 3006, 2999, nan, 3005.5, 3005.8, .01, .15, 1, entry, sl, tp), "reject NaN ATR");
    check(!MarketLevels(true, 3006, 2999, 5, 3005.5, 3005.8, .01, .15, inf, entry, sl, tp), "reject infinite RR");
    check(MarketLevels(true, 3006, 2999, 5, 3005.5, 3005.8, .01, .15, 1, entry, sl, tp),
          "market buy below signal high without breakout");
    check(near(entry, 3005.8) && near(sl, 2998.25) && near(tp, 3013.35), "buy Ask and RR 1:1");
    check(MarketStopsValid(true, 3005.5, 3005.8, sl, tp, .1), "buy stops validated against Bid");
    check(TargetFromEntry(true, 3005.9, sl, .01, 1, tp) && near(tp, 3013.55),
          "buy TP realigned after fill slippage, same SL");
    check(MarketLevels(false, 3006, 2999, 5, 3000, 3000.3, .01, .15, 1, entry, sl, tp),
          "market sell above signal low without breakout");
    check(near(entry, 3000) && near(sl, 3007.05) && near(tp, 2992.95), "sell Bid and RR 1:1");
    check(MarketStopsValid(false, 3000, 3000.3, sl, tp, .1), "sell stops validated against Ask");
    check(TargetFromEntry(false, 2999.9, sl, .01, 1, tp) && near(tp, 2992.75),
          "sell TP realigned after fill slippage, same SL");
    check(MarketLevels(true, 3006, 2999, 5, 3005.5, 3005.5, .25, 0, 1, entry, sl, tp),
          "zero spread and minimum one-tick SL buffer");
    check(near(entry, 3005.5) && near(sl, 2998.75), "SL remains outside candle");
    check(!MarketLevels(true, 3006, 2999, 0, 3005.5, 3005.8, .01, .15, 1, entry, sl, tp), "zero ATR");
    check(!MarketLevels(true, 3006, 2999, 5, 3005.5, 3005.4, .01, .15, 1, entry, sl, tp), "crossed quote");
    check(!MarketLevels(true, 3006, 2999, 5, 3005.5, 3005.8, 0, .15, 1, entry, sl, tp), "zero tick");
    check(!MarketLevels(true, 2999, 3006, 5, 3005.5, 3005.8, .01, .15, 1, entry, sl, tp), "reversed range");
    check(!MarketLevels(true, 3006, 2999, 5, nan, 3005.8, .01, .15, 1, entry, sl, tp), "NaN bid");
    check(!MarketLevels(true, 3006, 2999, 5, 3005.5, inf, .01, .15, 1, entry, sl, tp), "infinite ask");
    check(!MarketLevels(true, 3006, 2999, 5, 3005.5, 3005.8, .01, -.15, 1, entry, sl, tp), "negative stop buffer");
    check(!MarketLevels(true, 3006, 2999, 5, 2998, 2998.1, .01, .15, 1, entry, sl, tp), "buy gap beyond SL");
    check(!MarketLevels(false, 3006, 2999, 5, 3008, 3008.1, .01, .15, 1, entry, sl, tp), "sell gap beyond SL");
    check(!TargetFromEntry(true, 3000, 3000, .01, 1, tp), "zero risk fill rejected");
    check(!TargetFromEntry(true, 3000, 3001, .01, 1, tp), "buy fill below SL rejected");
    check(!TargetFromEntry(false, 3000, 2999, .01, 1, tp), "sell fill above SL rejected");
    check(!TargetFromEntry(true, nan, 2995, .01, 1, tp), "NaN fill rejected");
    check(!TargetFromEntry(true, 3000, 2995, .01, 0, tp), "zero RR rejected");
    check(!TargetFromEntry(false, 1, 10, .01, 1, tp), "nonpositive target rejected");
    check(MarketStopsValid(true, 100, 100.5, 99, 101, 1), "inclusive buy stop distance");
    check(!MarketStopsValid(true, 100, 100.5, 99.5, 101.5, 1), "buy SL distance uses Bid, not entry Ask");
    check(!MarketStopsValid(false, 100, 100.5, 101, 99, 1), "sell SL distance uses Ask, not entry Bid");
    check(!MarketStopsValid(true, 100, 100.5, 95, 100.5, 1), "TP near Bid prevents modification");
    check(!MarketStopsValid(false, 100, 100.5, 105, 100, 1), "TP near Ask prevents modification");
    check(!MarketStopsValid(true, 100, 100.5, 99, 101, 2), "freeze distance blocks modification");
    check(!MarketStopsValid(true, 100, 100.5, 99, 101, nan), "NaN stop distance rejected");
    check(!MarketStopsValid(true, 100, 99.5, 99, 101, 1), "crossed quote rejected for stops");

    check(FixedVolume(.01, .01, 100, .01) == .01, "fixed 0.01 lot exactly");
    check(FixedVolume(.01, .001, 100, .001) == .01, "three-decimal broker step");
    check(FixedVolume(.01, .01, .01, .01) == .01, "inclusive broker limits");
    check(FixedVolume(.01, .1, 100, .1) == 0, "never round up to broker minimum");
    check(FixedVolume(.01, .001, .005, .001) == 0, "never round down to broker maximum");
    check(FixedVolume(.01, .001, 100, .003) == 0, "reject incompatible step");
    check(FixedVolume(.015, .01, 100, .01) == 0, "never round requested lots");
    check(FixedVolume(.75, .25, 10, .25) == .75, "nondecimal lot step");
    check(FixedVolume(nan, .01, 100, .01) == 0, "reject NaN lots");
    check(FixedVolume(inf, .01, 100, .01) == 0, "reject infinite lots");
    check(FixedVolume(.01, nan, 100, .01) == 0, "reject NaN minimum");
    check(FixedVolume(.01, .01, inf, .01) == 0, "reject infinite maximum");
    check(FixedVolume(.01, .01, 100, nan) == 0, "reject NaN step");
    check(FixedVolume(.01, .01, 100, 0) == 0, "reject zero step");
    check(FixedVolume(.01, .01, 100, -.01) == 0, "reject negative step");
    check(FixedVolume(0, .01, 100, .01) == 0, "reject zero lots");
    check(FixedVolume(-.01, .01, 100, .01) == 0, "reject negative lots");
    check(FixedVolume(.01, 0, 100, .01) == 0, "reject zero minimum");
    check(FixedVolume(.01, .1, .01, .01) == 0, "reject reversed limits");

    std::mt19937 random(9132026);
    std::uniform_real_distribution<double> unit(0, 1);
    const double ticks[] = {.001, .01, .05, .1, .25};
    const double steps[] = {.001, .01, .1, .25};
    for (int i = 0; i < 10000; ++i) {
        const bool direction = i % 2 == 0;
        const double low = 1500 + 4000 * unit(random);
        const double high = low + 1 + 20 * unit(random);
        const double atr = 1 + 20 * unit(random);
        const double spread = unit(random);
        const double tick = ticks[i % 5];
        const double rr = i % 2 == 0 ? 1 : 1 + 3 * unit(random);
        const double bid = low + (high - low) * .5;
        const double ask = bid + spread;
        check(MarketLevels(direction, high, low, atr, bid, ask, tick, .15, rr, entry, sl, tp),
              "randomized valid levels");
        check(entry == (direction ? ask : bid), "entry is current market quote, not breakout level");
        check(direction ? (sl < low && tp > entry) : (sl > high + spread && tp < entry),
              "SL outside signal with spread allowance");
        check(std::abs(tp - entry) + 1e-7 >= rr * std::abs(entry - sl), "rounded reward/risk floor");
        check(std::abs(tp - entry) - rr * std::abs(entry - sl) < tick + 1e-7, "RR rounding within one tick");
        for (double price : {sl, tp})
            check(std::abs(price / tick - std::round(price / tick)) < 1e-7, "tick grid");
        const double fill = entry + (unit(random) - .5) * .1;
        check(TargetFromEntry(direction, fill, sl, tick, rr, tp), "actual fill target valid");
        check(std::abs(tp - fill) + 1e-7 >= rr * std::abs(fill - sl), "target uses actual fill");
        check(std::abs(tp - fill) - rr * std::abs(fill - sl) < tick + 1e-7, "actual fill RR within one tick");

        const double step = steps[i % 4];
        const double requested = NormalizeDouble((1 + i % 100) * step, 8);
        const double volume = FixedVolume(requested, step, 100, step);
        check(volume == requested, "valid fixed lots preserved exactly");
        check(FixedVolume(requested + step * .25, step, 100, step) == 0,
              "off-grid lots rejected, not rounded");
        check(FixedVolume(.01, .001, 1 + 100 * unit(random), .001) == .01,
              "fixed default does not grow with broker limit");
    }
    std::cout << "PASS: " << checks << " checks (including 10,000 deterministic randomized cases).\n";
}
