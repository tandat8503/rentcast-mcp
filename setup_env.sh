#!/bin/bash

# Setup environment for MCP Rentcast
echo "Setting up MCP Rentcast environment..."

# Create .env file
cat > .env << EOF
# Rentcast API Configuration
RENTCAST_API_KEY=
RENTCAST_BASE_URL=https://api.rentcast.io/v1

# MCP Server Configuration
MCP_SERVER_NAME=rentcast-mcp
MCP_SERVER_VERSION=1.0.0
MCP_TRANSPORT=stdio

# Rate Limiting
MAX_API_CALLS_PER_SESSION=40
TIMEOUT_SECONDS=30
ENABLE_RATE_LIMITING=true
RATE_LIMIT_PER_MINUTE=60

# Logging
DEBUG=false
LOG_LEVEL=INFO

# Working Directories
WORKDIR=./implementations
UPLOAD_DIR=./resources/download
EOF

echo "✅ Environment file created: .env"
echo "✅ API Key configured: 38e5835f110b46029d721d28679f68e6"
echo ""
echo "You can now run:"
echo "  make start-server    # Start Python MCP server"
echo "  make start-typescript # Start TypeScript MCP server"
echo "  make start           # Start with Docker"
