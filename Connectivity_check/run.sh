#!/usr/bin/env bash

# File paths
SCRIPT="./check_server.sh"
LOGFILE="./server_check.log"
PIDFILE="./server_check.pid"

# Check if the script is already running
if [ -f "$PIDFILE" ]; then
    PID=$(cat "$PIDFILE")
    if ps -p "$PID" > /dev/null 2>&1; then
        echo "Error: Script is already running (PID $PID)."
        echo "To stop it, use the following command:"
        echo "kill $PID && rm -f $PIDFILE"
        exit 1
    else
        # If the PID file exists but the process is not running, clean up the PID file
        echo "Warning: Found stale PID file. Removing it."
        rm -f "$PIDFILE"
    fi
fi

# Start the script with nohup
echo "Starting the script with nohup..."
nohup "$SCRIPT" > "$LOGFILE" 2>&1 &
PID=$!

# Save the PID to the PID file
echo $PID > "$PIDFILE"

# Wait briefly to check if the script started successfully
sleep 2
if ps -p "$PID" > /dev/null 2>&1; then
    echo "Script started successfully (PID $PID). Logs: $LOGFILE"
else
    echo "Error: Failed to start the script. Check $LOGFILE for details."
    # Clean up PID file if the script didn't start
    rm -f "$PIDFILE"
    exit 1
fi
