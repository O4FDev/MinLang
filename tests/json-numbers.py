"""Remote-only exact decimal oracle; no host float parser supplies expected bits."""
from fractions import Fraction
from functools import lru_cache
from pathlib import Path
import argparse
import hashlib
import os
import random
import re
import shutil
import struct
import subprocess
import sys
import tempfile

if not __debug__:
    raise RuntimeError("JSON number oracle requires Python assertions")
if hasattr(sys, "set_int_max_str_digits"):
    sys.set_int_max_str_digits(0)

MAXIMUM = 0x7FEFFFFFFFFFFFFF
INFINITY = 0x7FF0000000000000

@lru_cache(maxsize=16384)
def dyadic(bits):
    if bits == INFINITY:
        return Fraction(1 << 1024)
    exponent, mantissa = bits >> 52, bits & ((1 << 52) - 1)
    if exponent:
        mantissa += 1 << 52
        exponent -= 1075
    else:
        exponent = -1074
    return Fraction(mantissa << exponent) if exponent >= 0 else Fraction(mantissa, 1 << -exponent)

def rational(source):
    match = re.fullmatch(r"(-?)(0|[1-9][0-9]*)(?:\.([0-9]+))?(?:[eE]([+-]?[0-9]+))?", source)
    assert match, source[:100]
    negative, whole, fraction, exponent = match.groups()
    fraction = fraction or ""
    significand = int(whole + fraction)
    if not significand:
        return bool(negative), Fraction(0)
    power = int(exponent or "0") - len(fraction)
    if power > 20000:
        return bool(negative), Fraction(1 << 100000)
    # A huge negative exponent can cancel an equally long coefficient. Only
    # shortcut values proved far below every binary64 rounding boundary.
    if power < -20000 and len((whole + fraction).lstrip("0")) + power < -2000:
        return bool(negative), Fraction(0)
    return bool(negative), Fraction(significand * 10**power) if power >= 0 else Fraction(significand, 10**-power)

def rounded(source):
    negative, number = rational(source)
    sign = (1 << 63) if negative else 0
    if number >= (dyadic(MAXIMUM) + dyadic(INFINITY)) / 2:
        return sign | INFINITY
    low, high = 0, INFINITY
    while low + 1 < high:
        middle = (low + high) // 2
        if dyadic(middle) <= number:
            low = middle
        else:
            high = middle
    if number == dyadic(low):
        return sign | low
    midpoint = (dyadic(low) + dyadic(low + 1)) / 2
    if number > midpoint or (number == midpoint and low & 1):
        low += 1
    return sign | low

def decimal(number):
    numerator, denominator = number.numerator, number.denominator
    if denominator == 1:
        return str(numerator)
    # Every value generated here has a denominator containing only 2 and 5.
    twos = fives = 0
    while denominator % 2 == 0:
        denominator //= 2
        twos += 1
    while denominator % 5 == 0:
        denominator //= 5
        fives += 1
    assert denominator == 1
    places = max(twos, fives)
    coefficient = numerator * 2 ** (places - twos) * 5 ** (places - fives)
    digits = str(coefficient)
    if len(digits) <= places:
        return "0." + "0" * (places - len(digits)) + digits
    return digits[:-places] + "." + digits[-places:]

def corpus():
    cases = ["0", "-0", "0e9999", "-0e9999", "0.000e-9999", "1e9999", "-1e9999",
             "1e-9999", "-1e-9999", "0.29", "1.2345678901234567", "5e-324", "9e-324",
             "12e-324", "15e-324", "2.2250738585072014e-308", "1.7976931348623157e308",
             "1.7976931348623159e308", "9007199254740993", "-9223372036854775808"]
    for bits in [0, 1, 2, 3, 0xFFFFFFFFFFFFE, 0xFFFFFFFFFFFFF, 0x10000000000000,
                 0x3FEFFFFFFFFFFFFF, 0x3FF0000000000000, 0x3FF0000000000001,
                 0x7FEFFFFFFFFFFFFE, MAXIMUM]:
        middle = (dyadic(bits) + dyadic(bits + 1)) / 2
        epsilon = Fraction(1, 10**1200)
        for number in [middle - epsilon, middle, middle + epsilon]:
            for sign in ["", "-"]:
                cases.append(sign + decimal(number))
    midpoint = decimal((dyadic(0x3FF0000000000000) + dyadic(0x3FF0000000000001)) / 2)
    for zeros in [800, 10000]:
        cases.extend([midpoint + "0" * zeros, midpoint + "0" * zeros + "1",
                      "1" + "0" * zeros + "e-" + str(zeros),
                      "0." + "0" * zeros + "1e+" + str(zeros + 1),
                      "9" * zeros + "e-" + str(zeros - 1)])
    rng = random.Random(20261020)
    for count in [1, 2, 16, 17, 19, 50, 799, 800, 801, 1200]:
        for _ in range(20):
            coefficient = str(rng.randrange(1, 10)) + "".join(str(rng.randrange(10)) for _ in range(count - 1))
            power = rng.randrange(-330, 316) - count
            source = coefficient + "e" + str(power)
            cases.extend([source, "-" + source, coefficient + "000e" + str(power - 3)])
    # Huge exponents must saturate only after the complete lexeme is validated.
    cases.extend(["0e" + "9" * 10000, "-0e-" + "9" * 10000,
                  "1e" + "9" * 10000, "1e-" + "9" * 10000])
    cases.extend(["1" + "0" * 20001 + "e-20001", "-1" + "0" * 20001 + "e-20001"])
    return list(dict.fromkeys(cases))

