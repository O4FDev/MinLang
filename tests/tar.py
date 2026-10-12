#!/usr/bin/env python3
"""Tar interoperability and seeded malformed differential tests, no extraction.

--quick is a small macOS check. Full/sanitized runs belong on Boat.
MINYAR_TEST_RUNTIME may reuse an existing system-heap runtime object.
"""
import argparse
import io
from decimal import Decimal, ROUND_FLOOR, InvalidOperation
import os
from pathlib import Path
import random
import struct
import subprocess
import tarfile
import tempfile
import base64
import urllib.parse
import sys
from functools import lru_cache
from tar_support import strict_scan

from clang_helpers import clang_command, asan_leak_options

ROOT = Path(__file__).resolve().parents[1]
FOOTER = bytes(1024)


@lru_cache(maxsize=None)
def tar_provider(clang='clang', flags=()):
    # The shared helper is owned by the WS5 parent. An isolated implementation
    # checkout can select its reviewed tools without copying/committing them.
    tools = Path(os.environ.get('MINYAR_TAR_PROVIDER_TOOLS',ROOT / 'tools'))
    sys.path.insert(0,str(tools))
    from format_provider import format_provider
    return format_provider('tararchive',clang,flags)


def header(name="a", data=b"", kind=tarfile.REGTYPE, **fields):
    info = tarfile.TarInfo(name)
    info.type = kind
    info.size = len(data)
    info.mode = fields.pop("mode", 0o644)
    for key, value in fields.items():
        setattr(info, key, value)
    return info.tobuf(format=tarfile.USTAR_FORMAT) + data + bytes(-len(data) % 512)


def repair(block):
    result = bytearray(block)
    result[148:156] = b" " * 8
    result[148:156] = f"{sum(result[:512]):06o}\0 ".encode()
    return bytes(result)


def pax_record(key, value):
    body = key.encode() + b"=" + (value.encode() if isinstance(value, str) else value) + b"\n"
    size = len(body) + 2
    while True:
        record = str(size).encode() + b" " + body
        if len(record) == size:
            return record
        size = len(record)


