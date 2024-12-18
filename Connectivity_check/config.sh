#!/usr/bin/env bash

# General configuration
PROXY="10.121.125.146:80"                   # HPE Proxy server IP and port
PORT=22                                     # SSH port tested by the tool
LOGFILE="./server_check.log"                # Log file for server check results
APP_LOGFILE="./logs/app.log"                # Log file for application logs
INTERVAL=1800                               # Interval for server checks in seconds
INTERVAL=1                                 
TIMEOUT=1                                  # Timeout for network operations
HOST_DELAY=1                                # Delay between checking each host
RECIPIENT="jean.pourroy@hpe.com"            # Email recipient for notifications
SEND_EMAIL=true                             # Set to 'false' to disable email notifications
TEST_LOGFILE="./logs/server_check.log"      # For test results only
APP_LOGFILE="./logs/app.log"                # For application logs
FAILED_HOSTS_LOG="./logs/failed_hosts.log"  # For tracking newly failed hosts
MAX_ATTEMPT=6                               # Maximum number of attempts in first pass

# Debug mode (true/false)
DEBUG=${DEBUG:-true}

# Ensure required commands are available
NC_CMD=$(command -v ncat)
MAIL_CMD=$(command -v mail)

if [ -z "$NC_CMD" ]; then
    echo "Error: 'ncat' command not found. Please install it and try again."
    exit 1
fi

if [ -z "$MAIL_CMD" ]; then
    echo "Error: 'mail' command not found. Please install mailutils or bsd-mailx and try again."
    exit 1
fi

if [ ! -f "./hosts.csv" ]; then
    echo "Error: 'hosts.csv' file not found. Please create it with format: IP,owner"
    exit 1
fi
