package main

import (
	"bufio"
	"bytes"
	"context"
	"crypto/ecdsa"
	"crypto/elliptic"
	"crypto/rand"
	"crypto/sha256"
	"crypto/tls"
	"crypto/x509"
	"crypto/x509/pkix"
	"encoding/binary"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"math/big"
	"net"
	"net/url"
	"os"
	"path/filepath"
	"sort"
	"strconv"
	"sync"
	"time"

	"golang.org/x/net/http2"
	"golang.org/x/net/http2/hpack"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials"
	"google.golang.org/grpc/status"
)

func clientTLS(caPath, certPath, keyPath string, protocols []string, tls13 bool) *tls.Config {
	pem, err := os.ReadFile(caPath)
	if err != nil {
		fail("read roots: %v", err)
	}
	pool := x509.NewCertPool()
	if !pool.AppendCertsFromPEM(pem) {
		fail("parse roots")
	}
	certificate, err := tls.LoadX509KeyPair(certPath, keyPath)
	if err != nil {
		fail("load client identity: %v", err)
	}
	config := &tls.Config{RootCAs: pool, ServerName: "localhost", Certificates: []tls.Certificate{certificate}, NextProtos: protocols}
	if tls13 {
		config.MinVersion = tls.VersionTLS13
		config.MaxVersion = tls.VersionTLS13
	}
	return config
}

type command struct {
	Op      string `json:"op"`
	Name    string `json:"name"`
	Open    string `json:"open"`
	Payload string `json:"payload"`
	Banner  string `json:"banner"`
	Tail    string `json:"tail"`
	Path    string `json:"path"`
	Message string `json:"message"`
	Timeout int    `json:"timeout_ms"`
	Hold    int    `json:"hold_ms"`
	Grant   string `json:"grant"`
	Exit    string `json:"exit"`
	Conn    string `json:"conn"`
}

func (item command) opened() []byte {
	if item.Open != "" {
		return decodeHex(item.Open)
	}
	return encodeFrame(frameSpec{Open: &openRequest{Grant: item.Grant, Exit: item.Exit, Conn: item.Conn}})
}

type held struct {
	stream grpc.ClientStream
	cancel context.CancelFunc
}

func decodeHex(text string) []byte {
	data, err := hex.DecodeString(text)
	if err != nil {
		fail("command hex: %v", err)
	}
	return data
}

func statusName(err error) string {
	if err == nil || errors.Is(err, io.EOF) {
		return "OK"
	}
	return status.Code(err).String()
}

func sessionTransfer(connection *grpc.ClientConn, item command) map[string]any {
	ctx, cancel := context.WithTimeout(context.Background(), time.Duration(item.Timeout)*time.Millisecond)
	defer cancel()
	result := map[string]any{"op": "transfer"}
	stream, err := connection.NewStream(ctx, description, route, grpc.ForceCodec(rawCodec{}))
	if err != nil {
		result["error"] = err.Error()
		return result
	}
	if err := stream.SendMsg(item.opened()); err != nil {
		result["error"] = "send open: " + err.Error()
		return result
	}
	first, err := receiveFrame(stream)
	if err != nil {
		result["error"] = "first: " + err.Error()
		result["status"] = statusName(err)
		return result
	}
	result["first"] = first["body"]
	result["code"] = first["code"]
	payload := decodeHex(item.Payload)
	for at := 0; at < len(payload); at += 16384 {
		end := at + 16384
		if end > len(payload) {
			end = len(payload)
		}
		if err := stream.SendMsg(dataFrame(payload[at:end])); err != nil {
			result["error"] = "send data: " + err.Error()
			return result
		}
	}
	if err := stream.CloseSend(); err != nil {
		result["error"] = "close send: " + err.Error()
		return result
	}
	var received []byte
	chunks := []int{}
	for {
		message, err := receiveFrame(stream)
		if err != nil {
			result["status"] = statusName(err)
			if !errors.Is(err, io.EOF) {
				result["error"] = "receive: " + err.Error()
			}
			break
		}
		if body, _ := message["body"].(string); body != "data" {
			result["error"] = "unexpected response body " + body
			break
		}
		decoded, _ := hex.DecodeString(message["data"].(string))
		chunks = append(chunks, len(decoded))
		received = append(received, decoded...)
	}
	expected := append(append(decodeHex(item.Banner), payload...), decodeHex(item.Tail)...)
	result["received"] = len(received)
	result["chunks"] = chunks
	result["match"] = bytes.Equal(received, expected)
	return result
}