def fixtures():
    items = []
    for format in (tarfile.USTAR_FORMAT, tarfile.PAX_FORMAT, tarfile.GNU_FORMAT):
        stream = io.BytesIO()
        with tarfile.open(fileobj=stream, mode="w", format=format) as archive:
            specs = [("root/", tarfile.DIRTYPE, b""),
                     ("root/.wh.deleted", tarfile.REGTYPE, b""),
                     ("root/.wh..wh..opq", tarfile.REGTYPE, b""),
                     ("root/data", tarfile.REGTYPE, b"\0abc\xff\n"),
                     ("root/sym", tarfile.SYMTYPE, b""),
                     ("root/hard", tarfile.LNKTYPE, b""),
                     ("root/char", tarfile.CHRTYPE, b""),
                     ("root/block", tarfile.BLKTYPE, b""),
                     ("root/fifo", tarfile.FIFOTYPE, b""),
                     ("p" * 120 + "/" + "n" * 80, tarfile.REGTYPE, b"end")]
            if format != tarfile.USTAR_FORMAT:
                specs += [("é/" + "long" * 85, tarfile.REGTYPE, b"long"),
                          ("longlink", tarfile.SYMTYPE, b"")]
            for index, (name, kind, data) in enumerate(specs):
                info = tarfile.TarInfo(name)
                info.type = kind
                info.size = len(data)
                info.mode = 0o755 if kind == tarfile.DIRTYPE else 0o640
                info.uid, info.gid, info.mtime = 123, 456, 1700000000
                if kind in (tarfile.LNKTYPE, tarfile.SYMTYPE):
                    info.linkname = "root/data" if name != "longlink" else "target/" + "x" * 240
                if kind in (tarfile.CHRTYPE, tarfile.BLKTYPE):
                    info.devmajor, info.devminor = 1, 7
                if format == tarfile.PAX_FORMAT:
                    info.mtime = -1.25 if index == 3 else 1700000000.125
                    info.uid = 123456789012
                    info.pax_headers = {"SCHILY.xattr.user.oci": "kept"}
                archive.addfile(info, io.BytesIO(data))
        items.append((f"python-{format}", stream.getvalue()))
    items += [("empty", FOOTER),
              ("v7", repair(header()[:257] + bytes(255)) + FOOTER),
              ("full-width-name", header("n" * 100) + FOOTER),
              ("pax-size", header("pax", pax_record("size", "513"), tarfile.XHDTYPE) +
               repair(header("a", b"a" * 513)[:124] + b"00000000001\0" + header("a", b"a" * 513)[136:]) + header("next", b"cursor") + FOOTER),
              ("pax-global", header("global", pax_record("uid", "900"), tarfile.XGLTYPE) +
               header("a") + header("local", pax_record("uid", "901"), tarfile.XHDTYPE) +
               header("b") + header("c") + FOOTER),
              ("path-traversal-raw", header("../outside", b"raw") + FOOTER)]
    # GNU two's complement/base-256 and signed-checksum compatibility.
    binary = bytearray(header())
    binary[136:148] = b"\xff" * 11 + b"\xfe"
    items.append(("gnu-negative-time", repair(binary) + FOOTER))
    binary=bytearray(header())
    binary[108:116]=tarfile.itn(1<<40,8,tarfile.GNU_FORMAT)
    binary[116:124]=tarfile.itn(-(1<<40),8,tarfile.GNU_FORMAT)
    binary[136:148]=tarfile.itn((1<<63)-1,12,tarfile.GNU_FORMAT)
    items.append(("gnu-base256-wide-signed",repair(binary)+FOOTER))
    signed = bytearray(header())
    signed[0] = 0xff
    signed[148:156] = b" " * 8
    total = sum(byte if byte < 128 else byte - 256 for byte in signed[:512])
    signed[148:156] = f"{total:06o}\0 ".encode()
    items.append(("signed-checksum", bytes(signed) + FOOTER))
    def x(records, kind=tarfile.XHDTYPE):
        return header("metadata", b"".join(pax_record(k,v) for k,v in records), kind)
    capability = bytes.fromhex("0100000200000000000400000000000000000000")
    items += [
        ("zero-record-padding", header("padded",b"abc")+FOOTER+bytes(512*18)),
        ("binary-attributes", x([("hdrcharset","BINARY"),("path",b"byte/\xff"),
            ("SCHILY.xattr.security.capability",capability),("SCHILY.xattr.user.binary",b"\x00\xff\n=payload"),
            ("SCHILY.xattr.user.%literal",b"percent-name"),
            ("LIBARCHIVE.xattr.user.encoded",base64.b64encode(b"\x00\xff\x01")),
            ("LIBARCHIVE.xattr.user.escaped%25name",base64.b64encode(b"escaped-name")),
            ("VENDOR.opaque",b"\x00\xff\n=raw")])+header("base",b"contents")+FOOTER),
        ("binary-link-empty-base", x([("hdrcharset","BINARY"),("linkpath",b"target/\xff")])+header("link",kind=tarfile.SYMTYPE)+FOOTER),
        ("binary-link", x([("hdrcharset","BINARY"),("linkpath",b"target/\xff")])+header("link",kind=tarfile.SYMTYPE,linkname="fallback")+FOOTER),
        ("binary-owner-names", x([("hdrcharset","BINARY"),("uname",b"owner/\xff"),("gname",b"group/\xfe")])+header("owners")+FOOTER),
        ("long-owner-names", x([("uname","u"*120),("gname","g"*120)])+header("owners-long")+FOOTER),
        ("exact-path-limit", x([("path","p"*4096)])+header("base")+FOOTER),
        ("duplicate-pax-key", x([("uid","900"),("uid","901"),("VENDOR.test","first"),("VENDOR.test","last")])+header()+FOOTER),
        ("gnu-pax-combined", header("long",b"long-path\0",tarfile.GNUTYPE_LONGNAME)+
            header("link",b"long-link\0",tarfile.GNUTYPE_LONGLINK)+x([("uid","77"),("mtime","-1.25")])+header("base",kind=tarfile.SYMTYPE)+FOOTER),
        ("exact-large-time", x([("mtime","9223372036854775806.123456789"),("uid","9223372036854775807"),("gid","-9223372036854775808")])+header()+FOOTER),
        ("exact-small-negative-time", x([("mtime","-0.000000001")])+header()+FOOTER),
        ("exact-min-time", x([("mtime","-9223372036854775807.25")])+header()+FOOTER),
        ("exact-max-time", x([("mtime","9223372036854775807.999999999")])+header()+FOOTER),
    ]
    # Known-valid seeded mutations are mandatory successes, including nonzero
    # payload padding (only end/record padding must be zero).
    seed=bytearray(header("valid-mutation",b"abc")+FOOTER)
    seed[513]^=0x80; items.append(("known-valid-payload",bytes(seed)))
    seed[700]=0x9a; items.append(("known-valid-payload-padding",bytes(seed)))
    seed[108:116]=b"0000777\0"; items.append(("known-valid-repaired-header",repair(seed)))
    return items


