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
    check(!MomentumLevels(true, 3006, 2999, nan, .3, .01, .1, .15, 2, entry, sl, tp), "reject NaN ATR");
    check(!MomentumLevels(true, 3006, 2999, 5, .3, .01, .1, .15, inf, entry, sl, tp), "reject infinite RR");
    check(MomentumLevels(true, 3006, 2999, 5, .3, .01, .1, .15, 2, entry, sl, tp),
          "buy levels valid");
    check(near(entry, 3006.8) && near(sl, 2998.25) && near(tp, 3023.9), "buy prices");
    check(MomentumLevels(false, 3006, 2999, 5, .3, .01, .1, .15, 2, entry, sl, tp),
          "sell levels valid");
    check(near(entry, 2998.5) && near(sl, 3007.05) && near(tp, 2981.4), "sell prices");
    check(MomentumLevels(true, 3006, 2999, 5, 0, .25, 0, 0, 2, entry, sl, tp),
          "minimum one-tick buffers");
    check(near(entry, 3006.25) && near(sl, 2998.75), "zero buffers still outside candle");
    check(!MomentumLevels(true, 3006, 2999, 0, .3, .01, .1, .15, 2, entry, sl, tp), "zero ATR");
    check(!MomentumLevels(true, 3006, 2999, 5, -.3, .01, .1, .15, 2, entry, sl, tp), "negative spread");
    check(!MomentumLevels(true, 3006, 2999, 5, .3, 0, .1, .15, 2, entry, sl, tp), "zero tick");
    check(!MomentumLevels(true, 2999, 3006, 5, .3, .01, .1, .15, 2, entry, sl, tp), "reversed range");

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
        const double rr = 1 + 3 * unit(random);
        check(MomentumLevels(direction, high, low, atr, spread, tick, .1, .15, rr, entry, sl, tp),
              "randomized valid levels");
        check(direction ? (entry > high + spread && sl < low && tp > entry)
                        : (entry < low && sl > high + spread && tp < entry),
              "prices outside signal with spread allowance");
        check(std::abs(tp - entry) + 1e-7 >= rr * std::abs(entry - sl), "rounded reward/risk floor");
        for (double price : {entry, sl, tp})
            check(std::abs(price / tick - std::round(price / tick)) < 1e-7, "tick grid");

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
