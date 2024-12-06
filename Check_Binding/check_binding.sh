#!/bin/bash
#
# GENERAL OPTIONS
#SBATCH --account project_462000031
#SBATCH --partition standard
##SBATCH --reservation ??
#SBATCH --job-name=check                
#SBATCH --constraint=                   
#SBATCH --time=00:10:00                 # Job time limit (HH:MM:SS)
#SBATCH --output=run_%x-%j.out          # Standard output file name-jobid
#SBATCH --exclusive                     # We don't share nodes with others
#SBATCH --nodes=3 
#SBATCH --hint=multithread

EXE="xthi_mpi_mp"

#This function is used to print a nice output from the xthi program
XTHI_PRINTER(){
    awk '
    BEGIN {
        # Flag to check if we have printed the node summary
        have_summary=0
    }

    # Print the initial node summary lines as they are
    /^Node summary for/ {
        print
        have_summary=1
        next
    }

    # Lines that map a node number to a hostname, store them in an array
    # Example: "Node    0, hostname nid001216, ..."
    /^Node[[:space:]]+[0-9]+, hostname/ {
        print
        # Extract node number
        match($0, /Node[[:space:]]+([0-9]+)/, n_arr)
        # Extract hostname
        match($0, /hostname[[:space:]]+(nid[0-9]+)/, host_arr)
        node_host[n_arr[1]] = host_arr[1]
        next
    }

    # MPI summary line (e.g. "MPI summary: 10 ranks"), print it and then print the table header
    /^MPI summary:/ {
        print
        # Print table header
        printf(" ________________________________________________________________\n")
        printf("| %-10s | %-8s | %-6s | %-19s | %-7s |\n", "HOSTNAME", "MPI TASK", "THREAD", "      AFFINITY ", " TOTAL")
        printf("|----------------------------------------------------------------|\n")
        last_host=""
        last_rank=""
        thread_total=0
        rank_total=0
        next
    }

    # Lines with actual rank/thread/affinity info
    # Example: "Node    0, rank    0, thread   0, (affinity =    0)"
    /Node[[:space:]]+[0-9]+, rank[[:space:]]+[0-9]+, thread[[:space:]]+[0-9]+/ {
        # Extract node number
        match($0, /Node[[:space:]]+([0-9]+)/, node_arr)
        # Extract rank number
        match($0, /rank[[:space:]]+([0-9]+)/, rank_arr)
        # Extract thread number
        match($0, /thread[[:space:]]+([0-9]+)/, thread_arr)
        # Extract affinity value
        match($0, /\(affinity[[:space:]]*=[[:space:]]*([0-9]+)\)/, affinity_arr)

        # Assign extracted values to scalar variables for clarity
        node_id = node_arr[1]
        r = rank_arr[1]
        t = thread_arr[1]
        aff_val = affinity_arr[1]

        # Retrieve hostname from the node_host array
        h = node_host[node_id]

        # Increment the total number of threads encountered
        thread_total++

        # Here we assume only a single affinity value per line, so total=1
        # If needed, you can reintroduce logic to parse comma-separated or ranged lists.
        affinity_total=1

        # Determine how to print the rank column: only show "rank X" for the first thread of that rank
        if (r == last_rank) {
            rank_str="   ,,   "
        } else {
            rank_total++
            last_rank=r
            rank_str="rank " r
        }

        # Determine how to print the hostname column: only show the hostname for the first rank of that host
        if (h == last_host) {
            host_str="----------"
        } else {
            last_host=h
            host_str=h
        }

        # Print the formatted line
        printf("| %10s | %8s | %6d | %-19s | %7d |\n", host_str, rank_str, t, aff_val, affinity_total)
        next
    }

    END {
        # After processing all lines, print the bottom of the table and the summary
        if (rank_total > 0) {
            printf("|________________________________________________________________|\n")
            # Calculate threads per rank = total threads / total ranks
            # and print a final summary line
            printf("--> %s MPI ranks with %s threads each (total number of threads: %s)\n", rank_total, thread_total/rank_total, thread_total)
        }
    }'
}