def policy_fixtures():
    def x(pairs,kind=tarfile.XHDTYPE): return header("metadata",b"".join(pax_record(k,v) for k,v in pairs),kind)
    source = (x([("uid","900"),("VENDOR.test","global")],tarfile.XGLTYPE)+header("a",uid=7)+
              x([("uid","901"),("VENDOR.test","local")])+header("b",uid=7)+
              x([("uid",""),("VENDOR.test","")])+header("c",uid=7)+header("d",uid=7)+
              x([("uid",""),("VENDOR.test","")],tarfile.XGLTYPE)+header("e",uid=7)+FOOTER)
    expected=oracle(b"".join(header(name,uid=uid) for name,uid in zip("abcde",[900,901,7,900,7]))+FOOTER)
    multi=x([("uid","901")])+x([("uid","902")])+header("multi",uid=7)+FOOTER
    multi_expected=oracle(header("multi",uid=902)+FOOTER)
    sized=(x([("size","513")],tarfile.XGLTYPE)+repair(header("a",b"a"*513)[:124]+b"00000000001\0"+header("a",b"a"*513)[136:])+
           x([("size","")],tarfile.XGLTYPE)+header("next",b"cursor")+FOOTER)
    sized_expected=oracle(header("a",b"a"*513)+header("next",b"cursor")+FOOTER)
    deep=b''.join(x([("uid",str(800+i))]) for i in range(64))+header("deep")+FOOTER
    deep_expected=oracle(header("deep",uid=863)+FOOTER)
    combined=(header("long",b"global-long-path\0",tarfile.GNUTYPE_LONGNAME)+
              header("link",b"global-long-link\0",tarfile.GNUTYPE_LONGLINK)+
              x([("uid","900")],tarfile.XGLTYPE)+header("base",kind=tarfile.SYMTYPE)+FOOTER)
    combined_expected=oracle(header("global-long-path",kind=tarfile.SYMTYPE,linkname="global-long-link",uid=900)+FOOTER)
    return [("global-local-delete-override",source,expected),("multiple-local-override",multi,multi_expected),
            ("global-size-and-delete",sized,sized_expected),("exact-default-chain",deep,deep_expected),
            ("global-gnu-combined",combined,combined_expected)]


def oracle(source):
    with tarfile.open(fileobj=io.BytesIO(source), mode="r:", encoding="utf-8", errors="surrogateescape") as archive:
        entries = []
        for entry in archive:
            data = archive.extractfile(entry).read() if entry.isreg() else b""
            stamp = Decimal(entry.pax_headers.get("mtime", str(entry.mtime)))
            seconds = int(stamp.to_integral_value(rounding=ROUND_FLOOR))
            nanos = int((stamp - seconds) * 1_000_000_000)
            entries.append(((entry.name + ("/" if entry.isdir() and not entry.name.endswith("/") and source[entry.offset_data - 512:entry.offset_data - 412].rstrip(b"\0").endswith(b"/") else "")).encode("utf-8", "surrogateescape").hex(),
                            entry.linkname.encode("utf-8", "surrogateescape").hex(),
                            str(entry.mode), str(entry.uid), str(entry.gid), str(seconds), str(nanos),
                            str(entry.type[0] if entry.type != tarfile.AREGTYPE else 48),
                            str(entry.size), str(entry.devmajor), str(entry.devminor), data.hex(),
                            entry.uname.encode('utf-8','surrogateescape').hex(),
                            entry.gname.encode('utf-8','surrogateescape').hex()))
        return entries


