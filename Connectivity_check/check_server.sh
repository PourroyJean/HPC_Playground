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
PREV_FAILED_HOSTS=()

######################################
# FUNCTION: check_host
#   Checks the accessibility of a host, logs the result, and updates the appropriate array.
######################################
check_host() {
    local host="$1"
    local timestamp="$2"
    local retries=3
    local attempt=1
    local output=""
    local retcode=1

    # Retry logic
    while [ $attempt -le $retries ]; do
        output=$(ncat --proxy "$PROXY" --proxy-type http "$host" "$PORT" -w"$TIMEOUT" < /dev/null 2>/dev/null)
        retcode=$?

        if [[ -n "$output" ]]; then
            break
        fi

        # Increment attempt and retry
        attempt=$((attempt + 1))
        sleep 1  # Small delay before retrying
    done

    # Check if the output starts with "SSH-"
    if [[ $output == SSH-* ]]; then
        log_result "$timestamp" "$host" "accessible" "$retcode"
        SUCCESS_HOSTS+=("$host")
    else
        log_result "$timestamp" "$host" "inaccessible" "$retcode"
        FAILED_HOSTS+=("$host")
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
    echo "$timestamp,$host,$status,ret=$retcode" >> "$LOGFILE"
}

######################################
# FUNCTION: send_alert
#   Sends an email alert using the mail command.
######################################
send_alert() {
    local subject="$1"
    local body="$2"
    echo -e "$body" | mail -s "$subject" "$RECIPIENT"
}


# Main loop
# Continuously checks all hosts at the specified interval.
while true; do
    # Reload configuration in case it has changed
    source ./config.sh

    FAILED_HOSTS=()
    SUCCESS_HOSTS=()

    # Current timestamp for logging
    TEST_TIME=$(date -Iseconds)

    # Loop over each host and perform the check
    for HOST in "${HOSTS[@]}"; do
        check_host "$HOST" "$TEST_TIME"
    done


    # Sort the arrays to compare states easily
    IFS=$'\n' sorted_failed_current=($(sort <<<"${FAILED_HOSTS[*]}"))
    IFS=$'\n' sorted_failed_prev=($(sort <<<"${PREV_FAILED_HOSTS[*]}"))

    # If there are failed hosts
    if [ ${#FAILED_HOSTS[@]} -gt 0 ]; then
        # If current failures differ from previous failures, send an alert
        if [ "${sorted_failed_current[*]}" != "${sorted_failed_prev[*]}" ]; then
            SUBJECT="[LR4 Alert] - Some hosts are not accessible"
            
            BODY="Hello,\n\n"
            BODY+="Here are the results of the latest check (executed at $TEST_TIME):\n\n"
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
                echo -e "$BODY"
            fi
        fi
    else
        # No inaccessible hosts now; if previously there were some, send a recovery email
        if [ ${#PREV_FAILED_HOSTS[@]} -gt 0 ]; then
            SUBJECT="Recovery: All hosts are accessible again"
            BODY="Hello,\n\nAll hosts are now accessible (as of $TEST_TIME).\n\nRegards,\nYour monitoring script"
            send_alert "$SUBJECT" "$BODY"
        fi
    fi

    # Update the previous failed hosts array
    PREV_FAILED_HOSTS=("${FAILED_HOSTS[@]}")

    # Wait before the next check
    sleep "$INTERVAL"
done


