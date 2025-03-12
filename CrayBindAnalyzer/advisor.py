#!/usr/bin/env python3

import sys
import os
from collections import defaultdict
from mpich_parser import MPICHParser
from hpc_topology import format_id_ranges, format_id_ranges_as_list

def get_total_cores_per_node(cluster):
    """Calculate the total number of physical cores per node."""
    if not cluster.nodes:
        return 0
    # Assuming homogeneous nodes
    return cluster.nodes[0].get_core_count()

def get_threads_per_core(cluster):
    """Determine if hyperthreading is enabled and how many threads per core."""
    if not cluster.nodes or not cluster.nodes[0].numa_domains or not cluster.nodes[0].numa_domains[0].cores:
        return 1
    
    # Check if there are hyperthreads (assuming homogeneous cores)
    first_core = cluster.nodes[0].numa_domains[0].cores[0]
    return len(first_core.logical_cpus)

def count_unique_nics(cluster):
    """Count the number of unique NICs across all nodes."""
    unique_nics = set()
    for node in cluster.nodes:
        for numa in node.numa_domains:
            for nic in numa.nics:
                unique_nics.add(nic.id)
    return len(unique_nics)

def get_task_cores(task):
    """Get a formatted list of cores used by an MPI task."""
    cpu_ids = sorted([cpu.id for cpu in task.logical_cpus])
    return format_id_ranges(cpu_ids)

def get_task_numa_domains(task):
    """Get a list of NUMA domains used by an MPI task."""
    numa_domains = set()
    for cpu in task.logical_cpus:
        numa_domains.add(cpu.core.numa_domain.id)
    
    # No warning here anymore - we only want warnings for NIC-core NUMA mismatches
    return ", ".join(map(str, sorted(numa_domains)))

def get_cores_count(task):
    """Get the count of logical CPUs used by an MPI task."""
    return len(task.logical_cpus)

def check_nic_numa_mismatch(task, nic):
    """Check if task's selected NIC is on different NUMA domain than its cores.
    
    This function identifies NUMA domain mismatches between:
    1. The NUMA domain(s) where the MPI task's cores are located
    2. The NUMA domain where the selected NIC is physically attached
    
    A mismatch means the task must communicate across NUMA domains to reach its NIC,
    which can result in higher latency and reduced performance.
    
    Returns:
        A warning string if there's a mismatch, otherwise an empty string.
    """
    if not nic:
        return ""
        
    # Get all NUMA domains used by this task's CPUs
    task_numa_domains = set()
    for cpu in task.logical_cpus:
        task_numa_domains.add(cpu.core.numa_domain.id)
    
    # Check if the NIC's NUMA domain matches any of the task's NUMA domains
    nic_numa = nic.numa_domain.id
    if nic_numa not in task_numa_domains:
        return " *"  # Using simple ASCII character instead of emoji
    
    return ""

def truncate_core_list(core_list_str):
    """Truncate a core list string if it exceeds a certain length."""
    max_length = 25  # Increased from 10 to show more of the core list
    if len(core_list_str) > max_length:
        # Truncate the string and add "..."
        return core_list_str[:max_length-3] + "..."
    return core_list_str

