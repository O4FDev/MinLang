package main

import (
	"bytes"
	"context"
	"encoding/binary"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"strconv"
	"sync"
	"time"

	"golang.org/x/net/http2"
	"golang.org/x/net/http2/hpack"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/metadata"
	"google.golang.org/grpc/status"
	"google.golang.org/protobuf/proto"
	"google.golang.org/protobuf/reflect/protodesc"
	"google.golang.org/protobuf/reflect/protoreflect"
	"google.golang.org/protobuf/types/descriptorpb"
	"google.golang.org/protobuf/types/dynamicpb"
)

const route = "/PeerEdgeDial/OpenExitStream"

type field struct {
	Name  string `json:"n"`
	Value string `json:"v"`
	Hex   string `json:"x"`
}

type block struct {
	TableSize *uint32 `json:"tableSize"`
	Fields    []field `json:"fields"`
}

func fail(format string, arguments ...any) {
	fmt.Fprintf(os.Stderr, "peergrpc: "+format+"\n", arguments...)
	os.Exit(1)
}

func emit(value any) {
	encoded, err := json.Marshal(value)
	if err != nil {
		fail("encode output: %v", err)
	}
	os.Stdout.Write(append(encoded, '\n'))
}

func hpackBlocks(path string) {
	raw, err := os.ReadFile(path)
	if err != nil {
		fail("read blocks: %v", err)
	}
	var blocks []block
	if err := json.Unmarshal(raw, &blocks); err != nil {
		fail("parse blocks: %v", err)
	}
	var buffer bytes.Buffer
	encoder := hpack.NewEncoder(&buffer)
	for _, item := range blocks {
		if item.TableSize != nil {
			encoder.SetMaxDynamicTableSize(*item.TableSize)
		}
		buffer.Reset()
		for _, entry := range item.Fields {
			value := entry.Value
			if entry.Hex != "" {
				decoded, err := hex.DecodeString(entry.Hex)
				if err != nil {
					fail("field hex: %v", err)
				}
				value = string(decoded)
			}
			if err := encoder.WriteField(hpack.HeaderField{Name: entry.Name, Value: value}); err != nil {
				fail("encode field: %v", err)
			}
		}
		fmt.Println(hex.EncodeToString(buffer.Bytes()))
	}
}

var (
	descriptorOnce sync.Once
	frameType      protoreflect.MessageDescriptor
)

func schema() protoreflect.MessageDescriptor {
	descriptorOnce.Do(func() {
		optional := descriptorpb.FieldDescriptorProto_LABEL_OPTIONAL.Enum()
		kind := func(value descriptorpb.FieldDescriptorProto_Type) *descriptorpb.FieldDescriptorProto_Type {
			return value.Enum()
		}
		zero := int32(0)
		file := &descriptorpb.FileDescriptorProto{
			Name:   proto.String("peer.proto"),
			Syntax: proto.String("proto3"),
			MessageType: []*descriptorpb.DescriptorProto{
				{Name: proto.String("OpenExitStreamRequest"), Field: []*descriptorpb.FieldDescriptorProto{
					{Name: proto.String("dial_grant"), Number: proto.Int32(1), Type: kind(descriptorpb.FieldDescriptorProto_TYPE_BYTES), Label: optional},
					{Name: proto.String("exit_id"), Number: proto.Int32(2), Type: kind(descriptorpb.FieldDescriptorProto_TYPE_STRING), Label: optional},
					{Name: proto.String("conn_id"), Number: proto.Int32(3), Type: kind(descriptorpb.FieldDescriptorProto_TYPE_STRING), Label: optional},
				}},
				{Name: proto.String("ExitStatus"),
					EnumType: []*descriptorpb.EnumDescriptorProto{{Name: proto.String("Code"), Value: []*descriptorpb.EnumValueDescriptorProto{
						{Name: proto.String("OK"), Number: proto.Int32(0)},
						{Name: proto.String("GRANT_INVALID"), Number: proto.Int32(1)},
						{Name: proto.String("EXIT_OFFLINE"), Number: proto.Int32(2)},
						{Name: proto.String("POLICY_DENIED"), Number: proto.Int32(3)},
						{Name: proto.String("CONCURRENCY_FULL"), Number: proto.Int32(4)},
					}}},
					Field: []*descriptorpb.FieldDescriptorProto{
						{Name: proto.String("code"), Number: proto.Int32(1), Type: kind(descriptorpb.FieldDescriptorProto_TYPE_ENUM), TypeName: proto.String(".ExitStatus.Code"), Label: optional},
						{Name: proto.String("detail"), Number: proto.Int32(2), Type: kind(descriptorpb.FieldDescriptorProto_TYPE_STRING), Label: optional},
					}},
				{Name: proto.String("ExitByteFrame"),
					OneofDecl: []*descriptorpb.OneofDescriptorProto{{Name: proto.String("body")}},
					Field: []*descriptorpb.FieldDescriptorProto{
						{Name: proto.String("open"), Number: proto.Int32(1), Type: kind(descriptorpb.FieldDescriptorProto_TYPE_MESSAGE), TypeName: proto.String(".OpenExitStreamRequest"), Label: optional, OneofIndex: &zero},
						{Name: proto.String("status"), Number: proto.Int32(2), Type: kind(descriptorpb.FieldDescriptorProto_TYPE_MESSAGE), TypeName: proto.String(".ExitStatus"), Label: optional, OneofIndex: &zero},
						{Name: proto.String("data"), Number: proto.Int32(3), Type: kind(descriptorpb.FieldDescriptorProto_TYPE_BYTES), Label: optional, OneofIndex: &zero},
					}},
			},
		}
		described, err := protodesc.NewFile(file, nil)
		if err != nil {
			fail("schema: %v", err)
		}
		frameType = described.Messages().ByName("ExitByteFrame")
	})
	return frameType
}

