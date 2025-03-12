#!/usr/bin/env python3

import re
import sys
import os
from hpc_topology import (
    Cluster, Node, NUMADomain, PhysicalCore, 
    LogicalCPU, NIC, MPITask, OpenMPThread, Job, print_run
)

# Global debug flag
DEBUG = False

def create_cluster_from_file(filename):
    """
    Creates a Cluster object from an MPICH output file
    and extracts the node names.
    """
    cluster = Cluster()
    nodes_dict = {}  # To keep a reference to created Node objects
    
    # Regular expression to extract node information
    node_pattern = re.compile(r'\[PE_\d+\]: rank \d+ is on (nid\d+)')
    
    with open(filename, 'r') as f:
        content = f.read()
    
    # Extract unique node names
    node_names = set()
    for match in node_pattern.finditer(content):
        node_name = match.group(1)
        node_names.add(node_name)
    
    # Create Node objects and add them to the cluster
    for node_name in node_names:
        node = Node(name=node_name, numa_domains=[])
        nodes_dict[node_name] = node
        cluster.nodes.append(node)
    
    if DEBUG:
        print(f"Created cluster with {len(cluster.nodes)} nodes:")
        for node in cluster.nodes:
            print(f"  Node: {node.name}")
    
    return cluster, nodes_dict, content

def extract_numa_domains(content):
    """
    Extracts NUMA domain information from the content.
    Format of lines:
    PE 0:   Number of NUMA domains: 4
    PE 0:     numa_domain 0: cpu_list=[0-15,64-79]
    
    Returns:
        A list of tuples (numa_id, cpu_ranges) where cpu_ranges is a list of
        strings representing the ranges of CPUs in that NUMA domain.
    """
    numa_info = []
    
    # First determine if there's NUMA domain information in the content
    numa_count_pattern = re.compile(r'PE 0:\s+Number of NUMA domains:\s+(\d+)')
    numa_count_match = numa_count_pattern.search(content)
    
    if not numa_count_match:
        if DEBUG:
            print("Warning: Could not find NUMA domain count information")
        return numa_info
    
    # Extract NUMA domain information
    numa_pattern = re.compile(r'PE 0:\s+numa_domain (\d+): cpu_list=\[([^\]]+)\]')
    
    for match in numa_pattern.finditer(content):
        numa_id = int(match.group(1))
        cpu_list_str = match.group(2)
        cpu_ranges = cpu_list_str.split(',')
        numa_info.append((numa_id, cpu_ranges))
    
    # Make sure the number of NUMA domains we found matches the expected count
    expected_count = int(numa_count_match.group(1))
    if len(numa_info) != expected_count and DEBUG:
        print(f"Warning: Expected {expected_count} NUMA domains but found {len(numa_info)}")
    
    return numa_info

def add_numa_domains_to_cluster(cluster, nodes_dict, content):
    """
    Adds NUMA domains to the cluster nodes based on the information in the content.
    """
    numa_domains_dict = {}  # (node_name, numa_id) -> NUMADomain
    
    # Extract NUMA domain information
    numa_info = extract_numa_domains(content)
    
    if not numa_info:
        if DEBUG:
            print("Warning: No NUMA domain information found")
        return numa_domains_dict
    
    # For each node, create all the NUMA domains
    for node_name, node in nodes_dict.items():
        for numa_id, cpu_ranges in numa_info:
            # Create the NUMA domain
            numa_domain = NUMADomain(id=numa_id, node=node)
            node.numa_domains.append(numa_domain)
            numa_domains_dict[(node_name, numa_id)] = numa_domain
            
            # Process the CPU ranges
            # Split ranges into two parts: physical cores and hyperthreads
            physical_ranges, hyperthread_ranges = split_cpu_ranges(cpu_ranges)
            
            # Process physical core ranges
            create_cores_from_ranges(numa_domain, physical_ranges, is_hyperthread=False)
            
            # Process hyperthread ranges
            create_cores_from_ranges(numa_domain, hyperthread_ranges, is_hyperthread=True)
    
    if DEBUG:
        print("\nAdded NUMA domains to nodes:")
        for node in cluster.nodes:
            print(f"  Node {node.name} has {len(node.numa_domains)} NUMA domains")
            for numa in sorted(node.numa_domains, key=lambda n: n.id):
                physical_cores = [core for core in numa.cores]
                print(f"    NUMA {numa.id}: {len(physical_cores)} physical cores")
                
                # Collect all CPU IDs from all cores in this NUMA domain
                physical_cpu_ids = []
                hyperthread_cpu_ids = []
                
                for core in physical_cores:
                    for cpu in core.logical_cpus:
                        if cpu.id < 64:  # Assuming the threshold is 64 for physical vs HT
                            physical_cpu_ids.append(cpu.id)
                        else:
                            hyperthread_cpu_ids.append(cpu.id)
                
                # Sort the CPU IDs
                physical_cpu_ids.sort()
                hyperthread_cpu_ids.sort()
                
                # Convert to ranges
                physical_ranges = format_ranges(physical_cpu_ids)
                hyperthread_ranges = format_ranges(hyperthread_cpu_ids)
                
                # Combine and display
                cpu_list = physical_ranges + hyperthread_ranges
                cpu_list_str = ','.join(cpu_list)
                print(f"      CPU list: [{cpu_list_str}]")
    
    return numa_domains_dict

