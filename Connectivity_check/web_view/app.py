from flask import Flask, render_template, jsonify
from datetime import datetime
import csv
from collections import defaultdict
import os

app = Flask(__name__)

def get_owner(host):
    try:
        with open(os.path.join(os.path.dirname(os.path.dirname(__file__)), "hosts.csv"), 'r') as f:
            for line in f:
                ip, owner = line.strip().split(',')
                if ip == host:
                    return owner
    except Exception as e:
        print(f"Error reading owner info: {str(e)}")
    return "Unknown"

def parse_log_file(log_file=None):
    # Get the absolute path to the log file
    if log_file is None:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        parent_dir = os.path.dirname(current_dir)
        log_file = os.path.join(parent_dir, "logs/server_check.log")

    # Add detailed debug logging
    print("\n=== Debug Log File Information ===")
    print(f"Current working directory: {os.getcwd()}")
    print(f"App directory: {current_dir}")
    print(f"Parent directory: {parent_dir}")
    print(f"Attempting to read log file from: {log_file}")
    print(f"Absolute path to log file: {os.path.abspath(log_file)}")
    print(f"File exists: {os.path.exists(log_file)}")
    
    if os.path.exists(log_file):
        print(f"File size: {os.path.getsize(log_file)}")
        print(f"Last modified: {datetime.fromtimestamp(os.path.getmtime(log_file))}")
        print(f"File permissions: {oct(os.stat(log_file).st_mode)[-3:]}")
        print("\nFirst few lines of the file:")
        with open(log_file, 'r') as f:
            print(''.join(f.readlines()[:5]))
    print("===================================\n")

    latest_status = {}
    history = defaultdict(list)
    latest_timestamp = None
    accessibility_stats = defaultdict(lambda: {'total': 0, 'accessible': 0})
    attempt_stats = defaultdict(lambda: {'total_attempts': 0, 'count': 0})
    
    # First, process the file to get the latest status for each host
    try:
        with open(log_file, 'r') as f:
            lines = f.readlines()
            
            # Filter out non-CSV lines
            csv_lines = []
            for line in lines:
                # Only process lines that match our expected CSV format
                if line.count(',') == 3 and line.strip().startswith('20'):  # Starts with year
                    csv_lines.append(line)
            
            # Process all entries to calculate accessibility percentage
            for line in csv_lines:
                try:
                    timestamp_str, host, status, retcode = line.strip().split(',')
                    # Update accessibility statistics
                    accessibility_stats[host]['total'] += 1
                    if status.strip() == 'accessible':
                        accessibility_stats[host]['accessible'] += 1
                    
                    # Calculate attempt statistics
                    attempt = int(retcode)
                    attempt_stats[host]['total_attempts'] += attempt
                    attempt_stats[host]['count'] += 1
                except (ValueError, IndexError):
                    print(f"Skipping malformed line: {line.strip()}")
                    continue
            
            # Group entries by host to find the latest status for each
            host_entries = defaultdict(list)
            for line in csv_lines:
                try:
                    timestamp_str, host, status, retcode = line.strip().split(',')
                    timestamp = datetime.fromisoformat(timestamp_str)
                    host_entries[host].append((timestamp, status))
                except (ValueError, IndexError):
                    continue
                
                # Keep track of the overall latest timestamp
                if latest_timestamp is None or timestamp > latest_timestamp:
                    latest_timestamp = timestamp
            
            # Get the latest status for each host and calculate uptime percentage
            for host, entries in host_entries.items():
                latest_entry = sorted(entries, key=lambda x: x[0])[-1]
                stats = accessibility_stats[host]
                uptime_percent = (stats['accessible'] * 100 // stats['total']) if stats['total'] > 0 else 0
                
                latest_status[host] = {
                    'status': latest_entry[1],
                    'timestamp': latest_entry[0],
                    'uptime': uptime_percent,
                    'avg_attempt': round(attempt_stats[host]['total_attempts'] / attempt_stats[host]['count'], 1) if attempt_stats[host]['count'] > 0 else 0,
                    'owner': get_owner(host)
                }
                
                # Store the last 5 entries in history
                history[host] = [
                    {
                        'timestamp': timestamp,
                        'status': status,
                    }
                    for timestamp, status in sorted(entries, key=lambda x: x[0], reverse=True)[:5]
                ]
    except FileNotFoundError:
        # If the log file doesn't exist yet, return empty data
        print(f"Warning: Log file not found at {log_file}")
        return {}, {}, {
            'total_nodes': 0,
            'accessible_nodes': 0,
            'inaccessible_nodes': 0,
            'latest_timestamp': datetime.now()
        }
    
    # Calculate summary statistics based on latest status
    total_nodes = len(latest_status)
    accessible_nodes = sum(1 for status in latest_status.values() if status['status'].strip() == 'accessible')
    inaccessible_nodes = total_nodes - accessible_nodes
    
    summary = {
        'total_nodes': total_nodes,
        'accessible_nodes': accessible_nodes,
        'inaccessible_nodes': inaccessible_nodes,
        'latest_timestamp': latest_timestamp
    }
    
    return latest_status, history, summary

def get_failed_hosts(limit=20):
    failed_hosts_log = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs/failed_hosts.log")
    failed_hosts = []
    
    try:
        with open(failed_hosts_log, 'r') as f:
            lines = f.readlines()
            for line in reversed(lines[:limit]):  # Get last 20 entries in reverse order
                timestamp_str, host = line.strip().split(',')
                failed_hosts.append({
                    'timestamp': datetime.fromisoformat(timestamp_str),
                    'host': host
                })
    except FileNotFoundError:
        print(f"Warning: Failed hosts log not found at {failed_hosts_log}")
    
    return failed_hosts

@app.route('/')
def index():
    latest_status, history, summary = parse_log_file()
    failed_hosts = get_failed_hosts(20)  # Get last 20 entries
    sorted_hosts = sorted(
        latest_status.items(),
        key=lambda x: (x[1]['status'] != 'inaccessible', x[0])
    )
    
    return render_template(
        'index.html',
        hosts=sorted_hosts,
        history=history,
        summary=summary,
        failed_hosts=failed_hosts,
        current_time=datetime.now()
    )

@app.route('/update')
def update():
    latest_status, history, summary = parse_log_file()
    failed_hosts = get_failed_hosts(20)
    sorted_hosts = sorted(
        latest_status.items(),
        key=lambda x: (x[1]['status'] != 'inaccessible', x[0])
    )
    
    return jsonify({
        'hosts': {
            host: {
                'status': data['status'],
                'timestamp': data['timestamp'].strftime('%Y-%m-%d %H:%M:%S'),
                'uptime': data['uptime'],
                'avg_attempt': data['avg_attempt'],
                'owner': data['owner']
            }
            for host, data in sorted_hosts
        },
        'history': {
            host: [
                {
                    'timestamp': entry['timestamp'].strftime('%Y-%m-%d %H:%M:%S'),
                    'status': entry['status']
                }
                for entry in entries
            ]
            for host, entries in history.items()
        },
        'summary': {
            'total_nodes': summary['total_nodes'],
            'accessible_nodes': summary['accessible_nodes'],
            'inaccessible_nodes': summary['inaccessible_nodes'],
            'latest_timestamp': summary['latest_timestamp'].strftime('%d %B %Y %H:%M')
        },
        'current_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'failed_hosts': [{
            'timestamp': entry['timestamp'].strftime('%Y-%m-%d %H:%M:%S'),
            'host': entry['host']
        } for entry in failed_hosts]
    })

