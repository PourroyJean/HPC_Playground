#define _GNU_SOURCE

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sched.h>
#include <mpi.h>
#include <omp.h>
#include <numa.h>
#include <hwloc.h>
#include <sys/mman.h>
#include <linux/mempolicy.h>
#include <sys/syscall.h>
#include <errno.h>
#include <numaif.h>  // For mbind

// Default allocation size in MB
#define DEFAULT_ALLOC_SIZE_MB 512
// Default NUMA domain (-1 means use regular malloc)
#define DEFAULT_NUMA_DOMAIN -1

// Function declarations
static int parse_args(int argc, char *argv[], int *numa_domain);
static void get_cpu_info(hwloc_topology_t topology, int *cpu_id, int *core_numa, int *alloc_numa);
static int get_numa_node_of_address(void *addr);
static void print_results_table(int rank, int cpu_id, int core_numa, int alloc_numa, void *addr, size_t size);
static void* numa_alloc_on_node(size_t size, int node);

int main(int argc, char *argv[]) {
    int rank, size;
    size_t alloc_size_mb;
    int numa_domain;
    void *allocated_memory;
    hwloc_topology_t topology;
    int cpu_id, core_numa, alloc_numa;

    // Initialize MPI
    if (MPI_Init(&argc, &argv) != MPI_SUCCESS) {
        fprintf(stderr, "MPI initialization failed\n");
        return 1;
    }

    // Get MPI rank and size
    MPI_Comm_rank(MPI_COMM_WORLD, &rank);
    MPI_Comm_size(MPI_COMM_WORLD, &size);

    // Print debug information for rank 0 only
    if (rank == 0) {
        printf("\n=== Debug Information ===\n");
        printf("MPI Configuration:\n");
        printf("  Number of ranks: %d\n", size);
        printf("  Command line arguments:\n");
        for (int i = 0; i < argc; i++) {
            printf("    argv[%d] = %s\n", i, argv[i]);
        }
        printf("\nSystem Information:\n");
        printf("  Page size: %ld bytes\n", sysconf(_SC_PAGESIZE));
        printf("  Number of NUMA nodes: %d\n", numa_max_node() + 1);
        printf("  NUMA available: %s\n", numa_available() == -1 ? "No" : "Yes");
        printf("  Number of CPUs: %ld\n", sysconf(_SC_NPROCESSORS_ONLN));
        printf("  Current CPU: %d\n", sched_getcpu());
        printf("  Current NUMA node: %d\n", numa_node_of_cpu(sched_getcpu()));
        printf("=====================\n\n");
        fflush(stdout);
    }

    // Parse command line arguments
    alloc_size_mb = parse_args(argc, argv, &numa_domain);

    // Initialize hwloc topology with specific flags
    hwloc_topology_init(&topology);
    hwloc_topology_set_flags(topology, HWLOC_TOPOLOGY_FLAG_WHOLE_SYSTEM);
    hwloc_topology_load(topology);

    // Get CPU and NUMA information
    get_cpu_info(topology, &cpu_id, &core_numa, &alloc_numa);

    // Allocate memory based on whether NUMA domain is specified
    if (numa_domain >= 0) {
        // Use NUMA allocation if domain is specified
        allocated_memory = numa_alloc_on_node(alloc_size_mb * 1024 * 1024, numa_domain);
    } else {
        // Use regular malloc if no NUMA domain specified
        allocated_memory = malloc(alloc_size_mb * 1024 * 1024);
    }

    if (allocated_memory == NULL) {
        fprintf(stderr, "Rank %d: Memory allocation failed\n", rank);
        MPI_Abort(MPI_COMM_WORLD, 1);
    }

    // Print results in a table format
    print_results_table(rank, cpu_id, core_numa, numa_domain, allocated_memory, alloc_size_mb);

    // For the last MPI process, show numastat information before cleanup
    if (rank == size - 1) {
        printf("\n=== NUMA Statistics for Last Process (Rank %d) ===\n", rank);
        printf("Process ID: %d\n", getpid());
        printf("Allocated Memory Size: %zu MB\n", alloc_size_mb);
        printf("NUMA Domain: %d\n", numa_domain);
        
        // Initialize the memory to ensure it's allocated
        size_t total_size = alloc_size_mb * 1024 * 1024;
        char *mem = (char *)allocated_memory;
        for (size_t i = 0; i < total_size; i += 4096) {  // Touch each page
            mem[i] = 0;
        }
        
        // Signal other processes that we're ready to run numastat
        MPI_Barrier(MPI_COMM_WORLD);
        
        printf("\nRunning numastat...\n");
        char cmd[256];
        snprintf(cmd, sizeof(cmd), "numastat -p %d | sed 's/^/[%d] /'", getpid(), rank);
        system(cmd);
        printf("==============================================\n\n");
        fflush(stdout);
        
        // Signal other processes that numastat is done
        MPI_Barrier(MPI_COMM_WORLD);
    } else {
        // Other processes wait for the last process to be ready
        MPI_Barrier(MPI_COMM_WORLD);
        // Wait for numastat to complete
        MPI_Barrier(MPI_COMM_WORLD);
    }

    // Ensure all processes are synchronized before cleanup
    MPI_Barrier(MPI_COMM_WORLD);

    // Cleanup
    if (numa_domain >= 0) {
        munmap(allocated_memory, alloc_size_mb * 1024 * 1024);
    } else {
        free(allocated_memory);
    }
    hwloc_topology_destroy(topology);
    MPI_Finalize();
    return 0;
}

