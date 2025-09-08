#!/bin/bash

# Thoth Workspace Initialization Script
# Creates local directories for Docker bind mounts

set -e

echo "🏗️  Initializing Thoth workspace directories..."

# Create main workspace directories
mkdir -p workspace/{pdfs,notes,data,queries,discovery,knowledge,tmp}
mkdir -p data/{output,processed,embeddings,citations}
mkdir -p logs
mkdir -p cache

# Create subdirectories for organized data
mkdir -p workspace/data/{markdown,graph,discovery}
mkdir -p workspace/discovery/{sources,results}
mkdir -p workspace/knowledge/{citations,relationships,topics}

# Set permissions (containers run as thoth user, UID 1000)
chown -R 1000:1000 workspace data logs cache 2>/dev/null || {
    echo "⚠️  Could not set ownership to user 1000. This is normal on some systems."
    echo "   Docker will handle permissions automatically."
}

# Create .gitkeep files to preserve directory structure
find workspace data logs cache -type d -empty -exec touch {}/.gitkeep \;

echo "✅ Workspace initialized successfully!"
echo ""
echo "📁 Created directories:"
echo "   ./workspace/     - Main workspace (PDFs, notes, processed data)"
echo "   ./data/          - Application data (embeddings, outputs)"
echo "   ./logs/          - Application logs"
echo "   ./cache/         - Temporary cache files"
echo ""
echo "🔍 You can now watch these directories for real-time file changes!"
echo "   tail -f logs/*.log"
echo "   ls -la workspace/data/"
echo "   find workspace -name '*.pdf' -newer yesterday"