def compare_reference(actual, reference, source, name, provider_version):
    spans, _ = strict_scan(source)
    reference = list(reference)
    for i, fields in enumerate(reference[:len(actual)]):
        attrs = spans[i][4] if i < len(spans) else {}
        stamp = attrs.get(b"mtime", b"")
        if stamp.startswith(b"-") and b"." in stamp and Decimal(stamp.decode()) % 1:
            # libarchive 3.7.2 reads negative PAX fractions as (-whole,+frac).
            # Assert the exact known provider defect, then compare all other
            # fields. Minyar remains accountable to exact decimal expectations.
            trunc = int(Decimal(stamp.decode()))
            fraction = int(abs(Decimal(stamp.decode()) - trunc) * 1_000_000_000)
            expected = (str(trunc - 1), str(1_000_000_000 - fraction))
            if fields[5:7] != expected:
                assert provider_version == 3007002, (name,"unqualified C timestamp exception",provider_version)
                assert fields[5:7] == (str(trunc), str(fraction)), (name,"unexpected C timestamp",fields,stamp)
                fields = fields[:5] + expected + fields[7:]
                reference[i] = fields
    assert actual == reference[:len(actual)], (name,"libarchive metadata/payload",actual,reference)


def reference_input(source):
    spans, reason = strict_scan(source)
    has_globals = False
    multiple_local = False
    empty_links = False
    gnu_extensions = []
    for start,hdr,payload,end,attrs in spans:
        at=start; count=0; gnus=[]; long_link=None
        while at < hdr:
            kind=source[at+156:at+157]
            if kind == tarfile.XHDTYPE: count+=1
            if kind == tarfile.XGLTYPE: has_globals=True
            size=tarfile.nti(source[at+124:at+136]); next_at=at+512+size+(-size%512)
            if kind in (tarfile.GNUTYPE_LONGNAME,tarfile.GNUTYPE_LONGLINK): gnus.append(source[at:next_at])
            if kind == tarfile.GNUTYPE_LONGLINK: long_link=source[at+512:at+512+size].rstrip(b'\0')
            at=next_at
        multiple_local |= count>1
        empty_links |= bool(attrs.get(b'linkpath',long_link) and not source[hdr+157:hdr+257].rstrip(b'\0'))
        gnu_extensions.append(gnus)
    if not has_globals and not empty_links and not multiple_local: return source
    # Resolve global PAX independently (unsupported by libarchive). An empty
    # base link triggers a provider3.7.2 link-classification bug; give C a base
    # link so it can independently parse the PAX byte link and payload.
    out=bytearray()
    for (start,hdr,payload,end,attrs),gnus in zip(spans,gnu_extensions):
        if has_globals or multiple_local:
            out += b''.join(gnus)
            extension=b"".join(pax_record(k.decode('ascii'),v) for k,v in attrs.items())
            if extension: out += header("resolved-global",extension,tarfile.XHDTYPE)
        else: out += source[start:hdr]
        physical=bytearray(source[hdr:end])
        if physical[156] in (49,50) and not physical[157:257].rstrip(b"\0"):
            physical[157:257]=b"fallback"+bytes(92)
            physical=bytearray(repair(physical))
        out += physical
    return bytes(out)+FOOTER


