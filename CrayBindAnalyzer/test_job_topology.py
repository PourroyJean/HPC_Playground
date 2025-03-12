#!/usr/bin/env python3

from mpich_parser import MPICHParser
from hpc_topology import print_run

def main():
    """Test script to display job topology with selected NICs."""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python test_job_topology.py <input_file>")
        sys.exit(1)
    
    filename = sys.argv[1]
    
    # Set debug mode for more verbose output
    MPICHParser.DEBUG = True
    
    # Parse the file
    parser = MPICHParser(filename)
    cluster, job = parser.parse()
    
    # Print summary of MPI tasks and NICs
    print("\n === MPI Task and Selected NIC Summary ===")
    for task in job.mpi_tasks:
        print(f"MPI Task {task.id} on {task.node.name}: {len(task.logical_cpus)} CPUs")
        if task.selected_nics:
            print(f"  Selected NICs:")
            for nic in task.selected_nics:
                print(f"    - {nic.id} on NUMA {nic.numa_domain.id}")
        else:
            print("  No selected NICs")
    
    # Print detailed topology
    print("\n === Job Topology Tree ===")
    print_run(cluster, job)

if __name__ == "__main__":
    main() 