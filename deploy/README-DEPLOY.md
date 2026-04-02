# HKBK Hostel Management System - LAN Deployment Guide

## Overview

This guide will help you host the HKBK Hostel Management System on your local network (172.16.0.0/16 - 172.20.0.0/16) so that all devices on your LAN can access it.

---

## Files Created

| File | Purpose |
|------|---------|
| `deploy/hostel.service` | Systemd service file for auto-start on boot |
| `deploy/deploy.sh` | Main deployment script |
| `deploy/quickstart.sh` | Quick start script (no root needed) |
| `deploy/firewall.sh` | Firewall configuration script |
| `wsgi.py` | Production WSGI entry point |

---

## Prerequisites

- Python 3.8 or higher installed
- Linux OS (Ubuntu, Debian, CentOS, Fedora, etc.)
- Root/sudo access for service installation
- Network connectivity on 172.16.x.x - 172.20.x.x range

---

## Step-by-Step Deployment

### Step 1: Make Scripts Executable

Open a terminal and run:

```bash
cd /home/ibrar/Documents/hostel_mgmt
chmod +x deploy/deploy.sh
chmod +x deploy/quickstart.sh
chmod +x deploy/firewall.sh
```

### Step 2: Check Your LAN IP Address

Run this command to find your server's LAN IP:

```bash
hostname -I
```

You should see an IP starting with `172.16`, `172.17`, `172.18`, `172.19`, or `172.20`.

Example output:
```
172.16.0.5 192.168.1.5
```

The `172.16.0.5` is your LAN IP. Clients will use this to access the app.

### Step 3: Run the Deployment Script

#### Option A: Full Deployment with Auto-Start (Recommended for servers)

```bash
sudo ./deploy/deploy.sh
```

This will:
- Create log directory
- Set up Python virtual environment
- Install dependencies
- Install systemd service
- Start the service
- Configure firewall
- Show access URLs

#### Option B: Quick Start (For testing or desktop)

```bash
./deploy/quickstart.sh
```

This runs the server in a terminal window. Keep the terminal open for access.

### Step 4: Configure Firewall (If not done automatically)

```bash
sudo ./deploy/firewall.sh
```

Or manually:

**For UFW (Ubuntu/Debian):**
```bash
sudo ufw allow 5050/tcp
sudo ufw status
```

**For firewalld (CentOS/RHEL/Fedora):**
```bash
sudo firewall-cmd --permanent --add-port=5050/tcp
sudo firewall-cmd --reload
```

### Step 5: Access from Client Devices

On any device connected to your LAN (same router/switch), open a web browser and navigate to:

```
http://172.16.0.5:5050
```

Replace `172.16.0.5` with your actual server LAN IP.

---

## Managing the Service

### Check Status
```bash
sudo systemctl status hostel
```

### Start Service
```bash
sudo systemctl start hostel
```

### Stop Service
```bash
sudo systemctl stop hostel
```

### Restart Service
```bash
sudo systemctl restart hostel
```

### View Logs (Real-time)
```bash
sudo journalctl -u hostel -f
```

### View Application Logs
```bash
tail -f /home/ibrar/Documents/hostel_mgmt/logs/access.log
tail -f /home/ibrar/Documents/hostel_mgmt/logs/error.log
```

### Disable Auto-Start
```bash
sudo systemctl disable hostel
```

---

## Troubleshooting

### Port Already in Use

If port 5050 is already in use:

```bash
# Find what's using port 5050
sudo lsof -i :5050

# Kill the process
sudo kill -9 <PID>
```

Or change the port in `deploy/hostel.service` and `deploy/deploy.sh`.

### Service Won't Start

Check logs:
```bash
sudo journalctl -u hostel -n 50
```

Common issues:
- Wrong path in service file
- Missing dependencies
- Permission denied

### Cannot Access from Other Devices

1. Check firewall is open:
   ```bash
   sudo ufw status
   ```

2. Check server is listening:
   ```bash
   sudo netstat -tlnp | grep 5050
   ```

   Should show:
   ```
   tcp        0      0 0.0.0.0:5050            0.0.0.0:*               LISTEN      XXXX/gunicorn
   ```

3. Ping the server from client:
   ```bash
   ping 172.16.0.5
   ```

### Database Issues

If the database doesn't exist, create it:

```bash
cd /home/ibrar/Documents/hostel_mgmt
source venv/bin/activate
python -c "from app import create_app; app = create_app(); print('DB OK')"
```

---

## Network Configuration Notes

### Your LAN Range: 172.16.0.0/16

Your network uses the 172.16.0.0 - 172.20.0.0 range (Class B private). The server will accept connections from all devices on these subnets.

### Static IP Recommendation

For a production server, set a static IP:

1. Edit network config:
   ```bash
   sudo nano /etc/netplan/01-netcfg.yaml  # Ubuntu
   ```

2. Example configuration:
   ```yaml
   network:
     version: 2
     renderer: networkd
     ethernets:
       eth0:
         addresses:
           - 172.16.0.10/24
         gateway4: 172.16.0.1
         nameservers:
           addresses:
             - 8.8.8.8
   ```

3. Apply:
   ```bash
   sudo netplan apply
   ```

---

## Security Considerations

### For Internal Use Only

This setup is for your internal LAN. For internet access, you would need:
- Reverse proxy (nginx/apache)
- SSL certificate
- Proper firewall rules
- Domain name configuration

### Recommended for Internal LAN:
- [ ] Change default secret key in `app.py`
- [ ] Use strong passwords for all accounts
- [ ] Keep the system updated
- [ ] Regular backups of database

### To Change Secret Key:

Edit `app.py` line 12:
```python
app.secret_key = 'your-new-secure-random-key-here'
```

Generate a secure key:
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

---

## Backup & Recovery

### Backup Database

```bash
cp /home/ibrar/Documents/hostel_mgmt/database/hostel.db \
   /home/ibrar/Documents/hostel_mgmt/database/hostel_backup_$(date +%Y%m%d).db
```

### Restore Database

```bash
sudo systemctl stop hostel
cp /home/ibrar/Documents/hostel_mgmt/database/hostel_backup_20260101.db \
   /home/ibrar/Documents/hostel_mgmt/database/hostel.db
sudo systemctl start hostel
```

---

## Quick Reference

| Item | Value |
|------|-------|
| Default Port | 5050 |
| App Directory | /home/ibrar/Documents/hostel_mgmt |
| Log Directory | /home/ibrar/Documents/hostel_mgmt/logs |
| Database | /home/ibrar/Documents/hostel_mgmt/database/hostel.db |
| Service Name | hostel |
| WSGI Entry | wsgi.py |
| App Factory | app.py:create_app() |

### Service Commands:
```bash
sudo systemctl start hostel    # Start
sudo systemctl stop hostel     # Stop
sudo systemctl restart hostel  # Restart
sudo systemctl status hostel   # Status
sudo journalctl -u hostel -f   # Logs
```

---

## Need Help?

If you face issues:

1. Check logs: `sudo journalctl -u hostel -n 50`
2. Verify port: `sudo netstat -tlnp | grep 5050`
3. Test locally: `curl http://localhost:5050`
4. Check firewall: `sudo ufw status`

---

**Last Updated:** April 2026
**Version:** 1.0