def malformed():
    valid = header("a", b"abc") + FOOTER
    for cut in (0, 1, 511, 512, 514, 515, 1023, 1024, 1535, 1536, 2047):
        yield f"truncated-{cut}", valid[:cut]
    yield "single-end", bytes(512)
    yield "garbage-tail", valid + b"x"
    yield "entry-after-end", FOOTER + header("hidden") + FOOTER
    yield "zero-before-entry", bytes(512) + valid
    bad = bytearray(valid)
    bad[0] ^= 1
    yield "checksum", bytes(bad)
    for name, start, data in [("octal-digit", 100, b"0000099\0"),
                              ("octal-junk", 100, b"0000644x"),
                              ("negative-size", 124, b"\xff" * 12),
                              ("overflow", 124, b"\x80" + b"\xff" * 11),
                              ("oversize", 124, b"77777777777\0"),
                              ("bad-magic", 257, b"bogus\0"),
                              ("bad-version", 263, b"zz")]:
        bad = bytearray(valid)
        bad[start:start + len(data)] = data
        yield name, repair(bad)
    for name, content in [("pax-zero", b"0 path=x\n"),
                           ("pax-length", b"999 path=x\n"),
                           ("pax-no-equal", b"10 pathxx\n"),
                           ("pax-no-newline", b"10 path=x!"),
                           ("pax-overflow", b"99999999999999999999999 path=x\n"),
                           ("pax-empty-path", pax_record("path", "\0")),
                           ("pax-size-overflow", pax_record("size", "9223372036854775808")),
                           ("pax-negative-size", pax_record("size", "-1")),
                           ("pax-bad-mtime", pax_record("mtime", "1.nan")),
                           ("sparse", pax_record("GNU.sparse.map", "0,1")),
                           ("sparse-star",pax_record("SCHILY.filetype","sparse")),
                           ("fraction-precision",pax_record("mtime","1.0000000001"))]:
        yield name, header("pax", content, tarfile.XHDTYPE) + header() + FOOTER
    yield "dangling-pax", header("pax", pax_record("path", "long"), tarfile.XHDTYPE) + FOOTER
    yield "dangling-gnu", header("long", b"a\0", tarfile.GNUTYPE_LONGNAME) + FOOTER
    yield "old-gnu-sparse", header("sparse", kind=tarfile.GNUTYPE_SPARSE) + FOOTER
    yield "path-limit", header("pax", pax_record("path", "x" * 4097), tarfile.XHDTYPE) + header() + FOOTER
    yield "metadata-limit", header("long", b"x" * (1048576 + 1), tarfile.GNUTYPE_LONGNAME) + header() + FOOTER


