#!/bin/bash
echo "==== Railway Build Clean Script ===="

# Remove aria2 binaries (with error suppression)
echo "Removing aria2 binaries..."
find / -name "aria2c" -type f -delete 2>/dev/null ||:
find / -name "*aria2*" -type f -delete 2>/dev/null ||:

# Clean Python files 
echo "Cleaning Python files of aria2 references..."
find /app -type f -name "*.py" -exec sed -i 's/aria2c/disabled_downloader/g' {} \; 2>/dev/null ||:
find /app -type f -name "*.py" -exec sed -i 's/aria2/disabled_tool/g' {} \; 2>/dev/null ||:

# Set environment variables
echo "Setting environment variables to disable aria2..."
export YDL_NO_ARIA2C="1"
export HTTP_DOWNLOADER="native"
export YTDLP_DOWNLOADER="native"
export NO_EXTERNAL_DOWNLOADER="1"
export YTDLP_NO_ARIA2="1"

echo "Railway Build Clean Script completed."
exit 0