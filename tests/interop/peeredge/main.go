// Independent TLS/yamux device fixture. Never linked into the edge server.
package main

import (
	"bufio"
	"crypto/tls"
	"crypto/x509"
	"encoding/binary"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"strconv"
	"time"

	"github.com/hashicorp/yamux"
)

func frame(kind byte, data []byte) []byte {
	result := make([]byte, 16+len(data))
	copy(result, "HPW1")
	result[4] = kind
	binary.BigEndian.PutUint32(result[12:16], uint32(len(data)))
	copy(result[16:], data)
	return result
}

func run() error {
	if len(os.Args) != 8 { return fmt.Errorf("port roots cert key device exit initial-health required") }
	root, err := os.ReadFile(os.Args[2]); if err != nil { return err }
	pool := x509.NewCertPool(); if !pool.AppendCertsFromPEM(root) { return fmt.Errorf("invalid fixture roots") }
	cert, err := tls.LoadX509KeyPair(os.Args[3], os.Args[4]); if err != nil { return err }
	raw, err := tls.Dial("tcp", "127.0.0.1:"+os.Args[1], &tls.Config{
		MinVersion: tls.VersionTLS13, MaxVersion: tls.VersionTLS13, RootCAs: pool,
		ServerName: "localhost", Certificates: []tls.Certificate{cert}, NextProtos: []string{"hearth-peer.yamux/1"},
	}); if err != nil { return err }; defer raw.Close()
	if raw.ConnectionState().NegotiatedProtocol != "hearth-peer.yamux/1" || len(raw.ConnectionState().VerifiedChains) == 0 { return fmt.Errorf("unverified or wrong ALPN") }
	configuration := yamux.DefaultConfig(); configuration.EnableKeepAlive = false; configuration.LogOutput = io.Discard
	session, err := yamux.Client(raw, configuration); if err != nil { return err }; defer session.Close()
	stream, err := session.OpenStream(); if err != nil { return err }
	hello, _ := json.Marshal(map[string]string{"device_id": os.Args[5], "exit_id": os.Args[6]})
	// Fragment control headers and coalesce the tail with the first heartbeat.
	start := frame(1, hello); if _, err = stream.Write(start[:7]); err != nil { return err }
	if _, err = stream.Write(append(start[7:], frame(2, []byte(os.Args[7]))...)); err != nil { return err }
	fmt.Println("READY")
	scanner := bufio.NewScanner(os.Stdin)
	for scanner.Scan() {
		line := scanner.Text()
		if line == "close" { return nil }
		if line == "halfclose" { stream.Close(); fmt.Println("HALFCLOSED"); continue }
		if len(line) > 6 && line[:6] == "sleep " { n, err := strconv.Atoi(line[6:]); if err != nil { return err }; time.Sleep(time.Duration(n)*time.Millisecond); continue }
		if _, err := stream.Write(frame(2, []byte(line))); err != nil { return err }
		fmt.Println("SENT")
	}
	return scanner.Err()
}

func main() { if err := run(); err != nil { fmt.Fprintln(os.Stderr, err); os.Exit(1) } }