func sessionCall(connection *grpc.ClientConn, item command, path string, message []byte) map[string]any {
	ctx, cancel := context.WithTimeout(context.Background(), time.Duration(item.Timeout)*time.Millisecond)
	defer cancel()
	result := map[string]any{"op": item.Op}
	stream, err := connection.NewStream(ctx, description, path, grpc.ForceCodec(rawCodec{}))
	if err != nil {
		result["error"] = err.Error()
		result["status"] = statusName(err)
		return result
	}
	if err := stream.SendMsg(message); err != nil {
		result["status"] = statusName(err)
		result["error"] = "send: " + err.Error()
		return result
	}
	released := make(chan struct{})
	var once sync.Once
	release := func() { once.Do(func() { stream.CloseSend(); close(released) }) }
	if item.Hold > 0 {
		go func() {
			select {
			case <-time.After(time.Duration(item.Hold) * time.Millisecond):
				release()
			case <-released:
			}
		}()
	} else {
		release()
	}
	messages := []map[string]any{}
	for {
		response, err := receiveFrame(stream)
		if err != nil {
			result["status"] = statusName(err)
			if !errors.Is(err, io.EOF) {
				result["error"] = err.Error()
			}
			break
		}
		messages = append(messages, response)
	}
	release()
	result["messages"] = messages
	return result
}

func sessionHold(connection *grpc.ClientConn, item command, streams map[string]held) map[string]any {
	ctx, cancel := context.WithTimeout(context.Background(), time.Duration(item.Timeout)*time.Millisecond)
	result := map[string]any{"op": "hold", "name": item.Name}
	stream, err := connection.NewStream(ctx, description, route, grpc.ForceCodec(rawCodec{}))
	if err != nil {
		cancel()
		result["error"] = err.Error()
		return result
	}
	if err := stream.SendMsg(item.opened()); err != nil {
		cancel()
		result["error"] = err.Error()
		return result
	}
	first, err := receiveFrame(stream)
	if err != nil {
		cancel()
		result["error"] = err.Error()
		return result
	}
	streams[item.Name] = held{stream: stream, cancel: cancel}
	result["first"] = first["body"]
	result["code"] = first["code"]
	return result
}

func session(address, caPath, certPath, keyPath string) {
	connection, err := grpc.NewClient(address, grpc.WithTransportCredentials(credentials.NewTLS(clientTLS(caPath, certPath, keyPath, nil, false))))
	if err != nil {
		fail("dial: %v", err)
	}
	defer connection.Close()
	listener, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		fail("control listen: %v", err)
	}
	fmt.Printf("READY %d\n", listener.Addr().(*net.TCPAddr).Port)
	control, err := listener.Accept()
	if err != nil {
		fail("control accept: %v", err)
	}
	listener.Close()
	defer control.Close()
	reader := bufio.NewReaderSize(control, 1<<20)
	streams := map[string]held{}
	for {
		line, err := reader.ReadBytes('\n')
		if len(line) == 0 && err != nil {
			return
		}
		var item command
		if err := json.Unmarshal(line, &item); err != nil {
			fail("parse command: %v", err)
		}
		var result map[string]any
		switch item.Op {
		case "transfer":
			result = sessionTransfer(connection, item)
		case "call":
			result = sessionCall(connection, item, route, item.opened())
		case "raw":
			result = sessionCall(connection, item, item.Path, decodeHex(item.Message))
		case "hold":
			result = sessionHold(connection, item, streams)
		case "cancel":
			entry, found := streams[item.Name]
			result = map[string]any{"op": "cancel", "name": item.Name, "found": found}
			if found {
				entry.cancel()
				_, after := receiveFrame(entry.stream)
				result["status"] = statusName(after)
				delete(streams, item.Name)
			}
		default:
			fail("unknown session operation %q", item.Op)
		}
		encoded, _ := json.Marshal(result)
		if _, err := control.Write(append(encoded, '\n')); err != nil {
			return
		}
	}
}

