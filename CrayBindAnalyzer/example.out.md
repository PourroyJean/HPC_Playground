=================================================================
|   Node    |  MPI  |  2 x 64 cores x 2 threads | NIC (4 avail)  |
|   name    | ranks | Cores (total) |   NUMA    | NIC ID  | NUMA |
|-----------|- ---- |---------------|-----------|---------|------|
| nid005531 |  000  | 1-18    (18)  | 0         | cxi0    | 3    |
| nid005531 |  001  | 9,73     (2)  | 0         | cxi1    | 1    |
| nid005531 |  002  | 17,81    (2)  | 1         | cxi2    | 0    |
| nid005532 |  002  | 25,89    (2)  | 2         | cxi2    | 2    |
| nid005532 |  002  | 2,66     (2)  | 0         | cxi3    | 2    |
| nid005532 |  003  | 10,74    (2)  | 0         | cxi1    | 1    |
=================================================================


comments :
"2 x 640 cores x 2 threads"
 - 2 is the number of sockets : find a way to find it ?
 - 64 is the number of physical cores
 - 2 threads if hyperthread is enabled : if two list for one numa domain numa_domain 0: cpu_list=[0-15,64-79] ?

"1-18    (18)"
 - 1-18 is the list of cores, it can be complexe like, 1,3,5,7-18
 - (18) is the number of cores in the list

"0,1,3,4 ⚠️"
 - NUMA : it can have several NUMA for one MPI task.
 - ⚠️ : we set a danger if it is the case

"NIC (4)"
 - 4 is the total number of NIC found.
