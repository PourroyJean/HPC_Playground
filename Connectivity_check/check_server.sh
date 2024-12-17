#!/usr/bin/env bash

# Load configuration
source ./config.sh

# Read host list from file
mapfile -t HOSTS < hosts.txt

# Remove empty lines if any
TMP=()
for h in "${HOSTS[@]}"; do
    if [[ -n "$h" ]]; then
        TMP+=("$h")
    fi
done
HOSTS=("${TMP[@]}")

# Keep track of previously failed hosts
FAILED_HOSTS=()
PREV_FAILED_HOSTS=()
TEMP_FAILED_HOSTS=()

# At the start of the script, after loading config
# Create logs directory if it doesn't exist
mkdir -p "$(dirname "$APP_LOGFILE")"

# Then continue with the existing redirection
exec 1>> "$APP_LOGFILE"  # Redirect stdout to APP_LOGFILE
exec 2>> "$APP_LOGFILE"  # Redirect stderr to APP_LOGFILE


# Add this flag at the start
FIRST_RUN=true

######################################
# FUNCTION: check_host
#   Checks the accessibility of a host, logs the result, and updates the appropriate array.
#   Only logs the final result after all retries.
######################################
check_host() {
    local host="$1"
    local timestamp="$2"
    local do_log="${3:-false}"
    local output=""
    local retcode=1
    local needed_retry=false

    # Normal mode first
    output=$(ncat --proxy "$PROXY" --proxy-type http "$host" "$PORT" -w"$TIMEOUT" < /dev/null 2>&1)
    retcode=$?

    if [[ $output == *"SSH-"* ]]; then
        if [[ "$do_log" == "true" ]]; then
            log_result "$timestamp" "$host" "accessible" "$retcode"
        fi
        SUCCESS_HOSTS+=("$host")
        return 0
    else
        # Try verbose mode with increased timeout
        if [[ "$do_log" == "true" ]]; then
            local start_time=$(date +%s.%N)
            output=$(ncat -v --proxy "$PROXY" --proxy-type http "$host" "$PORT" -w"$((TIMEOUT*2))" < /dev/null 2>&1)
            retcode=$?
            local end_time=$(date +%s.%N)
            local duration=$(echo "$end_time - $start_time" | bc)
            
            if [[ $output == *"SSH-"* ]]; then
                log_result "$timestamp" "$host" "accessible" "$retcode"
                SUCCESS_HOSTS+=("$host")
                return 0
            fi
                        # Log retry attempt details only in app.log
            echo "=== Detailed connection attempt for $host ===" >> "$APP_LOGFILE"
            echo "Timestamp: $timestamp" >> "$APP_LOGFILE"
            echo "Command : ncat -v --proxy $PROXY --proxy-type http $host $PORT -w$((TIMEOUT*2))" >> "$APP_LOGFILE"
            echo "Return code: $retcode" >> "$APP_LOGFILE"
            echo "Duration: ${duration}s" >> "$APP_LOGFILE"
            echo "Output:" >> "$APP_LOGFILE"
            echo "$output" >> "$APP_LOGFILE"
            echo "===================================" >> "$APP_LOGFILE"

            # Only log the final failed status
            log_result "$timestamp" "$host" "inaccessible" "$retcode"
        fi
        TEMP_FAILED_HOSTS+=("$host")
        return 1
    fi
}

######################################
# FUNCTION: log_result
#   Logs the check result to the logfile.
#   Format: timestamp,host,status,return_code
######################################
log_result() {
    local timestamp="$1"
    local host="$2"
    local status="$3"
    local retcode="$4"
    echo "$timestamp,$host,$status,ret=$retcode" >> "$TEST_LOGFILE"
}

######################################
# FUNCTION: send_alert
#   Sends an email alert using the mail command.
######################################
send_alert() {
    local subject="$1"
    local body="$2"
    echo -e "$body" | mail -s "$subject" "$RECIPIENT"
    echo "Email alert sent to $RECIPIENT" >> "$APP_LOGFILE"
}


