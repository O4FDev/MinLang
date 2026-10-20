#!/usr/bin/env python3
"""Catalog exact language-guide examples; never repair or scaffold their source.

The expectations below are reviewed oracles derived from the guide's contracts,
literal values and arithmetic. This generator never executes Minyar programs.
New or changed source remains visible as unreviewed until explicitly classified.
"""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys
import unicodedata

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DOCUMENT = ROOT / "docs/language.md"
DEFAULT_OUTPUT = ROOT / "build/wasm/language-examples.json"


def standalone(title, expected, basis, *, reason=None, note=None):
    policy = {
        "title": title,
        "classification": "standalone",
        "runnable": True,
        "reason": reason or "A complete standalone program with no omitted declarations or host-only dependencies.",
        "expected": expected,
        "expectedExitCode": 0,
        "expectedBasis": basis,
    }
    if note:
        policy["note"] = note
    return policy


def contextual(title, classification, reason):
    return {"title": title, "classification": classification, "runnable": False, "reason": reason}


# Keys identify exact UTF-8 source, including indentation and trailing newlines.
# Do not update an expectation from observed engine output: review its basis.
POLICIES = {
    "12eba5ad22ce": contextual(
        "A test beside its function", "test-mode",
        "This example needs minyar test or --test-mode. Ordinary playground Run omits test blocks, so an empty run would not exercise the expectation.",
    ),
    "a90d7ae76d0f": standalone(
        "Documentation on a record", "",
        "Only a record and documentation comments are declared; there are no print calls or executable statements.",
        reason="A standalone declaration. Running it defines the record and produces no output.",
    ),
    "0cd1ff33cc0c": standalone(
        "Local constant bindings", "",
        "example() is declared but never called; the return and List mutation are inside that uncalled function.",
        reason="A standalone function declaration. Running it does not call example(), so it produces no output.",
    ),
    "4876a344d069": standalone(
        "Changing a binding", "",
        "The three statements change attempts from 3 to 2 to 1 and contain no print call.",
    ),
    "ef461b2c12f5": standalone(
        "Numbers and explicit conversions", "0.30000000000000004\n3.5\n-7\n",
        "The guide gives all three exact printed results in comments: binary64 addition, Float division and Integer truncation toward zero.",
    ),
    "6510e518eabd": standalone(
        "Recovering from Integer overflow", "Integer multiplication overflow\nstill alive\n",
        "MAX_INTEGER times 10 overflows, selecting the error branch. library/errors.min checkedMultiply defines the literal message 'Integer multiplication overflow'; the final print is unconditional.",
    ),
    "e7f740b48458": standalone(
        "Module constants", "",
        "These literal constant declarations contain no executable print calls.",
        reason="Standalone constant declarations. Running them produces no output.",
    ),
    "c2bce209fff3": contextual(
        "Global initialization", "fragment",
        "The CRC_TABLE initializer calls makeTable(), whose declaration is not included in this block.",
    ),
    "6078868dba17": standalone(
        "Ranges and List loops", "0\n1\n2\nMin\nyar\n",
        "The excluded range end visits 0, 1 and 2. List iteration then visits the two literal words in order.",
    ),
    "102f6e98ca26": standalone(
        "A record that counts down", "2\n1\n0\n",
        "The source starts with remaining = 3. Each successful advance() decrements before current() is printed, producing 2, then 1, then 0. The next advance sees zero and returns false, so no fourth value is printed; the guide's comment states the same sequence.",
    ),
    "8240dbfabf22": standalone(
        "Text length, indexing and slices", "6\nM\nMin\n42\n",
        "All four expected results are written in the guide's comments: six scalar values, the first Character, an excluded-end slice and Integer-to-Text conversion.",
    ),
    "d9b04c70a156": contextual(
        "Visible Unicode clusters and comparison", "unsupported-host",
        "This complete program imports unicode for Unicode 18 grapheme segmentation, normalization and case folding. The current browser bundle does not include that module's native Unicode provider, so the whole original program cannot run here yet, including its otherwise valid initial Text.length call.",
    ),
    "770782c176f4": standalone(
        "Words with values inside", "Hello, Ada! You have 42 messages.\nThe answer is true, and the star is ★.\n",
        "Substitute the literal name Ada, the Integer sum 20 + 22, Boolean true and the literal star into the two printed sentences.",
    ),
    "b3a24ca7dc1b": contextual(
        "An invitation in multiline Text", "fragment",
        "The interpolation refers to name, a binding from the preceding example that is not declared in this block.",
    ),
    "71b6cf725cfc": standalone(
        "Raw Text keeps its spelling", "",
        "Both values are raw Text literals. The interpolation-looking spelling inside program is literal text; neither binding is printed.",
    ),
    "e5c899050ee1": standalone(
        "Growing a typed List", "function\n1\n",
        "The empty List receives one literal element, 'function'. Index zero prints that word and the List length is one.",
    ),
    "3c3cb58aaf1d": standalone(
        "List literals and joined Text", "Minyar\n",
        "joinText joins the literal words 'Min' and 'yar', as the guide's comment records. The nested List is not printed.",
    ),
    "bda80626b7ad": standalone(
        "Sorting with a callback", "",
        "The comparator sorts the List but the example contains no print call; successful execution is intentionally quiet.",
    ),
    "408a54a577e5": standalone(
        "Bytes and a 32-bit Float", "9\n1.5\n",
        "Four initial bytes plus one byte plus four Float32 bytes make length 9. The exactly representable 1.5 is read from its original byte offset 5.",
    ),
    "03f2906c7af3": standalone(
        "UTF-8 bytes and Unicode Text", "5\n",
        "The literal héllo has five Unicode scalar values, although its UTF-8 representation occupies six bytes; the guide states both counts.",
    ),
    "1cb842b6f3b6": standalone(
        "Shared and cyclic records", "1\n",
        "root.children[0] is the leaf whose value is the literal 1. The later self-cycle adds no print call.",
    ),
    "52c733af18a9": contextual(
        "An appended copy of a List", "fragment",
        "Node and leaf are declared by the preceding example and are missing from this block.",
    ),
    "df8d0546bf62": standalone(
        "A named record", "Ada\n",
        "The constructed Person has the literal name Ada, and print reads that field once.",
    ),
    "7c0ce6449479": contextual(
        "Records inside a List", "fragment",
        "The Person type and ada binding come from the preceding record example and are not declared here.",
    ),
    "23481644869c": contextual(
        "Aliases observe field changes", "fragment",
        "The Person record declaration is omitted. The block is a continuation of the preceding record examples.",
    ),
    "a7cdc8bfbe33": standalone(
        "A record with a private field", "",
        "The Account type and its open/balance functions are declared, but no account is constructed and no function is called or printed.",
        reason="Standalone record and function declarations. Running them produces no output.",
    ),
    "eaa578f0560f": contextual(
        "An instance method", "fragment",
        "The method needs the preceding Account declaration, and account.deposit(10) also needs an account binding that this block does not create.",
    ),
    "48bcc49ec149": standalone(
        "A choice of shapes", "12.56636\n",
        "Circle(2.0) selects only the Circle arm. Multiplication by 2.0 twice scales the binary64 literal 3.14159 by four; the documented shortest-roundtrip Float spelling is 12.56636.",
    ),
    "c0407a26360b": contextual(
        "A match that produces a value", "fragment",
        "The Shape choice, its cases and the shape binding are supplied by the previous example, not by this block.",
    ),
    "4869b80f1a28": standalone(
        "An optional first word", "hello\n",
        "The one-element literal List makes first return Some('hello'), so the Some arm supplies the printed greeting.",
    ),
    "67ac940c6501": standalone(
        "A generic choice of trees", "",
        "The generic choice and two values are defined without print calls. Both concrete instantiations are part of the original source.",
    ),
    "ee5a3631871c": standalone(
        "A Set keeps one of each", "1\ntrue\nAda\ntrue\n",
        "Adding Ada twice leaves one element. contains is true, iteration of a singleton can only print Ada, and removing that present element returns true.",
    ),
    "8107bb77e6b7": standalone(
        "A generic fallback", "20\nquiet\n7\n",
        "The nonempty List returns its first literal value 20; the two empty Lists return their supplied fallbacks quiet and 7, as the comments state.",
    ),
    "d1abd53abf33": standalone(
        "A generic pair", "dawn\n",
        "The first field of the sole reading is the literal Text dawn; this is also stated by the print comment.",
    ),
    "169670f51c32": contextual(
        "Transparent type aliases", "fragment",
        "The Pair generic record declaration belongs to the previous example and is not included in this block.",
    ),
    "710fa0208f42": standalone(
        "A generic Ordered constraint", "2.7\n",
        "Sorting the three literal Floats puts the maximum literal 2.7 last. The returned value is not computed by approximate arithmetic; the guide's print comment specifies 2.7.",
    ),
    "b06ba27e14da": standalone(
        "A recoverable byte operation", "66\n",
        "The UTF-8 byte for ASCII A is 65; firstByte succeeds and increment adds one, selecting the Ok arm with Integer 66.",
    ),
    "8c837fc0b368": contextual(
        "Context on a recoverable failure", "fragment",
        "The errors module alias and readPort function are not defined or imported by this block.",
    ),
    "a87448c88d73": standalone(
        "Small decisions around a Result", "42\ntraveller\n",
        "Ok(21).map doubles 21 and converts 42 to Text. None uses the literal fallback traveller.",
    ),
    "15d273b2c55c": standalone(
        "A callback carries a thought", "42\n12\n",
        "The callback adds the captured literal offset 2 to 40 and then 10. Both expected sums are stated in comments.",
    ),
    "36478a3e9af2": standalone(
        "A parallel range of squares", "",
        "The range writes four List positions and contains no print call, so the original program has empty stdout.",
        note="The browser target executes this parallel range through its existing sequential backend. This run does not demonstrate native parallel speedup.",
    ),
    "1514c134ca8a": contextual(
        "A parallel reduction", "fragment",
        "The values List is not declared by this block. A standalone version would need a separate explicit input, which this catalog does not silently add.",
    ),
    "11665338a7d6": contextual(
        "A native parallel entry point", "unsupported-host",
        "This complete native example imports machine and calls raw-memory/parallel-entry APIs. The browser bundle does not provide the machine module or that native entry host API.",
    ),
    "aaa932f8d1f8": standalone(
        "Functions and top-level statements", "Everything is working\n",
        "double(21) returns 42, so the true branch prints its literal sentence and the other branch is not taken.",
    ),
    "1be65e6ef3e8": contextual(
        "An else-if chain", "fragment",
        "The score binding is an input from surrounding code and is not declared in this block.",
    ),
    "7934638fcc04": contextual(
        "A local module namespace", "fragment",
        "This single-file excerpt requires a separate ./geometry.min module defining Point and answer. The excerpt alone does not include that source file.",
    ),
    "134e22047032": contextual(
        "Continuing a statement", "fragment",
        "The first and second bindings and the add function are omitted; the block illustrates line continuation within surrounding code.",
    ),
    "16983a726a47": standalone(
        "Newlines inside an expression", "42\nready\n",
        "The two literal List values add to 42. Its length is two rather than zero, so the else branch prints ready.",
    ),
}


