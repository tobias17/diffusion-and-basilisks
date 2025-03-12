#!/bin/bash

# Compute the parent directory of this script and cd there
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Check if a parameter was passed in
if [ $# -eq 0 ]; then
   # No parameter provided, look in configs/default.txt
   if [ -f "configs/default.txt" ]; then
      # Read the first line of default.txt as the parameter
      PARAM=configs/$(head -n 1 "configs/default.txt")
   else
      echo "Error: No parameter provided and configs/default.txt not found."
      exit 1
   fi
else
   # Use the provided parameter
   PARAM="$1"
fi

# Start the game
python main.py "$PARAM"