PROBE = r'''
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <limits.h>
#include <math.h>
#include <fenv.h>
typedef struct { const unsigned char *bytes; long long byte_length; } MinyarText;
static _Noreturn void minyar_stop(const char *message) { fputs(message, stderr); exit(1); }
/* CONVERTER */
int main(int argc, char **argv) {
    if (argc != 2) return 2;
    FILE *input = fopen(argv[1], "r");
    if (!input) return 2;
    char line[32768];
    size_t count = 0;
    while (fgets(line, sizeof(line), input)) {
        size_t length = strlen(line);
        if (length < 18 || line[16] != '\t' || line[length - 1] != '\n') return 2;
        uint64_t expected = strtoull(line, NULL, 16);
        MinyarText text = {(unsigned char *)line + 17, length - 18};
        for (unsigned mode = 0; mode < 4; mode++) {
            static const int modes[] = {FE_TONEAREST, FE_TOWARDZERO, FE_DOWNWARD, FE_UPWARD};
            if (fesetround(modes[mode])) return 2;
            double value = minyar_runtime_jsonNumber(&text);
            uint64_t actual;
            memcpy(&actual, &value, sizeof(actual));
            if (actual != expected) {
                fprintf(stderr, "case %zu mode %u expected %016llx got %016llx: %.100s\n",
                        count, mode, (unsigned long long)expected, (unsigned long long)actual, line + 17);
                return 1;
            }
        }
        count++;
    }
    if (ferror(input)) return 2;
    fclose(input);
    static const char *invalid[] = {"", "-", "+1", "01", "1.", ".1", "1e", "1e+", "NaN", "Infinity", "1e999x", "0e999x", " 1", "1 ", "1,2", "0x1"};
    for (size_t i = 0; i < sizeof(invalid) / sizeof(*invalid); i++) {
        MinyarText text = {(const unsigned char *)invalid[i], (long long)strlen(invalid[i])};
        if (!isnan(minyar_runtime_jsonNumber(&text))) return 3;
    }
    puts("decimal grammar checks passed");
    printf("decimal oracle: %zu exact cases in four rounding modes passed\n", count);
    return 0;
}
'''

def run(command, *, environment=None, expected=0, diagnostic=None):
    scale = int(os.environ.get("MINYAR_TEST_TIMEOUT_SCALE", "1"))
    assert 1 <= scale <= 20
    result = subprocess.run([str(item) for item in command], capture_output=True, text=True,
                            env=environment, timeout=120 * scale)
    if result.returncode != expected:
        raise RuntimeError(f"command {command!r} returned {result.returncode}, expected {expected}\n"
                           + result.stdout + result.stderr)
    if diagnostic is not None and diagnostic not in result.stderr:
        raise RuntimeError("oracle failure did not report " + diagnostic + "\n" + result.stderr)
    return result.stdout

