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

// Maximum number of different sizes to test
#define MAX_SIZES 18

// Standard sizes for range expansion
#define NUM_STANDARD_SIZES 18
const size_t STANDARD_SIZES[NUM_STANDARD_SIZES] = {
    1, 2, 4, 8, 16, 32, 64, 128, 256, 512, 1024, 2048, 4096, 8192, 16384, 32768, 65536, 131072
};

// Number of iterations for the latency benchmark
#define LATENCY_ITERATIONS 100000  // Chosen for good accuracy/speed balance
#define WARMUP_ITERATIONS 1000     // Enough to warm caches effectively   

// Structure for MPI rank mapping information
struct mapping_info {
    int rank;
    int cpu_id;
    int cpu_numa;
    int memory_numa;
};

// Function declarations
static int parse_args(int argc, char *argv[], int *serial_mode, size_t *sizes, int *num_sizes, char **csv_filename, char **mapping_file);
static void get_cpu_info(hwloc_topology_t topology, int *cpu_id, int *core_numa);
static int get_numa_node_of_address(void *addr);
static void print_results_table_header(int num_sizes, size_t *sizes);
static void print_results_table_row(int rank, int world_size, int cpu_id, int core_numa, void *addr, int num_sizes, double *latencies);
static void print_results_table_footer(int num_sizes);
static double measure_memory_latency(void *memory, size_t size);
static void shuffle(size_t *array, size_t n);
static int write_mapping_info(const char *filename, struct mapping_info *info, int world_size);
static int collect_mapping_info(const char *mapping_file, int rank, int size, 
                              int cpu_id, int core_numa, void *addr);

