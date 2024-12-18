#!/bin/bash
# Documentation for process_lr4.sh script
# 
# This script processes LR4_list.csv, removing whitespace from IP addresses and owners, 
# and setting empty owners to "no owner". It writes the result to hosts.csv.
#
# Set DEBUG=1 to enable debug output

# Enable/disable debug output
DEBUG=${DEBUG:-0}
debug() {
    if [ "$DEBUG" -eq 1 ]; then
        echo "$@"
    fi
}

# Input and output files
INPUT_FILE="LR4_list.csv"
OUTPUT_FILE="hosts.csv"

# Check if input file exists
if [ ! -f "$INPUT_FILE" ]; then
    echo "Error: $INPUT_FILE not found"
    exit 1
fi

# Clear output file if it exists
> "$OUTPUT_FILE"

debug "Processing file line by line..."

# Process the file line by line
line_num=0
while IFS=$'\t' read -r ip owner || [ -n "$ip" ]; do
    ((line_num++))
    
    # Debug output
    debug "Line $line_num: IP='$ip' Owner='$owner'"
    
    # Skip empty lines
    if [ -z "$ip" ]; then
        debug "Skipping empty line $line_num"
        continue
    fi
    
    # Remove any whitespace from IP and owner
    ip=$(echo "$ip" | tr -d ' ')
    
    # If owner is empty or just whitespace, set to "no owner"
    if [ -z "${owner// }" ]; then
        debug "Line $line_num: Empty owner, setting to 'no owner'"
        owner="no owner"
    fi
    
    # Write to output file
    echo "$ip,$owner" >> "$OUTPUT_FILE"
done < "$INPUT_FILE"

# Count and display results
input_count=$(grep -v '^[[:space:]]*$' "$INPUT_FILE" | wc -l)
output_count=$(wc -l < "$OUTPUT_FILE")

echo -e "\nSummary:"
echo "Input lines (non-empty): $input_count"
echo "Output lines: $output_count"

if [ "$input_count" -ne "$output_count" ]; then
    echo -e "\nWarning: Input and output line counts don't match!"
    
    if [ "$DEBUG" -eq 1 ]; then
        # Additional debugging info
        echo -e "\nFirst few lines of INPUT_FILE:"
        head -n 5 "$INPUT_FILE"
        
        echo -e "\nLast few lines of INPUT_FILE:"
        tail -n 5 "$INPUT_FILE"
        
        echo -e "\nFirst few lines of OUTPUT_FILE:"
        head -n 5 "$OUTPUT_FILE"
        
        echo -e "\nLast few lines of OUTPUT_FILE:"
        tail -n 5 "$OUTPUT_FILE"
    fi
fi 