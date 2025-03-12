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
    """Get a list of NUMA domains used by an MPI task and a warning flag."""
    numa_domains = set()
    for cpu in task.logical_cpus:
        numa_domains.add(cpu.core.numa_domain.id)
    
    # Add a warning symbol if task spans multiple NUMA domains
    warning = " ⚠️" if len(numa_domains) > 1 else ""
    
    return ", ".join(map(str, sorted(numa_domains))) + warning

def get_cores_count(task):
    """Get the count of logical CPUs used by an MPI task."""
    return len(task.logical_cpus)

def get_nic_info_for_node(node):
    """Get NIC information for a node as a list of (nic_id, numa_domain) tuples."""
    nic_info = []
    for numa in node.numa_domains:
        for nic in numa.nics:
            nic_info.append((nic.id, numa.id))
    return sorted(nic_info, key=lambda x: x[1])  # Sort by NUMA domain ID

def truncate_core_list(core_list_str):
    """Truncate a core list string if it exceeds 10 characters."""
    if len(core_list_str) > 10:
        # Truncate the string and add "..."
        return core_list_str[:7] + "..."
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
    
    # Column definitions for the table
    columns = [
        {"name": "Node name", "min_width": 10},
        {"name": "MPI ranks", "min_width": 6},
        {"name": "Cores (total)", "min_width": 14},
        {"name": "NUMA", "min_width": 9},
        {"name": "NIC ID", "min_width": 8},
        {"name": "NUMA", "min_width": 6}
    ]
    
    # Prepare data rows
    rows = []
    nic_by_node = {}  # To track NICs for each node
    
    # Get NICs for each node - sorted by NUMA domain
    for node in cluster.nodes:
        nic_by_node[node.name] = get_nic_info_for_node(node)
    
    # Process MPI tasks
    for task in sorted(job.mpi_tasks, key=lambda t: t.id):
        node_name = task.node.name
        rank = str(task.id).zfill(3)  # Zero-padded rank
        cores = get_task_cores(task)
        cores_truncated = truncate_core_list(cores)
        cores_count = get_cores_count(task)
        numa_domains = get_task_numa_domains(task)
        
        # Create a row for this task
        row = [node_name, rank, f"{cores_truncated} ({cores_count})", numa_domains, "", ""]
        
        # If this node has NICs, add the first one to this row and remove it
        if node_name in nic_by_node and nic_by_node[node_name]:
            nic_id, numa_id = nic_by_node[node_name].pop(0)
            row[4] = nic_id
            row[5] = str(numa_id)
        
        rows.append(row)
    
    # Add remaining NICs as separate rows (with empty task info)
    for node_name, node_nics in sorted(nic_by_node.items()):
        for nic_id, numa_id in node_nics:
            row = [node_name, "", "", "", nic_id, str(numa_id)]
            rows.append(row)
    
    # Calculate column widths based on content and minimum widths
    col_widths = []
    for i, col in enumerate(columns):
        # Find max width from data and column name
        max_data_width = max([len(str(row[i])) for row in rows] + [len(col["name"])])
        # Use the larger of minimum width or max data width
        col_widths.append(max(col["min_width"], max_data_width))
    
    # Define header groups with proper column spans
    header_groups = [
        {"title": "Node", "columns": [0]},
        {"title": "MPI", "columns": [1]},
        {"title": f"{len(cluster.nodes)} x {cores_per_node} cores x {threads_per_core} threads", "columns": [2, 3]},
        {"title": f"NIC ({nic_count})", "columns": [4, 5]}
    ]
    
    # Calculate total width of the table
    total_width = sum(col_widths) + len(col_widths) * 3 + 1
    
    # Print the table
    # Top border
    print("=" * total_width)
    
    # Generate the first header row with column spans
    header1 = "|"
    for group in header_groups:
        # Calculate the width for this group (sum of columns + separators)
        span_width = sum(col_widths[i] for i in group["columns"])
        # Add space for internal separators if spanning multiple columns
        if len(group["columns"]) > 1:
            span_width += (len(group["columns"]) - 1) * 3
        header1 += f" {group['title']:{span_width}} |"
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
    print("=" * total_width)
    
    # Add a legend if there are any NUMA domain warnings
    has_warnings = any("⚠️" in row[3] for row in rows)
    if has_warnings:
        print("\nLegend:")
        print("⚠️ - MPI task spans multiple NUMA domains (potential performance issue)")

def main():
    """Main function to parse arguments and generate the table."""
    if len(sys.argv) < 2:
        print("Usage: python advisor.py <input_file>")
        sys.exit(1)
    
    filename = sys.argv[1]
    generate_table(filename)

if __name__ == "__main__":
    main() 