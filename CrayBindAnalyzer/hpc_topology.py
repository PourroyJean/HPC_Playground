from dataclasses import dataclass, field
from typing import List

@dataclass
class LogicalCPU:
    """Represents a logical CPU (thread) assigned to a physical core."""
    id: int
    core: "PhysicalCore"  # Reference to the parent core

@dataclass
class PhysicalCore:
    """Represents a physical CPU core, which contains one or more logical CPUs."""
    id: int
    numa_domain: "NUMADomain"  # Reference to the NUMA domain this core belongs to
    logical_cpus: List[LogicalCPU] = field(default_factory=list)

    def is_hyperthreaded(self) -> bool:
        """Returns True if this core has more than one logical CPU (hyperthreading enabled)."""
        return len(self.logical_cpus) > 1

@dataclass
class NIC:
    """Represents a network interface card (NIC) assigned to a specific NUMA domain."""
    id: str                   # NIC identifier (e.g., cxi0, cxi1)
    numa_domain: "NUMADomain"  # Reference to the NUMA domain the NIC is bound to

@dataclass
class NUMADomain:
    """Represents a NUMA domain that contains cores and network interfaces."""
    id: int
    node: "Node" = None      # Reference to the parent node
    cores: List[PhysicalCore] = field(default_factory=list)  # Physical cores in this NUMA
    nics: List[NIC] = field(default_factory=list)  # Network interfaces in this NUMA

    def __init__(self, id, node):
        self.id = id
        self.node = node
        self.cores = []
        self.nics = []
        
    def get_core_count(self):
        """Returns the number of physical cores in this NUMA domain."""
        return len(self.cores)
    
    def get_logical_cpu_count(self):
        """Returns the total number of logical CPUs across all cores in this NUMA domain."""
        return sum(len(core.logical_cpus) for core in self.cores)

@dataclass
class Node:
    """Represents a physical compute node, containing multiple NUMA domains."""
    name: str
    numa_domains: List[NUMADomain] = field(default_factory=list)  # NUMA domains in this node
    
    def get_core_count(self):
        """Returns the total number of physical cores across all NUMA domains."""
        return sum(numa.get_core_count() for numa in self.numa_domains)
    
    def get_logical_cpu_count(self):
        """Returns the total number of logical CPUs across all NUMA domains."""
        return sum(numa.get_logical_cpu_count() for numa in self.numa_domains)
    
    def __str__(self):
        """Returns a string representation of the node including the number of NUMA domains, cores, and CPUs."""
        return f"{self.name} ({len(self.numa_domains)} NUMA domains - {self.get_core_count()} cores, {self.get_logical_cpu_count()} CPUs)"

@dataclass
class Cluster:
    """Represents an HPC cluster composed of multiple compute nodes."""
    nodes: List[Node] = field(default_factory=list)

@dataclass
class OpenMPThread:
    """Represents an OpenMP thread, which may run on multiple LogicalCPUs."""
    id: int
    logical_cpus: List[LogicalCPU]  # The logical CPUs this OpenMP thread can use

@dataclass
class MPITask:
    """Represents an MPI task running on exactly one node."""
    id: int
    node: Node                      # The node this MPI task is running on
    logical_cpus: List[LogicalCPU]  # Logical CPUs assigned to this MPI task
    openmp_threads: List[OpenMPThread] = field(default_factory=list)

