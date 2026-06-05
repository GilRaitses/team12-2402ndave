#!/bin/bash
# EC2 first-boot setup for Team 12 hackathon demo (Ubuntu 22.04)
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y python3 python3-pip git
mkdir -p /opt/team12
chown ubuntu:ubuntu /opt/team12

cat > /etc/systemd/system/team12-api.service <<'UNIT'
[Unit]
Description=Team 12 Hackathon API Server
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/opt/team12/team12-2402ndave
EnvironmentFile=/opt/team12/team12-2402ndave/.env
Environment=API_PORT=8787
Environment=API_BIND=0.0.0.0
ExecStartPre=/usr/bin/python3 /opt/team12/team12-2402ndave/scripts/auth.py
ExecStartPre=/usr/bin/python3 /opt/team12/team12-2402ndave/scripts/fetch_all.py
ExecStart=/usr/bin/python3 /opt/team12/team12-2402ndave/backend/api_server.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
UNIT

systemctl daemon-reload
systemctl enable team12-api.service
