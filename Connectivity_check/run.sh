#!/usr/bin/env bash

# File paths
CHECK_SCRIPT="./check_server.sh"
WEB_APP="./web_view/app.py"
APP_LOGFILE="./logs/app.log"
WEB_PIDFILE="./web_app.pid"
CHECK_PIDFILE="./server_check.pid"

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
    nohup "$CHECK_SCRIPT" > "$APP_LOGFILE" 2>&1 &
    echo $! > "$CHECK_PIDFILE"
    sleep 2

    if check_process "$CHECK_PIDFILE"; then
        echo "Check server started successfully (PID $(cat $CHECK_PIDFILE))"
    else
        echo "Error: Failed to start check server. Check $APP_LOGFILE for details."
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
    nohup ./venv/bin/python "$WEB_APP" > logs/web_app.log 2>&1 &
    echo $! > "$WEB_PIDFILE"
    sleep 2

    if check_process "$WEB_PIDFILE"; then
        echo "Web app started successfully (PID $(cat $WEB_PIDFILE))"
        echo "Web interface available at: http://localhost:5000"
    else
        echo "Error: Failed to start web app. Check logs/web_app.log for details."
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

# Function to stop the server
stop_server() {
    echo "Stopping Check Server..."
    if [ -f "check_server.pid" ]; then
        kill $(cat check_server.pid) 2>/dev/null
        rm -f check_server.pid
        echo "Server stopped."
    else
        echo "No PID file found. Server might not be running."
    fi
}

# Function to start the server
start_server() {
    echo "Starting Check Server..."
    nohup ./check_server.sh > /dev/null 2>&1 & echo $! > check_server.pid
    echo "Server started with PID: $(cat check_server.pid)"
}

# Function to clean logs
clean_logs() {
    echo "Cleaning log files..."
    rm -f logs/failed_hosts.log logs/app.log logs/server_check.log logs/web_app.log
    echo "Log files removed."
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
    echo "5) Restart Check Server (with clean logs)"
    echo "6) Exit"
    echo
    read -p "Select an option (1-6): " choice

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
            echo "Restarting Check Server..."
            stop_service "$CHECK_PIDFILE" "check server"
            clean_logs
            sleep 2  # Give time for processes to fully stop
            start_check_server
            echo "Restart complete."
            ;;
        6)
            echo "Exiting..."
            exit 0
            ;;
        *)
            echo "Invalid option. Please select 1-6."
            ;;
    esac
done