def build_program(work, source, name, sanitize=False):
    compiler = Path(os.environ.get("MINYAR_TEST_COMPILER", ROOT / "build/minyarc"))
    clang = os.environ.get("MINYAR_TEST_CLANG", "clang")
    llvm = work / (name + ".ll")
    subprocess.run([compiler, source, llvm, "--library", ROOT / "library"], check=True, timeout=60)
    if sanitize:
        from llvm_sanitizer import instrument_address_sanitizer
        llvm.write_text(instrument_address_sanitizer(llvm.read_text()))
    flags = ["-O1", "-g", "-fsanitize=address,undefined", "-fno-omit-frame-pointer"] if sanitize else ["-O2"]
    runtime = os.environ.get("MINYAR_TEST_RUNTIME")
    if not runtime:
        runtime = work / "runtime.o"
        subprocess.run(clang_command([clang, *flags, "-DMINYAR_SYSTEM_HEAP=1", "-c",
                                     ROOT / "runtime/minyar_runtime.c", "-o", runtime]), check=True, timeout=60)
    elif sanitize:
        raise ValueError("sanitizer run requires a freshly instrumented runtime")
    native = []
    if "; minyar-native-library: tararchive" in llvm.read_text():
        cflags,libraries = tar_provider(clang,tuple(flags))
        native = [*cflags,ROOT / "runtime/native/tararchive.c",*libraries]
    executable = work / name
    subprocess.run(clang_command([clang, *flags, "-Wno-override-module", llvm, runtime, *native, "-o", executable]), check=True, timeout=60)
    return executable


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--sanitize", action="store_true")
    parser.add_argument("--libarchive", type=Path, help="compiled benchmarks/tar/libarchive.c oracle")
    args = parser.parse_args()
    cases = [(name, source, oracle(source)) for name, source in fixtures()]
    cases += policy_fixtures()
    cases += [(name, source, False) for name, source in malformed()]
    rng = random.Random(0x544152)
    seeds = [source for _, source in fixtures()]
    for index in range(64 if args.quick else 2000):
        source = bytearray(rng.choice(seeds))
        if index % 3 == 0:
            source = source[:rng.randrange(len(source))]
        else:
            for _ in range(rng.randrange(1, 5)):
                source[rng.randrange(len(source))] ^= 1 << rng.randrange(8)
        try:
            expected = oracle(source)
        except (tarfile.TarError, ValueError, OverflowError, OSError, InvalidOperation):
            expected = False
        spans, reason = strict_scan(bytes(source))
        if expected is not False and reason is None:
            cases.append((f"mutation-{index}", bytes(source), expected))
        else:
            cases.append((f"mutation-{index}", bytes(source), False))
    (ROOT / "build").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="tar-test-", dir=ROOT / "build") as temp:
        work = Path(temp)
        executable = build_program(work, ROOT / "tests/tar.min", "tar", args.sanitize)
        framing = work / "corpus.bin"
        framing.write_bytes(b"".join(struct.pack("<I", len(source)) + source for _, source, _ in cases))
        fixture = work / "writer-input.tar"
        writer_sources = [source for name,source in fixtures() if name in ("python-0","python-1","python-2","binary-attributes","binary-link","binary-owner-names","long-owner-names","gnu-base256-wide-signed","exact-path-limit","exact-large-time","exact-small-negative-time","exact-min-time","exact-max-time")]
        fixture.write_bytes(b"".join(source[:strict_scan(source)[0][-1][3]] for source in writer_sources) + FOOTER)
        written = work / "written.tar"
        environment = {**os.environ, "ASAN_OPTIONS": asan_leak_options() + ":halt_on_error=1", "UBSAN_OPTIONS": "halt_on_error=1"}
        result = subprocess.run([executable, framing, fixture, written], capture_output=True, text=True, env=environment, timeout=30)
        assert result.returncode == 0 and not result.stderr, (result.returncode, result.stdout[-2000:], result.stderr)
        if not args.sanitize:
            # Exercise the shared public linker as well as the direct custom
            # recipe. It must resolve the tar native marker by itself.
            public = work / 'public-tar'
            driver = Path(os.environ.get('MINYAR_TAR_PROVIDER_TOOLS',ROOT / 'tools')) / 'clang-driver.py'
            runtime = os.environ.get('MINYAR_TEST_RUNTIME',work / 'runtime.o')
            link_env={**environment,'MINYAR_CLANG':os.environ.get('MINYAR_TEST_CLANG','clang'),
                      'MINYAR_CLANG_FLAGS':'-O2 -Wno-override-module','MINYAR_NATIVE_FLAGS':'-O2'}
            subprocess.run([sys.executable,driver,'link',ROOT,work/'tar.ll',runtime,public,'1'],check=True,env=link_env,timeout=60)
            public_output=work/'public-written.tar'
            linked=subprocess.run([public,framing,fixture,public_output],capture_output=True,text=True,env=environment,timeout=30)
            assert linked.returncode==0 and linked.stdout==result.stdout and not linked.stderr,('public tar link',linked.stderr)
            assert public_output.read_bytes()==written.read_bytes(),'public/custom writer equality'
        actual = [[] for _ in cases]
        status = [None for _ in cases]
        actual_spans = [[] for _ in cases]
        actual_attrs = [{} for _ in cases]
        actual_xattrs = [{} for _ in cases]
        xattr_errors = [set() for _ in cases]
        last_path = [None for _ in cases]
        for line in result.stdout.splitlines():
            index, kind, *fields = line.split("|")
            index = int(index)
            if kind == "ENTRY":
                actual[index].append(tuple(fields))
                last_path[index]=fields[0]
            elif kind == "SPAN":
                actual_spans[index].append(tuple(map(int,fields[1:])))
                actual_attrs[index][fields[0]] = {}
            elif kind == "XATTR":
                actual_xattrs[index].setdefault(fields[0],{})[bytes.fromhex(fields[1])] = bytes.fromhex(fields[2])
            elif kind == "XATTRERROR":
                xattr_errors[index].add(last_path[index])
            elif kind == "ATTR":
                actual_attrs[index][fields[0]][bytes.fromhex(fields[1])] = bytes.fromhex(fields[2])
            else:
                status[index] = kind
        for index, (name, source, expected) in enumerate(cases):
            assert status[index] in ("END", "ERROR"), name
            spans, reason = strict_scan(source)
            assert actual_spans[index] == [span[:4] for span in spans], (name,"physical spans",actual_spans[index],spans)
            for fields, span in zip(actual[index],spans):
                assert actual_attrs[index][fields[0]] == span[4], (name,"effective raw PAX attributes",actual_attrs[index],span[4])
                xattrs={}; bad_encoding=False
                for k,v in span[4].items():
                    if k.startswith(b'SCHILY.xattr.'): key=k[13:]; value=v
                    elif k.startswith(b'LIBARCHIVE.xattr.'):
                        try:
                            key=urllib.parse.unquote_to_bytes(k[17:])
                            # Reject malformed percent escapes and noncanonical
                            # base64 tails independently of the Minyar decoder.
                            import re
                            if re.search(rb'%(?![0-9a-fA-F]{2})',k[17:]): raise ValueError('escape')
                            value=base64.b64decode(v+b'='*(-len(v)%4),validate=True)
                            if base64.b64encode(value).rstrip(b'=') != v.rstrip(b'='): raise ValueError('base64 tail')
                        except ValueError: bad_encoding=True; continue
                    else: continue
                    if not key or b'\0' in key or (key in xattrs and xattrs[key]!=value): bad_encoding=True
                    xattrs[key]=value
                assert (fields[0] in xattr_errors[index])==bad_encoding,(name,'xattr encoding status')
                if not bad_encoding:
                    assert actual_xattrs[index].get(fields[0],{}) == xattrs, (name,"binary xattrs",actual_xattrs[index],xattrs)
            if expected is False:
                assert status[index] == "ERROR", (name, "accepted malformed archive")
                spans, reason = strict_scan(source)
                assert reason is not None, (name, "no explicit strictness reason")
                complete = source[:spans[-1][3]] + FOOTER if spans else FOOTER
                assert actual[index] == oracle(complete), (name, "entries before error", actual[index], oracle(complete))
            else:
                assert status[index] == "END" and actual[index] == expected, (name, status[index], actual[index], expected)
        assert oracle(written.read_bytes()) == oracle(fixture.read_bytes()), "writer round trip"
        written_spans,_ = strict_scan(written.read_bytes())
        input_spans,_ = strict_scan(fixture.read_bytes())
        for w,i in zip(written_spans,input_spans):
            retained = {k:v for k,v in i[4].items() if k.startswith((b'SCHILY.xattr.',b'LIBARCHIVE.xattr.',b'VENDOR.'))}
            assert all(w[4].get(k)==v for k,v in retained.items()), "writer raw attribute preservation"
        # Exact canonical output: no record padding past the two end blocks.
        assert written.read_bytes()[-1024:] == FOOTER
        second = work / "second.tar"
        subprocess.run([executable, framing, fixture, second], check=True, stdout=subprocess.DEVNULL, timeout=30, env=environment)
        assert second.read_bytes() == written.read_bytes(), "writer determinism"
        reference_binary = args.libarchive
        if reference_binary is None:
            reference_binary = work / "libarchive"
            flags = ["-O1","-g","-fsanitize=address,undefined","-fno-omit-frame-pointer"] if args.sanitize else ["-O2"]
            cflags,libraries = tar_provider(os.environ.get("MINYAR_TEST_CLANG","clang"),tuple(flags))
            subprocess.run(clang_command([os.environ.get("MINYAR_TEST_CLANG","clang"),*flags,*cflags,ROOT/"benchmarks/tar/libarchive.c",*libraries,"-o",reference_binary]),check=True,timeout=60)
        if reference_binary:
            provider_version = int(subprocess.check_output([reference_binary,"version"],text=True).splitlines()[0])
            ref_framing = work / "reference-corpus.bin"
            ref_framing.write_bytes(b"".join(struct.pack("<I",len(reference_input(source))) + reference_input(source) for _,source,_ in cases))
            reference = subprocess.check_output([reference_binary,"corpus",ref_framing],text=True,env=environment,timeout=30)
            ref = [[] for _ in cases]
            ref_xattrs = [{} for _ in cases]
            for line in reference.splitlines():
                index,kind,*fields = line.split("|")
                if kind == "ENTRY": ref[int(index)].append(tuple(fields))
                if kind == "XATTR": ref_xattrs[int(index)].setdefault(fields[0],{})[bytes.fromhex(fields[1])]=bytes.fromhex(fields[2])
            for index,(name,source,expected) in enumerate(cases):
                # libarchive may emit an entry whose padding/footer later fails;
                # the complete entries our reader emits must match independently.
                compare_reference(actual[index], ref[index], source, name, provider_version)
                if isinstance(expected,list): assert len(ref[index]) == len(actual[index]), (name,"libarchive count")
                for row in actual[index]:
                    if row[0] not in xattr_errors[index]:
                        assert actual_xattrs[index].get(row[0],{})==ref_xattrs[index].get(row[0],{}),(name,'libarchive binary xattrs')
            output = subprocess.check_output([reference_binary,"verify",written],text=True,env=environment,timeout=10)
            refwritten = [tuple(line.split("|")[2:]) for line in output.splitlines() if "|ENTRY|" in line]
            compare_reference(oracle(fixture.read_bytes()), refwritten, written.read_bytes(), "writer", provider_version)
        contract = build_program(work,ROOT / "tests/tar-contract.min","contract",args.sanitize)
        plain=work/"plain.tar"; plain.write_bytes(header("plain",b"abc")+FOOTER)
        combined=work/"combined.tar"; combined.write_bytes(dict(fixtures())["gnu-pax-combined"])
        metadata=work/"metadata.tar"; metadata.write_bytes(dict(fixtures())["binary-attributes"])
        metadata_limit=tarfile.nti(metadata.read_bytes()[124:136])
        edited=work/"edited.tar"
        subprocess.run([contract,plain,combined,metadata,str(metadata_limit),edited],check=True,env=environment,timeout=30)
        rows=oracle(edited.read_bytes())
        assert len(rows)==1 and rows[0][0]==b"edited".hex() and rows[0][3:7]==("-7","9223372036854775807","-2","750000000"), ("edited field precedence",rows)
        assert rows[0][8]==str(len(b"contents")) and rows[0][11]==b"contents".hex(),("edited payload size",rows)
        original_attrs=strict_scan(metadata.read_bytes())[0][0][4]
        edited_attrs=strict_scan(edited.read_bytes())[0][0][4]
        for k,v in original_attrs.items():
            if k.startswith((b"SCHILY.xattr.",b"LIBARCHIVE.xattr.",b"VENDOR.")): assert edited_attrs[k]==v,("edited binary attrs",k)
        cref=subprocess.check_output([reference_binary,"verify",edited],text=True,env=environment,timeout=10)
        compare_reference(rows,[tuple(line.split("|")[2:]) for line in cref.splitlines() if "|ENTRY|" in line],edited.read_bytes(),"edited writer",provider_version)
        from tar_review import run as review_contracts
        review_contracts(work/'completed-review',args.sanitize,environment)
        print(f"tar: {len(cases)} fixture/malformed/differential cases; metadata, spans, binary xattrs, Python/libarchive writer interop, limits and determinism passed; provider {provider_version}")


if __name__ == "__main__":
    main()
