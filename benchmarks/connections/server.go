// Go comparator for run.py: same responses as benchmarks/livepatch/server.
// Build: go build -o server-go server.go
package main

import (
	"fmt"
	"net"
	"net/http"
	"os"
	"sync/atomic"
)

func main() {
	var served atomic.Int64
	listener, err := net.Listen("tcp", "127.0.0.1:"+os.Getenv("LIVEPATCH_PORT"))
	if err != nil {
		panic(err)
	}
	fmt.Printf("LISTENING %d\n", listener.Addr().(*net.TCPAddr).Port)
	http.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "text/plain")
		fmt.Fprintf(w, "version=1 served=%d\n", served.Add(1))
	})
	panic(http.Serve(listener, nil))
}
