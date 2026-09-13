#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
includes="$(grep -E '^[[:space:]]*#include[[:space:]]' Experts/MomentumCandleXAU/MomentumCandleXAU.mq5)"
if [[ "$includes" != '#include <Trade\Trade.mqh>' ]]; then
  echo 'FAIL: EA must only depend on the built-in MT5 Trade library.' >&2
  exit 1
fi
echo 'PASS: single-file EA packaging (no custom includes).'
binary="$(mktemp /tmp/momentum-core-test.XXXXXX)"
trap 'rm -f "$binary"' EXIT
g++ -std=c++17 -O2 -Wall -Wextra -Werror -pedantic -fsanitize=undefined \
  tests/momentum_core_test.cpp -o "$binary"
"$binary"