static int parse_args(int argc, char *argv[], int *numa_domain) {
    *numa_domain = DEFAULT_NUMA_DOMAIN;  // Default to -1 (use regular malloc)
    
    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--numa") == 0 && i + 1 < argc) {
            char *endptr;
            long domain = strtol(argv[i + 1], &endptr, 10);
            if (*endptr == '\0' && domain >= 0) {
                *numa_domain = (int)domain;
                i++; // Skip the next argument
                continue;
            }
        }
        
        // Handle size parameter (first non-option argument)
        char *endptr;
        long size = strtol(argv[i], &endptr, 10);
        if (*endptr == '\0' && size > 0) {
            return (int)size;
        }
    }
    return DEFAULT_ALLOC_SIZE_MB;
}

static void get_cpu_info(hwloc_topology_t topology, int *cpu_id, int *core_numa, int *alloc_numa) {
    hwloc_obj_t obj;
    hwloc_cpuset_t cpuset = hwloc_bitmap_alloc();
    
    // Get current CPU set
    if (hwloc_get_cpubind(topology, cpuset, 0) < 0) {
        hwloc_get_last_cpu_location(topology, cpuset, 0);
    }
    
    // Get the CPU object
    obj = hwloc_get_first_largest_obj_inside_cpuset(topology, cpuset);
    if (obj) {
        *cpu_id = obj->logical_index;
        
        // Find the NUMA node by traversing up the topology tree
        hwloc_obj_t current = obj;
        while (current) {
            if (current->type == HWLOC_OBJ_NUMANODE) {
                *core_numa = current->logical_index;
                fprintf(stderr, "Found NUMA node %d for CPU %d\n", *core_numa, *cpu_id);
                break;
            }
            current = current->parent;
        }
        
        if (!current) {
            // If no NUMA node found, try to get it from numa_node_of_cpu
            *core_numa = numa_node_of_cpu(*cpu_id);
            fprintf(stderr, "Using numa_node_of_cpu: NUMA node %d for CPU %d\n", *core_numa, *cpu_id);
        }
    } else {
        // Fallback: try to get CPU ID from sched_getcpu
        #ifdef _GNU_SOURCE
        *cpu_id = sched_getcpu();
        #else
        *cpu_id = -1;
        #endif
        
        if (*cpu_id >= 0) {
            *core_numa = numa_node_of_cpu(*cpu_id);
            fprintf(stderr, "Using sched_getcpu: NUMA node %d for CPU %d\n", *core_numa, *cpu_id);
        } else {
            *cpu_id = -1;
            *core_numa = -1;
        }
    }
    
    // Set the allocation NUMA node based on rank
    int rank;
    MPI_Comm_rank(MPI_COMM_WORLD, &rank);
    *alloc_numa = rank % 3;  // Map ranks 0,3,6 to N0, ranks 1,4,7 to N1, ranks 2,5,8 to N2
    
    hwloc_bitmap_free(cpuset);
}

static int get_numa_node_of_address(void *addr) {
    unsigned long node;
    
    if (get_mempolicy((int *)&node, NULL, 0, addr, MPOL_F_NODE | MPOL_F_ADDR) == 0) {
        return (int)node;
    }
    
    return -1;
}

