# Print the make dependencies of one Minyar compilation: every module file
# the compiler loads, like `clang -MMD -MP`.
#
#   LC_ALL=C awk -f build-support/minyar-dependencies.awk TARGET SOURCE [LIBRARY...]
#
# It reads bytes (LC_ALL=C), so every awk agrees on lengths and positions.
#
# LIBRARY lists the compiler's --library directories in order. Imports are
# found and resolved as compiler/stages/modules.min does: loadModule reads a
# top-level `use "SPECIFIER" as ALIAS` statement (one line, outside comments,
# Text literals and brackets), resolveImport maps `./` and `../` specifiers
# against the importing file's directory and bare package names to
# LIBRARY/NAME.min (the first directory holding the file, else the last), and
# normalizePath gives every module one spelling. The compiler loads nothing
# implicitly. Run it after a successful compilation: anything the compiler
# would reject, or a specifier this scanner cannot read exactly, stops it.

function fail(message) {
    printf "minyar-dependencies: %s\n", message > "/dev/stderr"
    failed = 1
    exit 1
}

function separator(character) {
    return character == "/" || character == "\\"
}

# compiler/stages/modules.min normalizePath
function normalize(path,    drive, absolute, position, rest, pieces, count, parts, active, index_, part, result) {
    drive = ""
    absolute = 0
    position = 1
    if (length(path) >= 2 && substr(path, 2, 1) == ":") {
        drive = substr(path, 1, 1) ":"
        position = 3
        if (position <= length(path) && separator(substr(path, position, 1))) {
            absolute = 1
            position++
        }
    } else if (length(path) > 0 && separator(substr(path, 1, 1))) {
        absolute = 1
        position = 2
    }
    rest = substr(path, position)
    gsub(/\\/, "/", rest)
    count = split(rest, pieces, "/")
    active = 0
    for (index_ = 1; index_ <= count; index_++) {
        part = pieces[index_]
        if (part == "..") {
            if (active > 0 && parts[active] != "..") active--
            else if (!absolute) parts[++active] = part
        } else if (part != "" && part != ".") {
            parts[++active] = part
        }
    }
    result = drive
    if (absolute) result = result "/"
    for (index_ = 1; index_ <= active; index_++) {
        if (length(result) > 0 && substr(result, length(result), 1) != "/") result = result "/"
        result = result parts[index_]
    }
    if (result == "") result = "."
    return result
}

# compiler/stages/modules.min directoryOfPath
function directory(path,    normalized, last, position) {
    normalized = normalize(path)
    last = 0
    for (position = 1; position <= length(normalized); position++)
        if (substr(normalized, position, 1) == "/") last = position
    if (last == 1) return "/"
    if (last == 0) return ""
    return substr(normalized, 1, last - 1)
}

function exists(path,    line, status) {
    status = (getline line < path)
    close(path)
    return status >= 0
}

function packagePath(root, specifier) {
    if (specifier !~ /^[A-Za-z0-9_-]+$/)
        fail(location ": package names use letters, digits, '-', and '_'; found '" specifier "'")
    return normalize(root "/" specifier ".min")
}

# compiler/stages/modules.min resolveImport and resolveModulePath
function resolve(importer, specifier,    first, second, base, index_, candidate) {
    first = substr(specifier, 1, 1)
    second = substr(specifier, 2, 1)
    if (libraries == 0 || (length(specifier) >= 2 && first == "." && (separator(second) || second == "."))) {
        if (!(length(specifier) >= 2 && first == "." && separator(second)) && !(length(specifier) >= 3 && first == "." && second == "." && separator(substr(specifier, 3, 1))))
            fail(location ": package module '" specifier "' is not available yet; local modules begin with './' or '../'")
        base = directory(importer)
        if (base == "") return normalize(specifier)
        return normalize(base "/" specifier)
    }
    for (index_ = 1; index_ < libraries; index_++) {
        candidate = packagePath(library[index_], specifier)
        if (exists(candidate)) return candidate
    }
    return packagePath(library[libraries], specifier)
}

function add(path) {
    if (path in seen) return
    seen[path] = 1
    modules[++moduleCount] = path
}

# Import statement tokens: use, then a Text literal, then as, then a name.
function word(text) {
    if (depth > 0) return
    if (state == 0 && text == "use" && round == 0 && square == 0 && brace == 0) {
        state = 1
    } else if (state == 2 && text == "as") {
        state = 3
    } else if (state == 3) {
        state = 0
        target_ = resolve(current, specifier_)
        if (!exists(target_)) fail(location ": imports '" specifier_ "', resolved to " target_ ", which does not exist")
        add(target_)
    } else {
        state = 0
    }
}

# exact is 1 for a one-line literal without escapes, whose text is its source.
function literal(text, exact) {
    if (depth > 0) return
    if (state == 1) {
        if (!exact) fail(location ": write the module name of 'use' as one plain line of Text so its dependencies can be tracked")
        specifier_ = text
        state = 2
    } else {
        state = 0
    }
}

function other() {
    if (depth == 0) state = 0
}

# compiler/stages/lexer.min decodeTextPart for one line without interpolation.
function unescape(text,    result, position, character) {
    result = ""
    for (position = 1; position <= length(text); position++) {
        character = substr(text, position, 1)
        if (character == "\\") {
            character = substr(text, ++position, 1)
            if (character == "n") character = "\n"
            else if (character == "r") character = "\r"
            else if (character == "t") character = "\t"
        }
        result = result character
    }
    return result
}

