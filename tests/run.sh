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
binary="$(mktemp /tmp/momentum-core-test.XXXXXX)"
trap 'rm -f "$binary"' EXIT
g++ -std=c++17 -O2 -Wall -Wextra -Werror -pedantic -fsanitize=undefined \
  tests/momentum_core_test.cpp -o "$binary"
"$binary"