# Main loop
while true; do
    # Reload configuration in case it has changed
    source ./config.sh

    FAILED_HOSTS=()
    SUCCESS_HOSTS=()
    NEWLY_FAILED_HOSTS=()
    NEWLY_RECOVERED_HOSTS=()
    TEMP_FAILED_HOSTS=()

    # First pass: Check all hosts (without logging)
    for HOST in "${HOSTS[@]}"; do
        for attempt in $(seq 1 3); do
            TEST_TIME=$(date -Iseconds)
            if check_host "$HOST" "$TEST_TIME" "false"; then
                break
            fi
            sleep "$HOST_DELAY"
        done
    done

    # Second pass: Retry failed hosts and log final results
    if [ ${#TEMP_FAILED_HOSTS[@]} -gt 0 ]; then
        echo "Retrying failed hosts: ${TEMP_FAILED_HOSTS[*]}" >> "$APP_LOGFILE"
        CURRENT_FAILED=("${TEMP_FAILED_HOSTS[@]}")
        TEMP_FAILED_HOSTS=()

        # Loop through each failed host and:
        # 1. Try to connect again with verbose logging
        # 2. If the host is still inaccessible and this isn't the first run:
        #    - If it was already in PREV_FAILED_HOSTS, add to FAILED_HOSTS (continuing failure)
        #    - Otherwise, add to NEWLY_FAILED_HOSTS (new failure)
        # 3. Add a delay between each check to avoid overwhelming the network
        for HOST in "${CURRENT_FAILED[@]}"; do
            TEST_TIME=$(date -Iseconds)
            if ! check_host "$HOST" "$TEST_TIME" "true"; then
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

    # Log successful hosts that didn't need retry
    for HOST in "${SUCCESS_HOSTS[@]}"; do
        if [[ ! " ${TEMP_FAILED_HOSTS[@]} " =~ " ${HOST} " ]]; then
            TEST_TIME=$(date -Iseconds)
            log_result "$TEST_TIME" "$HOST" "accessible" "0"
        fi
    done

    # Only send alert if there are newly failed hosts after retries
    if [ ${#NEWLY_FAILED_HOSTS[@]} -gt 0 ]; then
        SUBJECT="[LR4 Alert] - Host(s) became inaccessible"
        
        BODY="Hello,\n\n"
        BODY+="The following hosts became inaccessible during the latest check (performed at $TEST_TIME):\n\n"

        echo "Failed host: ${NEWLY_FAILED_HOSTS[*]}" >> "$APP_LOGFILE"
        for H in "${NEWLY_FAILED_HOSTS[@]}"; do
            BODY+=" - $H\n"
        done

        BODY+="\n--- All Results from the Latest Check ---\n\n"
        BODY+="Accessible hosts:\n"
        for H in "${SUCCESS_HOSTS[@]}"; do
            BODY+=" - $H\n"
        done

        BODY+="\nInaccessible hosts:\n"
        for H in "${FAILED_HOSTS[@]}"; do
            BODY+=" - $H\n"
        done

        BODY+="\nRegards,\nYour monitoring script"
        
        if [ "$SEND_EMAIL" == "true" ]; then
            send_alert "$SUBJECT" "$BODY"
        else
            echo -e "$BODY"                         >> "$APP_LOGFILE"
            echo "Email notifications are disabled" >> "$APP_LOGFILE"
        fi
    fi

    # After first complete cycle, set FIRST_RUN to false
    FIRST_RUN=false

    # Update the previous failed hosts array
    PREV_FAILED_HOSTS=("${FAILED_HOSTS[@]}")
    
    # Wait before the next check
    echo "Check cycle completed at $(date)" >> "$APP_LOGFILE"
    echo "Waiting ${INTERVAL} seconds until next cycle..." >> "$APP_LOGFILE"
    sleep "$INTERVAL"
done
