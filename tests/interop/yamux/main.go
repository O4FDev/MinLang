// Independent Go TLS + HashiCorp yamux oracle, never linked into Minyar.
package main
import("bytes"; "crypto/tls"; "crypto/x509"; "fmt"; "io"; "net"; "os"; "sync"; "time"; "github.com/hashicorp/yamux")
func main(){ if err:=run(); err!=nil { fmt.Fprintln(os.Stderr,err); os.Exit(1) } }
func run() error {
 a:=os.Args; root,e:=os.ReadFile(a[2]); if e!=nil{return e}; pool:=x509.NewCertPool(); if !pool.AppendCertsFromPEM(root){return fmt.Errorf("invalid CA")}
 cert,e:=tls.LoadX509KeyPair(a[3],a[4]); if e!=nil{return e}; config:=&tls.Config{MinVersion:tls.VersionTLS13,MaxVersion:tls.VersionTLS13,Certificates:[]tls.Certificate{cert},NextProtos:[]string{"minyar-test.yamux/1"}}
 server:=a[1]=="server"; var raw *tls.Conn
 if server { config.ClientAuth=tls.RequireAndVerifyClientCert; config.ClientCAs=pool; listener,e:=tls.Listen("tcp","127.0.0.1:0",config); if e!=nil{return e}; defer listener.Close(); fmt.Println("READY",listener.Addr().(*net.TCPAddr).Port); accepted,e:=listener.Accept(); if e!=nil{return e};raw=accepted.(*tls.Conn)
 }else{config.RootCAs=pool;config.ServerName="localhost"; raw,e=tls.Dial("tcp","127.0.0.1:"+a[1],config);if e!=nil{return e}}
 defer raw.Close(); raw.SetDeadline(time.Now().Add(12*time.Second)); if e=raw.Handshake();e!=nil{return e};if len(raw.ConnectionState().VerifiedChains)==0{return fmt.Errorf("peer was not verified")}
 conf:=yamux.DefaultConfig();conf.EnableKeepAlive=false;conf.LogOutput=io.Discard;var session *yamux.Session
 if server{session,e=yamux.Server(raw,conf)}else{session,e=yamux.Client(raw,conf)};if e!=nil{return e};defer session.Close()
 var group sync.WaitGroup;failures:=make(chan error,16)
 for i:=0;i<16;i++{var stream *yamux.Stream;if server{stream,e=session.AcceptStream()}else{stream,e=session.OpenStream()};if e!=nil{return e};group.Add(1)
 go func(i int,s *yamux.Stream){defer group.Done();if server{data,e:=io.ReadAll(io.LimitReader(s,65537));if e!=nil{failures<-e;return};if len(data)!=32768{failures<-fmt.Errorf("wrong length %d",len(data));return};if _,e=s.Write(data);e!=nil{failures<-e;return};s.Close()
 }else{data:=bytes.Repeat([]byte{byte(i)},32768);if _,e:=s.Write(data);e!=nil{failures<-e;return};s.Close();reply,e:=io.ReadAll(io.LimitReader(s,65537));if e!=nil{failures<-e;return};if !bytes.Equal(reply,data){failures<-fmt.Errorf("wrong stream %d",i)}}}(i,stream)}
 group.Wait();close(failures);for e:=range failures{return e}
 if server{deadline:=time.Now().Add(2*time.Second);for !session.IsClosed()&&time.Now().Before(deadline){time.Sleep(10*time.Millisecond)}}
 fmt.Println("Go TLS/yamux: 16 authenticated multiplexed half-closed streams passed");return nil
}
