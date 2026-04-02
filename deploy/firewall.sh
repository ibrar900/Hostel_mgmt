#!/bin/bash
# =============================================================================
# Firewall Configuration Script for HKBK Hostel Management System
# =============================================================================
# Opens port 5050 for LAN access on various firewall systems
#
# Supported: UFW (Ubuntu), firewalld (CentOS/RHEL/Fedora), iptables
# =============================================================================

PORT=5050

echo ""
echo "=========================================="
echo "  HKBK Firewall Configuration"
echo "=========================================="
echo ""

# Detect firewall type
if command -v ufw &> /dev/null; then
    echo "[*] Detected: UFW (Ubuntu/Debian)"
    echo ""
    echo "Opening port $PORT..."
    sudo ufw allow $PORT/tcp
    echo ""
    echo "UFW Status:"
    sudo ufw status | grep -E "(Status|$PORT)"
    echo ""

elif command -v firewall-cmd &> /dev/null; then
    echo "[*] Detected: firewalld (CentOS/RHEL/Fedora)"
    echo ""
    echo "Opening port $PORT..."
    sudo firewall-cmd --permanent --add-port=${PORT}/tcp
    sudo firewall-cmd --reload
    echo ""
    echo "Firewalld Status:"
    sudo firewall-cmd --list-ports
    echo ""

elif command -v iptables &> /dev/null; then
    echo "[*] Detected: iptables (Legacy)"
    echo ""
    echo "Opening port $PORT..."
    sudo iptables -C INPUT -p tcp --dport $PORT -j ACCEPT 2>/dev/null || \
        sudo iptables -A INPUT -p tcp --dport $PORT -j ACCEPT
    echo ""
    echo "Current iptables rule for port $PORT:"
    sudo iptables -L INPUT -n | grep $PORT || echo "Rule added (not shown in filter)"
    echo ""
    echo "IMPORTANT: To persist iptables rules after reboot, run:"
    echo "  Ubuntu/Debian: sudo apt install iptables-persistent"
    echo "  CentOS/RHEL:   sudo service iptables save"
    echo ""

else
    echo "[!] No firewall detected or firewall is disabled"
    echo ""
    echo "To check firewall status:"
    echo "  UFW:        sudo ufw status"
    echo "  firewalld:  sudo firewall-cmd --state"
    echo "  iptables:   sudo iptables -L"
    echo ""
fi

# Get LAN IP
LAN_IP=$(ip -4 addr show 2>/dev/null | grep -oP '(?<=inet\s)\d+(\.\d+){3}' | grep -E '^172\.(16|17|18|19|20)' | head -1)
if [ -z "$LAN_IP" ]; then
    LAN_IP=$(hostname -I 2>/dev/null | awk '{print $1}')
fi

echo "=========================================="
echo "  Access URLs"
echo "=========================================="
echo ""
echo "  → http://localhost:$PORT"
echo "  → http://$LAN_IP:$PORT"
echo ""
echo "  All devices on your LAN (172.16.0.0/16) can access"
echo "  using the above IP address."
echo ""
