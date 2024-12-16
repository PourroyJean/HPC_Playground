#!/usr/bin/env bash

# File paths
CHECK_SCRIPT="./check_server.sh"
WEB_APP="./web_view/app.py"
CHECK_LOGFILE="./server_check.log"
CHECK_PIDFILE="./server_check.pid"
WEB_PIDFILE="./web_app.pid"

# Function to check if a process is running
check_process() {
    local pidfile="$1"
    if [ -f "$pidfile" ]; then
        local pid=$(cat "$pidfile")
        if ps -p "$pid" > /dev/null 2>&1; then
            return 0  # Process is running
        else
            rm -f "$pidfile"  # Clean up stale PID file
        fi
    fi
    return 1  # Process is not running
}

# Function to start the check server
start_check_server() {
    if check_process "$CHECK_PIDFILE"; then
        echo "Check server is already running (PID $(cat $CHECK_PIDFILE))"
        return
    fi

    echo "Starting the check server..."
    nohup "$CHECK_SCRIPT" > "$CHECK_LOGFILE" 2>&1 &
    echo $! > "$CHECK_PIDFILE"
    sleep 2

    if check_process "$CHECK_PIDFILE"; then
        echo "Check server started successfully (PID $(cat $CHECK_PIDFILE))"
    else
        echo "Error: Failed to start check server. Check $CHECK_LOGFILE for details."
        rm -f "$CHECK_PIDFILE"
    fi
}

# Function to start the web app
start_web_app() {
    if check_process "$WEB_PIDFILE"; then
        echo "Web app is already running (PID $(cat $WEB_PIDFILE))"
        return
    fi

    echo "Starting the web app..."
    # Create a virtual environment if it doesn't exist
    if [ ! -d "venv" ]; then
        echo "Creating virtual environment..."
        python3 -m venv venv
        ./venv/bin/pip install -r web_view/requirements.txt
    fi

    # Start the Flask app with nohup
    nohup ./venv/bin/python "$WEB_APP" > web_app.log 2>&1 &
    echo $! > "$WEB_PIDFILE"
    sleep 2

    if check_process "$WEB_PIDFILE"; then
        echo "Web app started successfully (PID $(cat $WEB_PIDFILE))"
        echo "Web interface available at: http://localhost:5000"
    else
        echo "Error: Failed to start web app. Check web_app.log for details."
        rm -f "$WEB_PIDFILE"
    fi
}

# Function to show status
show_status() {
    echo "Current Status:"
    if check_process "$CHECK_PIDFILE"; then
        echo "- Check server: Running (PID $(cat $CHECK_PIDFILE))"
    else
        echo "- Check server: Stopped"
    fi

    if check_process "$WEB_PIDFILE"; then
        echo "- Web app: Running (PID $(cat $WEB_PIDFILE))"
    else
        echo "- Web app: Stopped"
    fi
}

# Function to stop services
stop_service() {
    local pidfile="$1"
    local service_name="$2"
    if [ -f "$pidfile" ]; then
        local pid=$(cat "$pidfile")
        if ps -p "$pid" > /dev/null 2>&1; then
            echo "Stopping $service_name (PID $pid)..."
            kill $pid
            sleep 2
            if ps -p "$pid" > /dev/null 2>&1; then
                echo "Warning: $service_name did not stop gracefully, forcing..."
                kill -9 $pid
            fi
        fi
        rm -f "$pidfile"
    fi
}

# Main menu
while true; do
    echo
    echo "LR4 Connectivity Check Control Panel"
    echo "-----------------------------------"
    show_status
    echo
    echo "Available actions:"
    echo "1) Start/Stop Check Server"
    echo "2) Start/Stop Web App"
    echo "3) Start Both Services"
    echo "4) Stop Both Services"
    echo "5) Exit"
    echo
    read -p "Select an option (1-5): " choice

    case $choice in
        1)
            if check_process "$CHECK_PIDFILE"; then
                stop_service "$CHECK_PIDFILE" "check server"
            else
                start_check_server
            fi
            ;;
        2)
            if check_process "$WEB_PIDFILE"; then
                stop_service "$WEB_PIDFILE" "web app"
            else
                start_web_app
            fi
            ;;
        3)
            start_check_server
            start_web_app
            ;;
        4)
            stop_service "$CHECK_PIDFILE" "check server"
            stop_service "$WEB_PIDFILE" "web app"
            ;;
        5)
            echo "Exiting..."
            exit 0
            ;;
        *)
            echo "Invalid option. Please select 1-5."
            ;;
    esac
done