def split_cpu_ranges(cpu_ranges):
    """
    Splits CPU ranges into physical cores and hyperthreads.
    
    Args:
        cpu_ranges: List of strings representing CPU ranges (e.g., ['0-15', '64-79'])
        
    Returns:
        A tuple (physical_ranges, hyperthread_ranges)
    """
    # For AMD CPUs, typically the hyperthread for core N is at core N+64
    # So we assume ranges with CPUs >= 64 are hyperthreads
    physical_ranges = []
    hyperthread_ranges = []
    
    for cpu_range in cpu_ranges:
        if '-' in cpu_range:
            start, end = map(int, cpu_range.split('-'))
            if start >= 64:
                hyperthread_ranges.append(cpu_range)
            else:
                physical_ranges.append(cpu_range)
        else:
            # Single CPU
            if int(cpu_range) >= 64:
                hyperthread_ranges.append(cpu_range)
            else:
                physical_ranges.append(cpu_range)
    
    return physical_ranges, hyperthread_ranges

def create_cores_from_ranges(numa_domain, cpu_ranges, is_hyperthread=False):
    """
    Creates PhysicalCore and LogicalCPU objects from CPU ranges.
    
    Args:
        numa_domain: NUMADomain to add cores to
        cpu_ranges: List of strings representing CPU ranges (e.g., ['0-15', '64-79'])
        is_hyperthread: Whether these CPUs are hyperthreads
    """
    # Map of physical core ID to PhysicalCore object
    existing_cores = {core.id: core for core in numa_domain.cores}
    
    for cpu_range in cpu_ranges:
        if '-' in cpu_range:
            start, end = map(int, cpu_range.split('-'))
            cpu_ids = range(start, end + 1)
        else:
            cpu_ids = [int(cpu_range)]
        
        for cpu_id in cpu_ids:
            if is_hyperthread:
                # For hyperthreads, we need to find the corresponding physical core
                # For AMD CPUs, typically the physical core ID = hyperthread ID - 64
                physical_core_id = cpu_id - 64
                
                # Check if the physical core exists
                if physical_core_id in existing_cores:
                    core = existing_cores[physical_core_id]
                    # Add the logical CPU (hyperthread) to the existing core
                    logical_cpu = LogicalCPU(id=cpu_id, core=core)
                    core.logical_cpus.append(logical_cpu)
                else:
                    if DEBUG:
                        print(f"Warning: Physical core {physical_core_id} not found for hyperthread {cpu_id}")
            else:
                # Create a new physical core
                core = PhysicalCore(id=cpu_id, numa_domain=numa_domain)
                numa_domain.cores.append(core)
                existing_cores[cpu_id] = core
                
                # Add a logical CPU for this physical core
                logical_cpu = LogicalCPU(id=cpu_id, core=core)
                core.logical_cpus.append(logical_cpu)

