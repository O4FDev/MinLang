"""Enable AddressSanitizer in Minyar-generated LLVM during correctness tests.

The linker flag supplies the sanitizer pipeline/runtime, but generated function
definitions also need sanitize_address. This is test-only: native/performance
IR is unchanged. UBSan checks in C runtime code remain a separate layer.
"""
import re


def address_sanitizer_enabled(flags):
    enabled = False
    for flag in flags:
        if flag.startswith('-fsanitize=') and 'address' in flag.split('=', 1)[1].split(','):
            enabled = True
        if flag.startswith('-fno-sanitize=') and {'address', 'all'} & set(flag.split('=', 1)[1].split(',')):
            enabled = False
    return enabled


def instrument_address_sanitizer(llvm):
    """Annotate the single-line function headers emitted by this compiler."""
    def annotate(match):
        header = match[1]
        # An identifier such as @sanitize_address is not a function attribute.
        opening = header.find('(')
        depth = 0
        attributes = None
        for index in range(opening, len(header)):
            if header[index] == '(':
                depth += 1
            elif header[index] == ')':
                depth -= 1
                if depth == 0:
                    attributes = header[index + 1:]
                    break
        if opening < 0 or attributes is None:
            raise ValueError('generated LLVM parameter list changed')
        attributes = re.sub(r'"(?:[^"\\]|\\.)*"', '', attributes)
        if re.search(r'\bsanitize_address\b', attributes):
            return match[0]
        return header + 'sanitize_address ' + match[2]
    definitions = len(re.findall(r'^define\b', llvm, flags=re.M))
    result, matched = re.subn(r'^(define [^\n{]*)(\{[ \t]*$)', annotate, llvm, flags=re.M)
    if definitions == 0 or matched != definitions:
        raise ValueError('generated LLVM function headers changed; sanitizer coverage cannot be assumed')
    return result


def prepare_llvm_for_link(path, flags):
    if address_sanitizer_enabled(flags):
        source = path.read_text()
        instrumented = instrument_address_sanitizer(source)
        if instrumented != source:
            path.write_text(instrumented)


if __name__ == '__main__':
    import argparse
    from pathlib import Path
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    args.output.write_text(instrument_address_sanitizer(args.source.read_text()))