func abrupt(address, caPath, certPath, keyPath, openHex string) {
	raw, err := tls.Dial("tcp", address, clientTLS(caPath, certPath, keyPath, []string{"h2"}, false))
	if err != nil {
		fail("dial: %v", err)
	}
	if raw.ConnectionState().NegotiatedProtocol != "h2" {
		fail("gateway did not negotiate h2")
	}
	var headers bytes.Buffer
	encoder := hpack.NewEncoder(&headers)
	for _, entry := range [][2]string{{":method", "POST"}, {":scheme", "https"}, {":authority", "localhost"}, {":path", route},
		{"content-type", "application/grpc"}, {"te", "trailers"}, {"grpc-timeout", "10S"}} {
		encoder.WriteField(hpack.HeaderField{Name: entry[0], Value: entry[1]})
	}
	message := decodeHex(openHex)
	envelope := append([]byte{0, 0, 0, 0, 0}, message...)
	binary.BigEndian.PutUint32(envelope[1:5], uint32(len(message)))
	writer := bufio.NewWriter(raw)
	framer := http2.NewFramer(writer, raw)
	framer.ReadMetaHeaders = hpack.NewDecoder(4096, nil)
	writer.WriteString(http2.ClientPreface)
	framer.WriteSettings()
	framer.WriteHeaders(http2.HeadersFrameParam{StreamID: 1, BlockFragment: headers.Bytes(), EndHeaders: true})
	framer.WriteData(1, false, envelope)
	writer.Flush()
	raw.SetReadDeadline(time.Now().Add(5 * time.Second))
	var data []byte
	admitted := false
	for !admitted {
		frame, err := framer.ReadFrame()
		if err != nil {
			fail("abrupt fixture did not establish a real relay: %v", err)
		}
		switch typed := frame.(type) {
		case *http2.SettingsFrame:
			if !typed.IsAck() {
				framer.WriteSettingsAck()
			}
		case *http2.DataFrame:
			if typed.StreamID != 1 {
				fail("data on unexpected stream %d", typed.StreamID)
			}
			data = append(data, typed.Data()...)
			if length := uint32(len(typed.Data())); length > 0 {
				framer.WriteWindowUpdate(0, length)
				framer.WriteWindowUpdate(1, length)
			}
		case *http2.RSTStreamFrame:
			fail("gateway reset the admitted stream")
		case *http2.GoAwayFrame:
			fail("gateway terminated the connection")
		}
		for len(data) >= 5 {
			size := int(binary.BigEndian.Uint32(data[1:5]))
			if data[0] != 0 || size > 65540 {
				fail("invalid gateway envelope")
			}
			if len(data) < 5+size {
				break
			}
			described := describeFrame(data[5 : 5+size])
			data = data[5+size:]
			if described["body"] == "status" {
				if described["code"] != int64(0) {
					fail("abrupt fixture was not admitted: %v", described)
				}
				admitted = true
			}
		}
		writer.Flush()
	}
	connection := raw.NetConn().(*net.TCPConn)
	connection.SetLinger(0)
	connection.Close()
	fmt.Println("ADMITTED")
}

func h2Probe(address, caPath, certPath, keyPath string) {
	raw, err := tls.Dial("tcp", address, clientTLS(caPath, certPath, keyPath, []string{"h2"}, true))
	if err != nil {
		fmt.Println("REJECTED handshake", err)
		return
	}
	defer raw.Close()
	if raw.ConnectionState().NegotiatedProtocol != "h2" {
		fail("gateway did not negotiate h2")
	}
	writer := bufio.NewWriter(raw)
	framer := http2.NewFramer(writer, raw)
	writer.WriteString(http2.ClientPreface)
	framer.WriteSettings()
	writer.Flush()
	raw.SetReadDeadline(time.Now().Add(3 * time.Second))
	for {
		frame, err := framer.ReadFrame()
		if err != nil {
			var timeout net.Error
			if errors.As(err, &timeout) && timeout.Timeout() {
				fmt.Println("TIMEOUT", err)
				return
			}
			fmt.Println("REJECTED read", err)
			return
		}
		if settings, ok := frame.(*http2.SettingsFrame); ok && !settings.IsAck() {
			fmt.Println("ACCEPTED")
			return
		}
	}
}

func deviceProbe(address, caPath, certPath, keyPath string) {
	raw, err := tls.Dial("tcp", address, clientTLS(caPath, certPath, keyPath, []string{"hearth-peer.yamux/1"}, true))
	if err != nil {
		fmt.Println("REJECTED handshake", err)
		return
	}
	defer raw.Close()
	raw.SetReadDeadline(time.Now().Add(3 * time.Second))
	buffer := make([]byte, 65536)
	count, err := raw.Read(buffer)
	if count > 0 {
		fmt.Println("DATA", count)
		return
	}
	var timeout net.Error
	if errors.As(err, &timeout) && timeout.Timeout() {
		fmt.Println("TIMEOUT")
		return
	}
	fmt.Println("REJECTED read", err)
}