def format_ranges(cpu_ids):
    """
    Converts a list of CPU IDs to a list of ranges.
    For example, [0, 1, 2, 3, 7, 8, 9] would become ['0-3', '7-9']
    
    Args:
        cpu_ids: A sorted list of CPU IDs
        
    Returns:
        A list of strings, each representing a range
    """
    if not cpu_ids:
        return []
    
    ranges = []
    range_start = cpu_ids[0]
    range_end = cpu_ids[0]
    
    for i in range(1, len(cpu_ids)):
        if cpu_ids[i] == range_end + 1:
            # Continue the current range
            range_end = cpu_ids[i]
        else:
            # End the current range and start a new one
            if range_start == range_end:
                ranges.append(str(range_start))
            else:
                ranges.append(f"{range_start}-{range_end}")
            range_start = cpu_ids[i]
            range_end = cpu_ids[i]
    
    # Don't forget the last range
    if range_start == range_end:
        ranges.append(str(range_start))
    else:
        ranges.append(f"{range_start}-{range_end}")
    
    return ranges

def extract_nic_info(content):
    """
    Extracts NIC information from the content.
    Format of lines:
    PE 0:   Number of NICs: 4
    PE 0:     nic_index 0: domain_name=cxi0, numa_domain=3, addr=0x7343
    
    Returns:
        A list of tuples (nic_index, domain_name, numa_id, addr)
    """
    nic_info = []
    
    # First determine if there's NIC information in the content
    nic_count_pattern = re.compile(r'PE 0:\s+Number of NICs:\s+(\d+)')
    nic_count_match = nic_count_pattern.search(content)
    
    if not nic_count_match:
        if DEBUG:
            print("Warning: Could not find NIC count information")
        return nic_info
    
    # Extract NIC information
    nic_pattern = re.compile(r'PE 0:\s+nic_index (\d+): domain_name=([^,]+), numa_domain=(\d+), addr=([^\s]+)')
    
    for match in nic_pattern.finditer(content):
        nic_index = int(match.group(1))
        domain_name = match.group(2)
        numa_id = int(match.group(3))
        addr = match.group(4)
        nic_info.append((nic_index, domain_name, numa_id, addr))
    
    # Make sure the number of NICs we found matches the expected count
    expected_count = int(nic_count_match.group(1))
    if len(nic_info) != expected_count and DEBUG:
        print(f"Warning: Expected {expected_count} NICs but found {len(nic_info)}")
    
    return nic_info

def add_nics_to_cluster(cluster, nodes_dict, numa_domains_dict, content):
    """
    Adds NICs to the cluster nodes based on the information in the content.
    """
    # Extract NIC information
    nic_info = extract_nic_info(content)
    
    if not nic_info:
        if DEBUG:
            print("Warning: No NIC information found")
        return
    
    if DEBUG:
        print("\nAdding NICs to cluster:")
    
    # Dictionary to keep track of NICs already added to NUMA domains
    added_nics = set()  # (node_name, domain_name)
    
    # For each NIC, add it to the appropriate NUMA domain in each node
    for nic_index, domain_name, numa_id, addr in nic_info:
        if DEBUG:
            print(f"  NIC {domain_name} (index {nic_index}) -> NUMA domain {numa_id}")
        
        # Iterate through nodes and add the NIC to the appropriate NUMA domain
        for node_name, node in nodes_dict.items():
            # Skip if we've already added this NIC to this node
            if (node_name, domain_name) in added_nics:
                continue
            
            # Find the corresponding NUMA domain
            numa_key = (node_name, numa_id)
            if numa_key in numa_domains_dict:
                numa_domain = numa_domains_dict[numa_key]
                
                # Create and add the NIC to the NUMA domain
                nic = NIC(id=domain_name, numa_domain=numa_domain)
                nic.address = addr  # Store the address information
                numa_domain.nics.append(nic)
                added_nics.add((node_name, domain_name))
            elif DEBUG:
                print(f"    Warning: Could not find NUMA domain {numa_id} in node {node_name}")
    
    if DEBUG:
        print("\nNIC Summary:")
        for node in cluster.nodes:
            print(f"  Node {node.name}:")
            for numa in sorted(node.numa_domains, key=lambda n: n.id):
                if numa.nics:
                    nic_names = [nic.id for nic in numa.nics]
                    print(f"    NUMA {numa.id}: NICs = {', '.join(nic_names)}")
                else:
                    print(f"    NUMA {numa.id}: No NICs")

def extract_mpi_task_info(content):
    """
    Extracts MPI task information from the content.
    Format of lines: [PE_0]: rank 0 is on nid005186
    
    Returns:
        A list of tuples (rank_id, node_name)
    """
    mpi_task_info = []
    
    # Extract MPI rank information
    rank_pattern = re.compile(r'\[PE_\d+\]: rank (\d+) is on (nid\d+)')
    
    for match in rank_pattern.finditer(content):
        rank_id = int(match.group(1))
        node_name = match.group(2)
        mpi_task_info.append((rank_id, node_name))
    
    return mpi_task_info

