#!/usr/bin/env python3
"""Independent selected bytes, polygon coverage, algebra and topology contracts."""
from collections import Counter
import hashlib
import math
import struct

POINTS = [-17, -1, 0, 7, 15, 16, 31]
CELLS = [(1, 3), (4, 16), (2, 8), (8, 8), (4, 4)]
PHASES = [0, .25, .5, .75, 0, 0, 0, 0, 0]
COLORS = [(0.617325, 0.430175, 0.378675), (.53, .72, .98),
          (0.617325, 0.430175, 0.378675), (.02, .03, .09)]
OPAQUE_BLOCKS = set(range(1, 22)) - {6, 10, 14, 15, 16, 21}
PLANTS = {14: 19, 15: 20, 16: 21, 21: 26}
FACES = [((16, 1), (30, 8), (16, 15), (2, 8)),
         ((2, 8), (16, 15), (16, 31), (2, 24)),
         ((16, 15), (30, 8), (30, 24), (16, 31))]


def expected_inputs():
    # Explicit row sets for designed flowers; unrelated noise shades are not reproduced.
    red = {5: [7, 8], 6: list(range(5, 10)), 7: list(range(5, 11)),
           8: list(range(5, 10)), 9: [6, 7, 8], 10: [7], 11: [7],
           12: [5, 7, 10], 13: [6, 7, 9], 14: [7, 8], 15: [7]}
    yellow = {7: [7], 8: [6, 7, 8, 9], 9: [5, 6, 7, 8, 9],
              10: [6, 7, 8, 9], 11: [7], 12: [5, 6, 7],
              13: [7, 8, 9, 10], 14: [6, 7], 15: [7]}
    selected = [(26, 7, 6, 'ffd800ff'), (26, 8, 6, 'ff8f00ff'),
                (26, 7, 7, 'ffff97ff'), (26, 8, 7, 'ffffffff'),
                (26, 8, 15, '423522ff'), (20, 7, 7, '742303ff'),
                (21, 7, 9, 'f19d25ff')]
    selected += [(9, x, y, '67502cff') for y in (3, 7, 11, 15) for x in range(16)]
    return {'atlas_bytes': 256 * 256 * 4, 'tile_count': 27, 'block_count': 22,
            'flower_rows': {'20': red, '21': yellow}, 'selected_rgba': selected,
            'points': POINTS, 'cells': CELLS, 'periodic_seed': 37,
            'states': [{'time': phase, 'rgb': COLORS[([0, 1, 2, 3, 0, 0, 0, 0, 0][i])],
                        'light': [0.48, 1, .48, .2, .48, .48, .48, .48, .48][i],
                        'drift': [0, 0, 0, 0, 0, .3, .3000012, 11.999, 12.001][i],
                        'timer': [0, 0, 0, 0, 0, .25, 0, 0, 0][i]}
                       for i, phase in enumerate(PHASES)],
            'uploads': {'clouds': [0, 1, 2, 3], 'bodies': [4, 5, 6]},
            'geometry': {'camera': [10, -3, 7], 'halo_radius': [120, 80],
                         'body_half_size': [45, 30], 'body_distance': 400,
                         'halo_distance': 410, 'halo_segments': 24},
            'limits': 'Selected bytes/alpha/algebra; cloud occupancy inferred from observed tops, not independently predicted.'}


def close(a, b, tolerance=1e-10):
    assert abs(a - b) <= tolerance, ('numeric', a, b, tolerance)