@dataclass
class Job:
    """Represents an HPC job consisting of multiple MPI tasks."""
    id: int
    name: str = "unnamed_job"
    mpi_tasks: List[MPITask] = field(default_factory=list)
    
    @property
    def num_tasks(self) -> int:
        """Returns the number of MPI tasks in this job."""
        return len(self.mpi_tasks)
    
    @property
    def num_nodes(self) -> int:
        """Returns the number of unique nodes used by this job."""
        return len(set(task.node.name for task in self.mpi_tasks))
    
    @property
    def total_threads(self) -> int:
        """Returns the total number of OpenMP threads across all MPI tasks."""
        return sum(len(task.openmp_threads) for task in self.mpi_tasks)
    
    @property
    def total_cpus_allocated(self) -> int:
        """Returns the total number of logical CPUs allocated across all MPI tasks."""
        return sum(len(task.logical_cpus) for task in self.mpi_tasks)
    
    @property
    def total_cpus_available(self) -> int:
        """Returns the total number of logical CPUs available across all nodes used by this job."""
        # Get unique nodes used by this job using node names to avoid unhashable Node objects
        node_names = set(task.node.name for task in self.mpi_tasks)
        node_objects = {}
        
        # Create a dictionary of unique nodes
        for task in self.mpi_tasks:
            if task.node.name not in node_objects:
                node_objects[task.node.name] = task.node
        
        # Sum up the logical CPU count for each unique node
        return sum(node.get_logical_cpu_count() for node in node_objects.values())
    
    @property
    def ranks_per_node(self) -> float:
        """Returns the average number of MPI ranks per node."""
        if self.num_nodes == 0:
            return 0
        return self.num_tasks / self.num_nodes
    
    @property
    def threads_per_rank(self) -> float:
        """Returns the average number of OpenMP threads per MPI rank."""
        if self.num_tasks == 0:
            return 0
        return self.total_threads / self.num_tasks
    
    @property
    def cpus_per_rank(self) -> float:
        """Returns the average number of CPUs per MPI rank."""
        if self.num_tasks == 0:
            return 0
        return self.total_cpus_allocated / self.num_tasks
    
    def get_numa_domains_per_node(self) -> int:
        """Returns the number of NUMA domains per node (assuming homogeneous nodes)."""
        if not self.mpi_tasks:
            return 0
        # Get the first node and return its NUMA domain count
        first_node = self.mpi_tasks[0].node
        return len(first_node.numa_domains)
    
    def get_cores_per_node(self) -> int:
        """Returns the number of cores per node (assuming homogeneous nodes)."""
        if not self.mpi_tasks:
            return 0
        # Get the first node and return its core count
        first_node = self.mpi_tasks[0].node
        return first_node.get_core_count()
    
    def get_summary(self) -> str:
        """Returns a formatted summary of the job with aligned values."""
        # Define the header
        summary = "=============== Job Summary ===============\n"
        
        # Define all the labels and values to ensure consistent alignment
        labels = [
            "Job ID",
            "Nodes Used",
            "MPI Ranks",
            "Threads per Rank",
            "Total CPUs Allocated",
            "Total CPUs Available",
            "NUMA Domains per Node",
            "Cores per Node"
        ]
        
        # Calculate and format values (convert float to int if it's a whole number)
        ranks_per_node = self.ranks_per_node
        if ranks_per_node.is_integer():
            ranks_per_node = int(ranks_per_node)
            
        threads_per_rank = self.threads_per_rank
        if threads_per_rank.is_integer():
            threads_per_rank = int(threads_per_rank)
            
        cpus_per_rank = self.cpus_per_rank
        if cpus_per_rank.is_integer():
            cpus_per_rank = int(cpus_per_rank)
        
        values = [
            str(self.id),
            str(self.num_nodes),
            f"{self.num_tasks}  ({ranks_per_node} per node)",
            str(threads_per_rank),
            f"{self.total_cpus_allocated}  ({cpus_per_rank} CPUs per rank)",
            str(self.total_cpus_available),
            str(self.get_numa_domains_per_node()),
            str(self.get_cores_per_node())
        ]
        
        # Find the length of the longest label for alignment
        max_label_length = max(len(label) for label in labels)
        
        # Format each line with proper alignment
        for label, value in zip(labels, values):
            summary += f"{label:{max_label_length}}: {value}\n"
        
        return summary

