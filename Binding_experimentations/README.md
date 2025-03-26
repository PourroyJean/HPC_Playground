## NUMA Memory Latency Benchmark

This project provides an MPI-based benchmark tool designed to measure memory latency across different NUMA (Non-Uniform Memory Access) domains using a pointer-chasing approach. The primary goal is to demonstrate how memory access latency varies depending on the NUMA node proximity between CPU cores and the allocated memory region.

## Key Features

- Pointer-chasing method: Accurately measures memory latency by creating a randomized linked list, thus preventing CPU caching and prefetching effects.

- MPI Parallelism: Supports parallel and serial measurement modes across multiple MPI ranks.

- Flexible Allocation: Allocates memory using standard methods, allowing external control of NUMA bindings (e.g., via numactl).

- Detailed Reporting: Provides clear, tabular output of latency measurements per MPI rank, alongside detailed system diagnostics.

## How It Works

- Each MPI rank allocates a specified amount of memory and initializes it as a randomly ordered linked list of pointers.

- The benchmark then measures the average time required to traverse this list, accurately reflecting the real memory latency experienced by the CPU.




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
srun --nodes 1 --ntasks 8 --cpu-bind=map_cpu:1,9,17,25,33,41,49,57 --hint=nomultithread ./numa_bench <size_in_mb>
```

With external NUMA control:
```bash
numactl --membind=<node_number> srun --nodes 1 --ntasks 8 --cpu-bind=map_cpu:1,9,17,25,33,41,49,57 --hint=nomultithread ./numa_bench <size_in_mb>
```

With serial execution mode:
```bash
numactl --membind=<node_number> srun --nodes 1 --ntasks 8 --cpu-bind=map_cpu:1,9,17,25,33,41,49,57 --hint=nomultithread ./numa_bench --serial <size_in_mb>
```

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
5. Memory latency measurements
6. NUMA statistics for the last process

Example output on an AMD EPYC 7A53 64-Core Processor:
```
srun --nodes 1 --ntasks 8  --cpu-bind=map_cpu:1,9,17,25,33,41,49,57  --hint=nomultithread numactl -
-membind=3 ./numa_allocator --serial 2048


=== Debug Information ===
MPI Configuration:
  Number of ranks: 8
  Command line arguments:
    argv[0] = ./numa_bench
    argv[1] = --serial
    argv[2] = 2048

System Information:
  Page size: 4096 bytes
  Number of NUMA nodes: 4
  NUMA available: Yes
  Number of CPUs: 128
  Current CPU: 1
  Current NUMA node: 0

===========================================================================================
|  MPI  |        CPU     |                             MEMORY                  |  LATENCY   |
|-------|---------|------|----------------|--------------|-------|-------------|------------|
| ranks | Cores   | NUMA |     Address    | SIZE (MB)    | NUMA  |  Page Size  | Avg (ns)   |
|-------|---------|------|----------------|--------------|-------|-------------|------------|
|  000  | 1       |   0  | 0x425620       | 2048         |   3   | kB=4        | 124.65     |
|  001  | 9       |   0  | 0x424f80       | 2048         |   3   | kB=4        | 124.76     |
|  002  | 17      |   1  | 0x424fc0       | 2048         |   3   | kB=4        | 120.75     |
|  003  | 25      |   1  | 0x424fc0       | 2048         |   3   | kB=4        | 123.03     |
|  004  | 33      |   2  | 0x425000       | 2048         |   3   | kB=4        | 116.44     |
|  005  | 41      |   2  | 0x425000       | 2048         |   3   | kB=4        | 114.53     |
|  006  | 49      |   3  | 0x425040       | 2048         |   3   | kB=4        | 108.24     |
|  007  | 57      |   3  | 0x425040       | 2048         |   3   | kB=4        | 107.13     |

Per-node process memory usage (in MBs) for PID 17959 (numa_bench)
                           Node 0          Node 1          Node 2          Node 3           Total
                  --------------- --------------- --------------- --------------- ---------------
Huge                         0.00            0.00            0.00            0.00            0.00
Heap                         0.00            0.00            0.00         2050.13         2050.13
Stack                        0.00            0.00            0.00            0.02            0.02
Private                      0.51            0.00            0.00           15.20           15.70
----------------  --------------- --------------- --------------- --------------- ---------------
Total                        0.51            0.00            0.00         2065.35         2065.86
```

### Analysis of Results

The example shows several important characteristics:

1. **NUMA Node Distribution**:
   - The system has 4 NUMA nodes
   - Each NUMA node has 2 CCDs (Core Complex Dies)
   - Memory is bound to NUMA node 3 using `numactl --membind=3`
   - Tasks are mapped to one CPU per CCD (1,9,17,25,33,41,49,57)

2. **Memory Latency Pattern**:
   - Local access (NUMA node 3): ~107-108 ns
   - Remote access (NUMA node 2): ~114-116 ns
   - Remote access (NUMA node 1): ~120-124 ns
   - Remote access (NUMA node 0): ~124-125 ns
   - Shows clear NUMA locality impact on memory access latency

3. **Memory Allocation**:
   - Total memory allocated: 2048 MB per rank
   - Memory is successfully bound to NUMA node 3
   - Small amounts of memory are allocated on other nodes for system overhead

## Notes

- Memory allocation is controlled externally using `numactl --membind`
- Memory is touched after allocation to ensure it's actually allocated
- The last MPI process shows detailed NUMA statistics using `numastat`
- CPU affinity information is obtained using hwloc
- The memory latency benchmark uses pointer chasing to measure actual memory access times
- Latency measurements help identify NUMA-related performance impacts