def generate_table(filename):
    """Generate a tabular view of the MPI job topology."""
    # Parse the input file
    parser = MPICHParser(filename)
    cluster, job = parser.parse()
    
    # Get summary information
    cores_per_node = get_total_cores_per_node(cluster)
    threads_per_core = get_threads_per_core(cluster)
    nic_count = count_unique_nics(cluster)
    
    # Column definitions with reasonable widths
    columns = [
        {"name": "Node name", "min_width": 10, "max_width": 15},
        {"name": "MPI ranks", "min_width": 6, "max_width": 10},
        {"name": "Cores (total)", "min_width": 25, "max_width": 31},
        {"name": "Core NUMA", "min_width": 9, "max_width": 12},
        {"name": "NIC ID", "min_width": 12, "max_width": 12},
        {"name": "NIC NUMA", "min_width": 8, "max_width": 10}
    ]
    
    # Prepare data rows
    rows = []
    
    # Process MPI tasks
    for task in sorted(job.mpi_tasks, key=lambda t: t.id):
        node_name = task.node.name
        rank = str(task.id).zfill(3)  # Zero-padded rank
        cores = get_task_cores(task)
        cores_truncated = truncate_core_list(cores)
        cores_count = get_cores_count(task)
        numa_domains = get_task_numa_domains(task)
        
        # Get selected NIC for this task (assuming one NIC per task for simplicity)
        selected_nic = task.selected_nics[0] if task.selected_nics else None
        nic_id = selected_nic.id if selected_nic else ""
        nic_numa = str(selected_nic.numa_domain.id) if selected_nic else ""
        
        # Check if there's a NUMA domain mismatch between cores and NIC
        nic_numa_warning = check_nic_numa_mismatch(task, selected_nic)
        nic_id += nic_numa_warning
        
        # Create a row for this task
        row = [node_name, rank, f"{cores_truncated} ({cores_count})", numa_domains, nic_id, nic_numa]
        rows.append(row)
    
    # Calculate column widths based on content and configured min/max widths
    col_widths = []
    for i, col in enumerate(columns):
        # Find max width from data and column name
        max_data_width = max([len(str(row[i])) for row in rows] + [len(col["name"])])
        # Use the larger of minimum width or max data width, but cap at max_width
        col_widths.append(min(max(col["min_width"], max_data_width), col["max_width"]))
    
    # Define header groups with proper column spans
    header_groups = [
        {"title": "Node", "columns": [0]},
        {"title": "MPI", "columns": [1]},
        {"title": f"{len(cluster.nodes)} x {cores_per_node} cores x {threads_per_core} threads", "columns": [2, 3]},
        {"title": f"NIC ({nic_count} avail)", "columns": [4, 5]}
    ]
    
    # Calculate total width of the table
    total_width = sum(col_widths) + len(col_widths) * 3 + 1
    
    # Print the table
    # Top border
    border = "=" * total_width
    print(border)
    
    # Generate the first header row with column spans - use exact width calculation
    parts = []
    parts.append("|")
    
    # First group - Node
    node_width = col_widths[0]
    parts.append(f" {header_groups[0]['title']:{node_width}} |")
    
    # Second group - MPI
    mpi_width = col_widths[1]
    parts.append(f" {header_groups[1]['title']:{mpi_width}} |")
    
    # Third group - Cores and NUMA (spans 2 columns)
    cores_numa_width = col_widths[2] + col_widths[3] + 3  # +3 for separator and spaces
    parts.append(f" {header_groups[2]['title']:{cores_numa_width}} |")
    
    # Fourth group - NIC (spans 2 columns)
    nic_width = col_widths[4] + col_widths[5] + 3  # +3 for separator and spaces
    parts.append(f" {header_groups[3]['title']:{nic_width}} |")
    
    # Join parts without newlines
    header1 = "".join(parts)
    print(header1)
    
    # Separator line
    separator = "|"
    for width in col_widths:
        separator += "-" + "-" * width + "-|"
    print(separator)
    
    # Second header row (column names)
    header2 = "|"
    for i, col in enumerate(columns):
        header2 += f" {col['name']:{col_widths[i]}} |"
    print(header2)
    
    # Separator line
    print(separator)
    
    # Data rows
    for row in rows:
        line = "|"
        for i, cell in enumerate(row):
            line += f" {cell:{col_widths[i]}} |"
        print(line)
    
    # Bottom border
    print(border)
    
    # Only show legend for NIC-core NUMA mismatches
    has_nic_numa_warnings = any("*" in row[4] for row in rows)
    
    if has_nic_numa_warnings:
        print("\nLegend:")
        print("* - MPI task's selected NIC is on a different NUMA domain than its cores (NUMA domain mismatch, potential performance issue)")

def main():
    """Main function to parse arguments and generate the table."""
    if len(sys.argv) < 2:
        print("Usage: python advisor.py <input_file>")
        sys.exit(1)
    
    filename = sys.argv[1]
    generate_table(filename)

if __name__ == "__main__":
    main() 