def print_run(cluster, job, show_detailed_cpu=False, indent="", last=True):
    """
    Print the cluster and job topology in a tree format.
    """
    # Print the cluster structure
    print(f"{indent}Cluster ({len(cluster.nodes)} nodes)")
    indent += "  " if not last else "  "
    
    # Print each node
    for i, node in enumerate(sorted(cluster.nodes, key=lambda n: n.name)):
        is_last_node = i == len(cluster.nodes) - 1
        prefix = "└── " if is_last_node else "├── "
        print(f"{indent}{prefix}Node: {str(node)}")
        
        # Increase indent for NUMA domains
        numa_indent = indent + ("    " if is_last_node else "│   ")
        
        # Print each NUMA domain
        for j, numa in enumerate(sorted(node.numa_domains, key=lambda n: n.id)):
            is_last_numa = j == len(node.numa_domains) - 1
            numa_prefix = "└── " if is_last_numa else "├── "
            core_count = numa.get_core_count()
            cpu_count = numa.get_logical_cpu_count()
            print(f"{numa_indent}{numa_prefix}NUMA: {numa.id} ({core_count} cores, {cpu_count} CPUs)")
            
            # Increase indent for cores
            cpu_indent = numa_indent + ("    " if is_last_numa else "│   ")
            
            # Print CPU information
            if show_detailed_cpu:
                # Detailed view shows each core and its logical CPUs
                for k, core in enumerate(sorted(numa.cores, key=lambda c: c.id)):
                    is_last_core = k == len(numa.cores) - 1
                    core_prefix = "└── " if is_last_core else "├── "
                    print(f"{cpu_indent}{core_prefix}Core: {core.id}")
                    
                    # Increase indent for logical CPUs
                    lcpu_indent = cpu_indent + ("    " if is_last_core else "│   ")
                    
                    # Print each logical CPU
                    for l, lcpu in enumerate(sorted(core.logical_cpus, key=lambda c: c.id)):
                        is_last_lcpu = l == len(core.logical_cpus) - 1
                        lcpu_prefix = "└── " if is_last_lcpu else "├── "
                        print(f"{lcpu_indent}{lcpu_prefix}CPU: {lcpu.id}")
            else:
                # Compact view shows CPU ranges
                cpu_ids = []
                for core in numa.cores:
                    for cpu in core.logical_cpus:
                        cpu_ids.append(cpu.id)
                
                if cpu_ids:
                    # Sort CPU IDs
                    cpu_ids.sort()
                    
                    # Create ranges for display (e.g., [0-15, 64-79])
                    ranges = []
                    start = cpu_ids[0]
                    end = cpu_ids[0]
                    
                    for i in range(1, len(cpu_ids)):
                        if cpu_ids[i] == end + 1:
                            end = cpu_ids[i]
                        else:
                            if start == end:
                                ranges.append(str(start))
                            else:
                                ranges.append(f"{start}-{end}")
                            start = cpu_ids[i]
                            end = cpu_ids[i]
                    
                    # Add the last range
                    if start == end:
                        ranges.append(str(start))
                    else:
                        ranges.append(f"{start}-{end}")
                    
                    range_str = ", ".join(ranges)
                    print(f"{cpu_indent}├── CPUs: {range_str}")
            
            # Print NICs in this NUMA domain
            if numa.nics:
                nic_names = [nic.id for nic in numa.nics]
                nic_str = ", ".join(nic_names)
                print(f"{cpu_indent}└── NICs: {nic_str}")
    
    # Print the job structure
    print(f"\n=============== Job: {job.name} (ID: {job.id}, {len(job.mpi_tasks)} MPI tasks) ===============")
    
    # Group MPI tasks by node
    tasks_by_node = {}
    for task in job.mpi_tasks:
        if task.node.name not in tasks_by_node:
            tasks_by_node[task.node.name] = []
        tasks_by_node[task.node.name].append(task)
    
    # Sort nodes
    sorted_nodes = sorted(tasks_by_node.keys())
    
    # Print each node's tasks
    for i, node_name in enumerate(sorted_nodes):
        node = next(node for node in cluster.nodes if node.name == node_name)
        is_last_node = i == len(sorted_nodes) - 1
        prefix = "└── " if is_last_node else "├── "
        print(f"{'  '}{prefix}Node: {str(node)}")
        
        # Increase indent for tasks
        task_indent = "  " + ("    " if is_last_node else "│   ")
        
        # Sort tasks by ID
        tasks = sorted(tasks_by_node[node_name], key=lambda t: t.id)
        
        # Print each task
        for j, task in enumerate(tasks):
            is_last_task = j == len(tasks) - 1
            task_prefix = "└── " if is_last_task else "├── "
            
            # Get CPU IDs used by this task
            cpu_ids = sorted([cpu.id for cpu in task.logical_cpus])
            
            # Format CPU IDs as ranges
            ranges = []
            if cpu_ids:
                start = cpu_ids[0]
                end = cpu_ids[0]
                
                for i in range(1, len(cpu_ids)):
                    if cpu_ids[i] == end + 1:
                        end = cpu_ids[i]
                    else:
                        if start == end:
                            ranges.append(str(start))
                        else:
                            ranges.append(f"{start}-{end}")
                        start = cpu_ids[i]
                        end = cpu_ids[i]
                
                # Add the last range
                if start == end:
                    ranges.append(str(start))
                else:
                    ranges.append(f"{start}-{end}")
            
            cpu_str = ", ".join(ranges)
            print(f"{task_indent}{task_prefix}MPI Rank {task.id} ({len(task.logical_cpus)} CPUs: {cpu_str})")
            
            # Increase indent for threads
            thread_indent = task_indent + ("    " if is_last_task else "│   ")
            
            # Print thread count
            thread_count = len(task.openmp_threads)
            if thread_count > 0:
                print(f"{thread_indent}├── {thread_count} OpenMP threads")
                
                # Print each thread
                for k, thread in enumerate(sorted(task.openmp_threads, key=lambda t: t.id)):
                    is_last_thread = k == thread_count - 1
                    thread_prefix = "└── " if is_last_thread else "├── "
                    
                    # Get CPU IDs used by this thread
                    thread_cpu_ids = sorted([cpu.id for cpu in thread.logical_cpus])
                    thread_cpu_str = ", ".join(map(str, thread_cpu_ids))
                    
                    print(f"{thread_indent}{thread_prefix}Thread {thread.id}: {thread_cpu_str}")
    
    # Print job summary at the end
    print(f"\n{job.get_summary()}")

def format_id_ranges(ids):
    """
    Formats a list of identifiers into compact ranges.
    Example: [1, 2, 3, 5, 6, 9] -> "1-3, 5-6, 9"
    """
    if not ids:
        return ""
    
    # Sort the IDs
    sorted_ids = sorted(ids)
    
    ranges = []
    start = sorted_ids[0]
    end = start
    
    for i in range(1, len(sorted_ids)):
        if sorted_ids[i] == end + 1:
            end = sorted_ids[i]
        else:
            if start == end:
                ranges.append(str(start))
            else:
                ranges.append(f"{start}-{end}")
            start = end = sorted_ids[i]
    
    # Process the last range
    if start == end:
        ranges.append(str(start))
    else:
        ranges.append(f"{start}-{end}")
    
    return ", ".join(ranges)

