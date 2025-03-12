# Projects

## 1. [OpenACC_Ftn_Unified](https://github.com/PourroyJean/HPC_Playground/tree/master/OpenACC_Ftn_Unified)  
This Fortran program benchmarks GPU unified memory performance (such as MI300A) using OpenACC directives. It performs element-wise multiplication of large square matrices to measure execution time, memory bandwidth (GB/s), and computational throughput (GFLOPS).

## 2. [Check_Binding](./Check_Binding)
Provides a simple check_binding.sh script demonstrating how to control CPU affinity, thread placement, and MPI distribution on Slurm-managed HPC clusters

## 3. [Connectivity check](./Connectivity_check)
Checker that regularly tests the accessibility of multiple hosts over SSH via a specified proxy. If any hosts become unreachable, the script will send email alerts and log the results.

## 4. [Cray Bind Analyzer](./CrayBindAnalyzer)
Checker that regularly tests the accessibility of multiple hosts over SSH via a specified proxy. If any hosts become unreachable, the script will send email alerts and log the results.



---------
---------
---------

#### Synchronizing internal and external gitHub repositories

This repository hosts a script (`auto_sync.sh`) that automatically synchronizes changes between the internal HPE GitHub and its public GitHub counterpart.