static void* numa_alloc_on_node(size_t size, int node) {
    void *addr;
    struct bitmask *nodemask;
    unsigned long maxnode = numa_max_node() + 1;
    
    // Initialize NUMA library if not already initialized
    if (numa_available() == -1) {
        fprintf(stderr, "NUMA not available\n");
        return NULL;
    }
    
    // Create and set up the nodemask
    nodemask = numa_bitmask_alloc(maxnode);
    if (nodemask == NULL) {
        fprintf(stderr, "Failed to allocate nodemask\n");
        return NULL;
    }
    
    // Set the bit for our target node
    numa_bitmask_setbit(nodemask, node);
    
    // Allocate memory with mmap first
    addr = mmap(NULL, size, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    if (addr == MAP_FAILED) {
        fprintf(stderr, "mmap failed: %s\n", strerror(errno));
        numa_bitmask_free(nodemask);
        return NULL;
    }
    
    // Set memory binding using mbind system call
    if (mbind(addr, size, MPOL_BIND, nodemask->maskp, maxnode, 0) != 0) {
        fprintf(stderr, "mbind failed: %s\n", strerror(errno));
        munmap(addr, size);
        numa_bitmask_free(nodemask);
        return NULL;
    }
    
    // Touch each page to ensure memory is actually allocated
    char *mem = (char *)addr;
    for (size_t i = 0; i < size; i += 4096) {  // Touch each page
        mem[i] = 0;
    }
    
    // Free the nodemask
    numa_bitmask_free(nodemask);
    
    return addr;
}

static void print_results_table(int rank, int cpu_id, int core_numa, int alloc_numa, void *addr, size_t size) {
    (void)cpu_id;  // Suppress unused parameter warning
    (void)alloc_numa;  // Suppress unused parameter warning
    char line[256];
    char cpu_list[256] = "N/A";
    
    // Get CPU affinity information using hwloc
    hwloc_topology_t topology;
    hwloc_topology_init(&topology);
    hwloc_topology_set_flags(topology, HWLOC_TOPOLOGY_FLAG_WHOLE_SYSTEM);
    hwloc_topology_load(topology);
    
    hwloc_cpuset_t cpuset = hwloc_bitmap_alloc();
    if (hwloc_get_cpubind(topology, cpuset, 0) == 0) {
        int first = -1;
        int last = -1;
        int count = 0;
        
        // Get the first and last CPU in the set
        first = hwloc_bitmap_first(cpuset);
        last = hwloc_bitmap_last(cpuset);
        count = hwloc_bitmap_weight(cpuset);
        
        if (count > 0) {
            // For hyperthreading, we expect exactly 2 cores (physical + hyperthread)
            if (count == 2) {
                snprintf(cpu_list, sizeof(cpu_list), "%d,%d", first, last);
            } else {
                // Fallback to showing just the current CPU
                snprintf(cpu_list, sizeof(cpu_list), "%d", first);
            }
        }
    }
    
    hwloc_bitmap_free(cpuset);
    hwloc_topology_destroy(topology);
    
    // Print header for rank 0 only
    if (rank == 0) {
        printf("\n====================================================================================================\n");
        printf("|    MPI    |        CPU     |                                   MEMORY                            |\n");
        printf("|-----------|---------|------|----------------|--------------|-------------|-----------------------|\n");
        printf("| MPI ranks | Cores   | NUMA |     Address    | SIZE (MB)    | NUMA Binded | Page Size             |\n");
        printf("|-----------|---------|------|----------------|--------------|-------------|-----------------------|\n");
        fflush(stdout);
    }
    
    // Ensure all processes are synchronized before printing data
    MPI_Barrier(MPI_COMM_WORLD);
    
    // Get NUMA maps information
    char numa_maps_info[256] = "N/A";
    int node = get_numa_node_of_address(addr);
    if (node >= 0) {
        snprintf(numa_maps_info, sizeof(numa_maps_info), "bind:%d", node);
    }
    
    // Get page size
    long page_size = sysconf(_SC_PAGESIZE);
    int page_size_kb = page_size / 1024;
    
    // Print data for each process in order
    snprintf(line, sizeof(line), "| %03d       | %-7s | %-4d | %-14p | %-12zu | %-11s | kernelpagesize_kB=%-2d |\n",
             rank, cpu_list, core_numa, addr, size, numa_maps_info, page_size_kb);
    
    // Print the line and flush
    printf("%s", line);
    fflush(stdout);
} 