def texel(data, tile, x, y):
    offset = ((tile // 16 * 16 + y) * 256 + tile % 16 * 16 + x) * 4
    return data[offset:offset + 4]


def convex(point, polygon):
    x, y = point
    cross = [(bx - ax) * (y - ay) - (by - ay) * (x - ax)
             for (ax, ay), (bx, by) in zip(polygon, polygon[1:] + polygon[:1])]
    return all(c >= 0 for c in cross) or all(c <= 0 for c in cross)


def validate_texture(directory, expected):
    data = (directory / 'atlas.bin').read_bytes()
    assert len(data) == expected['atlas_bytes'], 'atlas extent'
    active = set()
    for tile in range(27):
        for y in range(16):
            for x in range(16):
                active.add((tile // 16 * 16 + y) * 256 + tile % 16 * 16 + x)
                rgba = texel(data, tile, x, y)
                assert rgba[3] in (0, 255), ('tile alpha', tile, x, y)
                if rgba[3] == 0:
                    assert rgba == bytes(4), ('transparent RGB', tile, x, y)
                if tile == 18:
                    assert rgba == bytes([255] * 4), ('cloud tile', x, y)
                if tile == 16:
                    # Three concentric squares specified independently as coordinate sets.
                    color = 'ffffd9ff' if 6 <= x <= 9 and 6 <= y <= 9 else \
                            'ffffaaff' if 5 <= x <= 10 and 5 <= y <= 10 else \
                            'ffd54aff' if 4 <= x <= 11 and 4 <= y <= 11 else '00000000'
                    assert rgba.hex() == color, ('sun rings', x, y)
                if tile in (17, 26, 20, 21, 11):
                    if tile == 17:
                        opaque = x in range(4, 12) and y in range(4, 12)
                    elif tile == 26:
                        opaque = x in (7, 8) and y >= 6
                    elif tile in (20, 21):
                        rows = expected['flower_rows'][str(tile)]
                        opaque = x in rows.get(str(y), rows.get(y, []))
                    else:
                        opaque = x in (0, 15) or y in (0, 15) or \
                                 (x + y == 6 and 2 <= x <= 4) or (x + y == 25 and 12 <= x <= 13)
                        if x == 0 or y == 0:
                            assert rgba.hex() == 'd0eae9ff', ('glass edge', x, y)
                    assert rgba[3] == 255 * opaque, ('material alpha', tile, x, y)
    for tile, x, y, value in expected['selected_rgba']:
        assert texel(data, tile, x, y).hex() == value, ('exact RGBA', tile, x, y)
    icons = struct.unpack('<42d', (directory / 'icons.bin').read_bytes())
    for block in range(1, 22):
        left, top = block % 8 * 32, 64 + block // 8 * 32
        assert icons[(block - 1) * 2:(block - 1) * 2 + 2] == (left / 256, top / 256), ('icon UV', block)
        for y in range(32):
            for x in range(32):
                index = (top + y) * 256 + left + x
                active.add(index)
                rgba = data[index * 4:index * 4 + 4]
                assert rgba[3] in (0, 63, 127, 191, 255), ('icon quantization', block, x, y)
                if block in PLANTS:
                    assert rgba == texel(data, PLANTS[block], x // 2, y // 2), ('plant scaling', block, x, y)
                elif block in OPAQUE_BLOCKS:
                    count = sum(any(convex((x + dx, y + dy), face) for face in FACES)
                                for dx in (.25, .75) for dy in (.25, .75))
                    assert rgba[3] == count * 255 // 4, ('cube polygon alpha', block, x, y)
    assert all(data[index * 4:index * 4 + 4] == bytes(4) for index in range(256**2) if index not in active), 'unused atlas zero'
    return {'groups': 5, 'tile_texels': 27 * 256, 'icon_texels': 21 * 1024,
            'unused_texels': 256**2 - len(active), 'selected_exact_pixels': len(expected['selected_rgba'])}


def mix(x, y, seed):
    # Arbitrary precision projected to signed64, separately established in round1/7 noise reference.
    def signed(v):
        v %= 2**64
        return v if v < 2**63 else v - 2**64
    word = signed(x * 374761393 + y * 668265263 + seed * 1442695041)
    word = signed((word ^ (word >> 13)) * 1274126177)
    return ((word ^ (word >> 16)) & 0xffffff) / 2**24


def validate_periodic(directory, expected):
    actual = struct.unpack('<735d', (directory / 'periodic.bin').read_bytes())
    cursor = 0
    for cx, cy in CELLS:
        for px in POINTS:
            for py in POINTS:
                # Tensor-product basis weights, not the production nested interpolation.
                x, y = (px + .5) * cx / 16, (py + .5) * cy / 16
                ix, iy = math.floor(x), math.floor(y)
                sx, sy = x % 1, y % 1
                sx, sy = sx**2 * (3 - 2 * sx), sy**2 * (3 - 2 * sy)
                predicted = sum(mix((ix + dx) % cx, (iy + dy) % cy, 37) * wx * wy
                                for dx, wx in enumerate((1 - sx, sx))
                                for dy, wy in enumerate((1 - sy, sy)))
                for value in actual[cursor:cursor + 3]:
                    close(value, predicted, 2e-15)
                    assert 0 <= value < 1
                assert actual[cursor] == actual[cursor + 1] == actual[cursor + 2], 'period translation'
                cursor += 3
    return {'groups': 1, 'private_ABI_calls': cursor, 'base_coordinates': cursor // 3,
            'scope': 'Direct private generated-symbol scalar calls; no ordinary generated-call ownership claim.'}


def rows(path):
    payload = path.read_bytes()
    assert len(payload) % 40 == 0
    return list(struct.iter_unpack('<10f', payload))


def sub(a, b):
    return tuple(x - y for x, y in zip(a, b))


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def norm(a):
    return math.sqrt(dot(a, a))


def normal(a, b, c):
    u, v = sub(b, a), sub(c, a)
    return (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])


def validate_cloud(path, drift):
    vertices = rows(path)
    assert vertices and len(vertices) % 6 == 0
    offset = drift % 12
    faces = []
    occupied = set()
    for i in range(0, len(vertices), 6):
        face = vertices[i:i + 6]
        assert face[0] == face[3] and face[2] == face[4], 'cloud triangle join'
        corners = {tuple(v[:3]) for v in face}
        assert len(corners) == 4
        shade = face[0][5]
        assert all(v[3:5] == face[0][3:5] and v[5:8] == (shade,) * 3 and v[8:] == (1, 0) for v in face), 'cloud attributes'
        for v in face:
            close(v[3], .155, 1e-8)
            close(v[4], .0925, 1e-8)
            close((v[0] + offset) / 12 + 20, round((v[0] + offset) / 12 + 20), 4e-6)
            close(v[2] / 12 + 20, round(v[2] / 12 + 20), 1e-8)
            assert -240 - offset - .0001 <= v[0] <= 480 - offset + .0001 and -240 <= v[2] <= 480
            assert v[1] in (108, 112), 'cloud height'
        lo = tuple(min(v[a] for v in corners) for a in range(3))
        hi = tuple(max(v[a] for v in corners) for a in range(3))
        area_normal = normal(*[v[:3] for v in face[:3]])
        assert normal(*[v[:3] for v in face[3:]]) == area_normal, 'cloud both triangle winding'
        assert all(face[0][a] + face[2][a] == lo[a] + hi[a] for a in range(3)), 'cloud diagonal joins opposite corners'
        if lo[1] == hi[1] == 112:
            cell = (round((lo[0] + offset) / 12 + 20), round(lo[2] / 12 + 20))
            assert cell not in occupied, 'duplicate cloud cell'
            occupied.add(cell)
        faces.append((lo, hi, shade, area_normal))
    # Occupancy comes only from observed tops. Entire missing/extra cells can escape this oracle.
    predicted = Counter()
    for x, z in occupied:
        lo, hi = ((x - 20) * 12 - offset, 108, (z - 20) * 12), ((x - 19) * 12 - offset, 112, (z - 19) * 12)
        for axis, side, shade in [(1, 1, 1), (1, 0, .72), (0, 1, .88), (0, 0, .88), (2, 1, .8), (2, 0, .8)]:
            neighbor = (x + (1 if side else -1), z) if axis == 0 else (x, z + (1 if side else -1))
            if axis != 1 and neighbor in occupied:
                continue
            a, b = list(lo), list(hi)
            a[axis] = b[axis] = hi[axis] if side else lo[axis]
            # Quantize only for float32 storage; no permissive position rounding.
            pack = lambda values: struct.unpack('<3f', struct.pack('<3f', *values))
            predicted[(pack(a), pack(b), struct.unpack('<f', struct.pack('<f', shade))[0], axis, 1 if side else -1)] += 1
    observed = Counter()
    for lo, hi, shade, n in faces:
        axis = next(a for a in range(3) if lo[a] == hi[a])
        sign = 1 if n[axis] > 0 else -1
        assert n[axis] != 0 and all(n[a] == 0 for a in range(3) if a != axis)
        observed[(lo, hi, shade, axis, sign)] += 1
    assert observed == predicted, ('cloud exposed topology', path.name, len(observed), len(predicted))
    return occupied, len(vertices), len(faces)


def validate_bodies(path, phase):
    vertices = rows(path)
    assert len(vertices) == 312, 'body/halo vertex count'
    direction = (math.cos(phase * math.tau), math.sin(phase * math.tau), .3)
    direction = tuple(x / math.sqrt(1.09) for x in direction)
    sky = COLORS[0 if phase == 0 else 1 if phase == .25 else 3]
    for halo, radius in enumerate((120, 80)):
        sign = 1 if halo == 0 else -1
        center = tuple(c + sign * d * 410 for c, d in zip((10, -3, 7), direction))
        color, strength = ((1, .95, .7), .28) if halo == 0 else ((.8, .85, 1), .14)
        middle = tuple((1 - strength) * s + strength * c for s, c in zip(sky, color))
        for segment in range(24):
            face = vertices[halo * 144 + segment * 6:halo * 144 + (segment + 1) * 6]
            assert face[0] == face[3] and face[1] == face[5] and face[2] == face[4], 'halo double sided'
            for j, v in enumerate(face):
                for value, predicted in zip(v[:3], center):
                    if j in (0, 3): close(value, predicted, 4e-5)
                if j not in (0, 3):
                    offset = sub(v[:3], center)
                    close(norm(offset), radius, 6e-5)
                    close(dot(offset, direction), 0, 6e-5)
                for value, predicted in zip(v[5:8], middle if j in (0, 3) else sky): close(value, predicted, 5e-8)
                close(v[3], .155, 1e-8); close(v[4], .0925, 1e-8)
                assert v[8:] == (1, 0)
            next_face = vertices[halo * 144 + ((segment + 1) % 24) * 6:]
            for a, b in zip(face[2][:3], next_face[1][:3]): close(a, b, 1e-5)
            close(norm(sub(face[1][:3], face[2][:3])), 2 * radius * math.sin(math.pi / 24), 6e-5)
    for body, size in enumerate((45, 30)):
        face = vertices[288 + body * 12:300 + body * 12]
        sign = 1 if body == 0 else -1
        center = tuple(c + sign * d * 400 for c, d in zip((10, -3, 7), direction))
        corners = {v[:3] for v in face}
        assert len(corners) == 4 and face[0:3] == [face[6], face[8], face[7]] and face[3:6] == [face[9], face[11], face[10]], 'body double sided'
        mean = tuple(sum(v[a] for v in corners) / 4 for a in range(3))
        for a, b in zip(mean, center): close(a, b, 4e-5)
        distances = sorted(norm(sub(a, b)) for i, a in enumerate(sorted(corners)) for b in sorted(corners)[i + 1:])
        for value, predicted in zip(distances, [2 * size] * 4 + [2 * math.sqrt(2) * size] * 2): close(value, predicted, 6e-5)
        uv = {(v[3], v[4]) for v in face}
        assert uv == {(u, v) for u in (body / 16 + 2 / 256, body / 16 + 14 / 256) for v in (1 / 16 + 2 / 256, 1 / 16 + 14 / 256)}, 'body atlas inset'
        for v in face:
            close(dot(sub(v[:3], center), direction), 0, 6e-5)
            assert v[5:] == (1, 1, 1, 1, 0)
    return len(vertices)


def validate_atmosphere(directory, expected):
    states = list(struct.iter_unpack('<7d', (directory / 'states.bin').read_bytes()))
    assert len(states) == 9
    for i, state in enumerate(states):
        e = expected['states'][i]
        for a, b in zip(state, [e['time'], *e['rgb'], e['light'], e['drift'], e['timer']]): close(a, b)
    event_lines = [line.split() for line in (directory / 'events.txt').read_text().splitlines()]
    expected_order = ['create', 'create', 'upload', 'upload', 'upload', 'upload'] + ['upload', 'light', 'fog', 'draw'] * 3 + ['light', 'fog', 'draw']
    assert [r[0] for r in event_lines] == expected_order, 'graphics event order/strict timer boundary'
    expected_fogs = [(*COLORS[i], 5000, 6000) for i in (0, 1, 3)] + [(*COLORS[3], 160, 420)]
    for row, e in zip([r for r in event_lines if r[0] == 'fog'], expected_fogs):
        for a, b in zip(map(float, row[2:]), e): close(a, b)
    assert [int(r[1]) for r in event_lines if r[0] == 'draw'] == [1, 1, 1, 2], 'mesh draw handles'
    assert [float(r[2]) for r in event_lines if r[0] == 'light'] == [1, 1, 1, .2], 'light transitions'
    cloud_results = [validate_cloud(directory / f'upload-{i:02}-2.bin', drift) for i, drift in enumerate((0, .3000012, 11.999, 12.001))]
    before, after = cloud_results[2][0], cloud_results[3][0]
    # Same world-density cells remain after the array index shifts, with only boundary entry/exit.
    assert {(x, z) for x, z in before if x > 0} == {(x + 1, z) for x, z in after if x < 59}, 'cloud whole-cell continuity'
    body_vertices = sum(validate_bodies(directory / f'upload-{i + 4:02}-1.bin', phase) for i, phase in enumerate((0, .25, .75)))
    counts = {'creates': 2, 'uploads': 7, 'addVertex_calls': sum(r[1] for r in cloud_results) + body_vertices, 'draws': 4, 'lights': 4, 'fogs': 4}
    return {'groups': 4, 'state_rows': len(states), 'clouds': [{'inferred_cells': len(r[0]), 'vertices': r[1], 'faces': r[2]} for r in cloud_results], 'body_vertices': body_vertices, 'capture_api_counts': counts,
            'scope': 'Observed-top occupancy topology/continuity, not independent noise occupancy or real GPU upload.'}


def validate(directory, expected):
    return {'texture': validate_texture(directory, expected), 'periodic': validate_periodic(directory, expected), 'atmosphere': validate_atmosphere(directory, expected)}
