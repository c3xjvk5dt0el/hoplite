#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
includes="$(grep -E '^[[:space:]]*#include[[:space:]]' Experts/MomentumCandleXAU/MomentumCandleXAU.mq5)"
if [[ "$includes" != '#include <Trade\Trade.mqh>' ]]; then
  echo 'FAIL: EA must only depend on the built-in MT5 Trade library.' >&2
  exit 1
fi
echo 'PASS: single-file EA packaging (no custom includes).'
ea=Experts/MomentumCandleXAU/MomentumCandleXAU.mq5
grep -q '^input double InpFixedLots = 0.01;' "$ea"
if grep -nE 'RiskVolume|InpRiskPercent|InpMaxLots|InpRoundTripCostPerLot|ACCOUNT_EQUITY|ACCOUNT_BALANCE' "$ea"; then
  echo 'FAIL: percentage-based sizing must not remain in the fixed-lot EA.' >&2
  exit 1
fi
echo 'PASS: fixed 0.01 default with no equity/balance sizing.'
grep -q '^input double InpRewardRisk = 1.0;' "$ea"
grep -q 'trade.Buy(volume, _Symbol, entry, sl, tp, MARKET_COMMENT)' "$ea"
grep -q 'trade.Sell(volume, _Symbol, entry, sl, tp, MARKET_COMMENT)' "$ea"
if grep -nE 'BuyStop|SellStop|InpEntryBufferATR|InpPendingBars|ORDER_TIME_SPECIFIED|SYMBOL_EXPIRATION|ORDER_FILLING_RETURN' "$ea"; then
  echo 'FAIL: market entry must not depend on breakout or pending-order expiry/filling.' >&2
  exit 1
fi
echo 'PASS: market BUY/SELL with attached protection and default RR 1:1.'
binary="$(mktemp /tmp/momentum-core-test.XXXXXX)"
trap 'rm -f "$binary" "${pullback_binary:-}" "${sweep_binary:-}"' EXIT
g++ -std=c++17 -O2 -Wall -Wextra -Werror -pedantic -fsanitize=undefined \
  tests/momentum_core_test.cpp -o "$binary"
"$binary"

pullback=Experts/TrendPullbackXAU/TrendPullbackXAU.mq5
includes="$(grep -E '^[[:space:]]*#include[[:space:]]' "$pullback")"
[[ "$includes" == '#include <Trade\Trade.mqh>' ]]
grep -q '^input double InpFixedLots = 0.01;' "$pullback"
grep -q '^input double InpRewardRisk = 1.5;' "$pullback"
if grep -nE 'BuyStop|SellStop|BuyLimit|SellLimit|ACCOUNT_EQUITY|ACCOUNT_BALANCE' "$pullback"; then
  echo 'FAIL: pullback must use market entry and fixed volume.' >&2
  exit 1
fi
echo 'PASS: separate single-file pullback EA, fixed 0.01 lot, default RR 1:1.5.'
pullback_binary="$(mktemp /tmp/pullback-core-test.XXXXXX)"
g++ -std=c++17 -O2 -Wall -Wextra -Werror -pedantic -fsanitize=undefined \
  tests/trend_pullback_test.cpp -o "$pullback_binary"
"$pullback_binary"

sweep=Experts/SweepReclaimXAU/SweepReclaimXAU.mq5
includes="$(grep -E '^[[:space:]]*#include[[:space:]]' "$sweep")"
[[ "$includes" == '#include <Trade\Trade.mqh>' ]]
grep -q '^input double InpFixedLots = 0.01;' "$sweep"
grep -q '^input double InpRewardRisk = 1.0;' "$sweep"
grep -q '^input bool InpAllowLiveTrading = false;' "$sweep"
if grep -nE 'BuyStop|SellStop|BuyLimit|SellLimit|ACCOUNT_EQUITY|ACCOUNT_BALANCE' "$sweep"; then
  echo 'FAIL: sweep fallback must retain fixed market volume and no equity sizing.' >&2
  exit 1
fi
echo 'PASS: separate standalone sweep fallback, 0.01 lot, RR 1:1, live disabled by default.'
sweep_binary="$(mktemp /tmp/sweep-core-test.XXXXXX)"
g++ -std=c++17 -O2 -Wall -Wextra -Werror -pedantic -fsanitize=undefined \
  tests/sweep_reclaim_test.cpp -o "$sweep_binary"
"$sweep_binary"
python3 -m unittest discover -s tests -p 'test_*.py' -v
