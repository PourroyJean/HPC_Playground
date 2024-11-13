# GPU Unified Memory Benchmark with OpenACC

This Fortran program benchmarks GPU unified memory performance using OpenACC directives. It performs element-wise multiplication of large square matrices to measure execution time, memory bandwidth (GB/s), and computational throughput (GFLOPS).

## Key Features

- **GPU Acceleration**: Utilizes OpenACC to offload computations to the GPU with unified memory management.
- **Scalable Testing**: Evaluates performance across various matrix sizes specified in the `ARRAY_SIZES` array.
- **Performance Metrics**: Calculates and reports execution time, bandwidth, and GFLOPS for each matrix size.
- **Result Verification**: Ensures computational accuracy by verifying results after the first iteration.
- **Summary Output**: Generates a concise table summarizing performance metrics for easy analysis.

## Prerequisites

- Fortran compiler with OpenACC support (e.g., NVIDIA HPC SDK, PGI)
- Compatible GPU that supports Unified Memory and OpenACC
- OpenACC runtime libraries installed

## Customization

Modify the ARRAY_SIZES parameter in the code to test different matrix sizes:
 ``` 
 integer(kind=8), parameter :: ARRAY_SIZES(8) = [1024_8, 2048_8, 4096_8, 8192_8, 12288_8, 14336_8, 15360_8, 16384_8] 
 ```


### Compilation

Compile the program with OpenACC flags enabled. Here's an example using the NVIDIA HPC SDK compiler:

- module
```bash
module load PrgEnv-cray/8.5.0 rocm/6.2.1 craype-accel-amd-gfx942

module list
Currently Loaded Modules:
  1) craype-x86-trento   3) craype-network-ofi       5) cce/18.0.0      7) cray-dsmml/0.3.0    9) cray-libsci/24.07.0  11) rocm/6.2.1
  2) libfabric/1.20.1    4) perftools-base/24.07.0   6) craype/2.7.32   8) cray-mpich/8.1.30  10) PrgEnv-cray/8.5.0    12) craype-accel-amd-gfx942 
```
- compilation
```
ftn -hacc  offload_openacc.f90 -o ./offload_openacc
```


### Execution

- With unified memory
```
CRAY_ACC_USE_UNIFIED_MEM=1 HSA_XNACK=1 CRAY_ACC_DEBUG=0 ./offload_openacc
```


### Sample output

- Mi300A without unified memory
```
 ------------------------------------------------------------
 Matrix Size (GB) | Bandwidth (GB/s) | GFLOPS | Avg Time (s)
 ------------------------------------------------------------
          0.02 |           34.42 |    1.54 |    0.000685
          0.09 |           37.27 |    1.67 |    0.002522
          0.38 |           38.01 |    1.70 |    0.009877
          1.50 |           35.82 |    1.60 |    0.041982
          3.38 |           35.62 |    1.59 |    0.095468
          4.59 |           35.08 |    1.57 |    0.131342
          5.27 |           34.18 |    1.53 |    0.154553
          6.00 |           34.84 |    1.56 |    0.172746
```

- Mi300A with unified memory
```
  Summary Table
 ------------------------------------------------------------
 Matrix Size (GB) | Bandwidth (GB/s) | GFLOPS | Avg Time (s)
 ------------------------------------------------------------
          0.02 |          276.15 |   12.35 |    0.000119
          0.09 |          691.95 |   30.96 |    0.000192
          0.38 |          556.59 |   24.90 |    0.000714
          1.50 |          466.09 |   20.85 |    0.003381
          3.38 |          304.94 |   13.64 |    0.011389
          4.59 |          274.37 |   12.28 |    0.017187
          5.27 |          288.31 |   12.90 |    0.018734
          6.00 |          264.37 |   11.83 |    0.023753
```