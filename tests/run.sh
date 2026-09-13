#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
binary="$(mktemp /tmp/momentum-core-test.XXXXXX)"
trap 'rm -f "$binary"' EXIT
g++ -std=c++17 -O2 -Wall -Wextra -Werror -pedantic -fsanitize=undefined \
  tests/momentum_core_test.cpp -o "$binary"
"$binary"
