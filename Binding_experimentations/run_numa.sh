#!/bin/bash
#
# run_numa.sh - A wrapper script for numa_bench with flexible NUMA binding options
#
# This script controls NUMA binding for each MPI rank using numactl and provides
# various options for controlling memory allocation and execution behavior.
#

# Exit on any error
set -e

# Default values
NUMA_BINDING="0"
NUMA_SPECIFIED=0
VERBOSE=0
SERIAL_MODE=""
FORWARDED_ARGS=()

# Function to display help message
show_help() {
    cat << EOF
Usage: $0 [options] [-- <numa_bench_options>]

This script runs numa_bench with flexible NUMA binding options.

Options:
  --numa=VALUE     Control NUMA domain binding
                   - Single value (e.g., --numa=3): Bind all ranks to that NUMA node
                   - Comma-separated list (e.g., --numa=0,1,2,3): Bind each rank according to the list
                   - 'auto': Automatically distribute ranks across all NUMA nodes (round-robin)
                   Default: No NUMA binding

  --verbose        Enable verbose output showing rank, NUMA node, and commands

  --serial         Run in serial mode (one rank at a time)

  --help           Display this help message and exit

  --               Separator after which all arguments are passed directly to numa_bench

Examples:
  # Bind all MPI ranks to NUMA node 3
  srun --nodes=1 --ntasks=56 ./run_numa.sh --numa=3 -- --size=2048

  # Specify binding per rank
  srun --nodes=1 --ntasks=6 ./run_numa.sh --numa=0,1,2,3,0,1 -- --size=1024

  # Automatic round-robin binding with verbose output
  srun --nodes=1 --ntasks=56 ./run_numa.sh --numa=auto --verbose -- --size=2048
EOF
}

# Function to get the number of NUMA nodes
get_numa_node_count() {
    numactl -H | grep "available:" | awk '{print $2}'
}

# Function to check if numactl and numa_bench exist
check_prerequisites() {
    if ! command -v numactl &> /dev/null; then
        echo "Error: numactl not found. Please install numactl package." >&2
        exit 1
    fi

    if [ ! -x "./numa_bench" ]; then
        echo "Error: numa_bench executable not found or not executable." >&2
        echo "Please run 'make' to compile or check your current directory." >&2
        exit 1
    fi
}

# Parse command line arguments
parse_args() {
    # Flag to indicate if we've seen the -- separator
    local passthrough=0
    
    while [ $# -gt 0 ]; do
        # If we've seen --, add all remaining arguments to FORWARDED_ARGS
        if [ $passthrough -eq 1 ]; then
            FORWARDED_ARGS+=("$1")
            shift
            continue
        fi
        
        # Check if this argument is --
        if [ "$1" = "--" ]; then
            passthrough=1
            shift
            continue
        fi
        
        # Process script arguments
        case "$1" in
            --numa=*)
                NUMA_BINDING="${1#*=}"
                NUMA_SPECIFIED=1
                ;;
            --verbose)
                VERBOSE=1
                ;;
            --serial)
                SERIAL_MODE="--serial"
                ;;
            --help)
                show_help
                exit 0
                ;;
            *)
                echo "Unknown option: $1" >&2
                show_help
                exit 1
                ;;
        esac
        shift
    done
    
    # If --serial was specified both as a script arg and after --, remove it from script args
    if [ "$SERIAL_MODE" = "--serial" ] && [[ " ${FORWARDED_ARGS[*]} " == *" --serial "* ]]; then
        SERIAL_MODE=""
    fi
}

# Function to handle automatic NUMA node distribution
handle_auto_numa() {
    local num_ranks=$1
    local num_nodes=$(get_numa_node_count)
    
    if [ $num_nodes -eq 0 ]; then
        echo "Error: Could not detect NUMA nodes." >&2
        exit 1
    fi
    
    # Create an array for round-robin NUMA assignment
    local numa_list=""
    for ((i=0; i<num_ranks; i++)); do
        numa_id=$((i % num_nodes))
        [ -n "$numa_list" ] && numa_list+=","
        numa_list+="$numa_id"
    done
    
    echo "$numa_list"
}

