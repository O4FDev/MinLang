import sys, time
kind, count, fixture = sys.argv[1], int(sys.argv[2]), sys.argv[3]
values = [(i*1103515245+12345)%2147483647 for i in range(count)] if kind == 'integers' else [( ((i*1103515245+12345)%2147483647)%1024, i) for i in range(count)] if kind == 'records' else open(fixture,'rb').read().splitlines()
start = time.perf_counter_ns()
values.sort(key=(lambda row: row[0]) if kind == 'records' else None)
print(time.perf_counter_ns()-start)
checksum=0
for value in values:
    for number in (value[:8] if kind == 'hashes' else [value[1] if kind == 'records' else value]): checksum=(checksum*131+number)%1000000007
print(checksum)
