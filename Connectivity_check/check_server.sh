#!/usr/bin/env bash

# Read the list of hosts from a file, filtering out empty lines
read_hosts() {
    # Read only the IP addresses (first column) from hosts.csv
    HOSTS=()
    while IFS=, read -r ip owner || [[ -n "$ip" ]]; do
        HOSTS+=("$ip")
    done < "./hosts.csv"

    if [[ "$DEBUG" == "true" ]]; then
        echo "Hosts: ${HOSTS[@]}" >> "$APP_LOGFILE"
fi

}


# Logs the result of a host check to the test log file
# Parameters:
#   $1: Timestamp
#   $2: Hostname
#   $3: Status (accessible/inaccessible)
#   $4: Attempt number
log_result() {
    echo "$1,$2,$3,$4" >> "$TEST_LOGFILE"
}

# Sends an email alert with the provided subject and body
# Parameters:
#   $1: Email subject
#   $2: Email body
send_alert() {
    echo -e "$2" | mail -s "$1" "$RECIPIENT"
    echo "Email alert sent to $RECIPIENT" >> "$APP_LOGFILE"
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

# Checks host accessibility using `ncat` with two different modes
# Parameters:
#   $1: Hostname
#   $2: Timestamp
#   $3: Enable verbose logging (true/false)
#   $4: Attempt number (1-MAX_ATTEMPT for first pass, MAX_ATTEMPT+1 for second pass)
# Returns: 0 if host is accessible, 1 otherwise
check_host() {
    local host="$1" timestamp="$2" do_log="${3:-false}" attempt="${4:-1}" output

    if [[ "$do_log" == "false" ]]; then
        # Mode 1: Quick check with basic timeout
        output=$(ncat --proxy "$PROXY" --proxy-type http "$host" "$PORT" -w"$TIMEOUT" < /dev/null 2>&1)
        if [[ $output == *"SSH-"* ]]; then
            log_result "$timestamp" "$host" "accessible" "$attempt"
            return 0
        else
            return 1
        fi
    else
        # Mode 2: Verbose check with extended timeout and detailed logging
        output=$(ncat -v --proxy "$PROXY" --proxy-type http "$host" "$PORT" -w"$((TIMEOUT*2))" < /dev/null 2>&1)
        if [[ $output == *"SSH-"* ]]; then
            log_result "$timestamp" "$host" "accessible" "$attempt"
            return 0
        else
            #log only if host is newly failed (not part of FAILED_HOSTS_PREV)
            if [[ ! " ${FAILED_HOSTS_PREV[@]} " =~ " ${host}:" ]]; then
                {
                    echo "=== Detailed connection attempt for $host ==="
                    echo "Timestamp: $timestamp"
                    echo "Command: ncat -v --proxy $PROXY --proxy-type http $host $PORT -w$((TIMEOUT*2))"
                    echo "Attempt number: $attempt"
                    echo "Output:"
                    echo "$output"
                    echo "==================================="
                } >> "$APP_LOGFILE"
                log_result "$timestamp" "$host" "inaccessible" "$attempt"
            fi
            return 1
        fi
    fi
}

# ------------------------------------------------------------------------------------------------
# ------------------------------------------------------------------------------------------------
# ------------------------------------------------------------------------------------------------
# Load required configuration variables from an external file
source ./config.sh
# Create log directory if it doesn't exist and redirect stdout/stderr to the application log
mkdir -p "$(dirname "$APP_LOGFILE")"
exec 1>> "$APP_LOGFILE"
exec 2>> "$APP_LOGFILE"



# Initialize arrays for tracking host states
FAILED_HOSTS=()      #failed hosts this cycle    
FAILED_HOSTS_PREV=() #failed hosts from previous cycle
TEMP_FAILED_HOSTS=() #failed hosts this cycle that will be retried
FIRST_RUN=true #true for the first run, false for the following runs

# Read the hosts from hosts.csv
read_hosts

echo "Number of hosts: ${#HOSTS[@]}" >> "$APP_LOGFILE"


# Main monitoring loop: continuously checks hosts and logs results
while true; do
    source ./config.sh      # Reload configuration
    SUCCESS_HOSTS=()        # Will contain all currently successful hosts
    FAILED_HOSTS=()         # Will contain all currently failed hosts
    NEWLY_FAILED_HOSTS=()   # Will contain hosts that newly failed this iteration
    TEMP_FAILED_HOSTS=()    # Temporary storage for first pass failures

    # First pass: Non-verbose host checks with retries
    for HOST in "${HOSTS[@]}"; do
        host_failed=true
        for attempt in $(seq 1 "$MAX_ATTEMPT"); do
        sleep "$HOST_DELAY"
            TEST_TIME=$(date -Iseconds)
            if check_host "$HOST" "$TEST_TIME" "false" "$attempt"; then
                SUCCESS_HOSTS+=("$HOST")
                host_failed=false
                break
            fi
            
        done
        [[ "$host_failed" == "true" ]] && TEMP_FAILED_HOSTS+=("$HOST")
    done

    # Second pass: Verbose retries for failed hosts
    if [[ ${#TEMP_FAILED_HOSTS[@]} -gt 0 ]]; then
        [[ "$DEBUG" == "true" ]] && echo "Retrying failed hosts: ${TEMP_FAILED_HOSTS[*]}" >> "$APP_LOGFILE"
        for HOST in "${TEMP_FAILED_HOSTS[@]}"; do
        sleep "$HOST_DELAY"  # Add sleep between different hosts
            TEST_TIME=$(date -Iseconds)
            if check_host "$HOST" "$TEST_TIME" "true" "$((MAX_ATTEMPT + 1))"; then
                SUCCESS_HOSTS+=("$HOST")
                [[ "$DEBUG" == "true" ]] && echo "Host $HOST recovered after retry" >> "$APP_LOGFILE"
            else
                FAILED_HOSTS+=("${HOST}:${TEST_TIME}")
                if [[ "$FIRST_RUN" != "true" ]]; then
                    if [[ ! " ${FAILED_HOSTS_PREV[@]} " =~ " ${HOST}:" ]]; then
                        # Host is newly failed this iteration
                        NEWLY_FAILED_HOSTS+=("${HOST}:${TEST_TIME}")
                        echo "$TEST_TIME,$HOST" >> "$FAILED_HOSTS_LOG"
                    fi
                fi
            fi
            
        done
    fi



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
    FAILED_HOSTS_PREV=("${FAILED_HOSTS[@]}")
    echo "Check cycle completed at $(date)" >> "$APP_LOGFILE"
    sleep "$INTERVAL"

        # Log results only if DEBUG is true
    if [[ "$DEBUG" == "true" ]]; then
        echo "---------------- END OF CYCLE ------------------------" >> "$APP_LOGFILE"
        echo "  # Successful hosts: ${SUCCESS_HOSTS[*]}" >> "$APP_LOGFILE"
        echo "  # Failed hosts: ${FAILED_HOSTS[*]}" >> "$APP_LOGFILE"
        echo "  # Newly failed hosts: ${NEWLY_FAILED_HOSTS[*]}" >> "$APP_LOGFILE"
        echo "  # Total number of hosts: ${#HOSTS[@]}" >> "$APP_LOGFILE"
        echo "  # Number of successful hosts: ${#SUCCESS_HOSTS[@]}" >> "$APP_LOGFILE"
        echo "  # Number of failed hosts: ${#FAILED_HOSTS[@]}" >> "$APP_LOGFILE"
        echo "  # Number of newly failed hosts: ${#NEWLY_FAILED_HOSTS[@]}" >> "$APP_LOGFILE"
        echo "--------------------------------------------------------" >> "$APP_LOGFILE"
        total_processed=$((${#SUCCESS_HOSTS[@]} + ${#FAILED_HOSTS[@]}))
        if [[ $total_processed -ne ${#HOSTS[@]} ]]; then
            echo " /!\\ WARNING: Not all hosts were processed! Expected ${#HOSTS[@]}, got $total_processed" >> "$APP_LOGFILE"
        fi
    fi
done
