# Connectivity Checker

This project provides a simple Bash-based connectivity checker that regularly tests the accessibility of multiple hosts over SSH via a specified proxy. If any hosts become unreachable, the script will send email alerts and log the results.

## Features
- Periodically checks the connectivity of a list of hosts.
- Logs all results (accessible/inaccessible) with timestamps and return codes.
- Sends email notifications when hosts transition from accessible to inaccessible or vice versa.
- Hosts are easily managed by adding/removing them in `hosts.txt`.

## Files
- **config.sh**: Configuration file for proxy settings, interval, timeout, logfile, and email recipient.
- **hosts.txt**: List of hosts to be checked (one per line).
- **check_server.sh**: Main script that performs the checks and sends notifications.
- **server_check.log**: Log file where all results are recorded.

## Requirements
- `ncat` (for connecting via proxy)
- `mail` command (e.g., `mailutils` or `bsd-mailx` for sending emails)
- A valid proxy address and port specified in `config.sh`
- A `hosts.txt` file containing the list of hosts to test.

## How to Use
1. Clone or download this repository to your machine.
2. Update `config.sh` with your desired settings:
   - **PROXY**: `<proxy_host:port>`
   - **INTERVAL**: Frequency (in seconds) to run checks.
   - **RECIPIENT**: Email address for alerts.
3. Populate `hosts.txt` with the hosts you want to monitor.
4. Run the script:
   ```bash
   ./check_server.sh
