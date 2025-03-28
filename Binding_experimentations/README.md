## NUMA Memory Latency Benchmark

This project provides an MPI-based benchmark tool designed to measure memory latency across different NUMA (Non-Uniform Memory Access) domains using a pointer-chasing approach. The primary goal is to demonstrate how memory access latency varies depending on the NUMA node proximity between CPU cores and the allocated memory region.

## Key Features

- Pointer-chasing method: Accurately measures memory latency by creating a randomized linked list, thus preventing CPU caching and prefetching effects.

- MPI Parallelism: Supports parallel and serial measurement modes across multiple MPI ranks.

- Flexible Allocation: Allocates memory using standard methods, allowing external control of NUMA bindings (e.g., via numactl).

- Detailed Reporting: Provides clear, tabular output of latency measurements per MPI rank, alongside detailed system diagnostics.

- Multi-Size Testing: Supports testing multiple allocation sizes in a single run with automatic size progression.

## How It Works

- Each MPI rank allocates a specified amount of memory and initializes it as a randomly ordered linked list of pointers.

- The benchmark then measures the average time required to traverse this list, accurately reflecting the real memory latency experienced by the CPU.

## Documentation

Detailed analysis of benchmark results is available in the [experimentation.md](experimentation.md) file, which includes:

- Comprehensive analysis of latency patterns across different memory sizes
- Comparison between concurrent and serial execution modes
- Correlation with CPU cache hierarchy and NUMA topology
- Visualizations of memory access latency
- Insights into AMD EPYC architecture performance characteristics

## Requirements

- Linux operating system with NUMA support
- MPI implementation (e.g., OpenMPI, MPICH)
- NUMA development libraries (`libnuma-dev`)
- hwloc library (`libhwloc-dev`)

## Building

```bash
make clean
make
```

## Usage

Basic usage:
```bash
srun --nodes 1 --ntasks 8 --cpu-bind=map_cpu:1,9,17,25,33,41,49,57  numactl --membind=0 --hint=nomultithread ./numa_bench --size=1024
```

### Command Line Options

- `--size=SIZE`: Specify memory size to allocate in MB (default: 512)
- `--size=MIN-MAX`: Test multiple memory sizes from MIN to MAX MB
- `--serial`: Run in serial mode (one rank at a time)

### Using the Wrapper Script

The project includes a wrapper script `run_numa.sh` that provides additional flexibility in controlling NUMA bindings and memory allocation:

```bash
# Basic usage with wrapper script
srun --nodes=1 --ntasks=56 ./run_numa.sh --numa=3 -- --size=2048

# Specify binding per rank
srun --nodes=1 --ntasks=6 ./run_numa.sh --numa=0,1,2,3,0,1 -- --size=1024

# Automatic round-robin binding with verbose output
srun --nodes=1 --ntasks=56 ./run_numa.sh --numa=auto --verbose -- --size=2048

# Test multiple memory sizes from 1MB to 16GB
srun --nodes=1 --ntasks=8 ./run_numa.sh --numa=0,0,1,1,2,2,3,3 --verbose -- --size=1-16384
```

#### Wrapper Script Options

- `--numa=VALUE`: Control NUMA domain binding
  - Single value (e.g., `--numa=3`): Bind all ranks to that NUMA node
  - Comma-separated list (e.g., `--numa=0,1,2,3`): Bind each rank according to the list
  - `auto`: Automatically distribute ranks across all NUMA nodes (round-robin)
  - Default: No NUMA binding

- `--verbose`: Enable verbose output showing rank, NUMA node, and commands

- `--serial`: Run in serial mode (one rank at a time)

- `--`: Separator after which all arguments are passed directly to numa_bench

Note: All numa_bench options (including `--size`) should be passed after the `--` separator.

## Memory Latency Benchmark

The tool includes a memory latency benchmark that measures the actual memory access time for each MPI rank. This benchmark:

1. Creates a randomly shuffled linked list in the allocated memory
2. Uses pointer chasing to force memory accesses in a non-predictable pattern
3. Measures the time taken to traverse the linked list
4. Reports average latency per memory access in nanoseconds

The benchmark helps identify:
- Local vs. remote NUMA memory access latencies
- Impact of NUMA node binding on memory performance
- Memory access patterns and their effect on performance
- Cache effects across different allocation sizes

### Benchmark Configuration

- Number of iterations: 100,000 (configurable via `LATENCY_ITERATIONS`)
- Warm-up iterations: 1,000 (configurable via `WARMUP_ITERATIONS`)
- Random access pattern using Fisher-Yates shuffle algorithm
- Separate random seed for each MPI rank

