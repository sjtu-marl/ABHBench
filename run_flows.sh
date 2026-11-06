#!/bin/bash

# Define the script identifiers list
script_ids=("01" "05" "07" "08" "27")

# Check if enough parameters are provided
if [ "$#" -gt "${#script_ids[@]}" ]; then
    echo "Too many arguments provided. Expecting up to ${#script_ids[@]}."
    exit 1
fi

# Assign input parameters or use default value 10 if not provided
for idx in "${!script_ids[@]}"; do
    counts[idx]=${1:-10}
    shift
done

# Execute each script based on the counts provided
for idx in "${!script_ids[@]}"; do
    script_id=${script_ids[idx]}
    count=${counts[idx]}

    for ((i=1; i<=count; i++)); do
        PYTHONPATH=. python flow/flow_"${script_id}".py
    done
done
