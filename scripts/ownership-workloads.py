"""Ownership-study programs and independent expected results.

Sizes are compiled into temporary sources so each compiler receives the same input."""


def workloads(scale):
    count = 50000 * scale
    return {
        'borrowed_record_calls': (f'''record Point {{ x: Integer; y: Integer }}
function read(point: Point): Integer {{ return point.x + point.y }}
let point = Point {{ x: 3; y: 4 }}
let i = 0
let total = 0
while i < {count * 4} {{
total = total + read(point)
i = i + 1
}}
print(total)
''', f'{count * 28}\n'),
        'returned_alias_calls': (f'''function identity(text: Text): Text {{ return text }}
let original = "borrowed" + "!"
let i = 0
let total = 0
while i < {count} {{
let result = identity(original)
total = total + result.length
i = i + 1
}}
print(total)
''', f'{count * 9}\n'),
        'record_churn': (f'''record Point {{ x: Integer; y: Integer }}
let i = 0
let total = 0
while i < {count} {{
let point = Point {{ x: i; y: i + 1 }}
total = total + point.y - point.x
i = i + 1
}}
print(total)
''', f'{count}\n'),
        'wide_live_records': (f'''record Point {{ x: Integer; y: Integer }}
let points: List<Point> = []
let i = 0
while i < {count} {{
points.add(Point {{ x: i; y: i + 1 }})
i = i + 1
}}
let total = 0
i = 0
while i < points.length {{
total = total + points[i].y - points[i].x
i = i + 1
}}
print(total)
''', f'{count}\n'),
        'shared_list_updates': (f'''function identity(text: Text): Text {{ return text }}
let words: List<Text> = []
let i = 0
while i < 128 {{
words.add("seed" + "!")
i = i + 1
}}
let alias = words
i = 0
while i < {count} {{
let value = identity(Text(i + 40000))
words[i % 128] = value
alias[(i + 1) % 128] = words[i % 128]
i = i + 1
}}
print(words.length)
print(alias[({count} - 1) % 128])
''', f'128\n{count + 39999}\n'),
        'unicode_temporaries': (f'''let i = 0
let total = 0
while i < {count // 5} {{
let text = "é🙂" + Text(i + 40000)
total = total + text.length
printNothing(text)
i = i + 1
}}
print(total)
function printNothing(text: Text) {{ let length = text.byteLength }}
''', f'{sum(2 + len(str(i + 40000)) for i in range(count // 5))}\n'),
    }