func chainProbe(address, caPath, certPath, keyPath string) {
	raw, err := tls.Dial("tcp", address, clientTLS(caPath, certPath, keyPath, []string{"h2"}, false))
	if err == nil {
		raw.Close()
		fmt.Println("TRUSTED")
		return
	}
	var verification *tls.CertificateVerificationError
	if errors.As(err, &verification) {
		fmt.Println("VERIFY_FAILED", err)
		return
	}
	fmt.Println("OTHER", err)
}

type fixtureSummary struct {
	Peers        int               `json:"peers"`
	Certificates string            `json:"certificates"`
	Sha256       map[string]string `json:"sha256"`
}

func scaleFixtures(directory string, count int) {
	if _, err := os.Stat(directory); err == nil {
		fail("fixture directory already exists: %s", directory)
	}
	if err := os.MkdirAll(directory, 0o755); err != nil {
		fail("fixture directory: %v", err)
	}
	caKey, err := ecdsa.GenerateKey(elliptic.P256(), rand.Reader)
	if err != nil {
		fail("ca key: %v", err)
	}
	leafKey, err := ecdsa.GenerateKey(elliptic.P256(), rand.Reader)
	if err != nil {
		fail("leaf key: %v", err)
	}
	keyIdentifier := func(key *ecdsa.PublicKey) []byte {
		encoded, err := x509.MarshalPKIXPublicKey(key)
		if err != nil {
			fail("public key: %v", err)
		}
		digest := sha256.Sum256(encoded)
		return digest[:20]
	}
	name := pkix.Name{CommonName: "Minyar disposable scale root"}
	now := time.Now().UTC()
	caTemplate := &x509.Certificate{SerialNumber: big.NewInt(1), Subject: name, NotBefore: now.Add(-5 * time.Minute), NotAfter: now.Add(48 * time.Hour),
		BasicConstraintsValid: true, IsCA: true, MaxPathLen: 0, MaxPathLenZero: true, KeyUsage: x509.KeyUsageCertSign | x509.KeyUsageCRLSign,
		SubjectKeyId: keyIdentifier(&caKey.PublicKey)}
	caDER, err := x509.CreateCertificate(rand.Reader, caTemplate, caTemplate, &caKey.PublicKey, caKey)
	if err != nil {
		fail("ca certificate: %v", err)
	}
	ca, _ := x509.ParseCertificate(caDER)
	write := func(file string, data []byte) {
		if err := os.WriteFile(filepath.Join(directory, file), data, 0o644); err != nil {
			fail("write %s: %v", file, err)
		}
	}
	write("root.der", caDER)
	leafPKCS8, err := x509.MarshalPKCS8PrivateKey(leafKey)
	if err != nil {
		fail("leaf key encoding: %v", err)
	}
	write("leaf.pk8", leafPKCS8)
	registry := bytes.Buffer{}
	for index := -2; index < count; index++ {
		server := index == -2
		gateway := index == -1
		label := fmt.Sprintf("device-%05d", index)
		if server {
			label = "server"
		} else if gateway {
			label = "gateway"
		}
		template := &x509.Certificate{SerialNumber: big.NewInt(int64(index + 4)), Subject: pkix.Name{CommonName: label}, NotBefore: now.Add(-5 * time.Minute),
			NotAfter: now.Add(48 * time.Hour), BasicConstraintsValid: true, IsCA: false, KeyUsage: x509.KeyUsageDigitalSignature,
			SubjectKeyId: keyIdentifier(&leafKey.PublicKey), AuthorityKeyId: ca.SubjectKeyId}
		if server {
			template.DNSNames = []string{"localhost"}
			template.ExtKeyUsage = []x509.ExtKeyUsage{x509.ExtKeyUsageServerAuth}
		} else {
			uri, _ := url.Parse("hearth://device/" + label)
			template.URIs = []*url.URL{uri}
			template.ExtKeyUsage = []x509.ExtKeyUsage{x509.ExtKeyUsageClientAuth}
		}
		encoded, err := x509.CreateCertificate(rand.Reader, template, ca, &leafKey.PublicKey, caKey)
		if err != nil {
			fail("certificate %s: %v", label, err)
		}
		write(label+".der", encoded)
		if gateway {
			digest := sha256.Sum256(encoded)
			fmt.Fprintf(&registry, "{\"role\": \"gateway\", \"sha256\": \"%x\"}\n", digest)
		} else if !server {
			fmt.Fprintf(&registry, "{\"role\": \"device\", \"device_id\": \"%s\", \"exit_id\": \"exit-%05d\", \"revoked\": false, \"paused\": false, \"quarantined\": false, \"max_concurrent\": 8}\n", label, index)
		}
	}
	write("registry.ndjson", registry.Bytes())
	write("jwks.json", []byte("{\"keys\":[{\"kty\":\"OKP\",\"crv\":\"Ed25519\",\"kid\":\"pop-1\",\"alg\":\"EdDSA\",\"use\":\"sig\",\"x\":\"11qYAYKxCrfVS_7TyWQHOg7hcvPapiMlrwIaaPcHURo\"}]}\n"))
	entries, err := os.ReadDir(directory)
	if err != nil {
		fail("list fixtures: %v", err)
	}
	names := []string{}
	for _, entry := range entries {
		if entry.Type().IsRegular() {
			names = append(names, entry.Name())
		}
	}
	sort.Strings(names)
	summary := fixtureSummary{Peers: count, Certificates: "unique signed device URI SAN and serial; shared disposable lab leaf key", Sha256: map[string]string{}}
	for _, file := range names {
		data, err := os.ReadFile(filepath.Join(directory, file))
		if err != nil {
			fail("hash %s: %v", file, err)
		}
		digest := sha256.Sum256(data)
		summary.Sha256[file] = hex.EncodeToString(digest[:])
	}
	encoded, _ := json.MarshalIndent(summary, "", "  ")
	write("fixtures.json", append(encoded, '\n'))
}

