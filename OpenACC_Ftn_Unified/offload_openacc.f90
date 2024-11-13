program gpu_unified_memory_benchmark
    use iso_fortran_env
    use openacc
    implicit none

    ! Precision and array size parameters
    integer, parameter :: dp = real64
    integer, parameter :: KB = 1024
    integer, parameter :: MB = 1024 * KB
!    integer(kind=8), parameter :: ARRAY_SIZES(4) = [1024_8, 2048_8, 4096_8, 8192_8]
!    integer(kind=8), parameter :: ARRAY_SIZES(6) = [8192_8, 16384_8, 32768_8, 65536_8, 131072_8, 262144_8]
    integer(kind=8), parameter :: ARRAY_SIZES(8) = [1024_8, 2048_8, 4096_8, 8192_8, 12288_8, 14336_8, 15360_8, 16384_8]

    integer, parameter :: NUM_ITERATIONS = 4

    ! Variables for timing and results
    real(dp) :: start_time, end_time
    real(dp), allocatable :: timing_results(:)
    real(dp) :: bandwidth, flops
    integer(kind=8) :: count_rate, count_max, count1, count2

    ! Arrays for computation
    real(dp), allocatable :: A(:,:), B(:,:), C(:,:)
    integer :: i, j, size_idx, iter
    logical :: success

    ! Arrays for storing summary statistics
    real(dp), allocatable :: summary_matrix_sizes(:)
    real(dp), allocatable :: summary_bandwidths(:)
    real(dp), allocatable :: summary_gflops(:)
    real(dp), allocatable :: summary_avg_times(:)

    ! Allocate summary arrays
    allocate(summary_matrix_sizes(size(ARRAY_SIZES)))
    allocate(summary_bandwidths(size(ARRAY_SIZES)))
    allocate(summary_gflops(size(ARRAY_SIZES)))
    allocate(summary_avg_times(size(ARRAY_SIZES)))

    ! Get the system clock rate
    call system_clock(count_rate=count_rate, count_max=count_max)
    print *, "System clock rate:", count_rate

    ! Allocate timing results array
    allocate(timing_results(NUM_ITERATIONS))

    ! Test different array sizes
    do size_idx = 1, size(ARRAY_SIZES)
        print *, ""
        print *, "Testing array size:", ARRAY_SIZES(size_idx), "x", ARRAY_SIZES(size_idx)

        ! Allocate arrays with current size
        allocate(A(ARRAY_SIZES(size_idx), ARRAY_SIZES(size_idx)))
        allocate(B(ARRAY_SIZES(size_idx), ARRAY_SIZES(size_idx)))
        allocate(C(ARRAY_SIZES(size_idx), ARRAY_SIZES(size_idx)))

        ! Initialize data
        !$acc kernels
        do i = 1, ARRAY_SIZES(size_idx)
            do j = 1, ARRAY_SIZES(size_idx)
                A(i,j) = real(i * j, dp)
                B(i,j) = 2.0_dp * real(i * j, dp)
                C(i,j) = 0.0_dp  ! Initialize C to zero
            end do
        end do
        !$acc end kernels

        ! Warm-up run
        !$acc parallel loop collapse(2)
        do i = 1, ARRAY_SIZES(size_idx)
            do j = 1, ARRAY_SIZES(size_idx)
                C(i,j) = A(i,j) * B(i,j)
            end do
        end do
        !$acc end parallel loop

        ! Benchmark loop
        do iter = 1, NUM_ITERATIONS
            ! Reset C before each iteration
            !$acc kernels
            do i = 1, ARRAY_SIZES(size_idx)
                do j = 1, ARRAY_SIZES(size_idx)
                    C(i,j) = 0.0_dp
                end do
            end do
            !$acc end kernels

            ! Start timing
            call system_clock(count=count1)

            ! Compute kernel
            !$acc parallel loop collapse(2)
            do i = 1, ARRAY_SIZES(size_idx)
                do j = 1, ARRAY_SIZES(size_idx)
                    C(i,j) = A(i,j) * B(i,j)
                end do
            end do
            !$acc end parallel loop

            ! End timing
            call system_clock(count=count2)

            ! Calculate elapsed time
            timing_results(iter) = real(count2 - count1, dp) / real(count_rate, dp)

            ! Verify results after each iteration
            if (iter == 1) then  ! Only verify first iteration
                call verify_results(A, B, C, ARRAY_SIZES(size_idx), success)
                if (.not. success) then
                    print *, "Verification failed at iteration:", iter
                    exit
                end if
            end if
        end do

        if (success) then
            ! Calculate statistics and store for summary
            call calculate_stats(ARRAY_SIZES(size_idx), timing_results, &
                               summary_matrix_sizes(size_idx), &
                               summary_bandwidths(size_idx), &
                               summary_gflops(size_idx), &
                               summary_avg_times(size_idx))
        end if

        ! Cleanup
        deallocate(A, B, C)
        print *, "------------------------------------------------------------"
    end do

    ! Print summary table
    call print_summary_table(size(ARRAY_SIZES), &
                           summary_matrix_sizes, &
                           summary_bandwidths, &
                           summary_gflops, &
                           summary_avg_times)

    ! Cleanup
    deallocate(timing_results)
    deallocate(summary_matrix_sizes)
    deallocate(summary_bandwidths)
    deallocate(summary_gflops)
    deallocate(summary_avg_times)