def verify(destination, sanitize):
    header = Path("runtime/minyar_decimal.h").resolve()
    cases = [(source, rounded(source)) for source in corpus()]
    assert len(cases) == 708
    rows = [f"{bits:016x}\t{source}\n" for source, bits in cases]
    fixture = destination / "cases.tsv"
    fixture.write_text("".join(rows))
    binary = destination / "cases.bin"
    binary.write_bytes(b"".join(struct.pack("<QI", bits, len(source)) + source.encode("ascii")
                                for source, bits in cases))
    source = destination / "decimal-probe.c"
    source.write_text(PROBE.replace("/* CONVERTER */", '#include "' + header.as_posix() + '"'))
    print(f"corpus: {len(rows)} sha256={hashlib.sha256(fixture.read_bytes()).hexdigest()}", flush=True)
    clang = os.environ.get("MINYAR_TEST_CLANG", os.environ.get("CLANG", "clang"))
    environment = {**os.environ, "ASAN_OPTIONS": "detect_leaks=0", "UBSAN_OPTIONS": "halt_on_error=1"}
    if sanitize:
        environment["MINYAR_TEST_LINK_FLAGS"] = environment.get("MINYAR_TEST_LINK_FLAGS", "") + " -fsanitize=address,undefined"
    freestanding = destination / "decimal-freestanding.c"
    freestanding.write_text('#include <stdint.h>\n#include <stddef.h>\n#include <limits.h>\n'
                            '#include <string.h>\n#include <math.h>\n'
                            'typedef struct { const unsigned char *bytes; long long byte_length; } MinyarText;\n'
                            '_Noreturn void minyar_stop(const char *);\n'
                            '#include "' + header.as_posix() + '"\n')
    resource = run([clang, "-print-resource-dir"]).strip()
    for target in ["x86_64-unknown-none-elf", "aarch64-unknown-none-elf"]:
        llvm = destination / (target + ".ll")
        run([clang, "--target=" + target, "-std=c11", "-O2", "-ffreestanding", "-fno-builtin",
             "-nostdinc", "-isystem", Path(resource) / "include", "-isystem",
             Path("runtime/freestanding/include").resolve(), "-Wall", "-Wextra", "-Werror",
             "-S", "-emit-llvm", freestanding, "-o", llvm])
        run([clang, "--target=" + target, "-O2", "-ffreestanding", "-c", llvm,
             "-o", destination / (target + ".o")])
        ir = llvm.read_text()
        assert "define" in ir and "@minyar_runtime_jsonNumber(" in ir
        for name in re.findall(r"^declare[^\n]*@([^ (]+)\(", ir, flags=re.MULTILINE):
            assert name in {"memcpy", "memset", "minyar_stop"} or name.startswith("llvm."), name
    print("decimal freestanding x86_64/arm64 compilation passed", flush=True)
    for mode in (["sanitize"] if sanitize else ["O0", "O2"]):
        executable = destination / ("decimal-" + mode)
        command = [clang, "-std=c11", "-Wall", "-Wextra", "-Werror"]
        command += ["-O1", "-g", "-fsanitize=address,undefined", "-fno-omit-frame-pointer"] if mode == "sanitize" else ["-" + mode]
        run(command + [source, "-lm", "-o", executable])
        print(mode + ":", flush=True)
        expected = f"decimal grammar checks passed\ndecimal oracle: {len(cases)} exact cases in four rounding modes passed\n"
        assert run([executable, fixture], environment=environment) == expected
        # A corrupt expected bit must fail, proving this probe consumes its oracle.
        wrong = destination / "wrong.tsv"
        wrong.write_text("0000000000000001" + "".join(rows)[16:])
        assert run([executable, wrong], environment=environment, expected=1,
                   diagnostic="expected 0000000000000001 got 0000000000000000") == ""
    harness = Path(os.environ.get("MINYAR_JSON_NUMBER_HARNESS", "build/tooling/tests/json-numbers")).resolve()
    environment.update(MINYAR_JSON_NUMBER_CASES=str(binary), MINYAR_JSON_NUMBER_COUNT=str(len(cases)))
    expected = "JSON number APIs and gallery: O0/O2 with ownership checks passed\n"
    assert run([harness], environment=environment) == expected
    wrong_binary = destination / "wrong.bin"
    wrong_binary.write_bytes(struct.pack("<Q", 1) + binary.read_bytes()[8:])
    environment["MINYAR_JSON_NUMBER_CASES"] = str(wrong_binary)
    run([harness], environment=environment, expected=1, diagnostic="wrong JSON number bits: 0")
    print("JSON number native/API oracle controls passed", flush=True)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sanitize", action="store_true")
    options = parser.parse_args()
    destination = Path(tempfile.mkdtemp(prefix="minyar-json-numbers-"))
    try:
        verify(destination, options.sanitize)
    except BaseException:
        print(f"JSON number failure evidence: {destination}", file=sys.stderr)
        raise
    shutil.rmtree(destination)

if __name__ == "__main__":
    main()