type openRequest struct {
	Grant string `json:"grant"`
	Exit  string `json:"exit"`
	Conn  string `json:"conn"`
}

type exitStatus struct {
	Code   int32  `json:"code"`
	Detail string `json:"detail"`
}

type frameSpec struct {
	Open   *openRequest `json:"open"`
	Status *exitStatus  `json:"status"`
	Data   *string      `json:"data"`
}

func encodeFrame(spec frameSpec) []byte {
	descriptor := schema()
	message := dynamicpb.NewMessage(descriptor)
	body := descriptor.Oneofs().ByName("body")
	switch {
	case spec.Open != nil:
		inner := dynamicpb.NewMessage(descriptor.Fields().ByName("open").Message())
		fields := inner.Descriptor().Fields()
		grant, err := hex.DecodeString(spec.Open.Grant)
		if err != nil {
			fail("grant hex: %v", err)
		}
		if len(grant) > 0 {
			inner.Set(fields.ByName("dial_grant"), protoreflect.ValueOfBytes(grant))
		}
		if spec.Open.Exit != "" {
			inner.Set(fields.ByName("exit_id"), protoreflect.ValueOfString(spec.Open.Exit))
		}
		if spec.Open.Conn != "" {
			inner.Set(fields.ByName("conn_id"), protoreflect.ValueOfString(spec.Open.Conn))
		}
		message.Set(body.Fields().ByName("open"), protoreflect.ValueOfMessage(inner))
	case spec.Status != nil:
		inner := dynamicpb.NewMessage(descriptor.Fields().ByName("status").Message())
		fields := inner.Descriptor().Fields()
		if spec.Status.Code != 0 {
			inner.Set(fields.ByName("code"), protoreflect.ValueOfEnum(protoreflect.EnumNumber(spec.Status.Code)))
		}
		if spec.Status.Detail != "" {
			inner.Set(fields.ByName("detail"), protoreflect.ValueOfString(spec.Status.Detail))
		}
		message.Set(body.Fields().ByName("status"), protoreflect.ValueOfMessage(inner))
	case spec.Data != nil:
		data, err := hex.DecodeString(*spec.Data)
		if err != nil {
			fail("data hex: %v", err)
		}
		message.Set(body.Fields().ByName("data"), protoreflect.ValueOfBytes(data))
	default:
		fail("frame spec names no body")
	}
	encoded, err := proto.MarshalOptions{Deterministic: true}.Marshal(message)
	if err != nil {
		fail("marshal: %v", err)
	}
	return encoded
}

func describeFrame(raw []byte) map[string]any {
	descriptor := schema()
	message := dynamicpb.NewMessage(descriptor)
	if err := proto.Unmarshal(raw, message); err != nil {
		return map[string]any{"body": "", "error": err.Error()}
	}
	which := message.WhichOneof(descriptor.Oneofs().ByName("body"))
	if which == nil {
		return map[string]any{"body": ""}
	}
	value := message.Get(which)
	switch which.Name() {
	case "open":
		inner := value.Message()
		fields := inner.Descriptor().Fields()
		return map[string]any{"body": "open", "grant": hex.EncodeToString(inner.Get(fields.ByName("dial_grant")).Bytes()),
			"exit": inner.Get(fields.ByName("exit_id")).String(), "conn": inner.Get(fields.ByName("conn_id")).String()}
	case "status":
		inner := value.Message()
		fields := inner.Descriptor().Fields()
		return map[string]any{"body": "status", "code": int64(inner.Get(fields.ByName("code")).Enum()), "detail": inner.Get(fields.ByName("detail")).String()}
	default:
		return map[string]any{"body": "data", "data": hex.EncodeToString(value.Bytes())}
	}
}

