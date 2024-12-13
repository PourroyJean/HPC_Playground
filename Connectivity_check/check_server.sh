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
#   Attempts to connect via proxy and retrieve the SSH banner. 
#   Returns "<return_code>|<banner>".
######################################
check_host() {
    local host="$1"
    # Attempt to connect and read the SSH banner
    OUTPUT=$($NC_CMD --proxy "$PROXY" --proxy-type http "$host" "$PORT" -w"$TIMEOUT" < /dev/null 2>/dev/null)
    RET=$?
    echo "$RET|$OUTPUT"
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
        RESULT=$(check_host "$HOST")
        RET="${RESULT%%|*}"
        OUTPUT="${RESULT#*|}"

        # If the banner starts with "SSH-", we consider the host accessible
        if [[ $OUTPUT == SSH-* ]]; then
            log_result "$TEST_TIME" "$HOST" "accessible" "$RET"
            SUCCESS_HOSTS+=("$HOST")
        else
            # No valid SSH banner found
            log_result "$TEST_TIME" "$HOST" "inaccessible" "$RET"
            FAILED_HOSTS+=("$HOST")
        fi
    done

    # Sort the arrays to compare states easily
    IFS=$'\n' sorted_failed_current=($(sort <<<"${FAILED_HOSTS[*]}"))
    IFS=$'\n' sorted_failed_prev=($(sort <<<"${PREV_FAILED_HOSTS[*]}"))

    # If there are failed hosts
    if [ ${#FAILED_HOSTS[@]} -gt 0 ]; then
        # If current failures differ from previous failures, send an alert
        if [ "${sorted_failed_current[*]}" != "${sorted_failed_prev[*]}" ]; then
            SUBJECT="Alert: Some hosts are not accessible"
            
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
            
            send_alert "$SUBJECT" "$BODY"
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
