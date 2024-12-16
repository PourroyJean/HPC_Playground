from flask import Flask, render_template, jsonify
from datetime import datetime
import csv
from collections import defaultdict
import os

app = Flask(__name__)

def parse_log_file(log_file=None):
    # Get the absolute path to the log file
    if log_file is None:
        # Get the directory where app.py is located
        current_dir = os.path.dirname(os.path.abspath(__file__))
        # Go up one level to the parent directory and find the log file
        log_file = os.path.join(os.path.dirname(current_dir), "server_check.log")

    latest_status = {}
    history = defaultdict(list)
    latest_timestamp = None
    
    # First, process the file to get the latest status for each host
    try:
        with open(log_file, 'r') as f:
            lines = f.readlines()
            
            # Group entries by host to find the latest status for each
            host_entries = defaultdict(list)
            for line in lines:
                timestamp_str, host, status, retcode = line.strip().split(',')
                timestamp = datetime.fromisoformat(timestamp_str)
                host_entries[host].append((timestamp, status))
                
                # Keep track of the overall latest timestamp
                if latest_timestamp is None or timestamp > latest_timestamp:
                    latest_timestamp = timestamp
            
            # Get the latest status for each host
            for host, entries in host_entries.items():
                # Sort entries by timestamp and get the latest one
                latest_entry = sorted(entries, key=lambda x: x[0])[-1]
                latest_status[host] = {
                    'status': latest_entry[1],
                    'timestamp': latest_entry[0],
                }
                
                # Store the last 5 entries in history
                history[host] = [
                    {
                        'timestamp': timestamp,
                        'status': status,
                    }
                    for timestamp, status in sorted(entries, key=lambda x: x[0])[-5:]
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

@app.route('/')
def index():
    latest_status, history, summary = parse_log_file()
    sorted_hosts = sorted(
        latest_status.items(),
        key=lambda x: (x[1]['status'] != 'inaccessible', x[0])
    )
    
    return render_template(
        'index.html',
        hosts=sorted_hosts,
        history=history,
        summary=summary,
        current_time=datetime.now()
    )

@app.route('/update')
def update():
    latest_status, history, summary = parse_log_file()
    sorted_hosts = sorted(
        latest_status.items(),
        key=lambda x: (x[1]['status'] != 'inaccessible', x[0])
    )
    
    return jsonify({
        'hosts': {
            host: {
                'status': data['status'],
                'timestamp': data['timestamp'].strftime('%Y-%m-%d %H:%M:%S'),
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
        'current_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    })

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000) 