@app.route('/full_history/<host>')
def full_history(host):
    try:
        log_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs/server_check.log")
        
        # Add debug logging
        print(f"\n=== Debug Full History Request ===")
        print(f"Requested host: {host}")
        print(f"Log file path: {log_file}")
        print(f"File exists: {os.path.exists(log_file)}")
        
        if not os.path.exists(log_file):
            print(f"Log file not found at: {log_file}")
            return jsonify({'error': 'Log file not found'}), 404

        with open(log_file, 'r') as f:
            lines = f.readlines()
            
            # Filter lines for the specific host
            host_history = []
            for line in lines:
                try:
                    if line.count(',') == 3 and line.strip().startswith('20'):
                        timestamp_str, log_host, status, retcode = line.strip().split(',')
                        if log_host == host:
                            host_history.append({
                                'timestamp': datetime.fromisoformat(timestamp_str),
                                'status': status,
                                'retcode': retcode
                            })
                except Exception as e:
                    print(f"Error processing line: {line}")
                    print(f"Error details: {str(e)}")
                    continue
            
            # Sort by timestamp, newest first
            host_history.sort(key=lambda x: x['timestamp'], reverse=True)
            
            print(f"Found {len(host_history)} history entries for host {host}")
            print("===================================\n")
            
            return jsonify({
                'host': host,
                'history': [{
                    'timestamp': entry['timestamp'].strftime('%Y-%m-%d %H:%M:%S'),
                    'status': entry['status'],
                    'retcode': entry['retcode']
                } for entry in host_history]
            })
    except FileNotFoundError as e:
        print(f"FileNotFoundError: {str(e)}")
        return jsonify({'error': f'Log file not found: {str(e)}'}), 404
    except Exception as e:
        print(f"Unexpected error in full_history: {str(e)}")
        return jsonify({'error': f'Error fetching history: {str(e)}'}), 500

@app.route('/failed_hosts_history')
def failed_hosts_history():
    try:
        failed_hosts = []
        with open(os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs/failed_hosts.log"), 'r') as f:
            for line in f:
                timestamp, host = line.strip().split(',')
                dt = datetime.fromisoformat(timestamp)
                failed_hosts.append({
                    'timestamp': dt,
                    'host': host
                })
        failed_hosts.sort(key=lambda x: x['timestamp'], reverse=True)
        return jsonify({'history': [{
            'timestamp': entry['timestamp'].strftime('%Y-%m-%d %H:%M:%S'),
            'host': entry['host']
        } for entry in failed_hosts]})
    except FileNotFoundError:
        return jsonify({'history': []})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000) 