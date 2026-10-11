// Independent TLS/yamux device and Ed25519 grant verifier. Test-only.
package main

import (
	"bufio"
	"bytes"
	"crypto/ed25519"
	"crypto/sha256"
	"crypto/tls"
	"crypto/x509"
	"encoding/base64"
	"encoding/binary"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"strconv"
	"strings"
	"sync"
	"time"

	"github.com/hashicorp/yamux"
)

var public, _ = hex.DecodeString("d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a")
var banner = []byte{0, 255, 128, 1, 13, 10}
var tail = []byte{0, 254, 127, 0}

type claim struct {
	Iss  string `json:"iss"`
	Exit string `json:"exit_id"`
	Conn string `json:"conn_id"`
	Host string `json:"target_host"`
	IP   string `json:"target_ip"`
	Port int    `json:"port"`
	Iat  int64  `json:"iat"`
	Exp  int64  `json:"exp"`
}
type start struct {
	Token string `json:"dial_grant_bytes"`
	Exit  string `json:"exit_id"`
	Conn  string `json:"conn_id"`
	Host  string `json:"target_host"`
	IP    string `json:"target_ip"`
	Port  int    `json:"port"`
	Exp   int64  `json:"expires"`
}
type verifier struct {
	mu   sync.Mutex
	seen map[string]int64
}

