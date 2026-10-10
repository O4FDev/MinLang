#!/bin/sh
# Routing is configured by the trusted host orchestrator. Peer binaries have
# no NET_ADMIN/NET_RAW capabilities and execute as the unprivileged image user.
while [ ! -f /tmp/network-ready ]; do sleep 0.05; done
if [ "$(pwd)" = /quiche ] || [ -x /usr/local/bin/wsslhqclient ]; then
    # Upstream clients write session.bin or session.txt/tp.txt relative to cwd.
    # Keep its binaries read-only and give the nonroot peer ephemeral state.
    script=/run_endpoint.sh
    if [ "$(pwd)" = /quiche ]; then script=/quiche/run_endpoint.sh; fi
    state=$(mktemp -d /tmp/minyar-peer-state.XXXXXX) || exit 1
    cd "$state" || exit 1
    exec "$script"
fi
exec ./run_endpoint.sh
