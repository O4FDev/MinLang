#!/usr/bin/env python3
"""Malformed gRPC and an abruptly lost admitted gateway must release their calls."""
import argparse
import json
from pathlib import Path
import socket
import ssl
import struct
import tempfile
import time

import grpc
import h2.config
import h2.connection
import h2.events

from peer_edge_support import Lab, load

relay = load("edge_lifetime_relay", "peer-edge-relay.py")
peer = relay.peer


def abrupt_gateway(lab, device_output):
    context = ssl.create_default_context(cafile=str(lab.certs.path("ca", "pem")))
    context.load_cert_chain(str(lab.certs.path("gateway", "pem")),
                            str(lab.certs.path("gateway", "key")))
    context.set_alpn_protocols(["h2"])
    connection = context.wrap_socket(
        socket.create_connection(("127.0.0.1", lab.gateway_port), timeout=3),
        server_hostname="localhost")
    assert connection.selected_alpn_protocol() == "h2"
    protocol = h2.connection.H2Connection(
        config=h2.config.H2Configuration(client_side=True))
    protocol.initiate_connection()
    protocol.send_headers(1, [
        (":method", "POST"), (":scheme", "https"),
        (":authority", "localhost"), (":path", peer.PATH),
        ("content-type", "application/grpc"), ("te", "trailers"),
        ("grpc-timeout", "10S")])
    payload = relay.opened(lab.signed("abrupt-admitted"), "abrupt-admitted").SerializeToString()
    protocol.send_data(1, b"\0" + len(payload).to_bytes(4, "big") + payload)
    connection.sendall(protocol.data_to_send())
    data = bytearray()
    admitted = False
    deadline = time.monotonic() + 5
    while not admitted:
        assert time.monotonic() < deadline, "abrupt fixture did not establish a real relay"
        received = connection.recv(65536)
        assert received, "gateway closed before admitting fixture"
        for event in protocol.receive_data(received):
            if isinstance(event, h2.events.DataReceived):
                assert event.stream_id == 1
                data.extend(event.data)
                protocol.acknowledge_received_data(event.flow_controlled_length, event.stream_id)
            assert not isinstance(event, (h2.events.StreamReset, h2.events.ConnectionTerminated)), event
        while len(data) >= 5:
            size = int.from_bytes(data[1:5], "big")
            assert data[0] == 0 and size <= 65540
            if len(data) < 5 + size:
                break
            message = peer.Response.FromString(bytes(data[5:5 + size]))
            del data[:5 + size]
            if message.WhichOneof("body") == "status":
                assert message.status.code == 0, message
                admitted = True
        outgoing = protocol.data_to_send()
        if outgoing:
            connection.sendall(outgoing)
    # A real TCP reset discards TLS/gRPC trailers, rather than graceful RPC cancellation.
    connection.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))
    connection.close()
    lab.device_event(device_output, "CANCELLED abrupt-admitted")


def run(lab, mode):
    device, output = lab.start_device()
    with relay.channel(lab) as channel:
        rpc = relay.rpc(channel)
        relay.transfer(lab, rpc, "before-" + mode, b"before\0\xff")
        if mode == "malformed":
            for index, (path, payload) in enumerate([
                ("/PeerEdgeDial/Unknown", b""),
                (peer.PATH, b"\x1a\x01x"),
                (peer.PATH, b"\x0a\x01\xff"),
            ]):
                bad = channel.stream_stream(path, request_serializer=lambda value: value,
                                            response_deserializer=peer.Response.FromString)
                call = bad(iter([payload]), timeout=3)
                try:
                    list(call)
                    raise AssertionError("malformed gRPC call was accepted")
                except grpc.RpcError as error:
                    assert error.code() == grpc.StatusCode.INTERNAL, (index, error)
                relay.transfer(lab, rpc, "after-malformed-" + str(index), bytes([0, 255, index]))
        else:
            abrupt_gateway(lab, output)
            relay.transfer(lab, rpc, "after-abrupt", b"channel survives another gateway reset")
    device.stdin.write(b"close\n")
    device.stdin.flush()
    device.communicate(timeout=5)
    assert device.returncode == 0
    lines = lab.completed(timeout=20)
    records = [line for line in lines if line.startswith("EDGE_COUNTS ")]
    assert len(records) == 1, lines
    counts = dict(part.split("=") for part in records[0].split()[1:])
    assert int(counts["active"]) == 0 and int(counts["retained_relays"]) == 0, counts
    assert int(counts["calls_opened"]) == int(counts["calls_released"]), counts
    # Both positive health calls and each independently attempted call must be accounted.
    assert int(counts["calls_opened"]) >= (7 if mode == "malformed" else 3), counts
    return counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sanitize", action="store_true")
    parser.add_argument("--binary", type=Path)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--mode", choices=("malformed", "abrupt"), required=True)
    args = parser.parse_args()
    lab = None
    try:
        lab = Lab(args.evidence.resolve(), args.binary, args.sanitize, duration=12000)
        counts = run(lab, args.mode)
        report = {"status": 0, "mode": args.mode, "counts": counts}
        (args.evidence / "lifetime-result.json").write_text(json.dumps(report, indent=2) + "\n")
        print("GREEN gateway lifetime", json.dumps(report, sort_keys=True), flush=True)
    finally:
        if lab:
            lab.close()


if __name__ == "__main__":
    main()
