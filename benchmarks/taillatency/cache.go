// Same workload as cache.min. Build: go build -o cache-go cache.go
package main

import (
	"fmt"
	"os"
	"sort"
	"strconv"
	"strings"
	"time"
)

type Session struct {
	name  string
	items []int64
	score int64
}

func setting(name string, fallback int64) int64 {
	if v, err := strconv.ParseInt(os.Getenv(name), 10, 64); err == nil {
		return v
	}
	return fallback
}

func makeSession(id int64) *Session {
	items := []int64{}
	items = append(items, id, id*3, id*7, id%97)
	return &Session{name: "session-" + strconv.FormatInt(id, 10), items: items, score: id % 1000}
}

func serve(current []*Session, request, reads int64) int64 {
	size := int64(len(current))
	if size == 0 {
		return 0
	}
	var total int64
	for k := int64(0); k < reads; k++ {
		s := current[(request*7919+k*104729)%size]
		total += s.score + s.items[k%4]
	}
	return total
}

func rss() int64 {
	b, err := os.ReadFile("/proc/self/statm")
	if err != nil {
		return -1
	}
	f := strings.Fields(string(b))
	v, _ := strconv.ParseInt(f[1], 10, 64)
	return v * 4096
}

func main() {
	requests := setting("TAIL_REQUESTS", 20000)
	perRequest := setting("TAIL_BUILD", 200)
	swapEvery := setting("TAIL_SWAP", 1000)
	reads := setting("TAIL_READS", 64)
	interval := setting("TAIL_INTERVAL_NS", 0)
	var current, next []*Session
	latencies := []int64{}
	var checksum, id int64
	begin := time.Now()
	for r := int64(0); r < requests; r++ {
		if interval > 0 {
			arrival := begin.Add(time.Duration(r * interval))
			if d := time.Until(arrival); d > 0 {
				time.Sleep(d)
			}
		}
		start := time.Now()
		for b := int64(0); b < perRequest; b++ {
			next = append(next, makeSession(id))
			id++
		}
		checksum = (checksum + serve(current, r, reads)) % 1000000007
		if (r+1)%swapEvery == 0 {
			current = next
			next = nil
		}
		latencies = append(latencies, time.Since(start).Nanoseconds())
	}
	elapsed := time.Since(begin).Nanoseconds()
	sort.Slice(latencies, func(i, j int) bool { return latencies[i] < latencies[j] })
	p := func(m int) int64 {
		i := len(latencies) * m / 1000000
		if i >= len(latencies) {
			i = len(latencies) - 1
		}
		return latencies[i]
	}
	fmt.Printf("lang=go requests=%d checksum=%d total_ns=%d p50=%d p99=%d p999=%d max=%d rss=%d\n",
		requests, checksum, elapsed, p(500000), p(990000), p(999000), latencies[len(latencies)-1], rss())
}
