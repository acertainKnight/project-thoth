#!/bin/bash
# Restart all Thoth MCP server processes to pick up code changes

echo "Finding Thoth MCP processes..."
PIDS=$(ps aux | grep "[p]ython.*thoth mcp" | awk '{print $2}')

if [ -z "$PIDS" ]; then
    echo "No Thoth MCP processes found"
    exit 0
fi

echo "Found processes:"
ps aux | grep "[p]ython.*thoth mcp" | awk '{print "PID " $2 " started " $9}'

echo ""
echo "Killing old MCP processes..."
for pid in $PIDS; do
    echo "  Killing PID $pid"
    kill "$pid" 2>/dev/null || echo "    (already dead or no permission)"
done

echo ""
echo "Waiting for processes to terminate..."
sleep 2

# Check if any are still running
REMAINING=$(ps aux | grep "[p]ython.*thoth mcp" | wc -l)
if [ "$REMAINING" -gt 0 ]; then
    echo "Warning: Some processes still running. Force killing..."
    ps aux | grep "[p]ython.*thoth mcp" | awk '{print $2}' | xargs kill -9 2>/dev/null
    sleep 1
fi

echo ""
echo "✓ All MCP server processes terminated"
echo ""
echo "They will automatically restart when Letta tries to use them."
echo "Or you can manually start with: python -m thoth mcp stdio"
