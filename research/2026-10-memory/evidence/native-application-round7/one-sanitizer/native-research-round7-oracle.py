#!/usr/bin/env python3
"""Independent scalar expectations and whole-output invariants, never a copied generator."""
from collections import Counter
import hashlib
import math
import struct

SEED = 20260923
SIZE = 512
AREA = SIZE * SIZE
HEIGHT = 80
MASK = (1 << 64) - 1
GENERATED = {0, 1, 2, 3, 4, 5, 6, 7, 11, 13, 14, 15, 16, 17, 18, 19, 20}
OPAQUE = GENERATED - {0, 6, 7, 14, 15, 16}


def signed(value):
    value &= MASK
    return value if value < 1 << 63 else value - (1 << 64)


def mix(x, z, seed):
    # Independent arbitrary-precision arithmetic projected into signed64.
    word = signed(x * 374761393 + z * 668265263 + seed * 1442695041)
    word = signed((word ^ (word >> 13)) * 1274126177)
    return (word ^ (word >> 16)) & 0x7fffffff


def random(x, z, seed):
    return (mix(x, z, seed) & 0xffffff) / (1 << 24)


def noise(x, z, seed):
    ix, iz = math.floor(x), math.floor(z)
    tx, tz = x - ix, z - iz
    tx, tz = tx * tx * (3 - 2 * tx), tz * tz * (3 - 2 * tz)
    corners = [random(ix + dx, iz + dz, seed) for dz in (0, 1) for dx in (0, 1)]
    a = corners[0] + (corners[1] - corners[0]) * tx
    b = corners[2] + (corners[3] - corners[2]) * tx
    return a + (b - a) * tz


def fractal(x, z, seed, octaves):
    values = [noise(x * 2**i, z * 2**i, seed + 7919 * i) * 2.**(-i)
              for i in range(octaves)]
    return sum(values) / sum(2.**(-i) for i in range(octaves))


def elevation(x, z):
    continent = fractal(x / 90., z / 90., SEED, 4)
    hill = fractal(x / 28., z / 28., SEED + 101, 3)
    mountain = noise(x / 60., z / 60., SEED + 202)
    unrounded = 12 + continent * 30 + hill * 10 + max(0., mountain - .6) * 70
    return min(68, max(2, int(unrounded))), unrounded


