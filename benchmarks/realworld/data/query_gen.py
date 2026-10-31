#!/usr/bin/env python3
"""Deterministic CSV input for the real-world SQL workload.

Writes `sales.csv` with a header and N rows. Every column is a pure function of
the row index (a fixed 64-bit LCG), so the file is byte-identical on every host
and needs no stored fixture.

  query_gen.py OUT.csv [ROWS]
"""
import sys

REGIONS = 8
CATEGORIES = 12
MASK = (1 << 64) - 1


def main():
    out = sys.argv[1]
    rows = int(sys.argv[2]) if len(sys.argv) > 2 else 200000
    state = 0x2026_1030_0000_0001
    with open(out, "w", newline="\n") as f:
        f.write("id,region,category,quantity,price,shipdate\n")
        for i in range(rows):
            state = (state * 6364136223846793005 + 1442695040888963407) & MASK
            region = (state >> 33) % REGIONS
            state = (state * 6364136223846793005 + 1442695040888963407) & MASK
            category = (state >> 33) % CATEGORIES
            state = (state * 6364136223846793005 + 1442695040888963407) & MASK
            quantity = (state >> 40) % 20 + 1
            state = (state * 6364136223846793005 + 1442695040888963407) & MASK
            price = (state >> 20) % 100000
            state = (state * 6364136223846793005 + 1442695040888963407) & MASK
            year = 1992 + (state >> 40) % 6
            month = (state >> 32) % 12 + 1
            day = (state >> 24) % 28 + 1
            f.write(f"{i},region-{region:02d},category-{category:02d},{quantity},"
                    f"{price // 100}.{price % 100:02d},{year:04d}-{month:02d}-{day:02d}\n")


if __name__ == "__main__":
    main()