# Function to validate NUMA binding list
validate_numa_binding() {
    local binding=$1
    local num_ranks=$2
    
    # Count elements in the NUMA binding list
    local binding_count=$(echo "$binding" | tr ',' '\n' | wc -l)
    
    if [ "$binding_count" -ne "$num_ranks" ]; then
        echo "Error: Number of NUMA bindings ($binding_count) does not match number of MPI ranks ($num_ranks)." >&2
        exit 1
    fi
}

# Main execution function
run_with_numa_binding() {
    local rank=$SLURM_PROCID
    local total_ranks=$SLURM_NTASKS
    
    # If rank is not set, we're not running under SLURM
    if [ -z "$rank" ] || [ -z "$total_ranks" ]; then
        echo "Error: This script is designed to run under SLURM with srun." >&2
        exit 1
    fi
    
    # Construct the arguments for numa_bench
    local numa_bench_args=()
    
    # Add serial mode if specified and not in forwarded args
    if [ -n "$SERIAL_MODE" ]; then
        numa_bench_args+=($SERIAL_MODE)
    fi
    
    # Add forwarded arguments
    if [ ${#FORWARDED_ARGS[@]} -gt 0 ]; then
        numa_bench_args+=("${FORWARDED_ARGS[@]}")
    fi
    
    # If no NUMA binding specified, run without numactl
    if [ "$NUMA_SPECIFIED" -eq 0 ]; then
        local cmd="./numa_bench ${numa_bench_args[*]}"
        
        # Print verbose output if requested
        if [ "$VERBOSE" -eq 1 ]; then
            echo "[Rank $rank] Running without NUMA binding"
            echo "[Rank $rank] Executing: $cmd"
        fi
        
        # Execute the command
        if ! eval "$cmd"; then
            echo "Error: Command failed for rank $rank: $cmd" >&2
            exit 2
        fi
        return
    fi
    
    # Handle auto NUMA binding
    if [ "$NUMA_BINDING" = "auto" ]; then
        NUMA_BINDING=$(handle_auto_numa "$total_ranks")
    fi
    
    # For comma-separated list, validate and get the correct NUMA node for this rank
    if [[ $NUMA_BINDING == *,* ]]; then
        validate_numa_binding "$NUMA_BINDING" "$total_ranks"
        # Extract NUMA domain for this rank
        numa_domain=$(echo "$NUMA_BINDING" | cut -d ',' -f $((rank+1)))
    else
        # Single value for all ranks
        numa_domain=$NUMA_BINDING
    fi
    
    # Check if NUMA domain is valid
    if ! [[ "$numa_domain" =~ ^[0-9]+$ ]]; then
        echo "Error: Invalid NUMA domain '$numa_domain' for rank $rank." >&2
        exit 1
    fi
    
    # Verify if specified NUMA node exists
    local max_node=$(($(get_numa_node_count) - 1))
    if [ "$numa_domain" -gt "$max_node" ]; then
        echo "Error: NUMA domain $numa_domain does not exist. Max domain is $max_node." >&2
        exit 1
    fi
    
    # Prepare the command
    local cmd="numactl --membind=$numa_domain ./numa_bench ${numa_bench_args[*]}"
    
    # Print verbose output if requested
    if [ "$VERBOSE" -eq 1 ]; then
        echo "[Rank $rank] Binding to NUMA domain $numa_domain"
        echo "[Rank $rank] Executing: $cmd"
    fi
    
    # Execute the command
    if ! eval "$cmd"; then
        echo "Error: Command failed for rank $rank: $cmd" >&2
        exit 2
    fi
}

# Main script execution
main() {
    check_prerequisites
    parse_args "$@"
    run_with_numa_binding
}

# Call main function with all script arguments
main "$@" 