#!/bin/bash

# Make script executable with: chmod +x start.sh
# Then run with: ./start.sh

# Check if gunicorn is available
if command -v gunicorn &> /dev/null; then
    echo "Starting DataRefiner with Gunicorn..."
    gunicorn --bind 0.0.0.0:5000 --reuse-port --reload main:app
else
    echo "Starting DataRefiner with Python..."
    python main.py
fi