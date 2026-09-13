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

    check(near(RiskVolume(5, 855, .01, 1, .01), 0), "never force minimum lot over risk");
    check(near(RiskVolume(nan, 855, .01, 1, .01), 0), "reject NaN budget");
    check(near(RiskVolume(5, inf, .01, 1, .01), 0), "reject infinite loss");
    check(near(RiskVolume(5, 855, .01, 1, nan), 0), "reject NaN volume step");
    check(near(RiskVolume(10, 855, .01, 1, .01), .01), "round lot down");
    check(near(RiskVolume(100, 1000, .01, 1, .01), .1), "exact lot boundary");
    check(near(RiskVolume(99.999, 1000, .01, 1, .01), .09), "below lot boundary");
    check(near(RiskVolume(1000, 1000, .01, .5, .01), .5), "maximum lot cap");
    check(near(RiskVolume(1000, 1000, .01, .025, .01), .02), "non-grid max lot");
    check(near(RiskVolume(1000, 1000, .001, 1, .001), 1), "three-decimal lot step");
    check(near(RiskVolume(99, 100, .25, 10, .25), .75), "nondecimal lot step");
    check(near(RiskVolume(100, 0, .01, 1, .01), 0), "invalid loss estimate");
    check(near(RiskVolume(100, 1000, .1, .01, .01), 0), "cap below minimum");
    check(near(RiskVolume(100, 1000, .01, 1, 0), 0), "invalid lot step");
    check(RiskVolume(100, 1007, .01, 1, .01) < RiskVolume(100, 1000, .01, 1, .01),
          "commission reserve reduces volume");

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

        const double budget = .1 + 1000 * unit(random);
        const double loss = 10 + 5000 * unit(random);
        const double step = steps[i % 4];
        const double cap = step + 3 * unit(random);
        const double volume = RiskVolume(budget, loss, step, cap, step);
        check(volume * loss <= budget + 1e-8, "risk budget never exceeded");
        check(volume <= cap + 1e-8, "lot cap never exceeded");
        check(volume == 0 || volume >= step - 1e-8, "minimum lot respected");
        check(std::abs(volume / step - std::round(volume / step)) < 1e-7, "lot grid");
    }
    std::cout << "PASS: " << checks << " checks (including 10,000 deterministic randomized cases).\n";
}