## System Configuration

The example was run on a system with the following specifications:
- CPU: AMD EPYC 7A53 64-Core Processor
- CPU Family: 25
- Thread(s) per core: 2
- Core(s) per socket: 64
- Socket(s): 1
- NUMA node(s): 4

NUMA Node CPU Distribution:
- NUMA node0 CPU(s): 0-15,64-79
- NUMA node1 CPU(s): 16-31,80-95
- NUMA node2 CPU(s): 32-47,96-111
- NUMA node3 CPU(s): 48-63,112-127

## Example Output

The tool provides detailed information about:
1. MPI process distribution
2. CPU affinity for each process
3. NUMA node assignments
4. Memory allocation details
5. Memory latency measurements across multiple allocation sizes
6. NUMA statistics for the last process

Example output on an AMD EPYC 7A53 64-Core Processor with memory size range testing:
```
srun -t "00:60:00" --nodes 1 --ntasks 8  --cpu-bind=map_cpu:1,9,17,25,33,41,49,57  --hint=nomultithread ./run_numa.sh --numa=0,0,1,1,2,2,3,3 --verbose -- --size=1-16384

[Rank 0] Binding to NUMA domain 0
[Rank 0] Executing: numactl --membind=0 ./numa_bench --size=1-16384
[Rank 5] Binding to NUMA domain 2
[Rank 5] Executing: numactl --membind=2 ./numa_bench --size=1-16384
[Rank 7] Binding to NUMA domain 3
[Rank 7] Executing: numactl --membind=3 ./numa_bench --size=1-16384
[Rank 2] Binding to NUMA domain 1
[Rank 2] Executing: numactl --membind=1 ./numa_bench --size=1-16384
[Rank 4] Binding to NUMA domain 2
[Rank 4] Executing: numactl --membind=2 ./numa_bench --size=1-16384
[Rank 6] Binding to NUMA domain 3
[Rank 6] Executing: numactl --membind=3 ./numa_bench --size=1-16384
[Rank 1] Binding to NUMA domain 0
[Rank 1] Executing: numactl --membind=0 ./numa_bench --size=1-16384
[Rank 3] Binding to NUMA domain 1
[Rank 3] Executing: numactl --membind=1 ./numa_bench --size=1-16384

=== Debug Information ===
MPI Configuration:
  Number of ranks: 8
  Command line arguments:
    argv[0] = ./numa_bench
    argv[1] = --size=1-16384

System Information:
  Page size: 4096 bytes
  Number of NUMA nodes: 4
  NUMA available: Yes
  Number of CPUs: 128
  Current CPU: 1
  Current NUMA node: 0

Note: NUMA memory binding should be controlled externally using numactl --membind=<node>
=====================


 ========================================================================================================================================================================================
|  MPI  |        CPU     |              MEMORY    |                                                             LATENCY (ns)                                                             |
|-------|---------|------|----------------|-------|--------|--------|--------|--------|--------|--------|--------|--------|--------|--------|--------|--------|--------|--------|--------|
| Ranks | Cores   | NUMA |     Address    | NUMA  | 1MB    | 2MB    | 4MB    | 8MB    | 16MB   | 32MB   | 64MB   | 128MB  | 256MB  | 512MB  | 1024M  | 2048M  | 4096M  | 8192M  | 16384M |
|-------|---------|------|----------------|-------|--------|--------|--------|--------|--------|--------|--------|--------|--------|--------|--------|--------|--------|--------|--------|
|  000  | 1       |   0  | 0x527e70       |   0   | 11.53  | 12.92  | 14.25  | 14.93  | 18.67  | 37.73  | 72.45  | 108.77 | 105.56 | 114.71 | 154.92 | 164.07 | 178.93 | 171.25 | 130.76 |
|  001  | 9       |   0  | 0x526920       |   0   | 11.43  | 12.93  | 14.26  | 14.94  | 18.59  | 37.00  | 68.22  | 87.39  | 98.07  | 103.95 | 104.90 | 110.13 | 112.31 | 116.69 | 156.56 |
|  002  | 17      |   1  | 0x526960       |   1   | 11.48  | 12.93  | 14.24  | 14.96  | 18.60  | 37.64  | 68.62  | 108.25 | 98.41  | 120.04 | 149.20 | 162.67 | 183.60 | 164.67 | 155.69 |
|  003  | 25      |   1  | 0x526940       |   1   | 11.16  | 12.99  | 14.23  | 14.93  | 18.72  | 37.32  | 68.17  | 87.64  | 102.25 | 103.49 | 104.50 | 109.08 | 111.92 | 117.30 | 130.77 |
|  004  | 33      |   2  | 0x5269d0       |   2   | 11.47  | 12.93  | 14.21  | 14.93  | 18.51  | 36.19  | 75.32  | 85.91  | 122.77 | 120.02 | 147.15 | 164.27 | 180.87 | 170.07 | 156.06 |
|  005  | 41      |   2  | 0x526960       |   2   | 11.06  | 12.93  | 14.28  | 14.92  | 18.73  | 35.80  | 68.15  | 104.83 | 97.64  | 102.93 | 104.26 | 110.72 | 111.84 | 115.56 | 129.24 |
|  006  | 49      |   3  | 0x5269c0       |   3   | 11.47  | 12.95  | 14.25  | 14.96  | 18.62  | 36.97  | 78.35  | 86.35  | 108.96 | 109.47 | 153.43 | 164.00 | 170.84 | 163.13 | 156.71 |
|  007  | 57      |   3  | 0x5269c0       |   3   | 11.19  | 12.95  | 14.24  | 14.94  | 18.69  | 35.51  | 67.74  | 92.91  | 98.20  | 102.17 | 103.98 | 109.08 | 112.20 | 116.15 | 129.43 |
 ========================================================================================================================================================================================

Per-node process memory usage (in MBs) for PID 60919 (numa_bench)
                           Node 0          Node 1          Node 2          Node 3           Total
                  --------------- --------------- --------------- --------------- ---------------
Huge                         0.00            0.00            0.00            0.00            0.00
Heap                         0.00            0.00            0.00        16386.97        16386.97
Stack                        0.00            0.00            0.00            0.02            0.02
Private                      8.90            2.36            0.95            3.46           15.67
----------------  --------------- --------------- --------------- --------------- ---------------
Total                        8.90            2.36            0.95        16390.45        16402.66
```

