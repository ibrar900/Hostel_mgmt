#!/bin/bash
# =============================================================================
# Quick Start Script - Run the Hostel Management System
# =============================================================================
# No root required - just run this script!
#
# Usage:
#   chmod +x quickstart.sh && ./quickstart.sh
# =============================================================================

APP_DIR="/home/ibrar/Documents/hostel_mgmt"
PORT=5050

# Colors
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo ""
echo "=========================================="
echo "  HKBK Hostel Management - Quick Start"
echo "=========================================="
echo ""

cd "$APP_DIR"

# Check for virtual environment
if [ ! -d "$APP_DIR/venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install dependencies if needed
if ! pip show gunicorn &> /dev/null; then
    echo "Installing dependencies..."
    pip install -r requirements.txt
fi

# Get LAN IP
LAN_IP=$(ip -4 addr show 2>/dev/null | grep -oP '(?<=inet\s)\d+(\.\d+){3}' | grep -E '^172\.(16|17|18|19|20)' | head -1)
if [ -z "$LAN_IP" ]; then
    LAN_IP=$(hostname -I 2>/dev/null | awk '{print $1}')
fi

echo ""
echo -e "${GREEN}Starting HKBK Hostel Management System...${NC}"
echo ""
echo -e "Access URLs:"
echo -e "  ${CYAN}→ Local:   http://localhost:$PORT${NC}"
echo -e "  ${CYAN}→ LAN:     http://$LAN_IP:$PORT${NC}"
echo ""
echo -e "${YELLOW}Press CTRL+C to stop${NC}"
echo ""
echo "----------------------------------------------"
echo ""

# Start gunicorn
exec gunicorn \
    --bind 0.0.0.0:$PORT \
    --workers 2 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile - \
    wsgi:application
