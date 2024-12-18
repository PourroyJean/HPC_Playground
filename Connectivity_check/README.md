# SSH Connectivity Monitor

This tool monitors SSH connectivity to a list of hosts through a proxy server. It provides real-time monitoring, logging, and email notifications for connectivity changes.

## Features

- Monitors SSH connectivity (port 22) through an HTTP proxy
- Handles multiple retry attempts before marking a host as inaccessible
- Maintains history of connectivity status
- Sends email alerts when hosts become inaccessible
- Provides a web interface to view current and historical status
- Tracks host ownership information

## Requirements
- `ncat` (for connecting via proxy)
- `mail` command (e.g., `mailutils` or `bsd-mailx` for sending emails)
- Python 3 with Flask (for web interface)
- A valid proxy address and port specified in `config.sh`

## Setup and Configuration

1. Copy the LR4 list from SharePoint:
   - Copy the Excel content from SharePoint
   - Paste it into `LR4_list.csv` (tab-separated format)

2. Generate the hosts file:
   ```bash
   ./process_lr4.sh
   ```
   This will create `hosts.csv` with proper formatting and owner information.

3. Update `config.sh` with your settings:
   ```bash
   PROXY="proxy:port"        # HTTP proxy server
   PORT=22                   # SSH port to check
   INTERVAL=1800            # Check interval in seconds
   TIMEOUT=1               # Connection timeout
   HOST_DELAY=1            # Delay between host checks
   MAX_ATTEMPT=6           # Maximum retry attempts
   RECIPIENT="email@domain.com"  # Alert recipient
   SEND_EMAIL=true         # Enable/disable email alerts
   DEBUG=true             # Enable/disable debug logging
   ```

## Usage

1. Start both the monitoring script and web interface:
   ```bash
   ./run.sh
   ```
   This will start both the check_server.sh script and the Flask web server.

   Alternatively, you can run them separately:
   ```bash
   # Start just the monitoring
   ./check_server.sh

   # Start just the web interface
   cd web_view
   python app.py
   ```

## Logs

All logs are stored in the `logs/` directory:
- `app.log`: Application logs and debug information
- `server_check.log`: Connectivity check results
- `failed_hosts.log`: Record of newly failed hosts

## Web Interface

Access the web interface at `http://localhost:5000` to view:
- Current status of all hosts
- Uptime statistics
- Owner information
- Connection history
- Failed host history

Features:
- Filter by status (accessible/inaccessible)
- Filter by owner status
- Sort by various criteria
- Search functionality
- Expandable history view

## Debug Mode

Enable debug output by setting `DEBUG=true` in config.sh or:
```bash
DEBUG=true ./check_server.sh
```