type pooled struct {
	connection *tls.Conn
	writer     *bufio.Writer
	framer     *http2.Framer
}

func (peer pooled) acknowledge(frame http2.Frame) error {
	switch typed := frame.(type) {
	case *http2.SettingsFrame:
		if !typed.IsAck() {
			peer.framer.WriteSettingsAck()
			return peer.writer.Flush()
		}
	case *http2.GoAwayFrame:
		return errors.New("pooled gateway GOAWAY")
	}
	return nil
}

func poolPing(peers []pooled, round int) (int, error) {
	for index, peer := range peers {
		var nonce [8]byte
		binary.BigEndian.PutUint64(nonce[:], uint64(round*len(peers)+index))
		peer.framer.WritePing(false, nonce)
		if err := peer.writer.Flush(); err != nil {
			return 0, err
		}
	}
	for index, peer := range peers {
		var nonce [8]byte
		binary.BigEndian.PutUint64(nonce[:], uint64(round*len(peers)+index))
		peer.connection.SetReadDeadline(time.Now().Add(5 * time.Second))
		for {
			frame, err := peer.framer.ReadFrame()
			if err != nil {
				return 0, fmt.Errorf("pooled gateway PING deadline: %v", err)
			}
			if err := peer.acknowledge(frame); err != nil {
				return 0, err
			}
			if ping, ok := frame.(*http2.PingFrame); ok && ping.IsAck() && ping.Data == nonce {
				break
			}
		}
	}
	return len(peers), nil
}