def extract_thread_affinity_info(content):
    """
    Extracts thread affinity information from the content.
    Format of lines: CCE OMP: host nid005186 pid 113850 tid 113850 thread 0 affinity:  1 65
    
    Returns:
        A list of tuples (node_name, pid, thread_id, cpu_id1, cpu_id2)
    """
    thread_info = []
    
    # Extract thread affinity information
    thread_pattern = re.compile(r'CCE OMP: host (nid\d+) pid (\d+) tid \d+ thread (\d+) affinity:\s+(\d+)\s+(\d+)')
    
    for match in thread_pattern.finditer(content):
        node_name = match.group(1)
        pid = int(match.group(2))
        thread_id = int(match.group(3))
        cpu_id1 = int(match.group(4))
        cpu_id2 = int(match.group(5))
        thread_info.append((node_name, pid, thread_id, cpu_id1, cpu_id2))
    
    return thread_info

def create_job_from_content(cluster, nodes_dict, numa_domains_dict, content):
    """
    Creates a Job object from the MPICH output file content.
    """
    # Try to extract job ID from filename
    job_id = 1  # Default ID
    filename = os.path.basename(sys.argv[1])
    
    # Try to find a job ID in the filename (e.g., run_check-9883400.txt)
    id_match = re.search(r'(\d+)', filename)
    if id_match:
        job_id = int(id_match.group(1))
    
    # Create a new job
    job_name = f"job_from_{filename}"
    job = Job(id=job_id, name=job_name)
    
    # Extract MPI task information
    mpi_task_info = extract_mpi_task_info(content)
    
    # Dictionary for node name to Node object mapping
    node_name_to_obj = {node.name: node for node in cluster.nodes}
    
    # Create MPI tasks
    rank_to_mpi_task = {}  # For PID-to-rank mapping later
    
    for rank_id, node_name in mpi_task_info:
        if node_name in node_name_to_obj:
            node = node_name_to_obj[node_name]
            
            # Create MPI task
            mpi_task = MPITask(id=rank_id, node=node, logical_cpus=[])
            job.mpi_tasks.append(mpi_task)
            rank_to_mpi_task[rank_id] = mpi_task
    
    # Extract thread affinity information
    thread_info = extract_thread_affinity_info(content)
    
    # Group thread info by PID (which will be our MPI task ID)
    pid_to_threads = {}
    for node_name, pid, thread_id, cpu_id1, cpu_id2 in thread_info:
        if pid not in pid_to_threads:
            pid_to_threads[pid] = []
        pid_to_threads[pid].append((node_name, thread_id, cpu_id1, cpu_id2))
    
    # Map PIDs to ranks and create MPI tasks for any PIDs that don't match ranks
    pid_to_rank = {}
    
    # First, try to determine which PIDs correspond to which ranks
    # This is a bit of a heuristic since the log doesn't explicitly map PIDs to ranks
    if len(pid_to_threads) == len(mpi_task_info):
        # If number of PIDs matches number of ranks, assume they map in order
        sorted_pids = sorted(pid_to_threads.keys())
        sorted_ranks = sorted([rank for rank, _ in mpi_task_info])
        
        for i in range(len(sorted_pids)):
            pid_to_rank[sorted_pids[i]] = sorted_ranks[i]
    
    # Create MPI tasks for PIDs and add thread information
    for pid, threads in pid_to_threads.items():
        # Get the node name from the first thread (all threads of a process are on the same node)
        node_name = threads[0][0]
        node = node_name_to_obj.get(node_name)
        
        if not node:
            if DEBUG:
                print(f"Warning: Node {node_name} not found for PID {pid}")
            continue
        
        # Get or create the MPI task for this PID
        if pid in pid_to_rank and pid_to_rank[pid] in rank_to_mpi_task:
            mpi_task = rank_to_mpi_task[pid_to_rank[pid]]
        else:
            # If we couldn't map PID to a rank, create a new MPITask with the PID as ID
            mpi_task = MPITask(id=pid, node=node, logical_cpus=[])
            job.mpi_tasks.append(mpi_task)
        
        # Add thread information
        for _, thread_id, cpu_id1, cpu_id2 in threads:
            # Find the logical CPUs
            logical_cpus = []
            
            # Find the first CPU
            cpu1 = find_logical_cpu_in_node(node, cpu_id1)
            if cpu1:
                logical_cpus.append(cpu1)
                if cpu1 not in mpi_task.logical_cpus:
                    mpi_task.logical_cpus.append(cpu1)
            
            # Find the second CPU
            cpu2 = find_logical_cpu_in_node(node, cpu_id2)
            if cpu2:
                logical_cpus.append(cpu2)
                if cpu2 not in mpi_task.logical_cpus:
                    mpi_task.logical_cpus.append(cpu2)
            
            # Create an OpenMP thread
            if logical_cpus:
                omp_thread = OpenMPThread(id=thread_id, logical_cpus=logical_cpus)
                mpi_task.openmp_threads.append(omp_thread)
    
    # Sort MPI tasks by ID for cleaner output
    job.mpi_tasks.sort(key=lambda task: task.id)
    
    if DEBUG:
        print("\nCreated Job with MPI tasks and OpenMP threads:")
        print(f"  Job name: {job.name}")
        print(f"  Number of MPI tasks: {len(job.mpi_tasks)}")
        
        for task in job.mpi_tasks:
            cpu_ids = sorted([cpu.id for cpu in task.logical_cpus])
            cpu_ranges = format_ranges(cpu_ids)
            cpu_str = ', '.join(cpu_ranges)
            
            print(f"  MPI Task {task.id} on {task.node.name}: {len(task.openmp_threads)} OpenMP threads, CPUs: {cpu_str}")
            
            for thread in sorted(task.openmp_threads, key=lambda t: t.id):
                thread_cpu_ids = sorted([cpu.id for cpu in thread.logical_cpus])
                thread_cpu_str = ', '.join(map(str, thread_cpu_ids))
                print(f"    Thread {thread.id}: CPUs: {thread_cpu_str}")
    
    return job

