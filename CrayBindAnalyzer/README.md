# HPC Topology Parser

A Python tool for parsing and visualizing high-performance computing (HPC) cluster topologies and job allocation information from MPICH output files.

## Overview

This parser extracts and organizes information about hardware components (nodes, NUMA domains, CPU cores, logical CPUs, NICs) and software components (MPI tasks, OpenMP threads) from MPICH output files. It provides a comprehensive view of the relationship between hardware resources and their allocation to software processes in an HPC environment.

## Features

- **Hardware Topology Extraction**:
  - Extract node information and their relationships
  - Parse NUMA domains and their CPU assignments
  - Identify physical cores and logical CPUs
  - Map Network Interface Cards (NICs) to their NUMA domains

- **Job Allocation Analysis**:
  - Capture MPI task placement across nodes
  - Track OpenMP thread affinity to specific CPUs
  - Map the relationship between tasks and threads

- **Visualization**:
  - Tree-view representation of hardware topology
  - Hierarchical display of job allocation
  - Compact CPU range representation
  - Comprehensive job summary

## Installation

No special installation is required beyond standard Python 3. The tool uses only built-in Python libraries.

## Usage

```bash
# Basic usage
python mpich_parser.py <input_file>

# With debug information
python mpich_parser.py <input_file> --debug
```

## Input File Format

The parser is designed to work with MPICH output files that contain information about:

- Node assignments for MPI ranks
- NUMA domain CPU assignments
- NIC placement and addressing
- OpenMP thread CPU affinity

## Output Example

The parser produces a structured output that includes:

### Cluster Topology

```
Cluster (2 nodes)
  ├── Node: nid005186 (4 NUMA domains - 64 cores, 128 CPUs)
  │   ├── NUMA: 0 (16 cores, 32 CPUs)
  │   │   ├── CPUs: 0-15, 64-79
  │   │   └── NICs: cxi2
  │   ├── NUMA: 1 (16 cores, 32 CPUs)
  │   │   ├── CPUs: 16-31, 80-95
  │   │   └── NICs: cxi1
  ...
```

### Job Allocation

```
Job: job_from_run_check-9883400.txt (ID: 9883400, 4 MPI tasks)
  ├── Node: nid005186 (4 NUMA domains - 64 cores, 128 CPUs)
  │   ├── MPI Rank 0 (4 CPUs: 1-2, 65-66)
  │   │   ├── 2 OpenMP threads
  │   │   ├── Thread 0: 1, 65
  │   │   └── Thread 1: 2, 66
  ...
```

### Job Summary

```
=============== Job Summary ===============
Job ID               : 9883400
Nodes Used           : 2
MPI Ranks            : 4  (2 per node)
Threads per Rank     : 2
Total CPUs Allocated : 16  (4 CPUs per rank)
Total CPUs Available : 256
NUMA Domains per Node: 4
Cores per Node       : 64
```

## Project Structure

- `mpich_parser.py`: Main parser script that reads and processes the input files
- `hpc_topology.py`: Data model definitions and display functions for the hardware and software components

## Data Model

The project uses a comprehensive object model to represent hardware and software components:

- **Hardware Components**:
  - `Cluster`: Container for nodes in the cluster
  - `Node`: Physical compute server with NUMA domains
  - `NUMADomain`: NUMA region containing cores and NICs
  - `PhysicalCore`: CPU core containing logical CPUs
  - `LogicalCPU`: Individual hardware thread (CPU)
  - `NIC`: Network Interface Card

- **Software Components**:
  - `Job`: Container for MPI tasks
  - `MPITask`: Individual MPI process with OpenMP threads
  - `OpenMPThread`: Individual thread within an MPI task

## Use Cases

This tool is useful for:

1. **Understanding Hardware Topology**: Visualize the structure of HPC clusters
2. **Analyzing Job Placement**: See how MPI tasks and threads are distributed
3. **Performance Debugging**: Identify potential NUMA or CPU affinity issues
4. **Resource Utilization**: Compare allocated vs. available CPUs

## Future Enhancements

Potential future improvements:
- Support for additional input formats (Slurm, PBS, etc.)
- Export functionality to JSON or CSV formats
- Interactive visualization options
- Statistical analysis of job placement efficiency

## License

This project is released under the MIT License. 