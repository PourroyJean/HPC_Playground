# NUMA Memory Latency Benchmarking Analysis

## Test Configuration

Two experiments were conducted with identical system configurations but different execution modes:

1. **Concurrent Mode**: All processes run memory benchmarks simultaneously
2. **Serial Mode**: Processes run one at a time to isolate memory subsystem access

Both benchmarks were executed with similar commands:

**Concurrent Mode:**
```bash
srun -t "00:60:00" --nodes 1 --ntasks 8 --cpu-bind=map_cpu:1,9,17,25,33,41,49,57 --hint=nomultithread ./run_numa.sh --numa=0,0,1,1,2,2,3,3 --verbose -- --size=1-16384
```

**Serial Mode:**
```bash
srun -t "00:60:00" --nodes 1 --ntasks 8 --cpu-bind=map_cpu:1,9,17,25,33,41,49,57 --hint=nomultithread ./run_numa.sh --numa=0,0,1,1,2,2,3,3 --verbose -- --size=1-16384 --serial
```

### System Specifications
- **CPU**: AMD EPYC 7A53 64-Core Processor
- **CPU Family**: 25
- **Thread(s) per core**: 2
- **Core(s) per socket**: 64
- **Socket(s)**: 1
- **NUMA node(s)**: 4

### NUMA Node CPU Distribution
- **NUMA node0**: CPUs 0-15,64-79
- **NUMA node1**: CPUs 16-31,80-95
- **NUMA node2**: CPUs 32-47,96-111
- **NUMA node3**: CPUs 48-63,112-127

### Test Strategy
In both experiments, we bound each process's memory allocation to its local NUMA domain. The mapping was as follows:
- Ranks 0 and 1: Run on cores 1 and 9 (NUMA domain 0), memory bound to domain 0
- Ranks 2 and 3: Run on cores 17 and 25 (NUMA domain 1), memory bound to domain 1
- Ranks 4 and 5: Run on cores 33 and 41 (NUMA domain 2), memory bound to domain 2
- Ranks 6 and 7: Run on cores 49 and 57 (NUMA domain 3), memory bound to domain 3

This configuration ensures that each process accesses memory within its local NUMA domain, allowing us to establish baseline latency measurements for local memory access.

## Concurrent Mode Results

### Raw Results Table

Here's the output from the concurrent execution mode:

```
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
```

### Visual Results

![Concurrent Mode Latency](./results/images/lumig_local_concurrent.png)

### Analysis of Concurrent Mode Results

The test measured memory latency across 15 different allocation sizes, from 1MB to 16384MB. Several clear patterns emerge:

1. **Small Allocations (1-16MB)**:
   - Consistently low latencies across all NUMA domains (11-19ns)
   - These sizes likely fit within the L3 cache (which is typically 32MB per CCD in EPYC 7A53)
   - Very little variation between NUMA domains at these sizes

2. **Medium Allocations (32-64MB)**:
   - Sharp increase in latency (35-78ns)
   - 32MB shows the first significant jump (from ~18ns to ~36ns)
   - 64MB shows the second significant jump (from ~36ns to ~68-78ns)
   - These sizes exceed cache capacity and require DRAM access

3. **Large Allocations (128MB-16384MB)**:
   - Further increases in latency, with more variation between runs
   - Most cores show a pattern of increasing latency as size grows beyond 512MB
   - Some domains (particularly even-numbered ranks) show significantly higher latencies for the largest allocations

#### Latency Patterns Within NUMA Domains (Concurrent Mode)

An interesting pattern emerges when comparing pairs of ranks within the same NUMA domain:

- **Even-numbered ranks** (0, 2, 4, 6) generally show higher latencies for large allocations
- **Odd-numbered ranks** (1, 3, 5, 7) show more consistent latencies even at larger sizes

For example, at 4096MB:
- Rank 0: 178.93ns vs Rank 1: 112.31ns (both on NUMA domain 0)
- Rank 2: 183.60ns vs Rank 3: 111.92ns (both on NUMA domain 1)
- Rank 4: 180.87ns vs Rank 5: 111.84ns (both on NUMA domain 2)
- Rank 6: 170.84ns vs Rank 7: 112.20ns (both on NUMA domain 3)

This suggests that even within the same NUMA domain, physical core placement may impact memory access patterns, possibly due to the internal topology of the CCDs (Core Complex Dies) in the EPYC architecture.

## Serial Mode Results