func protoCommand(arguments []string) {
	if len(arguments) < 2 {
		fail("usage: proto encode SPEC.json | proto decode HEX...")
	}
	switch arguments[0] {
	case "encode":
		raw, err := os.ReadFile(arguments[1])
		if err != nil {
			fail("read specs: %v", err)
		}
		var specs []frameSpec
		if err := json.Unmarshal(raw, &specs); err != nil {
			fail("parse specs: %v", err)
		}
		for _, spec := range specs {
			fmt.Println(hex.EncodeToString(encodeFrame(spec)))
		}
	case "decode":
		for _, text := range arguments[1:] {
			raw, err := hex.DecodeString(text)
			if err != nil {
				fail("decode hex: %v", err)
			}
			emit(describeFrame(raw))
		}
	default:
		fail("unknown proto command %q", arguments[0])
	}
}

func events(path string, grpcMessages bool) {
	raw, err := os.ReadFile(path)
	if err != nil {
		fail("read frames: %v", err)
	}
	framer := http2.NewFramer(io.Discard, bytes.NewReader(raw))
	framer.ReadMetaHeaders = hpack.NewDecoder(4096, nil)
	framer.MaxHeaderListSize = 1 << 20
	seenHeaders := map[uint32]bool{}
	pending := map[uint32][]byte{}
	for {
		frame, err := framer.ReadFrame()
		if errors.Is(err, io.EOF) {
			break
		}
		if err != nil {
			emit(map[string]any{"event": "error", "error": err.Error()})
			os.Exit(3)
		}
		switch typed := frame.(type) {
		case *http2.SettingsFrame:
			if typed.IsAck() {
				emit(map[string]any{"event": "settings-ack"})
			} else {
				values := map[string]uint32{}
				typed.ForeachSetting(func(setting http2.Setting) error {
					values[strconv.Itoa(int(setting.ID))] = setting.Val
					return nil
				})
				emit(map[string]any{"event": "settings", "values": values})
			}
		case *http2.MetaHeadersFrame:
			fields := [][2]string{}
			for _, entry := range typed.Fields {
				fields = append(fields, [2]string{entry.Name, entry.Value})
			}
			kind := "headers"
			if seenHeaders[typed.StreamID] {
				kind = "trailers"
			}
			seenHeaders[typed.StreamID] = true
			emit(map[string]any{"event": kind, "stream": typed.StreamID, "fields": fields, "end": typed.StreamEnded()})
		case *http2.DataFrame:
			data := typed.Data()
			emit(map[string]any{"event": "data", "stream": typed.StreamID, "data": hex.EncodeToString(data), "end": typed.StreamEnded()})
			if grpcMessages {
				buffer := append(pending[typed.StreamID], data...)
				for len(buffer) >= 5 {
					size := int(binary.BigEndian.Uint32(buffer[1:5]))
					if buffer[0] != 0 || len(buffer) < 5+size {
						break
					}
					described := describeFrame(buffer[5 : 5+size])
					described["event"] = "message"
					described["stream"] = typed.StreamID
					emit(described)
					buffer = buffer[5+size:]
				}
				pending[typed.StreamID] = buffer
			}
		case *http2.RSTStreamFrame:
			emit(map[string]any{"event": "reset", "stream": typed.StreamID, "code": uint32(typed.ErrCode)})
		case *http2.GoAwayFrame:
			emit(map[string]any{"event": "goaway", "last": typed.LastStreamID, "code": uint32(typed.ErrCode)})
		case *http2.WindowUpdateFrame:
			emit(map[string]any{"event": "window", "stream": typed.StreamID, "increment": typed.Increment})
		case *http2.PingFrame:
			emit(map[string]any{"event": "ping", "ack": typed.IsAck()})
		default:
			emit(map[string]any{"event": "frame", "type": typed.Header().Type.String()})
		}
	}
	if grpcMessages {
		for stream, rest := range pending {
			if len(rest) > 0 {
				emit(map[string]any{"event": "partial", "stream": stream, "bytes": len(rest)})
			}
		}
	}
}

type rawCodec struct{}

func (rawCodec) Marshal(value any) ([]byte, error) { return value.([]byte), nil }
func (rawCodec) Unmarshal(data []byte, value any) error {
	*(value.(*[]byte)) = append([]byte(nil), data...)
	return nil
}
func (rawCodec) Name() string { return "proto" }

