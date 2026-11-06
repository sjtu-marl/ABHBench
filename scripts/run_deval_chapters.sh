#!/usr/bin/env bash
set -euo pipefail

# Default chapters (all available chapters)
default_chapters="1 7 8 10 27"

# Default number of loops
loops=1

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -n|--loops)
            if [[ $# -lt 2 ]] || [[ ! $2 =~ ^[0-9]+$ ]]; then
                echo "Error: -n requires a positive integer argument"
                echo "Usage: $0 [-n LOOPS] [chapter1 chapter2 ...]"
                exit 1
            fi
            loops="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: $0 [-n LOOPS] [chapter1 chapter2 ...]"
            echo "  -n, --loops LOOPS    Number of times to run all chapters (default: 1)"
            echo "  -h, --help          Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0                   # Run default chapters once"
            echo "  $0 1 7 8            # Run chapters 1, 7, 8 once"
            echo "  $0 -n 3             # Run default chapters 3 times"
            echo "  $0 -n 5 1 7 8       # Run chapters 1, 7, 8 five times"
            exit 0
            ;;
        -*)
            echo "Error: Unknown option $1"
            echo "Usage: $0 [-n LOOPS] [chapter1 chapter2 ...]"
            exit 1
            ;;
        *)
            break
            ;;
    esac
done

# Check if chapters were provided after parsing options
if [ $# -eq 0 ]; then
    echo "No chapters specified, using default chapters: $default_chapters"
    IFS=' ' read -r -a chapters_array <<<"$default_chapters"
else
    # Remaining arguments are chapter numbers
    chapters_array=("$@")
fi

# Display what will be run
if [ ${#chapters_array[@]} -eq 0 ] || [[ "${chapters_array[*]}" == "$default_chapters" ]]; then
    echo "Running deval for chapters: $default_chapters"
    chapters_display="$default_chapters"
else
    echo "Running deval for chapters: ${chapters_array[*]}"
    chapters_display="${chapters_array[*]}"
fi

if [ "$loops" -gt 1 ]; then
    echo "Will repeat $loops times"
fi
echo ""

# Create a temporary copy of the original config in system temp directory
original_config="config.yaml"
temp_config="$(mktemp --suffix=_config.yaml)"

if [ -f "$original_config" ]; then
    echo "Creating temporary config: $temp_config"
    cp "$original_config" "$temp_config"
else
    echo "Warning: Original config file $original_config not found!"
    exit 1
fi
echo ""

# Main loop - repeat the entire process N times
for ((loop=1; loop<=loops; loop++)); do
    if [ "$loops" -gt 1 ]; then
        echo "###################################################"
        echo "Starting loop $loop of $loops"
        echo "###################################################"
        echo ""
    fi
    
    # Run each chapter
    for c in "${chapters_array[@]}"; do
        echo "===================================================="
        if [ "$loops" -gt 1 ]; then
            echo "Loop $loop/$loops - Running chapter $c..."
        else
            echo "Running chapter $c..."
        fi
        echo "===================================================="
        
        # Run the chapter with the temporary config
        env "chapter_num=$c" "CONFIG=$temp_config" PYTHONPATH=. python -m scenes.DBH.deval.omni_scene
        
        if [ "$loops" -gt 1 ]; then
            echo "Loop $loop/$loops - Chapter $c completed."
        else
            echo "Chapter $c completed."
        fi
        echo ""
    done
    
    if [ "$loops" -gt 1 ]; then
        echo "Loop $loop of $loops completed!"
        echo ""
    fi
done

if [ "$loops" -gt 1 ]; then
    echo "All $loops loops completed successfully!"
else
    echo "All chapters completed successfully!"
fi