func (v *verifier) verify(data []byte, exit string) (start, error) {
	var s start
	if err := json.Unmarshal(data, &s); err != nil {
		return s, err
	}
	parts := strings.Split(s.Token, ".")
	if len(parts) != 3 {
		return s, fmt.Errorf("compact grant")
	}
	dec := base64.RawURLEncoding.Strict()
	h, err := dec.DecodeString(parts[0])
	if err != nil {
		return s, err
	}
	var hdr map[string]string
	if json.Unmarshal(h, &hdr) != nil || hdr["alg"] != "EdDSA" || hdr["typ"] != "hearth-dial-grant" || hdr["kid"] != "pop-1" {
		return s, fmt.Errorf("grant header")
	}
	sig, err := dec.DecodeString(parts[2])
	if err != nil || !ed25519.Verify(public, []byte(parts[0]+"."+parts[1]), sig) {
		return s, fmt.Errorf("signature")
	}
	p, err := dec.DecodeString(parts[1])
	if err != nil {
		return s, err
	}
	var c claim
	if json.Unmarshal(p, &c) != nil {
		return s, fmt.Errorf("claims")
	}
	now := time.Now().Unix()
	if c.Iss != "proxy-gateway" || c.Exit != exit || c.Exit != s.Exit || c.Conn == "" || c.Conn != s.Conn || c.Host != s.Host || c.IP != s.IP || c.Port != s.Port || c.Exp != s.Exp || c.Port < 1 || c.Port > 65535 || (c.Host == "") == (c.IP == "") || c.Exp <= now || c.Iat > now+30 || c.Exp <= c.Iat || c.Exp-c.Iat > 60 {
		return s, fmt.Errorf("binding, target or time")
	}
	v.mu.Lock()
	defer v.mu.Unlock()
	for k, exp := range v.seen {
		if exp <= now {
			delete(v.seen, k)
		}
	}
	if _, ok := v.seen[c.Conn]; ok {
		return s, fmt.Errorf("replay")
	}
	if len(v.seen) >= 4096 {
		return s, fmt.Errorf("replay capacity")
	}
	v.seen[c.Conn] = c.Exp
	return s, nil
}
func frameID(kind byte, id uint32, data []byte) []byte {
	result := make([]byte, 16+len(data))
	copy(result, "HPW1")
	result[4] = kind
	binary.BigEndian.PutUint32(result[8:12], id)
	binary.BigEndian.PutUint32(result[12:16], uint32(len(data)))
	copy(result[16:], data)
	return result
}
func frame(kind byte, data []byte) []byte { return frameID(kind, 0, data) }
func readFrame(r io.Reader) (byte, uint32, []byte, error) {
	h := make([]byte, 16)
	if _, err := io.ReadFull(r, h); err != nil {
		return 0, 0, nil, err
	}
	size := binary.BigEndian.Uint32(h[12:])
	id := binary.BigEndian.Uint32(h[8:12])
	if !bytes.Equal(h[:4], []byte("HPW1")) || h[5] != 0 || h[6] != 0 || h[7] != 0 || size > 65536 {
		return 0, 0, nil, fmt.Errorf("frame header")
	}
	data := make([]byte, size)
	_, err := io.ReadFull(r, data)
	return h[4], id, data, err
}
func relay(stream *yamux.Stream, v *verifier, exit string) {
	defer stream.Close()
	kind, id, data, err := readFrame(stream)
	if err != nil {
		return
	}
	if kind != 7 || id == 0 {
		return
	}
	s, err := v.verify(data, exit)
	if err != nil {
		stream.Write(frameID(4, id, []byte("grant_invalid")))
		fmt.Println("REJECT", id)
		return
	}
	digest := sha256.Sum256([]byte(s.Token))
	fmt.Printf("START %s %d %x\n", s.Conn, id, digest)
	if s.Host == "delay.example" {
		time.Sleep(800 * time.Millisecond)
	}
	if s.Host == "deny.example" {
		stream.Write(frameID(4, id, []byte("policy_denied")))
		return
	}
	if s.Host == "early.example" {
		stream.Write(frameID(5, id, []byte("forbidden")))
		return
	}
	if _, err = stream.Write(append(frameID(4, id, []byte("ok")), frameID(5, id, banner)...)); err != nil {
		return
	}
	for {
		k, fid, payload, err := readFrame(stream)
		if err == io.EOF {
			stream.Write(append(frameID(5, id, tail), frameID(6, id, nil)...))
			fmt.Println("CLOSED", s.Conn)
			return
		}
		if err != nil {
			fmt.Println("CANCELLED", s.Conn)
			return
		}
		if fid != id {
			return
		}
		if k == 6 {
			fmt.Println("CANCELLED", s.Conn)
			return
		}
		if k != 5 {
			return
		}
		if _, err = stream.Write(frameID(5, id, payload)); err != nil {
			return
		}
	}
}
func run() error {
	if len(os.Args) > 1 && os.Args[1] == "--verify-start" {
		if len(os.Args) != 4 {
			return fmt.Errorf("verify-start file exit")
		}
		data, err := os.ReadFile(os.Args[2])
		if err != nil {
			return err
		}
		v := &verifier{seen: make(map[string]int64)}
		s, err := v.verify(data, os.Args[3])
		if err != nil {
			return err
		}
		fmt.Println("VERIFIED", s.Conn)
		if _, err = v.verify(data, os.Args[3]); err == nil {
			return fmt.Errorf("accepted replay")
		}
		fmt.Println("REPLAY_REJECTED")
		return nil
	}
	if len(os.Args) != 8 {
		return fmt.Errorf("port roots cert key device exit initial-health required")
	}
	root, err := os.ReadFile(os.Args[2])
	if err != nil {
		return err
	}
	pool := x509.NewCertPool()
	if !pool.AppendCertsFromPEM(root) {
		return fmt.Errorf("roots")
	}
	cert, err := tls.LoadX509KeyPair(os.Args[3], os.Args[4])
	if err != nil {
		return err
	}
	raw, err := tls.Dial("tcp", "127.0.0.1:"+os.Args[1], &tls.Config{MinVersion: tls.VersionTLS13, MaxVersion: tls.VersionTLS13, RootCAs: pool, ServerName: "localhost", Certificates: []tls.Certificate{cert}, NextProtos: []string{"hearth-peer.yamux/1"}})
	if err != nil {
		return err
	}
	defer raw.Close()
	if raw.ConnectionState().NegotiatedProtocol != "hearth-peer.yamux/1" || len(raw.ConnectionState().VerifiedChains) == 0 {
		return fmt.Errorf("unverified ALPN")
	}
	configuration := yamux.DefaultConfig()
	configuration.EnableKeepAlive = false
	configuration.LogOutput = io.Discard
	session, err := yamux.Client(raw, configuration)
	if err != nil {
		return err
	}
	defer session.Close()
	stream, err := session.OpenStream()
	if err != nil {
		return err
	}
	v := &verifier{seen: make(map[string]int64)}
	go func() {
		for {
			accepted, err := session.AcceptStream()
			if err != nil {
				return
			}
			go relay(accepted, v, os.Args[6])
		}
	}()
	hello, _ := json.Marshal(map[string]string{"device_id": os.Args[5], "exit_id": os.Args[6]})
	initial := frame(1, hello)
	if _, err = stream.Write(initial[:7]); err != nil {
		return err
	}
	if _, err = stream.Write(append(initial[7:], frame(2, []byte(os.Args[7]))...)); err != nil {
		return err
	}
	fmt.Println("READY")
	// Long relay tests opt into the protocol's real fifteen-second heartbeat.
	// Admission timeout fixtures keep their existing silent-peer behavior.
	var control sync.Mutex
	health := os.Args[7]
	closed := false
	done := make(chan struct{})
	defer close(done)
	interval, err := strconv.Atoi(os.Getenv("MINYAR_PEER_DEVICE_HEARTBEAT_MS"))
	if os.Getenv("MINYAR_PEER_DEVICE_HEARTBEAT_MS") != "" && (err != nil || interval != 15000) {
		return fmt.Errorf("heartbeat fixture interval must be fifteen seconds")
	}
	if interval > 0 {
		go func() {
			ticker := time.NewTicker(time.Duration(interval) * time.Millisecond)
			defer ticker.Stop()
			for {
				select {
				case <-done:
					return
				case <-ticker.C:
					control.Lock()
					if !closed {
						_, err := stream.Write(frame(2, []byte(health)))
						if err != nil {
							closed = true
							fmt.Fprintln(os.Stderr, "heartbeat:", err)
						} else {
							fmt.Println("HEARTBEAT")
						}
					}
					control.Unlock()
				}
			}
		}()
	}
	scanner := bufio.NewScanner(os.Stdin)
	for scanner.Scan() {
		line := scanner.Text()
		if line == "close" {
			return nil
		}
		if line == "halfclose" {
			control.Lock()
			closed = true
			stream.Close()
			control.Unlock()
			fmt.Println("HALFCLOSED")
			continue
		}
		if strings.HasPrefix(line, "sleep ") {
			n, err := strconv.Atoi(line[6:])
			if err != nil {
				return err
			}
			time.Sleep(time.Duration(n) * time.Millisecond)
			continue
		}
		control.Lock()
		health = line
		_, err = stream.Write(frame(2, []byte(line)))
		control.Unlock()
		if err != nil {
			return err
		}
		fmt.Println("SENT")
	}
	return scanner.Err()
}
func main() {
	if err := run(); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