contains

    subroutine calculate_stats(N, timings, matrix_size, bandwidth, gflops, avg_time)
        integer(kind=8), intent(in) :: N
        real(dp), intent(in) :: timings(:)
        real(dp), intent(out) :: matrix_size, bandwidth, gflops, avg_time
        real(dp) :: min_time, max_time, stddev
        real(dp) :: data_size_gb
        integer :: i

        min_time = minval(timings)
        max_time = maxval(timings)
        avg_time = sum(timings) / size(timings)

        ! Calculate standard deviation
        stddev = 0.0_dp
        do i = 1, size(timings)
            stddev = stddev + (timings(i) - avg_time)**2
        end do
        stddev = sqrt(stddev / size(timings))

        ! Calculate data size in GB (3 arrays: A, B, C)
        data_size_gb = (3.0_dp * N * N * 8.0_dp) / (1024.0_dp**3)
        matrix_size = data_size_gb

        ! Calculate bandwidth in GB/s
        bandwidth = data_size_gb / min_time

        ! Calculate GFLOPS (1 multiplication per element)
        gflops = (1.0_dp * N * N) / (min_time * 1.0e9_dp)

        print '(A,F10.6)', "Min time (s):   ", min_time
        print '(A,F10.6)', "Max time (s):   ", max_time
        print '(A,F10.6)', "Avg time (s):   ", avg_time
        print '(A,F10.6)', "StdDev (s):     ", stddev
        print '(A,F10.2)', "Bandwidth GB/s: ", bandwidth
        print '(A,F10.2)', "GFLOPS:        ", gflops
        print '(A,F10.2)', "Matrix size GB: ", data_size_gb
    end subroutine calculate_stats

    subroutine print_summary_table(n_sizes, matrix_sizes, bandwidths, gflops, avg_times)
        integer, intent(in) :: n_sizes
        real(dp), intent(in) :: matrix_sizes(:), bandwidths(:), gflops(:), avg_times(:)
        integer :: i

        print *, ""
        print *, "Summary Table"
        print *, "----------------------------------------"
        print *, "Matrix Size (GB) | Bandwidth (GB/s) | GFLOPS | Avg Time (s)"
        print *, "----------------------------------------"
        do i = 1, n_sizes
            print '(F14.2, " |", F16.2, " |", F8.2, " |", F12.6)', &
                  matrix_sizes(i), bandwidths(i), gflops(i), avg_times(i)
        end do
        print *, "----------------------------------------"
    end subroutine print_summary_table

    subroutine verify_results(A, B, C, N, success)
        real(dp), intent(in) :: A(:,:), B(:,:), C(:,:)
        integer(kind=8), intent(in) :: N
        logical, intent(out) :: success
        integer :: i, j
        real(dp) :: expected, actual
        real(dp), parameter :: TOLERANCE = 1.0e-10_dp

        success = .true.
        verification: do i = 1, N
            do j = 1, N
                expected = A(i,j) * B(i,j)
                actual = C(i,j)
                if (abs(actual - expected) > TOLERANCE) then
                    print *, "Verification failed at (", i, ",", j, ")"
                    print *, "Expected:", expected, "Actual:", actual
                    print *, "A(i,j):", A(i,j), "B(i,j):", B(i,j)
                    success = .false.
                    exit verification
                end if
            end do
        end do verification

        if (success) then
            print *, "Result verification: PASSED"
        else
            print *, "Result verification: FAILED"
        end if
    end subroutine verify_results

end program gpu_unified_memory_benchmark