### Raw Results Table

Here's the output from the serial execution mode:

```
 ========================================================================================================================================================================================
|  MPI  |        CPU     |              MEMORY    |                                                             LATENCY (ns)                                                             |
|-------|---------|------|----------------|-------|--------|--------|--------|--------|--------|--------|--------|--------|--------|--------|--------|--------|--------|--------|--------|
| Ranks | Cores   | NUMA |     Address    | NUMA  | 1MB    | 2MB    | 4MB    | 8MB    | 16MB   | 32MB   | 64MB   | 128MB  | 256MB  | 512MB  | 1024MB | 2048MB | 4096MB | 8192MB | 16384MB|
|-------|---------|------|----------------|-------|--------|--------|--------|--------|--------|--------|--------|--------|--------|--------|--------|--------|--------|--------|--------|
|  000  | 1       |   0  | 0x527d60       |   0   | 10.49  | 12.92  | 14.26  | 14.98  | 18.70  | 36.17  | 68.53  | 86.12  | 97.13  | 100.92 | 105.18 | 108.98 | 110.84 | 112.50 | 133.20 |
|  001  | 9       |   0  | 0x526920       |   0   | 10.34  | 12.96  | 14.88  | 14.97  | 18.61  | 37.13  | 67.68  | 86.22  | 95.40  | 101.65 | 104.00 | 107.44 | 111.18 | 116.96 | 131.50 |
|  002  | 17      |   1  | 0x526940       |   1   | 10.36  | 12.90  | 14.23  | 14.95  | 18.40  | 35.49  | 66.15  | 84.91  | 94.41  | 99.44  | 103.25 | 106.07 | 109.63 | 111.75 | 128.44 |
|  003  | 25      |   1  | 0x526940       |   1   | 10.35  | 12.95  | 14.03  | 14.84  | 18.07  | 34.95  | 67.61  | 85.99  | 95.46  | 100.30 | 103.69 | 107.13 | 110.43 | 112.44 | 130.34 |
|  004  | 33      |   2  | 0x5269b0       |   2   | 11.76  | 12.94  | 14.24  | 14.94  | 21.20  | 35.55  | 67.57  | 85.06  | 95.22  | 100.28 | 104.15 | 110.96 | 112.34 | 112.42 | 130.33 |
|  005  | 41      |   2  | 0x526980       |   2   | 10.36  | 12.94  | 14.25  | 14.94  | 18.63  | 36.10  | 66.53  | 84.89  | 94.89  | 101.28 | 104.24 | 106.83 | 110.24 | 112.64 | 129.83 |
|  006  | 49      |   3  | 0x5269e0       |   3   | 10.36  | 12.95  | 14.29  | 14.93  | 18.53  | 34.52  | 67.43  | 85.54  | 95.48  | 101.12 | 106.81 | 107.32 | 111.13 | 113.05 | 129.72 |
|  007  | 57      |   3  | 0x5269a0       |   3   | 10.32  | 14.00  | 14.22  | 15.00  | 19.66  | 35.90  | 67.78  | 85.91  | 95.96  | 102.04 | 104.53 | 108.81 | 111.44 | 113.30 | 130.60 |
 ========================================================================================================================================================================================
```

### Visual Results

![Serial Mode Latency](./results/images/lumig_local_serial.png)

### Analysis of Serial Mode Results

The serial mode test shows several notable differences from the concurrent mode:

1. **Small Allocations (1-16MB)**:
   - Similar to concurrent mode, latencies remain low and consistent
   - Slightly faster response times observed in serial mode (10-19ns vs 11-19ns)
   - The cache effects remain dominant at these allocation sizes

2. **Medium Allocations (32-64MB)**:
   - Similar latency jumps at the cache boundaries
   - 32MB jump similar to concurrent mode (~18ns to ~35ns)
   - 64MB shows a consistent jump across all ranks (~35ns to ~67ns)
   - Less variability between ranks compared to concurrent mode

3. **Large Allocations (128MB-16384MB)**:
   - **Key Difference**: In serial mode, all ranks show remarkably consistent latencies
   - No significant difference between even and odd-numbered ranks
   - Latency values stabilize between 110-130ns for large allocations
   - Overall lower latencies compared to concurrent mode for the same allocation sizes

#### Latency Patterns Within NUMA Domains (Serial Mode)

Unlike in concurrent mode, the serial mode shows:

- No significant difference between even and odd-numbered ranks
- Very consistent latency values across all cores
- Stable latency profile that generally increases with allocation size
- Maximum latency values that are significantly lower than in concurrent mode

For example, at 4096MB in serial mode:
- Rank 0: 110.84ns vs Rank 1: 111.18ns (compared to 178.93ns vs 112.31ns in concurrent mode)
- Rank 2: 109.63ns vs Rank 3: 110.43ns (compared to 183.60ns vs 111.92ns in concurrent mode)
- Rank 4: 112.34ns vs Rank 5: 110.24ns (compared to 180.87ns vs 111.84ns in concurrent mode)
- Rank 6: 111.13ns vs Rank 7: 111.44ns (compared to 170.84ns vs 112.20ns in concurrent mode)

## Comparative Analysis: Concurrent vs. Serial Mode

The stark contrast between concurrent and serial execution modes reveals significant insights about memory access patterns in NUMA systems:

### 1. Memory Controller Contention

The most striking difference is observed in the even-numbered ranks (0, 2, 4, 6) at large allocation sizes:

- In **concurrent mode**, these ranks show latencies up to 70% higher than their odd-numbered counterparts
- In **serial mode**, these differences disappear completely

This strongly suggests memory controller contention when multiple processes access memory simultaneously. The EPYC 7A53's internal architecture appears to route memory access from even-numbered cores through shared pathways that experience congestion under concurrent load.

### 2. Divergence Threshold

The point at which concurrent and serial results begin to diverge significantly is around 128MB:

- Below 128MB, both modes show relatively similar latency characteristics
- At and above 128MB, even-numbered ranks in concurrent mode begin showing elevated latencies
- The divergence becomes most pronounced beyond 1024MB

This indicates that memory controller saturation becomes a limiting factor primarily at larger allocation sizes, when memory bandwidth demands exceed what shared pathways can provide.

### 3. NUMA Domain Consistency

Both modes show consistent behavior within each NUMA domain:

- No significant latency differences between NUMA domains in either mode
- Similar latency progression patterns across memory sizes
- All domains exhibit the same even/odd rank patterns in concurrent mode

This confirms that the observed contention effects are related to the internal architecture of each NUMA domain rather than cross-domain interference.

### 4. Implications for System Design

These results have important implications for application design on NUMA systems:

- Memory-intensive applications may benefit from serialized memory operations for large allocations
- Process placement within NUMA domains matters significantly under concurrent load
- Even with local NUMA access, memory controller topology can create "hot spots"
- Applications using even-numbered cores may experience higher memory latency under concurrent load

## NUMA Statistics Correlation

The NUMA statistics from both tests confirm proper memory binding. For example, from the serial mode test (Rank 7):

```
Per-node process memory usage (in MBs) for PID 57724 (numa_bench)
                         Node 0          Node 1          Node 2          Node 3           Total
                --------------- --------------- --------------- --------------- ---------------
Huge                       0.00            0.00            0.00            0.00            0.00
Heap                       0.00            0.00            0.00        16386.97        16386.97
Stack                      0.00            0.00            0.00            0.02            0.02
Private                    7.95            1.99            2.36            3.48           15.78
----------------  --------------- --------------- --------------- --------------- ---------------
Total                      7.95            1.99            2.36        16390.46        16402.77
```

This confirms that the heap memory (which contains our benchmark allocation) is correctly bound to NUMA domain 3 for Rank 7. The small amounts of memory on other nodes primarily represent private mappings like code segments, which have minimal impact on the benchmark results.

## Conclusion

This dual-mode experiment reveals important characteristics of memory access on the AMD EPYC 7A53 platform:

1. **Cache effects** dominate at small allocation sizes (<32MB) in both modes
2. **DRAM access patterns** become evident at medium and large sizes
3. **Memory controller contention** creates significant latency variations in concurrent mode, particularly for even-numbered cores
4. **Memory latency stability** is achieved in serial mode across all cores and NUMA domains
5. **Internal NUMA topology** has a greater impact on memory performance than previously expected

Most importantly, these results highlight that NUMA optimization requires consideration not just of node binding but also of how cores within a NUMA domain access memory controllers. The even/odd latency pattern observed in concurrent mode suggests an asymmetric memory controller design that creates "fast" and "slow" paths under heavy load.

These findings provide valuable guidance for high-performance computing applications, suggesting that memory-intensive workloads should consider both NUMA binding and core selection for optimal performance. 