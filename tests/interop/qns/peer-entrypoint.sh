#!/bin/sh
# Routing is configured by the trusted host orchestrator. Peer binaries have
# no NET_ADMIN/NET_RAW capabilities and execute as the unprivileged image user.
while [ ! -f /tmp/network-ready ]; do sleep 0.05; done
exec ./run_endpoint.sh
