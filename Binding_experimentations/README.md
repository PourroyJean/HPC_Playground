# NUMA Memory Allocator

A tool to demonstrate and test NUMA memory allocation in MPI applications. This tool helps understand how memory is allocated across NUMA nodes and how it relates to CPU affinity.

## Features

- Memory allocation with external NUMA control via `numactl --membind`
- Shows CPU affinity and NUMA node information for each MPI process
- Displays memory allocation statistics using `numastat`
- Provides detailed information about CPU cores and their NUMA node assignments
- Memory latency benchmark using pointer-chasing technique:
  - Measures memory access latency in nanoseconds
  - Uses randomized pointer chasing to prevent hardware prefetching
  - Reports per-rank memory latency statistics
  - Helps identify NUMA-related performance impacts

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
srun --nodes 1 --ntasks 56 --distribution=block:block --hint=multithread --cpu-bind=cores ./numa_allocator <size_in_mb>
```

With external NUMA control:
```bash
numactl --membind=<node_number> srun --nodes 1 --ntasks 56 --distribution=block:block --hint=multithread --cpu-bind=cores ./numa_allocator <size_in_mb>
```

With serial execution mode:
```bash
numactl --membind=<node_number> srun --nodes 1 --ntasks 56 --distribution=block:block --hint=multithread --cpu-bind=cores ./numa_allocator --serial <size_in_mb>
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

- Number of iterations: 1,000,000 (configurable via `LATENCY_ITERATIONS`)
- Warm-up iterations: 10,000 (configurable via `WARMUP_ITERATIONS`)
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
=== Debug Information ===
MPI Configuration:
  Number of ranks: 56
  Command line arguments:
    argv[0] = ./numa_allocator
    argv[1] = --serial
    argv[2] = 512

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
|  000  | 1,65    |   0  | 0x48ca40       | 512          |   3   | kB=4        | 126.39     |
|  001  | 2,66    |   0  | 0x48a2d0       | 512          |   3   | kB=4        | 128.32     |
...
|  055  | 63,127  |   3  | 0x48a2d0       | 512          |   3   | kB=4        | 112.08     |

Per-node process memory usage (in MBs) for PID 47463 (numa_allocator)
                           Node 0          Node 1          Node 2          Node 3           Total
                  --------------- --------------- --------------- --------------- ---------------
Huge                         0.00            0.00            0.00            0.00            0.00
Heap                         0.00            0.00            0.00          514.50          514.50
Stack                        0.00            0.00            0.00            0.02            0.02
Private                      6.22            0.00            0.00            9.57           15.79
----------------  --------------- --------------- --------------- --------------- ---------------
Total                        6.22            0.00            0.00          524.10          530.32
```

### Analysis of Results

The example shows several important characteristics:

1. **NUMA Node Distribution**:
   - The system has 4 NUMA nodes
   - Each NUMA node has 16 physical cores (32 logical cores with hyperthreading)
   - Memory is bound to NUMA node 3 using `numactl --membind=3`

2. **Memory Latency Pattern**:
   - Local access (NUMA node 3): ~107-112 ns
   - Remote access (NUMA node 2): ~113-117 ns
   - Remote access (NUMA node 1): ~120-125 ns
   - Remote access (NUMA node 0): ~126-132 ns
   - Shows clear NUMA locality impact on memory access latency

3. **Memory Allocation**:
   - Total memory allocated: 512 MB per rank
   - Memory is successfully bound to NUMA node 3
   - Small amounts of memory are allocated on other nodes for system overhead

## Notes

- Memory allocation is controlled externally using `numactl --membind`
- Memory is touched after allocation to ensure it's actually allocated
- The last MPI process shows detailed NUMA statistics using `numastat`
- CPU affinity information is obtained using hwloc
- The memory latency benchmark uses pointer chasing to measure actual memory access times
- Latency measurements help identify NUMA-related performance impacts