def slug(text):
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-") or "example"


def extract_blocks(markdown):
    """Read CommonMark-style fences without normalizing their source bytes."""
    # Only LF advances a source line. Unicode separators inside Text literals
    # and bare CR must not change the guide's physical file coordinates.
    pieces = markdown.split("\n")
    lines = [piece + "\n" for piece in pieces[:-1]]
    if pieces[-1]:
        lines.append(pieces[-1])
    headings = []
    index = 0
    while index < len(lines):
        current = lines[index].rstrip("\r\n")
        opening = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", current)
        if opening:
            marker, information = opening.groups()
            language = information.strip().split(maxsplit=1)
            minyar = bool(language) and language[0] == "minyar"
            opening_index = index
            start = index + 1
            closing = re.compile(r"^ {0,3}" + re.escape(marker[0]) + "{" + str(len(marker)) + r",}[ \t]*$")
            index = start
            while index < len(lines) and not closing.fullmatch(lines[index].rstrip("\r\n")):
                index += 1
            if minyar:
                if index == len(lines):
                    raise ValueError(f"Unclosed minyar fence at line {opening_index + 1}")
                yield {
                    "headings": [title for _, title in headings],
                    "heading": headings[-1][1] if headings else "Examples",
                    "fenceLine": opening_index + 1,
                    "line": start + 1,
                    "endLine": index,
                    "closingFenceLine": index + 1,
                    "source": "".join(lines[start:index]),
                }
        else:
            heading = re.match(r"^ {0,3}(#{1,6})[ \t]+(.+?)(?:[ \t]+#+)?[ \t]*$", current)
            if heading:
                level = len(heading[1])
                headings = [(depth, title) for depth, title in headings if depth < level]
                headings.append((level, heading[2]))
        index += 1