function push(kind) {
    kinds[++depth] = kind
    parens[depth] = 1
}

# One physical line of source; strings, comments and interpolations may span lines.
function scanLine(line,    length_, position, kind, rest, character, next_, close_) {
    length_ = length(line)
    position = 1
    while (position <= length_) {
        if (comment) {
            close_ = index(substr(line, position), "*/")
            if (close_ == 0) return
            position += close_ + 1
            comment = 0
            continue
        }
        if (quote) {
            # The closing quote of a Character literal whose value was a line break.
            quote = 0
            position++
            other()
            continue
        }
        kind = depth > 0 ? kinds[depth] : "code"
        rest = substr(line, position)
        if (kind == "text" || kind == "lines") {
            if (kind == "text") { if (!match(rest, /["\\]/)) return }
            else if (!match(rest, /"""|\\/)) return
            character = substr(rest, RSTART, 1)
            if (character == "\"") {
                depth--
                position += RSTART + (kind == "lines" ? 2 : 0)
            } else if (substr(rest, RSTART + 1, 1) == "(") {
                position += RSTART + 1
                push("interpolation")
            } else if (RSTART == length(rest)) {
                return
            } else {
                position += RSTART + 1
            }
            continue
        }
        if (kind == "raw" || kind == "raw lines") {
            close_ = index(rest, kind == "raw" ? "\"#" : "\"\"\"#")
            if (close_ == 0) return
            depth--
            position += close_ + (kind == "raw" ? 1 : 3)
            continue
        }
        character = substr(rest, 1, 1)
        next_ = substr(rest, 2, 1)
        if (character == " " || character == "\t" || character == "\r") {
            position++
        } else if (character == "/" && next_ == "/") {
            return
        } else if (character == "/" && next_ == "*") {
            comment = 1
            position += 2
        } else if (match(rest, /^[A-Za-z_][A-Za-z0-9_]*/)) {
            word(substr(rest, 1, RLENGTH))
            position += RLENGTH
        } else if (match(rest, /^[0-9][0-9A-Za-z_]*/)) {
            other()
            position += RLENGTH
        } else if (character == "\"" && substr(rest, 1, 3) == "\"\"\"") {
            literal("", 0)
            push("lines")
            return
        } else if (character == "\"") {
            if (match(substr(rest, 2), /["\\]/) && substr(rest, RSTART + 1, 1) == "\"") {
                literal(substr(rest, 2, RSTART - 1), 1)
                position += RSTART + 1
            } else if (match(rest, /^"([^"\\]|\\[^(])*"/)) {
                literal(unescape(substr(rest, 2, RLENGTH - 2)), 1)
                position += RLENGTH
            } else {
                literal("", 0)
                push("text")
                position++
            }
        } else if (character == "#" && next_ == "\"") {
            literal("", 0)
            if (substr(rest, 2, 3) == "\"\"\"") {
                push("raw lines")
                return
            }
            push("raw")
            position += 2
        } else if (character == "'") {
            other()
            if (next_ == "\\") {
                if (length(rest) == 2) { quote = 1; return }
                position += 4
            } else {
                if (length(rest) == 1) { quote = 1; return }
                # The value is one Character: one UTF-8 sequence of bytes.
                position += match(substr(rest, 2), /^[\300-\367][\200-\277]*/) ? RLENGTH + 2 : 3
            }
        } else {
            if (depth > 0) {
                if (character == "(") parens[depth]++
                if (character == ")" && --parens[depth] == 0) depth--
            } else {
                if (character == "(") round++
                if (character == ")" && round > 0) round--
                if (character == "[") square++
                if (character == "]" && square > 0) square--
                if (character == "{") brace++
                if (character == "}" && brace > 0) brace--
            }
            other()
            position++
        }
    }
}

function scan(path,    line, status, number) {
    current = path
    depth = 0
    round = 0
    square = 0
    brace = 0
    comment = 0
    quote = 0
    state = 0
    number = 0
    while ((status = (getline line < path)) > 0) {
        number++
        location = path ":" number
        if (number == 1 && substr(line, 1, 3) == "\357\273\277") line = substr(line, 4)
        scanLine(line)
        # A line break ends a top-level statement unless a comment or Text continues.
        if (!comment && depth == 0) state = 0
    }
    if (status < 0) fail("cannot read " path)
    close(path)
    if (comment || depth > 0 || quote) fail(path ": ends inside a comment, Text literal, or Character literal")
}

function escape(path) {
    gsub(/\$/, "$$$$", path)
    gsub(/#/, "\\#", path)
    gsub(/ /, "\\ ", path)
    return path
}

BEGIN {
    if (ARGC < 3) fail("usage: awk -f minyar-dependencies.awk TARGET SOURCE [LIBRARY...]")
    output = ARGV[1]
    libraries = 0
    for (argument = 3; argument < ARGC; argument++) library[++libraries] = ARGV[argument]
    moduleCount = 0
    add(normalize(ARGV[2]))
    for (scanned = 1; scanned <= moduleCount; scanned++) scan(modules[scanned])
    printf "%s:", escape(output)
    for (scanned = 1; scanned <= moduleCount; scanned++) printf " \\\n  %s", escape(modules[scanned])
    printf "\n"
    for (scanned = 2; scanned <= moduleCount; scanned++) printf "\n%s:\n", escape(modules[scanned])
    exit 0
}
