# PID is the pinned simulator's existing capture and ns3 child list.
# PID 1 must reap capture writers after forwarding a shutdown signal.
stop_children() {
    trap '' INT TERM
    kill -"$1" $PID 2>/dev/null || true
    for child in $PID; do
        wait "$child" || true
    done
}
trap 'stop_children SIGINT; exit 130' INT
trap 'stop_children SIGTERM; exit 143' TERM
wait
