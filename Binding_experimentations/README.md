# NUMA Benchmarking Suite

This suite provides tools to run NUMA-aware benchmarks under various core binding and memory allocation strategies on systems with Non-Uniform Memory Access (NUMA) architectures. It leverages SLURM for job execution and `numactl` for fine-grained control over process placement and memory policy.

The main script, `run_numa_benchmarks.sh`, orchestrates benchmark runs across specified NUMA domains, supporting both sequential and interleaved core binding patterns, while scaling the number of ranks per domain. It relies on `wrapper_numa.sh` to apply per-rank NUMA memory bindings before executing the actual benchmark binary.

This project provides an MPI-based benchmark tool `numa_bench` designed to measure memory latency across different NUMA (Non-Uniform Memory Access) domains using a pointer-chasing approach. The primary goal is to demonstrate how memory access latency varies depending on the NUMA node proximity between CPU cores and the allocated memory region.

## Features

* Supports **sequential** and **interleaved** core allocation strategies across specified NUMA domains.
* Configurable **NUMA domain selection** for benchmarks.
* Automatic **core binding** based on system topology defined in an architecture file.
* Handles core exclusion via `SKIP_CORES` directive.
* Scales tests by increasing the number of ranks per domain.
* **Dry-run mode** (`--dry-run`) to preview `srun` commands without execution.
* Customizable **job directory labels** (`--label`) for better organization.



# run_numa_benchmarks.sh

This script is the main entry point for running the benchmark suite. It orchestrates the execution across different configurations, calling `wrapper_numa.sh` via `srun` for each specific test case.

### Command-Line Options

- `--arch <config_file>`: **(Required)** Path to the architecture configuration file defining the system topology and parameters.

- `--sequential <domains>`: Run benchmark with sequential CPU allocation on the specified NUMA domains (comma-separated list, e.g., 0,1). Ranks are bound to cores sequentially within each specified domain's available core list.

- `--interleaved <domains>`: Run benchmark with interleaved CPU allocation across CCDs within the specified NUMA domains (comma-separated list, e.g., 0,1). Ranks are bound to cores by picking one core from each CCD in a round-robin fashion within each domain.

- `--dry-run`: Show the srun commands that would be generated and executed for each configuration without actually running them. Useful for verifying core/NUMA bindings.


### Examples

```bash
# Run sequential allocation on NUMA domains 0 and 1
sbatch ./run_numa_benchmarks.sh --arch architectures/lumi_partc --sequential 0,1

# Run interleaved allocation across three domains with custom label
sbatch ./run_numa_benchmarks.sh --arch architectures/lumi_partc --interleaved 0,1,2 --label test_run

# Preview commands without executing (dry-run)
./run_numa_benchmarks.sh --arch architectures/lumi_partc --sequential 0,1 --dry-run
```

### Output Structure

Results are stored in the `results_scaling/job_<SLURM_JOB_ID>` directory (with optional label suffix):
```
results_scaling/job_123456_my_test/
├── sequential_domain0_8ranks_16MB.csv
├── sequential_domains0,1_16ranks_16MB.csv
└── slurm_run_numa_benchmarks_123456.log
```

Each CSV file contains latency measurements for the specific configuration (allocation type, domains, ranks, memory size).


-----------------------------------------------------------------------------------------------------------------
# Wrapper Script (wrapper_numa.sh)

The `wrapper_numa.sh` script provides flexible NUMA binding control for individual MPI ranks. It is called by `run_numa_benchmarks.sh` for each rank to manage memory allocation policies and execute the actual benchmark binary.

### Command-Line Options

- `--numa=VALUE`: Control NUMA domain binding
  - Single value (e.g., `--numa=3`): Bind all ranks to that NUMA node
  - Comma-separated list (e.g., `--numa=0,1,2,3`): Bind each rank according to the list
  - `auto`: Automatically distribute ranks across all NUMA nodes (round-robin)
  - Default: No NUMA binding (bind to node 0)

- `--quiet`: Disable verbose output (default is verbose)
- `--dry-run`: Print commands that would be executed without running them
- `--help`: Display help message and exit
- `--`: Separator after which all arguments are passed directly to the benchmark

### Examples

```bash
# Bind all MPI ranks to NUMA node 3 with explicit CPU mapping
srun --nodes=1 --ntasks=4 --cpu-bind=map_cpu:1,17,33,49 ./wrapper_numa.sh --numa=3 -- --size=2048

# Specify binding per rank with CPU mapping across CCDs
srun --nodes=1 --ntasks=8 --cpu-bind=map_cpu:1,9,17,25,33,41,49,57 ./wrapper_numa.sh --numa=0,1,2,3,0,1,2,3 -- --size=1024

# Automatic round-robin binding with CPU mapping to first core of each CCD
srun --nodes=1 --ntasks=4 --cpu-bind=map_cpu:0,16,32,48 ./wrapper_numa.sh --numa=auto -- --size=2048

# Dry run to see what commands would be executed
srun --nodes=1 --ntasks=4 --cpu-bind=map_cpu:1,17,33,49 ./wrapper_numa.sh --numa=0,1,2,3 --dry-run -- --size=512
```

### Features

- Flexible NUMA binding per rank
- Automatic round-robin NUMA distribution
- Verbose output for debugging
- Dry-run mode for testing configurations
- Validation of NUMA domain specifications
- Automatic detection of available NUMA nodes

Note: This script is designed to run under SLURM with `srun` and requires the `numactl` package to be installed.

-----------------------------------------------------------------------------------------------------------------
# Memory Latency Benchmark

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





### Benchmark Configuration

- Number of iterations: 100,000 (configurable via `LATENCY_ITERATIONS`)
- Warm-up iterations: 1,000 (configurable via `WARMUP_ITERATIONS`)
- Random access pattern using Fisher-Yates shuffle algorithm
- Separate random seed for each MPI rank


### Exemple

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

1. **Memory Allocation**:
   - Total memory allocated scales up to 16GB per rank
   - Memory is successfully bound to designated NUMA nodes
   - Small amounts of memory are allocated on other nodes for system overhead

2. **Memory Size Scaling**:
   - The benchmark tests memory sizes from 1MB to 16384MB (16GB)
   - Clear latency patterns emerge at different memory size thresholds
   - Full analysis of these patterns available in [experimentation.md](experimentation.md)





---
## Future Enhancements

The following features are planned for future development:

- [ ] Memory Bandwidth Measurements
  - [ ] Add bandwidth measurement alongside latency
  - [ ] Implement different access patterns (sequential, random, strided)
  - [ ] Support for both read and write bandwidth tests
