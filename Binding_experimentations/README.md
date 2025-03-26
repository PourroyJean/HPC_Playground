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
|  002  | 3,67    |   0  | 0x48a2d0       | 512          |   3   | kB=4        | 126.38     |
|  003  | 4,68    |   0  | 0x48a2d0       | 512          |   3   | kB=4        | 130.27     |
|  004  | 5,69    |   0  | 0x48a2d0       | 512          |   3   | kB=4        | 129.34     |
|  005  | 6,70    |   0  | 0x48a2d0       | 512          |   3   | kB=4        | 129.53     |
|  006  | 7,71    |   0  | 0x48a2d0       | 512          |   3   | kB=4        | 131.26     |
|  007  | 9,73    |   0  | 0x48a2d0       | 512          |   3   | kB=4        | 127.29     |
|  008  | 10,74   |   0  | 0x48a2d0       | 512          |   3   | kB=4        | 127.00     |
|  009  | 11,75   |   0  | 0x48a2d0       | 512          |   3   | kB=4        | 126.25     |
|  010  | 12,76   |   0  | 0x48a2d0       | 512          |   3   | kB=4        | 129.12     |
|  011  | 13,77   |   0  | 0x48a2d0       | 512          |   3   | kB=4        | 128.49     |
|  012  | 14,78   |   0  | 0x48a2d0       | 512          |   3   | kB=4        | 131.50     |
|  013  | 15,79   |   0  | 0x48a2d0       | 512          |   3   | kB=4        | 132.10     |
|  014  | 17,81   |   1  | 0x48a2d0       | 512          |   3   | kB=4        | 120.31     |
|  015  | 18,82   |   1  | 0x48a2d0       | 512          |   3   | kB=4        | 122.05     |
|  016  | 19,83   |   1  | 0x48a2d0       | 512          |   3   | kB=4        | 121.79     |
|  017  | 20,84   |   1  | 0x48a2d0       | 512          |   3   | kB=4        | 123.23     |
|  018  | 21,85   |   1  | 0x48a2d0       | 512          |   3   | kB=4        | 123.43     |
|  019  | 22,86   |   1  | 0x48a2d0       | 512          |   3   | kB=4        | 124.46     |
|  020  | 23,87   |   1  | 0x48a2d0       | 512          |   3   | kB=4        | 124.41     |
|  021  | 25,89   |   1  | 0x48a2d0       | 512          |   3   | kB=4        | 120.85     |
|  022  | 26,90   |   1  | 0x48a2d0       | 512          |   3   | kB=4        | 122.31     |
|  023  | 27,91   |   1  | 0x48a2d0       | 512          |   3   | kB=4        | 122.44     |
|  024  | 28,92   |   1  | 0x48a2d0       | 512          |   3   | kB=4        | 123.66     |
|  025  | 29,93   |   1  | 0x48a2d0       | 512          |   3   | kB=4        | 123.51     |
|  026  | 30,94   |   1  | 0x48a2d0       | 512          |   3   | kB=4        | 125.16     |
|  027  | 31,95   |   1  | 0x48a2d0       | 512          |   3   | kB=4        | 125.07     |
|  028  | 33,97   |   2  | 0x48a2d0       | 512          |   3   | kB=4        | 113.16     |
|  029  | 34,98   |   2  | 0x48a2d0       | 512          |   3   | kB=4        | 114.81     |
|  030  | 35,99   |   2  | 0x48a2d0       | 512          |   3   | kB=4        | 114.53     |
|  031  | 36,100  |   2  | 0x48a2d0       | 512          |   3   | kB=4        | 115.61     |
|  032  | 37,101  |   2  | 0x48a2d0       | 512          |   3   | kB=4        | 115.98     |
|  033  | 38,102  |   2  | 0x48a2d0       | 512          |   3   | kB=4        | 117.26     |
|  034  | 39,103  |   2  | 0x48a2d0       | 512          |   3   | kB=4        | 117.54     |
|  035  | 41,105  |   2  | 0x48a2d0       | 512          |   3   | kB=4        | 113.60     |
|  036  | 42,106  |   2  | 0x48a2d0       | 512          |   3   | kB=4        | 115.09     |
|  037  | 43,107  |   2  | 0x48a2d0       | 512          |   3   | kB=4        | 114.88     |
|  038  | 44,108  |   2  | 0x48a2d0       | 512          |   3   | kB=4        | 116.47     |
|  039  | 45,109  |   2  | 0x48a2d0       | 512          |   3   | kB=4        | 116.55     |
|  040  | 46,110  |   2  | 0x48a2d0       | 512          |   3   | kB=4        | 117.70     |
|  041  | 47,111  |   2  | 0x48a2d0       | 512          |   3   | kB=4        | 117.76     |
|  042  | 49,113  |   3  | 0x48a2d0       | 512          |   3   | kB=4        | 107.06     |
|  043  | 50,114  |   3  | 0x48a2d0       | 512          |   3   | kB=4        | 108.70     |
|  044  | 51,115  |   3  | 0x48a2d0       | 512          |   3   | kB=4        | 108.87     |
|  045  | 52,116  |   3  | 0x48a2d0       | 512          |   3   | kB=4        | 110.40     |
|  046  | 53,117  |   3  | 0x48a2d0       | 512          |   3   | kB=4        | 109.97     |
|  047  | 54,118  |   3  | 0x48a2d0       | 512          |   3   | kB=4        | 112.07     |
|  048  | 55,119  |   3  | 0x48a2d0       | 512          |   3   | kB=4        | 112.09     |
|  049  | 57,121  |   3  | 0x48a2d0       | 512          |   3   | kB=4        | 107.99     |
|  050  | 58,122  |   3  | 0x48a2d0       | 512          |   3   | kB=4        | 109.24     |
|  051  | 59,123  |   3  | 0x48a2d0       | 512          |   3   | kB=4        | 109.51     |
|  052  | 60,124  |   3  | 0x48a2d0       | 512          |   3   | kB=4        | 110.45     |
|  053  | 61,125  |   3  | 0x48a2d0       | 512          |   3   | kB=4        | 110.53     |
|  054  | 62,126  |   3  | 0x48a2d0       | 512          |   3   | kB=4        | 111.87     |
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