### Analysis of Results

The example shows several important characteristics:

1. **Memory Size Scaling**:
   - The benchmark tests memory sizes from 1MB to 16384MB (16GB)
   - Clear latency patterns emerge at different memory size thresholds
   - Cache effects are visible at sizes under 32MB (~10-19ns latency)
   - DRAM access dominates at larger sizes (>64MB, ~65-180ns latency)

2. **NUMA Node Distribution**:
   - Each NUMA node has two ranks bound to it (0/1 to node 0, 2/3 to node 1, etc.)
   - All memory for a given rank is properly bound to its assigned NUMA node

3. **Latency Pattern Analysis**:
   - Interesting pattern between even and odd-numbered ranks within NUMA domains
   - Even-numbered ranks (0,2,4,6) show higher latencies for large allocations
   - Odd-numbered ranks (1,3,5,7) maintain more consistent latencies
   - Full analysis of these patterns available in [experimentation.md](experimentation.md)

4. **Memory Allocation**:
   - Total memory allocated scales up to 16GB per rank
   - Memory is successfully bound to designated NUMA nodes
   - Small amounts of memory are allocated on other nodes for system overhead

## Notes

- Memory allocation is controlled externally using `numactl --membind`
- Memory is touched after allocation to ensure it's actually allocated
- The last MPI process shows detailed NUMA statistics using `numastat`
- CPU affinity information is obtained using hwloc
- The memory latency benchmark uses pointer chasing to measure actual memory access times
- Latency measurements help identify NUMA-related performance impacts
- Analysis of results with cache hierarchy correlation available in experimentation.md

## Future Enhancements

The following features are planned for future development:

- [ ] Memory Bandwidth Measurements
  - [ ] Add bandwidth measurement alongside latency
  - [ ] Implement different access patterns (sequential, random, strided)
  - [ ] Support for both read and write bandwidth tests

- [x] Multi-Size Memory Testing
  - [x] Support for testing multiple allocation sizes in a single run
  - [x] Automatic size progression (e.g., 1MB to 16GB)
  - [x] Comparison of latency across different sizes
  - [x] Detection of memory size thresholds affecting performance

- [ ] Enhanced Visualization and Reporting
  - [ ] Export results in CSV/JSON format for external analysis
  - [x] Support for comparing multiple test runs
  - [x] Analysis of results with cache hierarchy correlation

- [x] Per-Task NUMA Domain Assignment
  - [x] Allow specifying different NUMA domains for each MPI task
  - [x] Support for NUMA domain mapping via command line arguments
  - [x] Enable testing of cross-NUMA node memory access patterns
  - [x] Provide flexibility in memory placement strategies

