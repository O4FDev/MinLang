"""Annotate generated program LLVM before its AddressSanitizer link pipeline.

C runtime modules are compiled separately to native objects. This helper never
processes them. Ordinary and effectively disabled sanitizer inputs are untouched.
"""
import argparse
from pathlib import Path
import re


def address_sanitizer_enabled(flags):
    enabled = False
    for flag in flags:
        if flag.startswith('-fsanitize=') and 'address' in flag.split('=', 1)[1].split(','):
            enabled = True
        elif flag.startswith('-fno-sanitize=') and {'address', 'all'} & set(flag.split('=', 1)[1].split(',')):
            enabled = False
    return enabled


def unquoted(text):
    """Keep token positions while masking quoted names/attributes and escapes."""
    result = list(text)
    quoted = False
    escaped = False
    for index, value in enumerate(text):
        if quoted:
            result[index] = ' '
            if escaped:
                escaped = False
            elif value == '\\':
                escaped = True
            elif value == '"':
                quoted = False
        elif value == '"':
            result[index] = ' '
            quoted = True
    if quoted:
        raise ValueError('generated LLVM has an unterminated quoted header token')
    return ''.join(result)


def instrument_address_sanitizer(llvm):
    definitions = 0
    groups = {}
    for line in llvm.splitlines():
        match = re.fullmatch(r'attributes\s+#(\d+)\s*=\s*\{(.*)\}\s*', line)
        if match:
            groups[match[1]] = unquoted(match[2])

    lines = llvm.splitlines(keepends=True)
    for index, line in enumerate(lines):
        if not re.match(r'^\s*define\b', line):
            continue
        definitions += 1
        ending = '\r\n' if line.endswith('\r\n') else ('\n' if line.endswith('\n') else '')
        header = line[:-len(ending)] if ending else line
        masked = unquoted(header)
        # Names may contain quoted '(' or '{'. Only the global-name token
        # followed by its real parameter delimiter starts this function.
        function = next((candidate for candidate in re.finditer(
            r'@(?:[-a-zA-Z$._0-9]+|"(?:[^"\\]|\\.)*")\s*\(', header)
                         if masked[candidate.start()] == '@'
                         and masked[candidate.end() - 1] == '('), None)
        if function is None or not masked.rstrip().endswith('{'):
            raise ValueError('generated LLVM function headers changed; sanitizer coverage cannot be assumed')
        opening = function.end() - 1
        depth = 0
        closing = None
        for position in range(opening, len(masked)):
            value = masked[position]
            if value == '(':
                depth += 1
            elif value == ')':
                depth -= 1
                if depth == 0:
                    closing = position
                    break
        if closing is None:
            raise ValueError('generated LLVM parameter list changed')
        brace = masked.rfind('{')
        attributes = masked[closing + 1:brace]
        if any(value in attributes for value in '{}'):
            raise ValueError('generated LLVM function attributes changed')
        enabled = bool(re.search(r'(?<![\w.@-])sanitize_address(?![\w.-])', attributes))
        for group in re.findall(r'#(\d+)\b', attributes):
            if group not in groups:
                raise ValueError('generated LLVM refers to a missing attribute group')
            enabled |= bool(re.search(r'(?<![\w.@-])sanitize_address(?![\w.-])', groups[group]))
        if not enabled:
            lines[index] = header[:brace] + 'sanitize_address ' + header[brace:] + ending
    if definitions == 0:
        raise ValueError('generated LLVM contains no function definitions; sanitizer coverage cannot be assumed')
    return ''.join(lines)


def prepare_llvm_for_link(path, flags):
    """Compatibility API for tests which own and intentionally rewrite their IR."""
    if address_sanitizer_enabled(flags):
        source = path.read_bytes().decode('utf-8')
        instrumented = instrument_address_sanitizer(source)
        if instrumented != source:
            path.write_bytes(instrumented.encode('utf-8'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    args.output.write_bytes(instrument_address_sanitizer(
        args.source.read_bytes().decode('utf-8')).encode('utf-8'))