def expected_inputs():
    # Fixed coordinate candidates chosen without observing generated output.
    candidates = {(edge, coordinate) for edge in (0, 511) for coordinate in range(0, 512, 16)}
    candidates |= {(coordinate, edge) for edge in (0, 511) for coordinate in range(0, 512, 16)}
    candidates |= {(511, 511), (0, 511), (511, 0)}
    ore_touched = set()
    directions = [(1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)]
    vein_steps = 0
    for ore, divisor, maximum, length in [(17, 90, 60, 8), (18, 180, 40, 6),
                                         (19, 900, 24, 5), (20, 2200, 14, 4)]:
        seed = SEED + ore * 7717
        for index in range(AREA // divisor):
            x, y, z = mix(index, 1, seed) % SIZE, 1 + mix(index, 3, seed) % maximum, mix(index, 2, seed) % SIZE
            for step in range(length):
                vein_steps += 1
                if (x, z) in candidates:
                    ore_touched.add((x, z))
                dx, dy, dz = directions[mix(index, step + 10, seed) % 6]
                x, y, z = x + dx, y + dy, z + dz
    cave_touched = set()
    tunnel_steps = 0
    radius_maximum = 0.
    for index in range(AREA // 1400):
        seed = SEED + 1000 + index * 17
        x, z = random(index, 1, seed) * SIZE, random(index, 2, seed) * SIZE
        y = 6 + random(index, 3, seed) * 40
        yaw = random(index, 4, seed) * 6.283185307179586
        pitch = (random(index, 5, seed) - .5) * .6
        for step in range(60 + mix(index, 6, seed) % 90):
            tunnel_steps += 1
            radius_maximum = max(radius_maximum, 1.4 + math.sin(step * .15) * .6 + random(step, index, seed) * .8)
            # Production reaches <=3 cells. Radius4 plus epsilon gives conservative
            # exclusion without modeling sphere tests, material tests or voxel writes.
            cave_touched.update((cx, cz) for cx, cz in candidates
                                if abs(cx - math.floor(x)) <= 4 and abs(cz - math.floor(z)) <= 4)
            yaw += (random(step, index * 3, seed) - .5) * .5
            pitch = min(.6, max(-.6, pitch + (random(step, index * 5, seed) - .5) * .3))
            x += math.sin(yaw) * math.cos(pitch)
            y += math.sin(pitch)
            z += math.cos(yaw) * math.cos(pitch)
            if y < 4:
                pitch = abs(pitch)
    selected = sorted(candidates - ore_touched - cave_touched)
    assert len(selected) >= 32, len(selected)
    rows = []
    for x, z in selected:
        h, real = elevation(x, z)
        # Declarative strata model. Excluded coordinates receive no ore, cave or
        # vegetation writes; tree centers3..508 with radius2 cannot reach borders.
        column = bytes(11 if y == 0 else
                       (4 if h <= 31 else 13 if h > 52 else 1) if y == h else
                       (4 if h <= 31 else 2) if y < h and y > h - 4 and h <= 52 else
                       3 if y < h else 7 if y <= 30 else 0 for y in range(HEIGHT))
        rows.append({'x': x, 'z': z, 'height': h, 'height_float': real,
                     'height_integer_margin': min(real % 1, 1 - real % 1), 'column_hex': column.hex()})
    assert min(row['height_integer_margin'] for row in rows) > 1e-8
    return {'seed': SEED, 'candidates': len(candidates), 'ore_exclusions': sorted(ore_touched),
            'cave_exclusions': sorted(cave_touched), 'selected_columns': rows,
            'independent_logical_vein_steps': vein_steps, 'independent_logical_tunnel_steps': tunnel_steps,
            'largest_modeled_radius': radius_maximum,
            'scope': 'Scalar/noise and path exclusion model; full80byte equality only for selected untouched boundary columns. No whole-world oracle.'}


def validate(directory, expected):
    world = (directory / 'world.bin').read_bytes()
    assert len(world) == AREA * HEIGHT, ('extent', len(world))
    state = (directory / 'state.bin').read_bytes()
    initial = (512, 512, 80, SEED, AREA * HEIGHT, AREA, 1024, 0, 0, 0, 0, 0, 0, 0)
    assert state == struct.pack('<14q', *initial) + bytes([1] * 6), ('state', state.hex())
    assert (directory / 'dirty.bin').read_bytes() == bytes([1]) * 1024, 'dirty'
    histogram = Counter(world)
    assert set(histogram) <= GENERATED, ('codes', set(histogram) - GENERATED)
    assert world[:AREA] == bytes([11]) * AREA, 'bedrock floor'
    assert histogram[11] == AREA, ('bedrock count', histogram[11])
    assert world[76 * AREA:] == bytes(4 * AREA), 'height upper bound'
    assert 7 not in world[31 * AREA:], 'water above sea'
    assert 5 not in world[74 * AREA:], 'log upper bound'
    raw_tops = (directory / 'tops.bin').read_bytes()
    assert len(raw_tops) == AREA * 8, 'tops extent'
    actual_tops = struct.unpack('<' + 'q' * AREA, raw_tops)
    # Independent descending scan using material-role set, never production isOpaque.
    scanned = [-1] * AREA
    pending = AREA
    for y in range(75, -1, -1):
        base = y * AREA
        for position, block in enumerate(world[base:base + AREA]):
            if scanned[position] < 0 and block in OPAQUE:
                scanned[position] = y
                pending -= 1
        if not pending:
            break
    assert tuple(scanned) == actual_tops, 'top metadata'
    for row in expected['selected_columns']:
        position = row['z'] * SIZE + row['x']
        column = bytes(world[y * AREA + position] for y in range(HEIGHT))
        assert column.hex() == row['column_hex'], ('sample column', row['x'], row['z'])
        assert actual_tops[position] == row['height'], ('sample top', position)
    return {'block_bytes_checked': len(world), 'block_histogram': dict(sorted(histogram.items())),
            'tops_compared': AREA, 'dirty_slots_compared': 1024,
            'full_columns_compared': len(expected['selected_columns']),
            'sampled_column_bytes': HEIGHT * len(expected['selected_columns']),
            'alias_flags': 6, 'world_sha256': hashlib.sha256(world).hexdigest(),
            'world_equality_scope': 'Selected columns only; full byte invariants and all top metadata consistency are distinct.',
            'repeatability': 'One generation only; output hash is identity, not repeatability evidence.'}
