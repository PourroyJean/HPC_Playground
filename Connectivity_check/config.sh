#!/usr/bin/env bash

# General configuration
PROXY="10.121.125.146:80"
PORT=22
TIMEOUT=5
LOGFILE="./server_check.log"
INTERVAL=60
RECIPIENT="jean.pourroy@hpe.com"

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

if [ ! -f "./hosts.txt" ]; then
    echo "Error: 'hosts.txt' file not found. Please create it with one host/IP per line."
    exit 1
fi
