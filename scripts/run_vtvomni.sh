#!/usr/bin/env bash
set -euo pipefail

chapters="1 7 8 27"
max_loops=10

while getopts "c:n:" opt; do
    case $opt in
    c) chapters="$OPTARG" ;;
    n) max_loops="$OPTARG" ;;
    *)
        echo "Usage: $0 [-c \"1 7 8 27\"] [-n 10]"
        exit 1
        ;;
    esac
done

IFS=' ' read -r -a chapters_array <<<"$chapters"

for c in "${chapters_array[@]}"; do
    for ((i = 1; i <= max_loops; i++)); do
        echo "chapter=$c loop=$i"
        env \
            flags.clearml_tag=vtvomni \
            agent.collect_n_choices=1 \
            agent.collect_n_important_choices=20 \
            chapter_num="$c" \
            PYTHONPATH=. \
            python scenes/DBH/llm/vt_scene.py
        env \
            flags.clearml_tag=vtvomni \
            agent.collect_n_choices=1 \
            agent.collect_n_important_choices=20 \
            chapter_num="$c" \
            PYTHONPATH=. \
            python scenes/DBH/llm/omni_scene.py
    done
done