var description = &grpc.StreamDesc{StreamName: "OpenExitStream", ServerStreams: true, ClientStreams: true}

func pattern(start, length int) []byte {
	result := make([]byte, 0, length)
	for len(result) < length {
		result = append(result, byte((start+len(result))%256))
	}
	return result
}

func opened(connection string) []byte {
	return encodeFrame(frameSpec{Open: &openRequest{Grant: hex.EncodeToString([]byte("fixture.jwt.signature")), Exit: "exit-a", Conn: connection}})
}

func dataFrame(data []byte) []byte {
	text := hex.EncodeToString(data)
	return encodeFrame(frameSpec{Data: &text})
}

func receiveFrame(stream grpc.ClientStream) (map[string]any, error) {
	var raw []byte
	if err := stream.RecvMsg(&raw); err != nil {
		return nil, err
	}
	return describeFrame(raw), nil
}

type transferResult struct {
	Index    int    `json:"index"`
	First    string `json:"first"`
	Code     int64  `json:"code"`
	Received int    `json:"received"`
	Expected int    `json:"expected"`
	Match    bool   `json:"match"`
	Status   string `json:"status"`
	Error    string `json:"error"`
}

func transfer(connection *grpc.ClientConn, index int, connID string, timeout time.Duration, chunk int, prefix []byte, payload []byte, header metadata.MD) transferResult {
	result := transferResult{Index: index, Expected: len(prefix) + len(payload)}
	ctx, cancel := context.WithTimeout(context.Background(), timeout)
	defer cancel()
	if header != nil {
		ctx = metadata.NewOutgoingContext(ctx, header)
	}
	stream, err := connection.NewStream(ctx, description, route, grpc.ForceCodec(rawCodec{}))
	if err != nil {
		result.Error = err.Error()
		return result
	}
	if err := stream.SendMsg(opened(connID)); err != nil {
		result.Error = "send open: " + err.Error()
		return result
	}
	first, err := receiveFrame(stream)
	if err != nil {
		result.Error = "first response: " + err.Error()
		return result
	}
	result.First, _ = first["body"].(string)
	result.Code, _ = first["code"].(int64)
	if len(prefix) > 0 {
		if err := stream.SendMsg(dataFrame(prefix)); err != nil {
			result.Error = "send prefix: " + err.Error()
			return result
		}
	}
	for at := 0; at < len(payload); at += chunk {
		end := at + chunk
		if end > len(payload) {
			end = len(payload)
		}
		if err := stream.SendMsg(dataFrame(payload[at:end])); err != nil {
			result.Error = "send data: " + err.Error()
			return result
		}
	}
	if err := stream.CloseSend(); err != nil {
		result.Error = "close send: " + err.Error()
		return result
	}
	var received []byte
	for {
		message, err := receiveFrame(stream)
		if errors.Is(err, io.EOF) {
			break
		}
		if err != nil {
			result.Status = status.Code(err).String()
			result.Error = "receive: " + err.Error()
			return result
		}
		if body, _ := message["body"].(string); body != "data" {
			result.Error = "unexpected response body " + body
			return result
		}
		decoded, _ := hex.DecodeString(message["data"].(string))
		received = append(received, decoded...)
	}
	result.Status = codes.OK.String()
	result.Received = len(received)
	result.Match = bytes.Equal(received, append(append([]byte(nil), prefix...), payload...))
	return result
}

func cancelled(connection *grpc.ClientConn, connID string) map[string]any {
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	stream, err := connection.NewStream(ctx, description, route, grpc.ForceCodec(rawCodec{}))
	if err != nil {
		return map[string]any{"cancel": connID, "error": err.Error()}
	}
	if err := stream.SendMsg(opened(connID)); err != nil {
		return map[string]any{"cancel": connID, "error": err.Error()}
	}
	first, err := receiveFrame(stream)
	if err != nil {
		return map[string]any{"cancel": connID, "error": err.Error()}
	}
	cancel()
	_, after := receiveFrame(stream)
	return map[string]any{"cancel": connID, "first": first["body"], "code": first["code"], "after": status.Code(after).String()}
}

func dial(port string) *grpc.ClientConn {
	connection, err := grpc.NewClient("127.0.0.1:"+port, grpc.WithTransportCredentials(insecure.NewCredentials()))
	if err != nil {
		fail("dial: %v", err)
	}
	return connection
}

