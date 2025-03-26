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
#include <errno.h>
#include <linux/mempolicy.h>  // For MPOL_F_NODE and MPOL_F_ADDR
#include <numaif.h>          // For get_mempolicy
#include <time.h>            // For time() function for random seed

// Default allocation size in MB
#define DEFAULT_ALLOC_SIZE_MB 512

// Number of iterations for the latency benchmark
#define LATENCY_ITERATIONS 1000000
#define WARMUP_ITERATIONS 10000

// Function declarations
static int parse_args(int argc, char *argv[], int *serial_mode);
static void get_cpu_info(hwloc_topology_t topology, int *cpu_id, int *core_numa);
static int get_numa_node_of_address(void *addr);
static void print_results_table(int rank, int cpu_id, int core_numa, void *addr, size_t size, double latency_ns);
static double measure_memory_latency(void *memory, size_t size);
static void shuffle(size_t *array, size_t n);

int main(int argc, char *argv[]) {
    int rank, size;
    size_t alloc_size_mb;
    void *allocated_memory;
    hwloc_topology_t topology;
    int cpu_id, core_numa;
    double latency_ns = -1.0;
    int serial_mode = 0;

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
        printf("\nNote: NUMA memory binding should be controlled externally using numactl --membind=<node>\n");
        printf("=====================\n\n");
        fflush(stdout);
    }

    // Parse command line arguments
    alloc_size_mb = parse_args(argc, argv, &serial_mode);

    // Initialize hwloc topology with specific flags
    hwloc_topology_init(&topology);
    hwloc_topology_set_flags(topology, HWLOC_TOPOLOGY_FLAG_WHOLE_SYSTEM);
    hwloc_topology_load(topology);

    // Get CPU and NUMA information
    get_cpu_info(topology, &cpu_id, &core_numa);

    // Allocate memory using standard malloc
    // Note: NUMA binding should be controlled externally using numactl --membind=<node>
    allocated_memory = malloc(alloc_size_mb * 1024 * 1024);

    if (allocated_memory == NULL) {
        fprintf(stderr, "Rank %d: Memory allocation failed\n", rank);
        MPI_Abort(MPI_COMM_WORLD, 1);
    }

    // Measure memory latency
    if (serial_mode) {
        // In serial mode, only one rank runs the benchmark at a time
        double *all_latencies = malloc(size * sizeof(double));
        if (!all_latencies) {
            fprintf(stderr, "Failed to allocate latency array\n");
            MPI_Abort(MPI_COMM_WORLD, 1);
        }

        for (int current_rank = 0; current_rank < size; current_rank++) {
            if (rank == current_rank) {
                // Current rank runs the benchmark
                all_latencies[current_rank] = measure_memory_latency(allocated_memory, alloc_size_mb * 1024 * 1024);
                // Broadcast the result to all ranks
                MPI_Bcast(&all_latencies[current_rank], 1, MPI_DOUBLE, current_rank, MPI_COMM_WORLD);
            } else {
                // Other ranks wait for the current rank to finish
                MPI_Bcast(&all_latencies[current_rank], 1, MPI_DOUBLE, current_rank, MPI_COMM_WORLD);
            }
            // Synchronize all ranks before moving to the next one
            MPI_Barrier(MPI_COMM_WORLD);
        }

        // Each rank uses its own latency result
        latency_ns = all_latencies[rank];
        free(all_latencies);
    } else {
        // In parallel mode, all ranks run the benchmark simultaneously
        latency_ns = measure_memory_latency(allocated_memory, alloc_size_mb * 1024 * 1024);
    }

    // Print results in a table format
    print_results_table(rank, cpu_id, core_numa, allocated_memory, alloc_size_mb, latency_ns);

    // For the last MPI process, show numastat information before cleanup
    if (rank == size - 1) {
        printf("\n=== NUMA Statistics for Last Process (Rank %d) ===\n", rank);
        printf("Process ID: %d\n", getpid());
        printf("Allocated Memory Size: %zu MB\n", alloc_size_mb);
        
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
    free(allocated_memory);
    hwloc_topology_destroy(topology);
    MPI_Finalize();
    return 0;
}

// Implementation of Fisher-Yates shuffle algorithm
static void shuffle(size_t *array, size_t n) {
    if (n <= 1) return;
    
    // Use different seed for each MPI rank
    int rank;
    MPI_Comm_rank(MPI_COMM_WORLD, &rank);
    srand(time(NULL) + rank);
    
    for (size_t i = n - 1; i > 0; i--) {
        size_t j = rand() % (i + 1);
        size_t temp = array[i];
        array[i] = array[j];
        array[j] = temp;
    }
}

