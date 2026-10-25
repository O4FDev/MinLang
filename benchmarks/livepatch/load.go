// Closed-loop HTTP/1.1 keep-alive load for the live-patch experiment.
// Usage: load ADDR CONNECTIONS SECONDS OUT.csv
// Writes one row per completed or failed request:
// conn,start_ns,latency_ns,status(ok|error),version,served
package main

import (
	"bufio"
	"fmt"
	"net"
	"os"
	"strconv"
	"strings"
	"sync"
	"time"
)

type row struct {
	conn, start, latency int64
	ok                   bool
	version, served      int64
}

func worker(id int, addr string, deadline time.Time, origin time.Time, out *[]row, wg *sync.WaitGroup) {
	defer wg.Done()
	var c net.Conn
	var rd *bufio.Reader
	request := []byte("GET /hit HTTP/1.1\r\nHost: livepatch\r\n\r\n")
	for time.Now().Before(deadline) {
		start := time.Now()
		r := row{conn: int64(id), start: start.Sub(origin).Nanoseconds()}
		ok := func() bool {
			if c == nil {
				var err error
				c, err = net.DialTimeout("tcp", addr, 200*time.Millisecond)
				if err != nil {
					c = nil
					return false
				}
				rd = bufio.NewReader(c)
			}
			c.SetDeadline(time.Now().Add(2 * time.Second))
			if _, err := c.Write(request); err != nil {
				return false
			}
			length := -1
			closing := false
			status, err := rd.ReadString('\n')
			if err != nil || !strings.Contains(status, " 200 ") {
				return false
			}
			for {
				line, err := rd.ReadString('\n')
				if err != nil {
					return false
				}
				line = strings.TrimRight(line, "\r\n")
				if line == "" {
					break
				}
				if k, v, found := strings.Cut(line, ":"); found {
					name, value := strings.TrimSpace(k), strings.TrimSpace(v)
					if strings.EqualFold(name, "content-length") {
						length, _ = strconv.Atoi(value)
					} else if strings.EqualFold(name, "connection") && strings.EqualFold(value, "close") {
						closing = true
					}
				}
			}
			if length < 0 {
				return false
			}
			body := make([]byte, length)
			if _, err := io_ReadFull(rd, body); err != nil {
				return false
			}
			if closing {
				// The server ends this keep-alive connection after the response.
				c.Close()
				c = nil
			}
			for _, field := range strings.Fields(string(body)) {
				if k, v, found := strings.Cut(field, "="); found {
					n, _ := strconv.ParseInt(v, 10, 64)
					if k == "version" {
						r.version = n
					} else if k == "served" {
						r.served = n
					}
				}
			}
			return true
		}()
		r.latency = time.Since(start).Nanoseconds()
		r.ok = ok
		if !ok {
			if c != nil {
				c.Close()
				c = nil
			}
			time.Sleep(time.Millisecond)
		}
		*out = append(*out, r)
	}
	if c != nil {
		c.Close()
	}
}

func io_ReadFull(rd *bufio.Reader, buf []byte) (int, error) {
	n := 0
	for n < len(buf) {
		m, err := rd.Read(buf[n:])
		n += m
		if err != nil {
			return n, err
		}
	}
	return n, nil
}

func main() {
	if len(os.Args) != 5 {
		fmt.Fprintln(os.Stderr, "usage: load ADDR CONNECTIONS SECONDS OUT.csv")
		os.Exit(2)
	}
	conns, _ := strconv.Atoi(os.Args[2])
	seconds, _ := strconv.ParseFloat(os.Args[3], 64)
	origin := time.Now()
	deadline := origin.Add(time.Duration(seconds * float64(time.Second)))
	results := make([][]row, conns)
	var wg sync.WaitGroup
	for i := 0; i < conns; i++ {
		wg.Add(1)
		go worker(i, os.Args[1], deadline, origin, &results[i], &wg)
	}
	wg.Wait()
	f, err := os.Create(os.Args[4])
	if err != nil {
		panic(err)
	}
	w := bufio.NewWriter(f)
	fmt.Fprintf(w, "# origin_unix_ns=%d\n", origin.UnixNano())
	for _, rs := range results {
		for _, r := range rs {
			status := "error"
			if r.ok {
				status = "ok"
			}
			fmt.Fprintf(w, "%d,%d,%d,%s,%d,%d\n", r.conn, r.start, r.latency, status, r.version, r.served)
		}
	}
	w.Flush()
	f.Close()
}
