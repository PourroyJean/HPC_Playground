#!/usr/bin/env python3

import re
import sys
import os
from collections import defaultdict
from hpc_topology import (
    Cluster, Node, NUMADomain, PhysicalCore, 
    LogicalCPU, NIC, MPITask, OpenMPThread, Job, print_run,
    format_id_ranges, format_id_ranges_as_list
)

# Global debug flag
DEBUG = False

class MPICHParser:
    """Parser for MPICH output files that builds a topology model and job information."""
    
    def __init__(self, filename):
        """Initialize the parser with the input filename."""
        self.filename = filename
        self.content = self._read_file(filename)
        self.cluster = Cluster()
        self.nodes_dict = {}
        self.numa_domains_dict = {}
        self.job = None
    
    def _read_file(self, filename):
        """Read the content of the MPICH output file."""
        with open(filename, 'r') as f:
            return f.read()
    
    def parse(self):
        """Parse the file and build the topology model and job."""
        self._parse_nodes()
        self._parse_numa_domains()
        self._parse_nics()
        self._parse_job()
        return self.cluster, self.job
    
    def _parse_nodes(self):
        """Extract node information and create Node objects."""
        # Regular expression to extract node information
        node_pattern = re.compile(r'\[PE_\d+\]: rank \d+ is on (nid\d+)')
        
        # Extract unique node names
        node_names = set()
        for match in node_pattern.finditer(self.content):
            node_name = match.group(1)
            node_names.add(node_name)
        
        # Create Node objects and add them to the cluster
        for node_name in node_names:
            node = Node(name=node_name, numa_domains=[])
            self.nodes_dict[node_name] = node
            self.cluster.nodes.append(node)
        
        if DEBUG:
            print(f"Created cluster with {len(self.cluster.nodes)} nodes:")
            for node in self.cluster.nodes:
                print(f"  Node: {node.name}")
    
    def _extract_numa_domains(self):
        """
        Extract NUMA domain information from the content.
        
        Returns:
            A list of tuples (numa_id, cpu_ranges) where cpu_ranges is a list of
            strings representing the ranges of CPUs in that NUMA domain.
        """
        numa_info = []
        
        # First determine if there's NUMA domain information in the content
        numa_count_pattern = re.compile(r'PE 0:\s+Number of NUMA domains:\s+(\d+)')
        numa_count_match = numa_count_pattern.search(self.content)
        
        if not numa_count_match:
            if DEBUG:
                print("Warning: Could not find NUMA domain count information")
            return numa_info
        
        # Extract NUMA domain information
        numa_pattern = re.compile(r'PE 0:\s+numa_domain (\d+): cpu_list=\[([^\]]+)\]')
        
        for match in numa_pattern.finditer(self.content):
            numa_id = int(match.group(1))
            cpu_list_str = match.group(2)
            cpu_ranges = cpu_list_str.split(',')
            numa_info.append((numa_id, cpu_ranges))
        
        # Make sure the number of NUMA domains we found matches the expected count
        expected_count = int(numa_count_match.group(1))
        if len(numa_info) != expected_count and DEBUG:
            print(f"Warning: Expected {expected_count} NUMA domains but found {len(numa_info)}")
        
        return numa_info
    
    def _parse_numa_domains(self):
        """Parse NUMA domain information and add it to nodes."""
        # Extract NUMA domain information
        numa_info = self._extract_numa_domains()
        
        if not numa_info:
            if DEBUG:
                print("Warning: No NUMA domain information found")
            return
        
        # For each node, create all the NUMA domains
        for node_name, node in self.nodes_dict.items():
            for numa_id, cpu_ranges in numa_info:
                # Create the NUMA domain
                numa_domain = NUMADomain(id=numa_id, node=node)
                node.numa_domains.append(numa_domain)
                self.numa_domains_dict[(node_name, numa_id)] = numa_domain
                
                # Process all CPU ranges together in a simpler way
                self._add_cpus_to_numa_domain(numa_domain, cpu_ranges)
        
        if DEBUG:
            self._print_numa_summary()
    
    def _add_cpus_to_numa_domain(self, numa_domain, cpu_ranges):
        """
        Add CPUs to a NUMA domain from CPU range strings.
        
        Args:
            numa_domain: NUMADomain to add cores to
            cpu_ranges: List of strings representing CPU ranges (e.g., ['0-15', '64-79'])
        """
        # Parse all CPU IDs from ranges
        all_cpu_ids = []
        for cpu_range in cpu_ranges:
            if '-' in cpu_range:
                start, end = map(int, cpu_range.split('-'))
                all_cpu_ids.extend(range(start, end + 1))
            else:
                all_cpu_ids.append(int(cpu_range))
        
        # Sort CPU IDs for consistent processing
        all_cpu_ids.sort()
        
        # Map physical cores by ID
        physical_cores = {}
        
        # Create physical cores and logical CPUs
        for cpu_id in all_cpu_ids:
            # For AMD CPUs, typically the hyperthread for core N is at core N+64
            is_hyperthread = cpu_id >= 64
            core_id = cpu_id - 64 if is_hyperthread else cpu_id
            
            # Create physical core if it doesn't exist
            if core_id not in physical_cores:
                # Only create new cores for non-hyperthread CPUs
                if not is_hyperthread:
                    physical_core = PhysicalCore(id=core_id, numa_domain=numa_domain)
                    numa_domain.cores.append(physical_core)
                    physical_cores[core_id] = physical_core
            
            # Add logical CPU to the corresponding physical core
            if core_id in physical_cores:
                physical_core = physical_cores[core_id]
                logical_cpu = LogicalCPU(id=cpu_id, core=physical_core)
                physical_core.logical_cpus.append(logical_cpu)
            elif DEBUG and is_hyperthread:
                print(f"Warning: No physical core {core_id} found for hyperthread {cpu_id}")
    
    def _print_numa_summary(self):
        """Print a summary of NUMA domains for debugging."""
        print("\nAdded NUMA domains to nodes:")
        for node in self.cluster.nodes:
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
                physical_ranges = format_id_ranges_as_list(physical_cpu_ids)
                hyperthread_ranges = format_id_ranges_as_list(hyperthread_cpu_ids)
                
                # Combine and display
                cpu_list = physical_ranges + hyperthread_ranges
                cpu_list_str = ','.join(cpu_list)
                print(f"      CPU list: [{cpu_list_str}]")
    
    def _extract_nic_info(self):
        """
        Extract NIC information from the content.
        
        Returns:
            A list of tuples (nic_index, domain_name, numa_id, addr)
        """
        nic_info = []
        
        # First determine if there's NIC information in the content
        nic_count_pattern = re.compile(r'PE 0:\s+Number of NICs:\s+(\d+)')
        nic_count_match = nic_count_pattern.search(self.content)
        
        if not nic_count_match:
            if DEBUG:
                print("Warning: Could not find NIC count information")
            return nic_info
        
        # Extract NIC information
        nic_pattern = re.compile(r'PE 0:\s+nic_index (\d+): domain_name=([^,]+), numa_domain=(\d+), addr=([^\s]+)')
        
        for match in nic_pattern.finditer(self.content):
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
    
    def _parse_nics(self):
        """Parse NIC information and add it to NUMA domains."""
        # Extract NIC information
        nic_info = self._extract_nic_info()
        
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
            for node_name, node in self.nodes_dict.items():
                # Skip if we've already added this NIC to this node
                if (node_name, domain_name) in added_nics:
                    continue
                
                # Find the corresponding NUMA domain
                numa_key = (node_name, numa_id)
                if numa_key in self.numa_domains_dict:
                    numa_domain = self.numa_domains_dict[numa_key]
                    
                    # Create and add the NIC to the NUMA domain
                    nic = NIC(id=domain_name, numa_domain=numa_domain)
                    nic.address = addr  # Store the address information
                    numa_domain.nics.append(nic)
                    added_nics.add((node_name, domain_name))
                elif DEBUG:
                    print(f"    Warning: Could not find NUMA domain {numa_id} in node {node_name}")
        
        if DEBUG:
            self._print_nic_summary()
    
    def _print_nic_summary(self):
        """Print a summary of NICs for debugging."""
        print("\nNIC Summary:")
        for node in self.cluster.nodes:
            print(f"  Node {node.name}:")
            for numa in sorted(node.numa_domains, key=lambda n: n.id):
                if numa.nics:
                    nic_names = [nic.id for nic in numa.nics]
                    print(f"    NUMA {numa.id}: NICs = {', '.join(nic_names)}")
                else:
                    print(f"    NUMA {numa.id}: No NICs")
    
    def _extract_mpi_task_info(self):
        """
        Extract MPI task information from the content.
        
        Returns:
            A list of tuples (rank_id, node_name)
        """
        mpi_task_info = []
        
        # Extract MPI rank information
        rank_pattern = re.compile(r'\[PE_\d+\]: rank (\d+) is on (nid\d+)')
        
        for match in rank_pattern.finditer(self.content):
            rank_id = int(match.group(1))
            node_name = match.group(2)
            mpi_task_info.append((rank_id, node_name))
        
        return mpi_task_info
    
    def _extract_thread_affinity_info(self):
        """
        Extract thread affinity information from the content.
        
        Returns:
            A list of tuples (node_name, pid, thread_id, cpu_id1, cpu_id2)
        """
        thread_info = []
        
        # Extract thread affinity information
        thread_pattern = re.compile(r'CCE OMP: host (nid\d+) pid (\d+) tid \d+ thread (\d+) affinity:\s+(\d+)\s+(\d+)')
        
        for match in thread_pattern.finditer(self.content):
            node_name = match.group(1)
            pid = int(match.group(2))
            thread_id = int(match.group(3))
            cpu_id1 = int(match.group(4))
            cpu_id2 = int(match.group(5))
            thread_info.append((node_name, pid, thread_id, cpu_id1, cpu_id2))
        
        return thread_info
    
    def _extract_selected_nic_info(self):
        """
        Extract information about NICs selected by each Processing Element (PE/MPI task).
        
        Returns:
            A list of tuples (pe_id, node_name, nic_index, domain_name, numa_node)
        """
        selected_nic_info = []
        
        # Extract selected NIC information
        # Format: PE 3: Host nid005187 selected NIC index=1, domain_name=cxi1, numa_node=1, address=[0x73c2]
        nic_pattern = re.compile(r'PE (\d+): Host (nid\d+) selected NIC index=(\d+), domain_name=([^,]+), numa_node=(\d+)')
        
        for match in nic_pattern.finditer(self.content):
            pe_id = int(match.group(1))
            node_name = match.group(2)
            nic_index = int(match.group(3))
            domain_name = match.group(4)
            numa_node = int(match.group(5))
            selected_nic_info.append((pe_id, node_name, nic_index, domain_name, numa_node))
        
        if DEBUG:
            print(f"Found {len(selected_nic_info)} selected NICs:")
            for info in selected_nic_info:
                print(f"  PE {info[0]} on {info[1]} selected NIC {info[3]} (index={info[2]}, numa={info[4]})")
        
        return selected_nic_info
    
    def _parse_job(self):
        """Parse job information and create a Job object with MPI tasks and OpenMP threads."""
        # Try to extract job ID from filename
        job_id = 1  # Default ID
        filename = os.path.basename(self.filename)
        
        # Try to find a job ID in the filename (e.g., run_check-9883400.txt)
        id_match = re.search(r'(\d+)', filename)
        if id_match:
            job_id = int(id_match.group(1))
        
        # Create a new job
        job_name = f"job_from_{filename}"
        self.job = Job(id=job_id, name=job_name)
        
        # Extract MPI task information
        mpi_task_info = self._extract_mpi_task_info()
        
        # Dictionary for node name to Node object mapping
        node_name_to_obj = {node.name: node for node in self.cluster.nodes}
        
        # Create MPI tasks
        rank_to_mpi_task = {}  # For PID-to-rank mapping later
        
        for rank_id, node_name in mpi_task_info:
            if node_name in node_name_to_obj:
                node = node_name_to_obj[node_name]
                
                # Create MPI task
                mpi_task = MPITask(id=rank_id, node=node, logical_cpus=[])
                self.job.mpi_tasks.append(mpi_task)
                rank_to_mpi_task[rank_id] = mpi_task
        
        # Extract and process selected NIC information
        selected_nic_info = self._extract_selected_nic_info()
        
        # Associate selected NICs with MPI tasks
        for pe_id, node_name, nic_index, domain_name, numa_node in selected_nic_info:
            # Find the MPI task with this ID
            if pe_id in rank_to_mpi_task:
                mpi_task = rank_to_mpi_task[pe_id]
                
                # Find the corresponding NIC in the node
                node = node_name_to_obj.get(node_name)
                if node:
                    # Look for the NIC with the matching domain_name in the specified NUMA domain
                    for numa in node.numa_domains:
                        if numa.id == numa_node:
                            for nic in numa.nics:
                                if nic.id == domain_name:
                                    # Add this NIC to the MPI task's selected NICs
                                    mpi_task.selected_nics.append(nic)
                                    break
        
        # Extract thread affinity information
        thread_info = self._extract_thread_affinity_info()
        
        # Group thread info by PID (which will be our MPI task ID)
        pid_to_threads = defaultdict(list)
        for node_name, pid, thread_id, cpu_id1, cpu_id2 in thread_info:
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
                self.job.mpi_tasks.append(mpi_task)
            
            # Add thread information
            for _, thread_id, cpu_id1, cpu_id2 in threads:
                # Find the logical CPUs
                logical_cpus = []
                
                # Find the first CPU
                cpu1 = self._find_logical_cpu_in_node(node, cpu_id1)
                if cpu1:
                    logical_cpus.append(cpu1)
                    if cpu1 not in mpi_task.logical_cpus:
                        mpi_task.logical_cpus.append(cpu1)
                
                # Find the second CPU
                cpu2 = self._find_logical_cpu_in_node(node, cpu_id2)
                if cpu2:
                    logical_cpus.append(cpu2)
                    if cpu2 not in mpi_task.logical_cpus:
                        mpi_task.logical_cpus.append(cpu2)
                
                # Create an OpenMP thread
                if logical_cpus:
                    omp_thread = OpenMPThread(id=thread_id, logical_cpus=logical_cpus)
                    mpi_task.openmp_threads.append(omp_thread)
        
        # Sort MPI tasks by ID for cleaner output
        self.job.mpi_tasks.sort(key=lambda task: task.id)
        
        if DEBUG:
            self._print_job_summary()
    
    def _find_logical_cpu_in_node(self, node, cpu_id):
        """
        Find a logical CPU with the given ID in the specified node.
        
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
    
    def _print_job_summary(self):
        """Print a summary of the job for debugging."""
        print("\nCreated Job with MPI tasks and OpenMP threads:")
        print(f"  Job name: {self.job.name}")
        print(f"  Number of MPI tasks: {len(self.job.mpi_tasks)}")
        
        for task in self.job.mpi_tasks:
            cpu_ids = sorted([cpu.id for cpu in task.logical_cpus])
            cpu_ranges = format_id_ranges_as_list(cpu_ids)
            cpu_str = ', '.join(cpu_ranges)
            
            print(f"  MPI Task {task.id} on {task.node.name}: {len(task.openmp_threads)} OpenMP threads, CPUs: {cpu_str}")
            
            for thread in sorted(task.openmp_threads, key=lambda t: t.id):
                thread_cpu_ids = sorted([cpu.id for cpu in thread.logical_cpus])
                thread_cpu_str = ', '.join(map(str, thread_cpu_ids))
                print(f"    Thread {thread.id}: CPUs: {thread_cpu_str}")
    
    def _format_ranges(self, cpu_ids):
        """
        Convert a list of CPU IDs to a list of ranges.
        For example, [0, 1, 2, 3, 7, 8, 9] would become ['0-3', '7-9']
        
        Args:
            cpu_ids: A sorted list of CPU IDs
            
        Returns:
            A list of strings, each representing a range
        """
        return format_id_ranges_as_list(cpu_ids)

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
    parser = MPICHParser(filename)
    cluster, job = parser.parse()
    
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