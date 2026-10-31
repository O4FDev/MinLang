#!/bin/bash
# cache-provision.sh: run as root once on the shard-cache box (created from the shard image). Serves
# /home/agent/fgc read-only to the shards with an rsync daemon listening only on the box's private VPC address.
set -euo pipefail
private=$(curl -fsS http://169.254.169.254/metadata/v1/interfaces/private/0/ipv4/address)
install -d -o agent -g agent /home/agent/fgc
cat > /etc/rsyncd.conf <<EOF
address = $private
use chroot = no
max connections = 32
[fgc]
    path = /home/agent/fgc
    read only = yes
    uid = agent
    gid = agent
    hosts allow = 10.0.0.0/8
EOF
systemctl enable --now rsync
systemctl restart rsync
echo "CACHE-PROVISION-OK rsync://$private/fgc"
