#!/bin/bash
#
# GENERAL OPTIONS
#SBATCH --account project_465001098
#SBATCH --partition standard
#SBATCH --reservation LUMItraining_C
#SBATCH --job-name=check                
#SBATCH --constraint=                   
#SBATCH --time=00:10:00                 # Job time limit (HH:MM:SS)
#SBATCH --output=run_%x-%j.out          # Standard output file name-jobid
#SBATCH --exclusive                     # We don't share nodes with others
#SBATCH --nodes=3 
#SBATCH --hint=multithread

EXE="xthi"

#This function is used to print a nice output from the xthi program
XTHI_PRINTER(){
    sort -k4n -k6n | awk 'BEGIN {
    printf(" ________________________________________________________________\n")
    printf("| %-10s | %-8s | %-6s | %-19s | %-7s |\n", "HOSTNAME", "MPI TASK", "THREAD", "      AFFINITY ", " TOTAL")
    printf("|----------------------------------------------------------------|\n")
    last_host = ""; last_rank = "" ; host_str "" ; thread_total = 0 ; rank_total = 0
}
#only treat lines with "nid"
/nid/{
    match($0, /on (nid[0-9]+)/, host)
    match($0, /rank ([0-9]+)/, rank)
    match($0, /thread ([0-9]+)/, thread)
    match($0, /= (.*)\)/, affinity)

    #each xthi line is a thread
    thread_total++

    #Calculate the number of value (cores) in affinity
    affinity_total = 0
    split(affinity[1], values, ",")
    for (i in values) {
        if (values[i] ~ /-/) {
            split(values[i], range, "-")
            affinity_total += range[2] - range[1] + 1
        } else {
            affinity_total++
        }
    }

    # The MPI rank is only displayed once
    if (rank[1] == last_rank) {
        # printf ("equal : rank[1](%s), last_rank(%s)", rank[1], last_rank)
        rank_str = "   ,,   "
    } else {
        rank_total++
        last_rank = rank[1]
        rank_str = "rank " rank[1]
    }

    # The hostname is only displayed once
    if (host[1] == last_host) {
        # printf ("equal : host[1](%s), last_host(%s)", host[1], last_host)
        host_str = "----------"
    } else {
        # printf ("host[1](%s), last_host(%s)", host[1], last_host)
        last_host = host[1]
        host_str = host[1]
    }
    
    # FINAL PRINT
    printf("| %10s | %8s | %6s | %-19s | %7s |\n", host_str, rank_str, thread[1], affinity[1], affinity_total)
    
}
END{
    printf("|________________________________________________________________|\n")
    printf("--> %s MPI ranks with %s threads each (total number of threads: %s)\n", rank_total, thread_total/rank_total, thread_total)
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
