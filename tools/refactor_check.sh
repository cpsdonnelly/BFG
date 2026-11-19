#!/bin/sh
# Behaviour check for pure refactors (To do 18): seeded AI-vs-AI games in both
# turn systems, with no window (the same games as in the window); a refactor
# must leave every final-state hash unchanged. Optional rules off (--rules none),
# as the saved results were recorded.
#   tools/refactor_check.sh > after.txt ; diff before.txt after.txt
cd "$(dirname "$0")/.." || exit 1
unset DISPLAY      # no window: a stray Tk call fails loudly instead of needing xvfb
export PYTHONHASHSEED=0
for sys in igougo aa; do
  /usr/bin/python3.12 tools/headless_runner.py --no-display --rules none --games 6 --procs 4 \
    --system "$sys" --timeout 300 2>/dev/null | grep '^seed' | sed "s/ [0-9.]*s hash/ hash/; s/^/$sys /"
done
/usr/bin/python3.12 tools/headless_runner.py --no-display --rules none --games 4 --procs 4 \
  --fleet1 tools/gui_checks/sm_test_fleet.json --fleet2 tools/gui_checks/ork_test_fleet.json \
  --timeout 300 2>/dev/null | grep '^seed' | sed "s/ [0-9.]*s hash/ hash/; s/^/sm-orks /"
