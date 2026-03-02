#!/bin/bash
# tldr-tube MCP server launcher
# Activates the conda environment and starts the MCP server.
#
# Usage:
#   ./run_mcp.sh               # start server (stdio, for MCP clients)
#   mcp dev ./run_mcp.sh       # start with MCP Inspector (browser UI)
#
# Register in Claude Desktop (~/.claude/mcp_settings.json):
#   {
#     "mcpServers": {
#       "tldr-tube": {
#         "command": "/path/to/tldr-tube/run_mcp.sh"
#       }
#     }
#   }

set -e

# Resolve the project root (directory containing this script)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Activate the tldr-tube conda environment
if ! command -v conda &> /dev/null; then
    echo "❌ Conda not found. Please install Miniconda first." >&2
    exit 1
fi

source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate tldr-tube

# Start the MCP server
exec python "$SCRIPT_DIR/mcp_server.py"
