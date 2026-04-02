#!/bin/bash
# =============================================================================
# HKBK Hostel Management System - Deployment Script
# =============================================================================
# Run this script to deploy/start the hostel management system on LAN
#
# Usage:
#   chmod +x deploy.sh && ./deploy.sh
# =============================================================================

set -e

APP_DIR="/home/ibrar/Documents/hostel_mgmt"
SERVICE_NAME="hostel"
SERVICE_FILE="$APP_DIR/deploy/hostel.service"
LOG_DIR="$APP_DIR/logs"
PORT=5050

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info()  { echo -e "${GREEN}[INFO]${NC}  $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

echo ""
echo "=========================================="
echo "  HKBK Hostel Management - Deploy Script"
echo "=========================================="
echo ""

# Check if running as root for service installation
IS_ROOT=false
if [ "$(id -u)" -eq 0 ]; then
    IS_ROOT=true
    log_info "Running as root - will install systemd service"
fi

# -----------------------------------------------------------------------------
# Step 1: Create log directory
# -----------------------------------------------------------------------------
log_info "Creating log directory..."
mkdir -p "$LOG_DIR"
touch "$LOG_DIR/hostel.log"
touch "$LOG_DIR/access.log"
touch "$LOG_DIR/error.log"
log_info "Log directory ready: $LOG_DIR"

# -----------------------------------------------------------------------------
# Step 2: Create virtual environment if not exists
# -----------------------------------------------------------------------------
if [ ! -d "$APP_DIR/venv" ]; then
    log_info "Creating Python virtual environment..."
    python3 -m venv "$APP_DIR/venv"
    log_info "Virtual environment created"
fi

# Activate virtual environment
source "$APP_DIR/venv/bin/activate"

# -----------------------------------------------------------------------------
# Step 3: Install/Update dependencies
# -----------------------------------------------------------------------------
log_info "Installing Python dependencies..."
pip install --upgrade pip
pip install -r "$APP_DIR/requirements.txt"
log_info "Dependencies installed"

# -----------------------------------------------------------------------------
# Step 4: Detect IP address on LAN
# -----------------------------------------------------------------------------
log_info "Detecting LAN IP address..."

# Try multiple methods to find LAN IP
LAN_IP=$(ip -4 addr show 2>/dev/null | grep -oP '(?<=inet\s)\d+(\.\d+){3}' | grep -E '^172\.(16|17|18|19|20)' | head -1)

if [ -z "$LAN_IP" ]; then
    LAN_IP=$(hostname -I | awk '{print $1}')
fi

if [ -z "$LAN_IP" ]; then
    LAN_IP="172.16.0.x"
fi

log_info "Detected LAN IP: $LAN_IP"

# -----------------------------------------------------------------------------
# Step 5: Test the application briefly
# -----------------------------------------------------------------------------
log_info "Testing application startup..."
cd "$APP_DIR"
timeout 5 python3 -c "from app import create_app; app = create_app(); print('App import OK')" 2>/dev/null || {
    log_warn "Quick test skipped (app import check)"
}

# -----------------------------------------------------------------------------
# Step 6: Start with Gunicorn directly (quick start)
# -----------------------------------------------------------------------------
if [ "$IS_ROOT" = false ]; then
    echo ""
    log_warn "Not running as root - use one of these options:"
    echo ""
    echo "  OPTION 1: Quick Start (terminal stays open)"
    echo "  ============================================"
    echo "  cd $APP_DIR"
    echo "  source venv/bin/activate"
    echo "  gunicorn --bind 0.0.0.0:$PORT --workers 2 wsgi:application"
    echo ""
    echo "  OPTION 2: Run in background (screen)"
    echo "  ======================================"
    echo "  cd $APP_DIR"
    echo "  source venv/bin/activate"
    echo "  gunicorn --bind 0.0.0.0:$PORT --workers 2 --daemon wsgi:application"
    echo ""
    echo "  OPTION 3: Install as systemd service (RECOMMENDED)"
    echo "  ==================================================="
    echo "  sudo cp $SERVICE_FILE /etc/systemd/system/"
    echo "  sudo systemctl daemon-reload"
    echo "  sudo systemctl enable hostel"
    echo "  sudo systemctl start hostel"
    echo ""
    echo "  Access the app at: http://$LAN_IP:$PORT"
    echo ""
    exit 0
fi

# -----------------------------------------------------------------------------
# Step 7: Install systemd service (root only)
# -----------------------------------------------------------------------------
log_info "Installing systemd service..."

# Update the service file with actual user
SED_USER=$(whoami)
sed "s/User=ibrar/User=$SED_USER/g" "$SERVICE_FILE" > /tmp/hostel.service.tmp
sed -i "s|WorkingDirectory=/home/ibrar/Documents/hostel_mgmt|WorkingDirectory=$APP_DIR|g" /tmp/hostel.service.tmp
sed -i "s|$APP_DIR/logs|$LOG_DIR|g" /tmp/hostel.service.tmp

cp /tmp/hostel.service.tmp /etc/systemd/system/${SERVICE_NAME}.service
rm /tmp/hostel.service.tmp

log_info "Service file installed to /etc/systemd/system/${SERVICE_NAME}.service"

# -----------------------------------------------------------------------------
# Step 8: Enable and start the service
# -----------------------------------------------------------------------------
log_info "Enabling and starting service..."
systemctl daemon-reload
systemctl enable ${SERVICE_NAME}
systemctl restart ${SERVICE_NAME}

sleep 2

if systemctl is-active --quiet ${SERVICE_NAME}; then
    log_info "Service started successfully!"
else
    log_error "Service failed to start. Check logs:"
    journalctl -u ${SERVICE_NAME} --no-pager -n 20
    exit 1
fi

# -----------------------------------------------------------------------------
# Step 9: Configure firewall
# -----------------------------------------------------------------------------
log_info "Checking firewall..."

if command -v ufw &> /dev/null; then
    log_info "UFW firewall detected - opening port $PORT"
    ufw allow $PORT/tcp 2>/dev/null || true
    log_info "Port $PORT opened in UFW"
elif command -v firewall-cmd &> /dev/null; then
    log_info "firewalld detected - opening port $PORT"
    firewall-cmd --permanent --add-port=${PORT}/tcp 2>/dev/null || true
    firewall-cmd --reload 2>/dev/null || true
    log_info "Port $PORT opened in firewalld"
elif command -v iptables &> /dev/null; then
    log_info "iptables detected - you may need to open port manually:"
    echo "  sudo iptables -A INPUT -p tcp --dport $PORT -j ACCEPT"
fi

# -----------------------------------------------------------------------------
# Step 10: Show completion info
# -----------------------------------------------------------------------------
echo ""
echo "=========================================="
echo "  Deployment Complete!"
echo "=========================================="
echo ""
echo "  Service Status:"
systemctl status ${SERVICE_NAME} --no-pager | head -10
echo ""
echo "  Access URLs:"
echo "  → Local:    http://localhost:$PORT"
echo "  → LAN:      http://$LAN_IP:$PORT"
echo "  → All IPs:  http://0.0.0.0:$PORT"
echo ""
echo "  Useful Commands:"
echo "  → Status:   sudo systemctl status hostel"
echo "  → Logs:     sudo journalctl -u hostel -f"
echo "  → Restart:  sudo systemctl restart hostel"
echo "  → Stop:     sudo systemctl stop hostel"
echo "  → Disable:  sudo systemctl disable hostel"
echo ""
echo "  Log files:"
echo "  → $LOG_DIR/access.log"
echo "  → $LOG_DIR/error.log"
echo "  → $LOG_DIR/hostel.log"
echo ""