def find_logical_cpu_in_node(node, cpu_id):
    """
    Finds a logical CPU with the given ID in the specified node.
    
    Args:
        node: The Node object to search in
        cpu_id: The ID of the logical CPU to find
        
    Returns:
        The LogicalCPU object if found, None otherwise
    """
    for numa in node.numa_domains:
        for core in numa.cores:
            for cpu in core.logical_cpus:
                if cpu.id == cpu_id:
                    return cpu
    return None

def parse_mpich_output(filename):
    """
    Main function to parse an MPICH output file and build a cluster model and job.
    
    Returns:
        A tuple containing (Cluster, Job)
    """
    # Create the basic cluster structure with nodes
    cluster, nodes_dict, content = create_cluster_from_file(filename)
    
    # Add NUMA domains to nodes
    numa_domains_dict = add_numa_domains_to_cluster(cluster, nodes_dict, content)
    
    # Add NICs to NUMA domains
    add_nics_to_cluster(cluster, nodes_dict, numa_domains_dict, content)
    
    # Create the job with MPI tasks and OpenMP threads
    job = create_job_from_content(cluster, nodes_dict, numa_domains_dict, content)
    
    return cluster, job

def main():
    if len(sys.argv) < 2:
        print("Usage: python mpich_parser.py <input_file> [--debug]")
        sys.exit(1)
    
    # Check for debug flag
    global DEBUG
    DEBUG = "--debug" in sys.argv
    
    # Remove the debug flag from the args if present
    if DEBUG:
        sys.argv.remove("--debug")
    
    filename = sys.argv[1]
    
    # Parse the MPICH output file
    cluster, job = parse_mpich_output(filename)
    
    # Only print the topology summary in debug mode
    if DEBUG:
        print("\n=============== Cluster Topology Summary ===============")
        for node in cluster.nodes:
            print(f"Node: {node.name}")
            for numa in sorted(node.numa_domains, key=lambda n: n.id):
                core_count = len(numa.cores)
                print(f"  NUMA Domain {numa.id}: {core_count} cores")
                
                # Count total logical CPUs
                logical_cpu_count = sum(len(core.logical_cpus) for core in numa.cores)
                print(f"    Total logical CPUs: {logical_cpu_count}")
    
    # Always display the tree view
    print("\n=============== Tree View of Structure ===============")
    print_run(cluster, job, show_detailed_cpu=False)

if __name__ == "__main__":
    main() 