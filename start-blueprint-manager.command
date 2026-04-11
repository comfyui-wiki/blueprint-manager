#!/bin/bash
# Double-click in Finder → opens Terminal and runs Blueprint Manager.
# Ctrl+C in that window stops the server.

cd "$(dirname "$0")" || exit 1
export BLUEPRINT_MANAGER_IN_TERMINAL=1

PORT=8099
if lsof -i :"$PORT" -sTCP:LISTEN &>/dev/null; then
    echo "Port $PORT is already in use. Stop it first:"
    echo "  kill \$(lsof -ti :$PORT -sTCP:LISTEN)"
    read -r -p "Press Enter to close…"
    exit 1
fi

echo ""
echo "Blueprint Manager — http://localhost:$PORT"
echo "Press Ctrl+C to stop."
echo ""

( sleep 1.5 && open "http://localhost:$PORT" ) &

exec python3 main.py --port "$PORT"