static double measure_memory_latency(void *memory, size_t size) {
    // Set up the pointer-chasing linked list
    size_t num_pointers = size / sizeof(void*);
    void **pointers = (void**)memory;
    
    // Create an array of indices and shuffle them
    size_t *indices = malloc(num_pointers * sizeof(size_t));
    if (!indices) {
        fprintf(stderr, "Failed to allocate indices array for latency test\n");
        return -1.0;
    }
    
    for (size_t i = 0; i < num_pointers; i++) {
        indices[i] = i;
    }
    
    // Shuffle the indices to create a random path through memory
    shuffle(indices, num_pointers);
    
    // Create the pointer chain using the shuffled indices
    for (size_t i = 0; i < num_pointers - 1; i++) {
        pointers[indices[i]] = &pointers[indices[i + 1]];
    }
    // Complete the cycle
    pointers[indices[num_pointers - 1]] = &pointers[indices[0]];
    
    // Warm up the cache and ensure memory is paged in
    void **p = &pointers[indices[0]];
    for (int i = 0; i < WARMUP_ITERATIONS; i++) {
        p = *p;
    }
    
    // Measure memory access time
    double start_time = MPI_Wtime();
    
    // Chase pointers through memory
    p = &pointers[indices[0]];
    for (int i = 0; i < LATENCY_ITERATIONS; i++) {
        p = *p;
    }
    
    double end_time = MPI_Wtime();
    double total_time = end_time - start_time;
    
    // Calculate average latency in nanoseconds
    double latency_ns = (total_time * 1e9) / LATENCY_ITERATIONS;
    
    // Add a dummy use of p to prevent compiler optimization
    if (p == NULL) {
        fprintf(stderr, "Should never happen but prevents optimization\n");
    }
    
    free(indices);
    return latency_ns;
}

static int parse_args(int argc, char *argv[], int *serial_mode) {
    *serial_mode = 0;
    
    // Handle command line arguments
    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--serial") == 0) {
            *serial_mode = 1;
            continue;
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

static void get_cpu_info(hwloc_topology_t topology, int *cpu_id, int *core_numa) {
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
            
            // If we still can't determine the NUMA node, use a reasonable default
            if (*core_numa == -1) {
                fprintf(stderr, "Warning: Could not determine NUMA node for CPU %d, defaulting to 0\n", *cpu_id);
                *core_numa = 0;
            }
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
            
            // If we still can't determine the NUMA node, use a reasonable default
            if (*core_numa == -1) {
                fprintf(stderr, "Warning: Could not determine NUMA node for CPU %d, defaulting to 0\n", *cpu_id);
                *core_numa = 0;
            }
        } else {
            *cpu_id = -1;
            *core_numa = -1;
        }
    }
    
    hwloc_bitmap_free(cpuset);
}

static int get_numa_node_of_address(void *addr) {
    unsigned long node;
    
    if (get_mempolicy((int *)&node, NULL, 0, addr, MPOL_F_NODE | MPOL_F_ADDR) == 0) {
        return (int)node;
    }
    
    return -1;
}

static void print_results_table(int rank, int cpu_id, int core_numa, void *addr, size_t size, double latency_ns) {
    (void)cpu_id;  // Suppress unused parameter warning
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
        printf("\n ========================================================================================\n");
        printf("|  MPI  |        CPU     |                             MEMORY                  |  LATENCY   |\n");
        printf("|-------|---------|------|----------------|--------------|-------|-------------|------------|\n");
        printf("| ranks | Cores   | NUMA |     Address    | SIZE (MB)    | NUMA  |  Page Size  | Avg (ns)   |\n");
        printf("|-------|---------|------|----------------|--------------|-------|-------------|------------|\n");
        fflush(stdout);
    }
    
    // Ensure all processes are synchronized before printing data
    MPI_Barrier(MPI_COMM_WORLD);
    
    // Get NUMA maps information
    char numa_maps_info[256] = "N/A";
    int node = get_numa_node_of_address(addr);
    if (node >= 0) {
        snprintf(numa_maps_info, sizeof(numa_maps_info), "%d", node);
    }
    
    // Get page size
    long page_size = sysconf(_SC_PAGESIZE);
    int page_size_kb = page_size / 1024;
    
    // Print data for each process in order
    snprintf(line, sizeof(line), "|  %03d  | %-7s |   %-2d | %-14p | %-12zu |   %-2s  | kB=%-8d | %-10.2f |\n",
             rank, cpu_list, core_numa, addr, size, numa_maps_info, page_size_kb, latency_ns);
    
    // Print the line and flush
    printf("%s", line);
    fflush(stdout);
} 