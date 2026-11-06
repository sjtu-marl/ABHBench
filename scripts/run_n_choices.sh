#!/usr/bin/env bash
# Usage: ./scripts/run_n_choices.sh [script] [args...]

SCRIPT=${1:-scenes/other/harp.py}
shift || true # drop script path from $@
DISPLAY=:100
PYTHONPATH=.

for v in {10..100..10}; do
    echo "agent.collect_n_choices=$v"
    DISPLAY=$DISPLAY PYTHONPATH=$PYTHONPATH \
        env "agent.collect_n_choices=$v" \
        python "$SCRIPT" "$@"
done