def make_catalog(markdown, filename="docs/language.md"):
    examples = []
    seen = Counter()
    for block in extract_blocks(markdown):
        digest = hashlib.sha256(block["source"].encode("utf-8")).hexdigest()
        base_id = f"language-{slug(block['heading'])}-{digest[:12]}"
        seen[base_id] += 1
        stable_id = base_id if seen[base_id] == 1 else f"{base_id}-{seen[base_id]}"
        policy = POLICIES.get(digest[:12])
        if policy is None:
            policy = contextual(
                f"{block['heading']}: example awaiting review", "unreviewed",
                "This new or changed documentation block has not been reviewed as a standalone browser program. Its exact source is retained; no declarations, imports or expected output have been guessed.",
            )
        examples.append({"id": stable_id, "file": filename, **block, "sourceSha256": digest, **policy})
    classifications = Counter(example["classification"] for example in examples)
    return {
        "schemaVersion": 1,
        "document": {"file": filename, "sha256": hashlib.sha256(markdown.encode("utf-8")).hexdigest()},
        "summary": {
            "total": len(examples),
            "runnable": sum(example["runnable"] for example in examples),
            "byClassification": dict(sorted(classifications.items())),
        },
        "examples": examples,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--document", type=Path, default=DEFAULT_DOCUMENT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--require-reviewed", action="store_true", help="Reject unreviewed source before writing any output")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--stdout", action="store_true", help="Print the deterministic catalog without writing a file")
    mode.add_argument("--check", action="store_true", help="Require a current catalog and a reviewed classification for every block")
    args = parser.parse_args()
    document = args.document.resolve()
    try:
        filename = document.relative_to(ROOT).as_posix()
    except ValueError:
        filename = document.as_posix()
    try:
        # read_text() would translate CRLF; the catalog promises the original text.
        catalog = make_catalog(document.read_bytes().decode("utf-8"), filename)
    except (OSError, UnicodeError, ValueError) as error:
        print(f"language examples: {error}", file=sys.stderr)
        return 1
    unreviewed = [example["id"] for example in catalog["examples"] if example["classification"] == "unreviewed"]
    if args.require_reviewed and unreviewed:
        print("language examples: classify new or changed blocks: " + ", ".join(unreviewed), file=sys.stderr)
        return 1
    rendered = json.dumps(catalog, ensure_ascii=False, indent=2) + "\n"
    if args.stdout:
        sys.stdout.write(rendered)
        return 0
    if args.check:
        try:
            current = args.output.read_bytes().decode("utf-8")
        except OSError:
            current = None
        if current != rendered:
            print("language examples: catalog is stale; run python3 tools/playground-language-examples.py", file=sys.stderr)
            return 1
        if unreviewed:
            print("language examples: classify new or changed blocks: " + ", ".join(unreviewed), file=sys.stderr)
            return 1
        print(f"language examples: all {len(catalog['examples'])} exact source blocks are current and reviewed")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(rendered.encode("utf-8"))
    summary = catalog["summary"]
    print(f"language examples: wrote {summary['total']} blocks, {summary['runnable']} runnable, {len(unreviewed)} unreviewed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