int main(int argc, char *argv[]) {
    int rank, size;
    size_t sizes[MAX_SIZES];
    int num_sizes = 0;
    void *allocated_memory = NULL;
    hwloc_topology_t topology;
    int cpu_id, core_numa;
    double *latencies = NULL;
    int serial_mode = 0;
    char *csv_filename = NULL;
    char *mapping_file = NULL;

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
    if (parse_args(argc, argv, &serial_mode, sizes, &num_sizes, &csv_filename, &mapping_file) != 0) {
        MPI_Abort(MPI_COMM_WORLD, 1);
        return 1;
    }

    // Initialize hwloc topology with specific flags
    hwloc_topology_init(&topology);
    hwloc_topology_set_flags(topology, HWLOC_TOPOLOGY_FLAG_WHOLE_SYSTEM);
    hwloc_topology_load(topology);

    // Get CPU and NUMA information
    get_cpu_info(topology, &cpu_id, &core_numa);

    // Allocate memory for storing latency results
    latencies = (double *)malloc(num_sizes * sizeof(double));
    if (!latencies) {
        fprintf(stderr, "Rank %d: Failed to allocate latency results array\n", rank);
        MPI_Abort(MPI_COMM_WORLD, 1);
        return 1;
    }

    // Allocate memory for the first size to get NUMA information
    allocated_memory = malloc(sizes[0] * 1024 * 1024);
    if (allocated_memory == NULL) {
        fprintf(stderr, "Rank %d: Memory allocation failed for size %zu MB\n", rank, sizes[0]);
        free(latencies);
        MPI_Abort(MPI_COMM_WORLD, 1);
        return 1;
    }

    // If mapping file is specified, collect and write mapping information
    if (mapping_file) {
        if (collect_mapping_info(mapping_file, rank, size, cpu_id, core_numa, allocated_memory) != 0) {
            free(latencies);
            free(allocated_memory);
            hwloc_topology_destroy(topology);
            MPI_Abort(MPI_COMM_WORLD, 1);
            return 1;
        }
    }

    // Loop through each memory size
    for (int i = 0; i < num_sizes; i++) {
        size_t current_size_mb = sizes[i];
        
        // Free previous allocation if any
        if (allocated_memory != NULL) {
            free(allocated_memory);
            allocated_memory = NULL;
        }
        
        // Allocate memory using standard malloc
        // Note: NUMA binding should be controlled externally using numactl --membind=<node>
        allocated_memory = malloc(current_size_mb * 1024 * 1024);

        if (allocated_memory == NULL) {
            fprintf(stderr, "Rank %d: Memory allocation failed for size %zu MB\n", rank, current_size_mb);
            free(latencies);
            MPI_Abort(MPI_COMM_WORLD, 1);
            return 1;
        }

        // Ensure all ranks proceed to measurement at the same time
        MPI_Barrier(MPI_COMM_WORLD);

        // Measure memory latency
        if (serial_mode) {
            // In serial mode, only one rank runs the benchmark at a time
            double *all_latencies = malloc(size * sizeof(double));
            if (!all_latencies) {
                fprintf(stderr, "Failed to allocate latency array\n");
                free(latencies);
                free(allocated_memory);
                MPI_Abort(MPI_COMM_WORLD, 1);
                return 1;
            }

            for (int current_rank = 0; current_rank < size; current_rank++) {
                if (rank == current_rank) {
                    // Current rank runs the benchmark
                    all_latencies[current_rank] = measure_memory_latency(allocated_memory, current_size_mb * 1024 * 1024);
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
            latencies[i] = all_latencies[rank];
            free(all_latencies);
        } else {
            // In parallel mode, all ranks run the benchmark simultaneously
            latencies[i] = measure_memory_latency(allocated_memory, current_size_mb * 1024 * 1024);
        }

        // Ensure all ranks have completed this size before moving to the next
        MPI_Barrier(MPI_COMM_WORLD);
    }

    // Print results in a table format
    if (rank == 0) {
        print_results_table_header(num_sizes, sizes);
    }
    
    // Ensure header is printed before rows
    MPI_Barrier(MPI_COMM_WORLD);
    
    // Print each rank's row
    print_results_table_row(rank, size, cpu_id, core_numa, allocated_memory, num_sizes, latencies);
    
    // Ensure all rows are printed before footer
    MPI_Barrier(MPI_COMM_WORLD);
    
    if (rank == 0) {
        print_results_table_footer(num_sizes);
    }

    // For the last MPI process, show numastat information before cleanup
    if (rank == size - 1) {
        printf("\n=== NUMA Statistics for Last Process (Rank %d) ===\n", rank);
        printf("Process ID: %d\n", getpid());
        printf("Allocated Memory Size: %zu MB\n", sizes[num_sizes-1]);
        
        // Initialize the memory to ensure it's allocated
        size_t total_size = sizes[num_sizes-1] * 1024 * 1024;
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

    // After all measurements are done, gather results to rank 0 for CSV output
    if (csv_filename != NULL) {
        // Allocate array to store all results in rank 0
        double *all_latencies = NULL;
        if (rank == 0) {
            all_latencies = malloc(num_sizes * size * sizeof(double));
            if (!all_latencies) {
                fprintf(stderr, "Error: Failed to allocate memory for gathering results\n");
                MPI_Abort(MPI_COMM_WORLD, 1);
                return 1;
            }
        }

        // Gather results from all ranks to rank 0
        MPI_Gather(latencies, num_sizes, MPI_DOUBLE, all_latencies, num_sizes, MPI_DOUBLE, 0, MPI_COMM_WORLD);

        // Write CSV file on rank 0
        if (rank == 0) {
            FILE *csv_file = fopen(csv_filename, "w");
            if (!csv_file) {
                fprintf(stderr, "Error: Failed to open CSV file %s\n", csv_filename);
                free(all_latencies);
                MPI_Abort(MPI_COMM_WORLD, 1);
                return 1;
            }

            // Write header
            fprintf(csv_file, "size (MB)");
            for (int r = 0; r < size; r++) {
                fprintf(csv_file, ",%d", r);
            }
            fprintf(csv_file, "\n");

            // Write data rows
            for (int i = 0; i < num_sizes; i++) {
                fprintf(csv_file, "%zu", sizes[i]);
                for (int r = 0; r < size; r++) {
                    fprintf(csv_file, ",%.2f", all_latencies[r * num_sizes + i]);
                }
                fprintf(csv_file, "\n");
            }

            fclose(csv_file);
            free(all_latencies);
        }

        // Free CSV filename
        free(csv_filename);
    }

    // Cleanup
    if (allocated_memory != NULL) {
        free(allocated_memory);
    }
    free(latencies);
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

/*
 * Measure memory latency using pointer chasing technique
 * 
 * This function:
 * 1. Creates a linked list of pointers in the allocated memory
 * 2. Randomizes the pointer chain to prevent CPU prefetching
 * 3. Uses volatile pointers to prevent compiler optimizations
 * 4. Measures the time taken to traverse this random path
 * 
 * Why pointer chasing?
 * - Forces actual memory accesses
 * - Prevents CPU prefetching by using random access pattern
 * - Each access must wait for the previous one to complete
 * 
 * Why volatile?
 * - Prevents compiler from optimizing away the pointer chase loop
 * - Ensures each memory access is actually performed
 * - Gives more accurate latency measurements
 * 
 * Parameters:
 *   memory: Pointer to the allocated memory region
 *   size: Size of the memory region in bytes
 * 
 * Returns:
 *   Average latency per memory access in nanoseconds
 */
static double measure_memory_latency(void *memory, size_t size) {
    // Set up the pointer-chasing linked list
    size_t num_pointers = size / sizeof(void*);
    void **pointers = (void**)memory;
    size_t *indices = NULL;
    
    // Create an array of indices and shuffle them
    indices = malloc(num_pointers * sizeof(size_t));
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
    volatile void **p = (volatile void **)&pointers[indices[0]];
    for (int i = 0; i < WARMUP_ITERATIONS; i++) {
        p = (volatile void **)*p;
    }
    
    // Measure memory access time
    double start_time = MPI_Wtime();
    
    // Chase pointers through memory
    p = (volatile void **)&pointers[indices[0]];
    for (int i = 0; i < LATENCY_ITERATIONS; i++) {
        p = (volatile void **)*p;
    }
    
    double end_time = MPI_Wtime();
    double total_time = end_time - start_time;
    
    // Calculate average latency in nanoseconds
    double latency_ns = (total_time * 1e9) / LATENCY_ITERATIONS;
    
    // Add a dummy use of p to prevent compiler optimization
    if (p == NULL) {
        fprintf(stderr, "Should never happen but prevents optimization\n");
    }
    
    // Clean up indices array
    free(indices);
    return latency_ns;
}

// Helper function to add a size to the size array if it's not already there
static int add_size_if_unique(size_t *sizes, int *num_sizes, size_t size_to_add) {
    // Check if we've hit the maximum number of sizes
    if (*num_sizes >= MAX_SIZES) {
        return -1; // Too many sizes
    }
    
    // Verify the size is positive
    if (size_to_add <= 0) {
        return -2; // Invalid size
    }
    
    // Check if size already exists in the array
    for (int i = 0; i < *num_sizes; i++) {
        if (sizes[i] == size_to_add) {
            return 0; // Size already exists, no need to add
        }
    }
    
    // Add the size to the array
    sizes[*num_sizes] = size_to_add;
    (*num_sizes)++;
    return 0;
}

static int parse_args(int argc, char *argv[], int *serial_mode, size_t *sizes, int *num_sizes, char **csv_filename, char **mapping_file) {
    *serial_mode = 0;
    *num_sizes = 0;
    *csv_filename = NULL;
    *mapping_file = NULL;
    int size_argument_found = 0;
    
    // Handle command line arguments
    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--serial") == 0) {
            *serial_mode = 1;
            continue;
        }
        
        // Check for --mapping option
        if (strncmp(argv[i], "--mapping=", 10) == 0) {
            *mapping_file = strdup(argv[i] + 10);
            if (!*mapping_file) {
                fprintf(stderr, "Error: Failed to allocate memory for mapping filename\n");
                return -1;
            }
            continue;
        }
        
        // Check for --csv option
        if (strncmp(argv[i], "--csv=", 6) == 0) {
            *csv_filename = strdup(argv[i] + 6);
            if (!*csv_filename) {
                fprintf(stderr, "Error: Failed to allocate memory for CSV filename\n");
                return -1;
            }
            continue;
        }
        
        // Check for --size option
        if (strncmp(argv[i], "--size=", 7) == 0) {
            char *size_str = argv[i] + 7;
            
            // Check if we already processed a size argument
            if (size_argument_found) {
                fprintf(stderr, "Error: Multiple --size arguments provided\n");
                return -1;
            }
            
            size_argument_found = 1;
            
            // Check for range format (e.g., 128-1024)
            char *dash = strchr(size_str, '-');
            if (dash) {
                *dash = '\0'; // Split the string at the dash
                char *start_str = size_str;
                char *end_str = dash + 1;
                
                // Parse start and end of range
                char *endptr;
                long start_size = strtol(start_str, &endptr, 10);
                if (*endptr != '\0' || start_size <= 0) {
                    fprintf(stderr, "Error: Invalid range start value '%s'\n", start_str);
                    return -1;
                }
                
                long end_size = strtol(end_str, &endptr, 10);
                if (*endptr != '\0' || end_size <= 0) {
                    fprintf(stderr, "Error: Invalid range end value '%s'\n", end_str);
                    return -1;
                }
                
                if (start_size > end_size) {
                    fprintf(stderr, "Error: Range start (%ld) is greater than range end (%ld)\n", 
                            start_size, end_size);
                    return -1;
                }
                
                // Find indices in standard size array
                int start_idx = -1, end_idx = -1;
                for (int j = 0; j < NUM_STANDARD_SIZES; j++) {
                    if (STANDARD_SIZES[j] >= (size_t)start_size && start_idx == -1) {
                        start_idx = j;
                    }
                    if (STANDARD_SIZES[j] <= (size_t)end_size) {
                        end_idx = j;
                    }
                }
                
                if (start_idx == -1 || end_idx == -1 || start_idx > end_idx) {
                    fprintf(stderr, "Error: Unable to find standard sizes in range %ld-%ld\n", 
                            start_size, end_size);
                    fprintf(stderr, "Valid range is from %zu to %zu MB\n", 
                            STANDARD_SIZES[0], STANDARD_SIZES[NUM_STANDARD_SIZES-1]);
                    return -1;
                }
                
                // Add all sizes in the range
                for (int j = start_idx; j <= end_idx; j++) {
                    if (add_size_if_unique(sizes, num_sizes, STANDARD_SIZES[j]) < 0) {
                        fprintf(stderr, "Error: Too many sizes specified (max %d)\n", MAX_SIZES);
                        return -1;
                    }
                }
            }
            // Check for comma-separated list (e.g., 128,512,1024)
            else if (strchr(size_str, ',')) {
                char *token;
                char *saveptr;
                char *size_list = strdup(size_str); // Create a copy to tokenize
                
                if (!size_list) {
                    fprintf(stderr, "Error: Memory allocation failed for size list\n");
                    return -1;
                }
                
                // Parse comma-separated list
                token = strtok_r(size_list, ",", &saveptr);
                while (token != NULL) {
                    char *endptr;
                    long parsed_size = strtol(token, &endptr, 10);
                    
                    if (*endptr != '\0' || parsed_size <= 0) {
                        fprintf(stderr, "Error: Invalid size value '%s' in list\n", token);
                        free(size_list);
                        return -1;
                    }
                    
                    if (add_size_if_unique(sizes, num_sizes, (size_t)parsed_size) < 0) {
                        fprintf(stderr, "Error: Too many sizes specified (max %d)\n", MAX_SIZES);
                        free(size_list);
                        return -1;
                    }
                    
                    token = strtok_r(NULL, ",", &saveptr);
                }
                
                free(size_list);
            }
            // Single value format (e.g., 512)
            else {
                char *endptr;
                long parsed_size = strtol(size_str, &endptr, 10);
                
                if (*endptr != '\0' || parsed_size <= 0) {
                    fprintf(stderr, "Error: Invalid size value '%s'\n", size_str);
                    return -1;
                }
                
                if (add_size_if_unique(sizes, num_sizes, (size_t)parsed_size) < 0) {
                    fprintf(stderr, "Error: Too many sizes specified (max %d)\n", MAX_SIZES);
                    return -1;
                }
            }
            
            continue;
        }
        
        // Unrecognized option
        fprintf(stderr, "Warning: Unrecognized option '%s'\n", argv[i]);
    }
    
    // If no size was specified, use the default
    if (*num_sizes == 0) {
        sizes[0] = DEFAULT_ALLOC_SIZE_MB;
        *num_sizes = 1;
    }
    
    return 0;
}

static void get_cpu_info(hwloc_topology_t topology, int *cpu_id, int *core_numa) {
    // Get current CPU directly using sched_getcpu
    #ifdef _GNU_SOURCE
    *cpu_id = sched_getcpu();
    #else
    *cpu_id = -1;
    #endif
    
    if (*cpu_id >= 0) {
        // Get NUMA node for the current CPU
        *core_numa = numa_node_of_cpu(*cpu_id);
        if (*core_numa == -1) {
            fprintf(stderr, "Warning: Could not determine NUMA node for CPU %d, defaulting to 0\n", *cpu_id);
            *core_numa = 0;
        }
    } else {
        // Fallback to hwloc if sched_getcpu fails
        hwloc_cpuset_t cpuset = hwloc_bitmap_alloc();
        if (hwloc_get_cpubind(topology, cpuset, 0) < 0) {
            hwloc_get_last_cpu_location(topology, cpuset, 0);
        }
        
        hwloc_obj_t obj = hwloc_get_first_largest_obj_inside_cpuset(topology, cpuset);
        if (obj) {
            *cpu_id = obj->logical_index;
            *core_numa = numa_node_of_cpu(*cpu_id);
        } else {
            *cpu_id = -1;
            *core_numa = -1;
        }
        
        hwloc_bitmap_free(cpuset);
    }
}

static int get_numa_node_of_address(void *addr) {
    unsigned long node;
    
    if (get_mempolicy((int *)&node, NULL, 0, addr, MPOL_F_NODE | MPOL_F_ADDR) == 0) {
        return (int)node;
    }
    
    return -1;
}

static void print_results_table_header(int num_sizes, size_t *sizes) {
    // Calculate the width for latency section based on number of sizes
    const int column_width = 9; // Fixed width for each column (7 for value + 1 space + 1 separator)
    int latency_section_width = num_sizes * column_width + 1; // +1 for final separator
    
    // Calculate padding for centering "LATENCY (ns)"
    int latency_text_length = 13; // Length of "LATENCY (ns)"
    int padding_before = (latency_section_width - latency_text_length) / 2;
    int padding_after = latency_section_width - latency_text_length - padding_before;
    
    // Calculate total width of the entire table
    int fixed_section_width = 40; // Width of MPI+CPU+MEMORY sections (reduced by 6)
    int total_width = fixed_section_width + latency_section_width;
    
    // Print top line
    printf("\n ");
    for (int i = 0; i < total_width; i++) {
        printf("=");
    }
    printf("\n");
    
    // Print header row with LATENCY centered
    printf("|  MPI  |        CPU     |            MEMORY    |");
    
    // Print padding before LATENCY
    for (int i = 0; i < padding_before; i++) {
        printf(" ");
    }
    
    printf("LATENCY (ns)");
    
    // Print padding after LATENCY
    for (int i = 0; i < padding_after; i++) {
        printf(" ");
    }
    printf("|\n");
    
    // Print first separator line
    printf("|-------|---------|------|----------|-------|");
    for (int i = 0; i < num_sizes; i++) {
        printf("--------|");
    }
    printf("\n");
    
    // Print column headers row
    printf("| Ranks | Cores   | NUMA | Address  | NUMA  |");
    
    // Print each size as a column header with fixed width, including MB unit
    for (int i = 0; i < num_sizes; i++) {
        // Format size with MB unit - always use MB
        char size_text[10];
        snprintf(size_text, sizeof(size_text), "%zuMB", sizes[i]);
        printf(" %-7s|", size_text);
    }
    printf("\n");
    
    // Print second separator line
    printf("|-------|---------|------|----------|-------|");
    for (int i = 0; i < num_sizes; i++) {
        printf("--------|");
    }
    printf("\n");
    
    fflush(stdout);
}

static void print_results_table_row(int rank, int world_size, int cpu_id, int core_numa, void *addr, int num_sizes, double *latencies) {
    // Suppress unused parameter warning
    (void)cpu_id;
    
    // Use strict ordering to print ranks sequentially
    for (int r = 0; r < world_size; r++) {
        if (rank == r) {
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
            
            // Get NUMA maps information
            char numa_maps_info[256] = "N/A";
            int node = get_numa_node_of_address(addr);
            if (node >= 0) {
                snprintf(numa_maps_info, sizeof(numa_maps_info), "%d", node);
            }
            
            // Print fixed part of the row
            printf("|  %03d  | %-7s |   %-2d | %-8p |   %-2s  |", 
                   rank, cpu_list, core_numa, addr, numa_maps_info);
            
            // Print each latency measurement with fixed width formatting (7 chars for value)
            for (int i = 0; i < num_sizes; i++) {
                printf(" %-6.2f |", latencies[i]);
            }
            
            printf("\n");
            fflush(stdout);
        }
        
        // Synchronize after each rank prints
        MPI_Barrier(MPI_COMM_WORLD);
    }
}

static void print_results_table_footer(int num_sizes) {
    // Calculate total width based on known dimensions
    const int column_width = 9; // Same as in header
    int latency_section_width = num_sizes * column_width + 1;
    int fixed_section_width = 40; // Width of MPI+CPU+MEMORY sections (reduced by 6)
    int total_width = fixed_section_width + latency_section_width;
    
    // Print bottom line with correct width
    printf(" ");
    for (int i = 0; i < total_width; i++) {
        printf("=");
    }
    printf("\n");
    fflush(stdout);
}

static int write_mapping_info(const char *filename, struct mapping_info *info, int world_size) {
    FILE *f = fopen(filename, "w");
    if (!f) {
        fprintf(stderr, "Error: Could not open mapping file %s for writing\n", filename);
        return -1;
    }
    
    // Write CSV header
    fprintf(f, "rank,cpu_id,cpu_numa,memory_numa\n");
    
    // Write each rank's info
    for (int i = 0; i < world_size; i++) {
        fprintf(f, "%d,%d,%d,%d\n",
                info[i].rank,
                info[i].cpu_id,
                info[i].cpu_numa,
                info[i].memory_numa);
    }
    
    fclose(f);
    return 0;
}

static int collect_mapping_info(const char *mapping_file, int rank, int size, 
                              int cpu_id, int core_numa, void *addr) {
    struct mapping_info my_info;
    struct mapping_info *all_info = NULL;
    
    // Fill in local information
    my_info.rank = rank;
    my_info.cpu_id = cpu_id;
    my_info.cpu_numa = core_numa;
    my_info.memory_numa = get_numa_node_of_address(addr);
    
    // Allocate buffer on rank 0
    if (rank == 0) {
        all_info = malloc(size * sizeof(struct mapping_info));
        if (!all_info) {
            fprintf(stderr, "Error: Failed to allocate memory for mapping info\n");
            return -1;
        }
    }
    
    // Gather all information to rank 0
    MPI_Gather(&my_info, sizeof(struct mapping_info), MPI_BYTE,
               all_info, sizeof(struct mapping_info), MPI_BYTE,
               0, MPI_COMM_WORLD);
    
    // Rank 0 writes the mapping file
    if (rank == 0) {
        int ret = write_mapping_info(mapping_file, all_info, size);
        free(all_info);
        if (ret != 0) {
            return -1;
        }
        printf("Mapping information written to %s\n", mapping_file);
    }
    
    return 0;
} 
