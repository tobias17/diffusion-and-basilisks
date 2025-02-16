#!/bin/bash
while true; do
   LATEST=$(ls -t logs/game/*/debug.log | head -n1)
   tail -f "$LATEST" & 
   TAIL_PID=$!
   
   # Watch for new files
   while [ "$LATEST" = "$(ls -t logs/game/*/debug.log | head -n1)" ]; do
      sleep 1
   done
   
   # Kill the old tail when a new file appears
   kill $TAIL_PID
   echo ""
   echo "========== New File Detected =========="
   echo ""
done
