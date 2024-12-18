#!/usr/bin/env bash

# Load required configuration variables from an external file
source ./config.sh

# Read the list of hosts from a file, filtering out empty lines
mapfile -t HOSTS < hosts.txt
TMP=()
for h in "${HOSTS[@]}"; do
    [[ -n "$h" ]] && TMP+=("$h")
done
HOSTS=("${TMP[@]}")

# Initialize arrays for tracking host states
FAILED_HOSTS=()
PREV_FAILED_HOSTS=()
TEMP_FAILED_HOSTS=()

# Create log directory if it doesn't exist and redirect stdout/stderr to the application log
mkdir -p "$(dirname "$APP_LOGFILE")"
exec 1>> "$APP_LOGFILE"
exec 2>> "$APP_LOGFILE"

# Track if this is the first run of the monitoring loop
FIRST_RUN=true

# Logs the result of a host check to the test log file
# Parameters:
#   $1: Timestamp
#   $2: Hostname
#   $3: Status (accessible/inaccessible)
#   $4: Return code
log_result() {
    echo "$1,$2,$3,ret=$4" >> "$TEST_LOGFILE"
}

# Sends an email alert with the provided subject and body
# Parameters:
#   $1: Email subject
#   $2: Email body
send_alert() {
    echo -e "$2" | mail -s "$1" "$RECIPIENT"
    echo "Email alert sent to $RECIPIENT" >> "$APP_LOGFILE"
}

# Checks host accessibility using `ncat` with retries and logging
# Parameters:
#   $1: Hostname
#   $2: Timestamp
#   $3: Enable verbose logging (true/false)
# Updates: SUCCESS_HOSTS or TEMP_FAILED_HOSTS
check_host() {
    local host="$1" timestamp="$2" do_log="${3:-false}" output retcode

    # Attempt 1: Basic connection check
    output=$(ncat --proxy "$PROXY" --proxy-type http "$host" "$PORT" -w"$TIMEOUT" < /dev/null 2>&1)
    retcode=$?

    # Host accessible if output contains SSH banner
    if [[ $output == *"SSH-"* ]]; then
        [[ "$do_log" == "true" ]] && log_result "$timestamp" "$host" "accessible" "$retcode"
        SUCCESS_HOSTS+=("$host")
        return 0
    fi

    # Attempt 2: Verbose connection check with extended timeout
    if [[ "$do_log" == "true" ]]; then
        local start_time=$(date +%s.%N)
        output=$(ncat -v --proxy "$PROXY" --proxy-type http "$host" "$PORT" -w"$((TIMEOUT*2))" < /dev/null 2>&1)
        retcode=$?
        local duration=$(echo "$(date +%s.%N) - $start_time" | bc)

        if [[ $output == *"SSH-"* ]]; then
            log_result "$timestamp" "$host" "accessible" "$retcode"
            SUCCESS_HOSTS+=("$host")
            return 0
        fi

        # Log details of the verbose failed attempt
        {
            echo "=== Detailed connection attempt for $host ==="
            echo "Timestamp: $timestamp"
            echo "Command: ncat -v --proxy $PROXY --proxy-type http $host $PORT -w$((TIMEOUT*2))"
            echo "Return code: $retcode"
            echo "Duration: ${duration}s"
            echo "Output:"
            echo "$output"
            echo "==================================="
        } >> "$APP_LOGFILE"

        log_result "$timestamp" "$host" "inaccessible" "$retcode"
    fi

    TEMP_FAILED_HOSTS+=("$host")
    return 1
}

# Prepares the alert message containing the check results
# Parameters:
#   $1: Timestamp
#   $2: Newly failed hosts (array reference)
#   $3: Accessible hosts (array reference)
#   $4: Failed hosts (array reference)
# Returns: Formatted alert message
prepare_alert_message() {
    local timestamp="$1"
    local -n new_fails="$2" successes="$3" failures="$4"

    local message="Hello,\n\n"
    message+="The following hosts became inaccessible during the latest check (performed at $timestamp):\n\n"
    for host in "${new_fails[@]}"; do
        message+=" - $host\n"
    done

    message+="\n--- All Results from the Latest Check ---\n\n"
    message+="Accessible hosts:\n"
    for host in "${successes[@]}"; do
        message+=" - $host\n"
    done

    message+="\nInaccessible hosts:\n"
    for host in "${failures[@]}"; do
        message+=" - $host\n"
    done

    message+="\nRegards,\nYour monitoring script"
    echo -e "$message"
}

# Main monitoring loop: continuously checks hosts and logs results
while true; do
    source ./config.sh  # Reload configuration

    FAILED_HOSTS=()
    SUCCESS_HOSTS=()
    NEWLY_FAILED_HOSTS=()
    TEMP_FAILED_HOSTS=()

    # First pass: Non-verbose host checks with retries
    for HOST in "${HOSTS[@]}"; do
        host_failed=true
        for attempt in $(seq 1 3); do
            TEST_TIME=$(date -Iseconds)
            if check_host "$HOST" "$TEST_TIME" "false"; then
                host_failed=false
                break
            fi
            sleep "$HOST_DELAY"
        done
        [[ "$host_failed" == "true" ]] && TEMP_FAILED_HOSTS+=("$HOST")
    done

    # Second pass: Verbose retries for failed hosts
    if [[ ${#TEMP_FAILED_HOSTS[@]} -gt 0 ]]; then
        echo "Retrying failed hosts: ${TEMP_FAILED_HOSTS[*]}" >> "$APP_LOGFILE"
        for HOST in "${TEMP_FAILED_HOSTS[@]}"; do
            TEST_TIME=$(date -Iseconds)
            if check_host "$HOST" "$TEST_TIME" "true"; then
                echo "Host $HOST recovered after retry" >> "$APP_LOGFILE"
            else
                if [[ "$FIRST_RUN" != "true" ]]; then
                    if [[ " ${PREV_FAILED_HOSTS[@]} " =~ " ${HOST}:" ]]; then
                        FAILED_HOSTS+=("${HOST}:${TEST_TIME}")
                    else
                        NEWLY_FAILED_HOSTS+=("${HOST}:${TEST_TIME}")
                        echo "$TEST_TIME,$HOST" >> "$FAILED_HOSTS_LOG"
                    fi
                fi
            fi
            sleep "$HOST_DELAY"
        done
    fi

    # Log successful hosts
    for HOST in "${SUCCESS_HOSTS[@]}"; do
        if [[ ! " ${TEMP_FAILED_HOSTS[@]} " =~ " ${HOST} " ]]; then
            log_result "$(date -Iseconds)" "$HOST" "accessible" "0"
        fi
    done

    # Send alerts if there are newly failed hosts
    if [[ ${#NEWLY_FAILED_HOSTS[@]} -gt 0 ]]; then
        SUBJECT="[LR4 Alert] - Host(s) became inaccessible"
        BODY=$(prepare_alert_message "$TEST_TIME" NEWLY_FAILED_HOSTS SUCCESS_HOSTS FAILED_HOSTS)
        if [[ "$SEND_EMAIL" == "true" ]]; then
            send_alert "$SUBJECT" "$BODY"
        else
            echo -e "$BODY" >> "$APP_LOGFILE"
            echo "Email notifications are disabled" >> "$APP_LOGFILE"
        fi
    fi

    # Update previous failures and proceed to the next cycle
    FIRST_RUN=false
    PREV_FAILED_HOSTS=("${FAILED_HOSTS[@]}")
    echo "Check cycle completed at $(date)" >> "$APP_LOGFILE"
    sleep "$INTERVAL"
done
