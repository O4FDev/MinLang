#!/usr/bin/env python3
# Print the tables of runtime/minyar_crc32c.h: python3 tools/generate-crc32c-tables.py 8192 256
POLY = 0x82F63B78
def byte_step(c):
    for _ in range(8):
        c = (c >> 1) ^ POLY if c & 1 else c >> 1
    return c
t0 = [byte_step(i) for i in range(256)]
slices = [t0]
for k in range(1, 8):
    prev = slices[-1]
    slices.append([(prev[i] >> 8) ^ t0[prev[i] & 0xFF] for i in range(256)])
def zeros(n):
    # operator taking a raw register to the register after n zero bytes
    basis = []
    for j in range(32):
        c = 1 << j
        for _ in range(n):
            c = t0[c & 0xFF] ^ (c >> 8)
        basis.append(c)
    tables = []
    for k in range(4):
        row = []
        for i in range(256):
            v = 0
            for b in range(8):
                if i >> b & 1:
                    v ^= basis[8 * k + b]
            row.append(v)
        tables.append(row)
    return tables
def emit(name, rows):
    out = ["static const uint32_t %s[%d][256] = {" % (name, len(rows))]
    for row in rows:
        out.append("    {")
        for i in range(0, 256, 8):
            out.append("        " + ", ".join("0x%08x" % v for v in row[i:i + 8]) + ",")
        out.append("    },")
    out.append("};")
    return "\n".join(out)
import sys
LONG, SHORT = int(sys.argv[1]), int(sys.argv[2])
print(emit("crc32c_slices", slices))
print(emit("crc32c_long_shift", zeros(LONG)))
print(emit("crc32c_short_shift", zeros(SHORT)))
