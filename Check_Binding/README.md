# HPC CPU Binding Demo

CPU binding ensures that MPI tasks and OpenMP threads are optimally placed on available cores, improving performance by enhancing data locality and minimizing overhead.

This repository provides a simple [check_binding.sh](./check_binding.sh) script demonstrating how to control CPU affinity, thread placement, and MPI distribution on Slurm-managed HPC clusters (tested on an HPE Supercomputer).

## Overview

Proper CPU binding and thread placement can significantly improve performance by:
- Utilizing Slurm options (`--distribution`, `--cpu-bind`) to control MPI rank placement.
- Configuring OpenMP environment variables (`OMP_PROC_BIND`, `OMP_PLACES`) for thread placement.
- Visualizing CPU mapping using the `xthi` utility.

## Installing xthi

To install `xthi`:

```bash
git clone https://github.com/ARCHER2-HPC/xthi
cd xthi/src
make
# cp xthi_mpi xthi_mpi_mp "$HOME/.local/bin/"
```


On HPE systems, the standard modules are generally sufficient. Just ensure that MPI is loaded before building and running xthi.
If necessary, add the compiled binary’s location to your PATH.


After installing, adapt the `EXE` value in [check_binding.sh](./check_binding.sh) to point to the binary created
## Usage

1. Adjust parameters in [check_binding.sh](./check_binding.sh) as needed (e.g., project name, partition).
2. Submit the job:
   ```bash
   sbatch check_binding.sh
   ```


# Result exemple
Below is an example of the output when using specific OpenMP settings and distributing MPI ranks across nodes on Lumi-C

```
Node summary for    3 nodes:
Node    0, hostname nid001641, mpi   4, omp   2, executable xthi_mpi_mp
Node    1, hostname nid001642, mpi   3, omp   2, executable xthi_mpi_mp
Node    2, hostname nid001643, mpi   3, omp   2, executable xthi_mpi_mp
MPI summary: 10 ranks 
 ________________________________________________________________
| HOSTNAME   | MPI TASK | THREAD |       AFFINITY      |  TOTAL  |
|----------------------------------------------------------------|
|  nid001641 |   rank 0 |      0 | 0                   |       1 |
| ---------- |    ,,    |      1 | 0                   |       1 |
| ---------- |   rank 1 |      0 | 128                 |       1 |
| ---------- |    ,,    |      1 | 128                 |       1 |
| ---------- |   rank 2 |      0 | 1                   |       1 |
| ---------- |    ,,    |      1 | 1                   |       1 |
| ---------- |   rank 3 |      0 | 129                 |       1 |
| ---------- |    ,,    |      1 | 129                 |       1 |
|  nid001642 |   rank 4 |      0 | 0                   |       1 |
| ---------- |    ,,    |      1 | 0                   |       1 |
| ---------- |   rank 5 |      0 | 128                 |       1 |
| ---------- |    ,,    |      1 | 128                 |       1 |
| ---------- |   rank 6 |      0 | 1                   |       1 |
| ---------- |    ,,    |      1 | 1                   |       1 |
|  nid001643 |   rank 7 |      0 | 0                   |       1 |
| ---------- |    ,,    |      1 | 0                   |       1 |
| ---------- |   rank 8 |      0 | 128                 |       1 |
| ---------- |    ,,    |      1 | 128                 |       1 |
| ---------- |   rank 9 |      0 | 1                   |       1 |
| ---------- |    ,,    |      1 | 1                   |       1 |
|________________________________________________________________|
--> 10 MPI ranks with 2 threads each (total number of threads: 20)
```