// Application-ready idle gateways: each completes TLS 1.3, h2 and a real
// SETTINGS exchange, then answers PING rounds without reconnecting.
func gatewayPool(address, caPath, certPath, keyPath string, count int) {
	config := clientTLS(caPath, certPath, keyPath, []string{"h2"}, true)
	peers := []pooled{}
	closeAll := func() {
		for _, peer := range peers {
			peer.connection.Close()
		}
	}
	for index := 0; index < count; index++ {
		raw, err := net.DialTimeout("tcp", address, 5*time.Second)
		if err != nil {
			closeAll()
			fail("idle gateway dial: %v", err)
		}
		raw.(*net.TCPConn).SetNoDelay(true)
		connection := tls.Client(raw, config)
		connection.SetDeadline(time.Now().Add(5 * time.Second))
		if err := connection.Handshake(); err != nil || connection.ConnectionState().NegotiatedProtocol != "h2" {
			closeAll()
			fail("idle gateway handshake: %v", err)
		}
		writer := bufio.NewWriter(connection)
		peer := pooled{connection: connection, writer: writer, framer: http2.NewFramer(writer, connection)}
		writer.WriteString(http2.ClientPreface)
		peer.framer.WriteSettings()
		writer.Flush()
		for settled := false; !settled; {
			frame, err := peer.framer.ReadFrame()
			if err != nil {
				closeAll()
				fail("idle gateway closed during SETTINGS: %v", err)
			}
			if settings, ok := frame.(*http2.SettingsFrame); ok && !settings.IsAck() {
				settled = true
			}
			if err := peer.acknowledge(frame); err != nil {
				closeAll()
				fail("idle gateway SETTINGS: %v", err)
			}
		}
		connection.SetDeadline(time.Time{})
		peers = append(peers, peer)
		if (index+1)%256 == 0 {
			fmt.Println("CONNECTED", index+1)
		}
	}
	listener, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		closeAll()
		fail("control listener: %v", err)
	}
	fmt.Println("READY", listener.Addr().(*net.TCPAddr).Port)
	control, err := listener.Accept()
	listener.Close()
	if err != nil {
		closeAll()
		fail("control accept: %v", err)
	}
	reader := bufio.NewReader(control)
	for {
		line, err := reader.ReadBytes('\n')
		if err != nil {
			closeAll()
			return
		}
		var request struct {
			Op    string `json:"op"`
			Round int    `json:"round"`
		}
		result := map[string]any{}
		if err := json.Unmarshal(line, &request); err != nil {
			result["error"] = err.Error()
		} else if request.Op == "ping" {
			acks, err := poolPing(peers, request.Round)
			result["acks"] = acks
			if err != nil {
				result["error"] = err.Error()
			}
		} else if request.Op == "close" {
			closeAll()
			result["closed"] = len(peers)
			encoded, _ := json.Marshal(result)
			control.Write(append(encoded, '\n'))
			return
		} else {
			result["error"] = "unknown pool operation"
		}
		encoded, _ := json.Marshal(result)
		control.Write(append(encoded, '\n'))
	}
}

// RST_STREAM on stream zero is a connection error; complete authenticated
// traffic on other sockets must still work after this peer is retired.
func malformedGateway(address, caPath, certPath, keyPath string) {
	connection, err := tls.Dial("tcp", address, clientTLS(caPath, certPath, keyPath, []string{"h2"}, false))
	if err != nil {
		fail("malformed gateway dial: %v", err)
	}
	connection.Write(append([]byte(http2.ClientPreface), 0, 0, 4, 3, 0, 0, 0, 0, 0, 0, 0, 0, 8))
	connection.Close()
	fmt.Println("SENT")
}

func edgeCommand(arguments []string) bool {
	if len(arguments) == 0 {
		return false
	}
	switch arguments[0] {
	case "session":
		if len(arguments) != 5 {
			fail("usage: session ADDRESS CA CERT KEY")
		}
		session(arguments[1], arguments[2], arguments[3], arguments[4])
	case "abrupt":
		if len(arguments) != 6 {
			fail("usage: abrupt ADDRESS CA CERT KEY OPEN_HEX")
		}
		abrupt(arguments[1], arguments[2], arguments[3], arguments[4], arguments[5])
	case "h2-probe", "device-probe", "chain-probe":
		if len(arguments) != 5 {
			fail("usage: %s ADDRESS CA CERT KEY", arguments[0])
		}
		map[string]func(string, string, string, string){"h2-probe": h2Probe, "device-probe": deviceProbe, "chain-probe": chainProbe}[arguments[0]](arguments[1], arguments[2], arguments[3], arguments[4])
	case "gateway-pool":
		if len(arguments) != 6 {
			fail("usage: gateway-pool ADDRESS CA CERT KEY COUNT")
		}
		count, err := strconv.Atoi(arguments[5])
		if err != nil || count < 1 {
			fail("invalid gateway count")
		}
		gatewayPool(arguments[1], arguments[2], arguments[3], arguments[4], count)
	case "malformed-gateway":
		if len(arguments) != 5 {
			fail("usage: malformed-gateway ADDRESS CA CERT KEY")
		}
		malformedGateway(arguments[1], arguments[2], arguments[3], arguments[4])
	case "scale-fixtures":
		if len(arguments) != 3 {
			fail("usage: scale-fixtures DIRECTORY COUNT")
		}
		count, err := strconv.Atoi(arguments[2])
		if err != nil || count < 1 {
			fail("invalid fixture count")
		}
		scaleFixtures(arguments[1], count)
	default:
		return false
	}
	return true
}