SRUN() {
  echo -e "\n"
  printf "export %s=%s\n" "OMP_PROC_BIND" $OMP_PROC_BIND
  printf "export %s=%s\n" "OMP_PLACES" $OMP_PLACES
  printf "export %s=%s\n" "OMP_NUM_THREADS" $OMP_NUM_THREADS
  echo   "srun $@" >&1
  srun "$@" | XTHI_PRINTER
  wait
}

#Default options
export OMP_PROC_BIND=close
export OMP_PLACES=sockets
export OMP_NUM_THREADS=2
export OMP_WAIT_POLICY=PASSIVE

##### DISTRIBUTION LEVEL 1 - BETWEEN NODES #####
SRUN --nodes 3 --ntasks 10 --distribution=block --hint=multithread $EXE 
SRUN --nodes 3 --ntasks 10 --distribution=cyclic --hint=multithread $EXE
SRUN --nodes 3 --ntasks 10 --distribution=plane=2 --hint=multithread $EXE 



##### DISTRIBUTION LEVEL 2 - INSIDE NODE #####

SRUN --nodes 1 --ntasks 256 --distribution=block:block --hint=multithread $EXE 
SRUN --nodes 1 --ntasks 256 --distribution=block:cyclic --hint=multithread $EXE
SRUN --nodes 1 --ntasks 128 --distribution=block:fcyclic --hint=multithread $EXE

##### Custom binding
export bind="0,2,16,18,32,34,48,50"
SRUN --nodes 1 -n 8 --cpu-bind=map_cpu:${bind} $EXE
# Hexadecimal mask
export bind=0x3,0x30000,0x300000000,0x3000000000000 
SRUN -N 1 -n 4 --cpu-bind=mask_cpu:${bind} $EXE



##### DISTRIBUTION LEVEL 3 - THREADS PLACEMENT #####

## FIRST: CHECK WHERE THE MPI RANKS ARE PINNED
# Here we create 1 tasks per numa node (cyclic) and check the maximum visible cores (sockets)
export OMP_PLACES=sockets
export OMP_NUM_THREADS=1
SRUN --nodes 1 -n 8 -c 32 --distribution=block:cyclic: --hint=multithread $EXE 

##### DISTRIBUTION LEVEL 3 - OMP_PLACES

#CLOSE + threads
export OMP_PROC_BIND=close
export OMP_PLACES=threads
export OMP_NUM_THREADS=4
SRUN --nodes 1 -n 8 -c 32 --distribution=block:cyclic: --hint=multithread $EXE 

#CLOSE + cores
export OMP_PROC_BIND=close
export OMP_PLACES=cores
export OMP_NUM_THREADS=4
SRUN --nodes 1 -n 8 -c 32 --distribution=block:cyclic: --hint=multithread $EXE 

# SPREAD + threads
export OMP_PROC_BIND=spread
export OMP_PLACES=threads
export OMP_NUM_THREADS=4
SRUN --nodes 1 -n 8 -c 32 --distribution=block:cyclic: --hint=multithread $EXE

# SPREAD + cores
export OMP_PROC_BIND=spread
export OMP_PLACES=cores
export OMP_NUM_THREADS=4
SRUN --nodes 1 -n 8 -c 32 --distribution=block:cyclic: --hint=multithread $EXE

#MASTER + threads
export OMP_PROC_BIND=master
export OMP_PLACES=threads
export OMP_NUM_THREADS=4
SRUN --nodes 1 -n 8 -c 32 --distribution=block:cyclic: --hint=multithread $EXE

#MASTER + cores
export OMP_PROC_BIND=master
export OMP_PLACES=cores
export OMP_NUM_THREADS=4
SRUN --nodes 1 -n 8 -c 32 --distribution=block:cyclic: --hint=multithread $EXE

# FALSE + threads/cores/sockets/
export OMP_PROC_BIND=false
export OMP_PLACES=cores
export OMP_NUM_THREADS=4
SRUN --nodes 1 -n 8 -c 32 --distribution=block:cyclic: --hint=multithread $EXE