func transfers(port string) {
	connection := dial(port)
	defer connection.Close()
	run := func(index int) transferResult {
		payload := append(bytes.Repeat(pattern(index, 256-index), 200+index*5), []byte(fmt.Sprintf("TAIL-%d", index))...)
		return transfer(connection, index, fmt.Sprintf("conn-%d", index), 8*time.Second, 8192, bytes.Repeat(pattern(0, 256), 256), payload, nil)
	}
	results := make([]transferResult, 3)
	var group sync.WaitGroup
	for index := 0; index < 3; index++ {
		group.Add(1)
		go func(index int) { defer group.Done(); results[index] = run(index) }(index)
	}
	group.Wait()
	for _, result := range results {
		emit(result)
	}
	emit(cancelled(connection, "cancel-me"))
	emit(run(3))
}

func churnPayload(index int) []byte {
	size := (index * 131) % 4097
	if index%257 == 0 {
		size = 65536
	}
	return append(bytes.Repeat(pattern(0, 256), 257)[:size], []byte(strconv.Itoa(index))...)
}

func churn(port string) {
	connection := dial(port)
	defer connection.Close()
	run := func(index int) transferResult {
		return transfer(connection, index, "churn-"+strconv.Itoa(index), 15*time.Second, 65536, nil, churnPayload(index),
			metadata.Pairs("x-churn-key", strconv.Itoa(index%71)))
	}
	failures := 0
	report := func(result transferResult) {
		if result.Error != "" || !result.Match || result.First != "status" || result.Code != 0 {
			failures++
			emit(result)
		}
	}
	for index := 0; index < 1024; index++ {
		report(run(index))
	}
	results := make([]transferResult, 1024)
	work := make(chan int)
	var group sync.WaitGroup
	for worker := 0; worker < 32; worker++ {
		group.Add(1)
		go func() {
			defer group.Done()
			for index := range work {
				results[index-1024] = run(index)
			}
		}()
	}
	for index := 1024; index < 2048; index++ {
		work <- index
	}
	close(work)
	group.Wait()
	for _, result := range results {
		report(result)
	}
	cancelledCount := 0
	for index := 0; index < 64; index++ {
		outcome := cancelled(connection, "cancel-"+strconv.Itoa(index))
		if outcome["first"] == "status" && outcome["code"] == int64(0) && outcome["error"] == nil {
			cancelledCount++
		} else {
			emit(outcome)
		}
	}
	final := run(2048)
	report(final)
	emit(map[string]any{"summary": true, "failures": failures, "cancelled": cancelledCount, "transfers": 2049})
}

func selfTest() {
	encoded := opened("conn-1")
	described := describeFrame(encoded)
	if described["body"] != "open" || described["exit"] != "exit-a" || described["conn"] != "conn-1" || described["grant"] != hex.EncodeToString([]byte("fixture.jwt.signature")) {
		fail("protobuf self-test decoded %v", described)
	}
	var buffer bytes.Buffer
	encoder := hpack.NewEncoder(&buffer)
	fields := []hpack.HeaderField{{Name: ":path", Value: route}, {Name: "te", Value: "trailers"}}
	for _, entry := range fields {
		if err := encoder.WriteField(entry); err != nil {
			fail("hpack self-test: %v", err)
		}
	}
	decoded, err := hpack.NewDecoder(4096, nil).DecodeFull(buffer.Bytes())
	if err != nil || len(decoded) != len(fields) || decoded[0] != fields[0] || decoded[1] != fields[1] {
		fail("hpack self-test decoded %v %v", decoded, err)
	}
	fmt.Println("peergrpc ready")
}

func main() {
	if len(os.Args) < 2 {
		fail("usage: peergrpc hpack|proto|events|transfers|churn ...")
	}
	switch os.Args[1] {
	case "self-test":
		selfTest()
	case "hpack":
		if len(os.Args) != 3 {
			fail("usage: hpack BLOCKS.json")
		}
		hpackBlocks(os.Args[2])
	case "proto":
		protoCommand(os.Args[2:])
	case "events":
		if len(os.Args) < 3 || len(os.Args) > 4 || (len(os.Args) == 4 && os.Args[3] != "--grpc") {
			fail("usage: events FRAMES [--grpc]")
		}
		events(os.Args[2], len(os.Args) == 4)
	case "transfers":
		if len(os.Args) != 3 {
			fail("usage: transfers PORT")
		}
		transfers(os.Args[2])
	case "churn":
		if len(os.Args) != 3 {
			fail("usage: churn PORT")
		}
		churn(os.Args[2])
	default:
		if !edgeCommand(os.Args[1:]) {
			fail("unknown command %q", os.Args[1])
		}
	}
}
