#!/bin/sh
# Behaviour check for pure refactors (To do 18): seeded AI-vs-AI games in both
# turn systems; a refactor must leave every final-state hash unchanged.
#   tools/refactor_check.sh > after.txt ; diff before.txt after.txt
cd "$(dirname "$0")/.." || exit 1
export PYTHONHASHSEED=0
for sys in igougo aa; do
  xvfb-run -a /usr/bin/python3.12 tools/headless_runner.py --games 6 --procs 4 \
    --system "$sys" --timeout 300 2>/dev/null | grep '^seed' | sed "s/ [0-9.]*s hash/ hash/; s/^/$sys /"
done
xvfb-run -a /usr/bin/python3.12 tools/headless_runner.py --games 4 --procs 4 \
  --fleet1 tools/gui_checks/sm_test_fleet.json --fleet2 tools/gui_checks/ork_test_fleet.json \
  --timeout 300 2>/dev/null | grep '^seed' | sed "s/ [0-9.]*s hash/ hash/; s/^/sm-orks /"
